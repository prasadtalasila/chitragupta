"""What does surviving a dead parse worker actually cost?

`docs/ARCHITECTURE.md` and the paper's Evaluation section describe three
robustness mechanisms qualitatively -- the docling pool is rebuilt when a
worker dies (#593), the stall watchdog gives up on a silent pool, and a
suspicious sync exits nonzero -- and put no number against any of them.
#610 (B3) asks for the two that have a cost: how much wall clock a
rebuild adds, how many documents it loses, whether the narrowing pool
terminates, and how long the watchdog's cancellation path takes to run
once it fires.

Both arms use **real** failures rather than fakes. The rebuild arm
SIGKILLs an actual pool worker mid-parse, which is what the OOM killer
does; the watchdog arm hands the pool a FIFO in place of a PDF, which
blocks a real worker in a real read forever. Neither monkeypatches the
mechanism it measures -- the only patch is a counter around
`_executor_for`, which records how many pools got built without changing
which ones do.

Each arm runs in a subprocess against a **throwaway CONTENT_DIR**, so a
parse this benchmark drives never writes into the corpus it reads.

**The watchdog arm now terminates and is still off by default.**
`arm_stall` used to sit in `futex_wait_queue` for hours after the healthy
documents were done, even with a working `terminate_workers` -- because
`chitragupta/sync_pool.py`'s stall-timeout branch called
`executor.shutdown(wait=False, cancel_futures=True)` *before*
`pdf_text.terminate_workers(executor)`, and `ProcessPoolExecutor.shutdown()`
sets `executor._processes = None` unconditionally, even with `wait=False`
(CPython `concurrent/futures/process.py`). `terminate_workers` reads that
same attribute to find which OS processes to signal, so by the time it
ran there was nothing left to kill -- the FIFO-blocked worker was never
actually terminated, its death was never observed, and the executor's own
manager thread blocked forever waiting for a result that would never
arrive. That was issue #698, fixed by reordering those two calls (and
their two sibling copies in `chitragupta/enrich/_docling_pool.py` and
`sync_pool.py`'s own `_drain_pool`) so `terminate_workers` runs while
`executor._processes` is still populated. `arm_stall` is kept opt-in via
`--with-stall-arm` regardless -- it still blocks a real worker in a real
read for the full `--stall-timeout`, which is deliberately slow, not
because it hangs anymore.

An unrelated fix landed alongside it: every arm previously measured
nothing at all, because the throwaway `CONTENT_DIR` had no ledger, so
`build_corpus()` returned zero rows. `_seeded_content_dir` copies the real
ledger in to fix that. Of #610's B3 questions, this script now answers
all four: rebuild wall-clock overhead, documents lost, pool-narrowing
convergence, and (with `--with-stall-arm`) the stall watchdog's
cancellation latency.

Needs the "enrich" Poetry group and a synced corpus (it parses real PDFs
named in the ledger).

    CHITRAGUPTA_PROJECT=. .venv-full/bin/python \\
        bench/bench_pool_rebuild.py --tag 2026-09-04-pool-rebuild
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

RESULT_MARKER = "BENCH_RESULT "


def overhead(baseline_seconds: float, injected_seconds: float) -> float:
    """How much longer the interrupted run took, as a ratio. Reported
    rather than a difference because the absolute seconds depend on how
    many documents the arm was given, and the ratio is the part that
    transfers to a full corpus."""
    if not baseline_seconds:
        return 0.0
    return round(injected_seconds / baseline_seconds, 4)


def lost_documents(status: dict) -> list:
    """Citekeys the run gave up on, by the marker the pool writes for
    exactly that case. Counted from the status map rather than from
    'expected minus parsed', so a document that failed for an unrelated
    reason is not miscounted as a pool casualty."""
    from chitragupta.enrich.docling_parse import POOL_DEATH_ERROR

    return sorted(key for key, value in status.items() if value == POOL_DEATH_ERROR)


def self_check() -> None:
    """Fabricate a difference each aggregation is supposed to see.

    The overhead ratio is the number this script publishes, and the one
    a wrong denominator would silently turn into 1.0; the lost-document
    count is the number that decides whether a rebuild rescued the run
    or merely delayed it, and a marker match that had gone stale would
    report every interrupted run as lossless.
    """
    assert overhead(10.0, 15.0) == 1.5, overhead(10.0, 15.0)
    assert overhead(10.0, 10.0) == 1.0, "an unchanged run must read as 1.0, not 0.0"
    assert overhead(0.0, 5.0) == 0.0, "a zero baseline must not divide"
    from chitragupta.enrich.docling_parse import POOL_DEATH_ERROR

    status = {"a": "ok", "b": POOL_DEATH_ERROR, "c": POOL_DEATH_ERROR}
    assert lost_documents(status) == ["b", "c"], lost_documents(status)
    assert lost_documents({"a": "ok"}) == [], "a clean run must report no casualties"


def _sample_docs(limit: int) -> list:
    """The `limit` smallest PDFs in the corpus, smallest first.

    Smallest because this arm is measuring the *pool's* recovery, not
    docling's throughput: the cheapest documents that still exercise a
    real parse make the rebuild's model reload the dominant term, which
    is the cost being measured.
    """
    from chitragupta.enrich import corpus

    docs = [d for d in corpus.build_corpus() if d.pdf_path and Path(d.pdf_path).exists()]
    # An empty sample is the #698 failure mode and must not be a quiet
    # one: two arms then report "0 documents" as though that were a
    # measurement, and the third never returns at all.
    if not docs:
        raise SystemExit(
            "No parsable documents in the corpus this arm was pointed at -- every "
            "measurement would be over zero documents (issue #698)."
        )
    docs.sort(key=lambda d: Path(d.pdf_path).stat().st_size)
    return docs[:limit]


def _kill_a_worker(executors: list, status: dict, killed: list) -> None:
    """SIGKILL one worker of the live pool, once the run has proved it
    is making progress. Waiting for the first landed result matters:
    killing before any document completes measures a pool that never
    worked, which is a different failure from one that died mid-run."""
    deadline = time.time() + 300
    while time.time() < deadline:
        if status and executors:
            processes = list(getattr(executors[-1], "_processes", {}) or {})
            if processes:
                os.kill(processes[0], signal.SIGKILL)
                killed.append(processes[0])
                return
        time.sleep(0.05)


def arm_parse(kill: bool, limit: int, workers: int) -> dict:
    """One parse of `limit` documents through the real docling pool,
    optionally with a worker killed partway. Returns the timings and
    counts, never the parsed text."""
    from chitragupta.enrich import _docling_pool

    docs = _sample_docs(limit)
    executors, builds, killed = [], [], []
    original = _docling_pool._executor_for

    def counting_executor_for(count):
        builds.append(count)
        executor = original(count)
        executors.append(executor)
        return executor

    _docling_pool._executor_for = counting_executor_for
    status: dict = {}
    killer = threading.Thread(target=_kill_a_worker, args=(executors, status, killed), daemon=True)
    if kill:
        killer.start()
    started = time.time()
    try:
        _docling_pool._parse_with_pool(docs, list(docs), {}, status, workers)
    finally:
        _docling_pool._executor_for = original
    elapsed = time.time() - started
    lost = lost_documents(status)
    return {
        "arm": "worker-killed" if kill else "uninterrupted",
        "documents": len(docs),
        "workers_requested": workers,
        "seconds": round(elapsed, 2),
        "pools_built": len(builds),
        "worker_counts_per_build": builds,
        "killed_pid": killed[0] if killed else None,
        "parsed": sum(1 for v in status.values() if not str(v).startswith("error")),
        "lost": len(lost),
        "lost_citekeys": lost,
    }


def arm_stall(limit: int, timeout: float, workers: int) -> dict:
    """The watchdog's cancellation path, fired by a real block.

    A FIFO stands in for a PDF: a worker that opens it blocks in the
    kernel and never returns, which is what a hung parse looks like from
    the pool's side. Everything else in the batch is a real PDF that
    parses normally, so the gap the watchdog measures opens only after
    the healthy documents are done -- the same shape as a real hang at
    the tail of a run.
    """
    from chitragupta import config, sync_pool
    from types import SimpleNamespace

    docs = _sample_docs(limit)
    fifo_dir = Path(tempfile.mkdtemp(prefix="bench-stall-"))
    fifo = fifo_dir / "hangs-forever.pdf"
    os.mkfifo(fifo)
    refs = [SimpleNamespace(citekey=d.citekey, pdf_path=d.pdf_path) for d in docs]
    refs.append(SimpleNamespace(citekey="bench_stall_fifo", pdf_path=str(fifo)))

    original_timeout = config.PARSER_STALL_TIMEOUT
    config.PARSER_STALL_TIMEOUT = timeout
    started = time.time()
    try:
        results = list(sync_pool._parse_parallel(refs, workers, None))
    finally:
        config.PARSER_STALL_TIMEOUT = original_timeout
    elapsed = time.time() - started
    failures = {key: str(exc) for key, _text, exc in results if exc is not None}
    return {
        "arm": "stall-watchdog",
        "documents": len(refs),
        "stall_timeout": timeout,
        "seconds": round(elapsed, 2),
        "gave_up_on": sorted(failures),
        "fifo_reported_failed": "bench_stall_fifo" in failures,
        "fifo_message": failures.get("bench_stall_fifo"),
        "healthy_documents_parsed": sum(1 for _k, text, exc in results if exc is None and text),
    }


def _seeded_content_dir() -> Path:
    """A throwaway CONTENT_DIR that nonetheless has documents in it.

    The ledger is copied in, and it is the only thing copied. `corpus
    .build_corpus()` reads nothing else, and the `pdf_path` it hands back
    points under `papers/`, outside CONTENT_DIR entirely -- so the arms
    read the real PDFs and write every parse artefact into this tempdir.
    The "a parse this benchmark drives never writes into the corpus it
    reads" guarantee is unchanged; what changes is that there is now
    something to parse.

    Without this the directory is empty, `build_corpus()` returns no
    rows, and every arm runs over **zero** documents -- which is why B3
    produced no measurement (issue #698). The `uninterrupted` and
    `worker-killed` arms then return in under a second having parsed
    nothing, and the `stall` arm hangs forever: its FIFO worker blocks by
    design, and with no healthy document to finish first, the gap the
    watchdog measures never opens.
    """
    from chitragupta import config

    # Refused rather than skipped. A missing ledger is precisely the
    # state that produced #698: the arms run, report zero documents, and
    # the watchdog arm then blocks forever -- a ten-hour silence that
    # looked like a deadlock in the pool. Copying "if it exists" would
    # rebuild that trapdoor.
    if not config.LEDGER_PATH.exists():
        raise SystemExit(
            f"No ledger at {config.LEDGER_PATH}, so every arm would run over zero "
            "documents and the watchdog arm would never terminate (issue #698). "
            "Run `python -m chitragupta.corpus sync` first, or point "
            "CHITRAGUPTA_PROJECT at a synced project."
        )
    content_dir = Path(tempfile.mkdtemp(prefix="bench-pool-content-"))
    shutil.copy2(config.LEDGER_PATH, content_dir / config.LEDGER_PATH.name)
    return content_dir


def _run_arm_in_subprocess(arm: str, args) -> dict:
    """One arm, in its own process against a throwaway CONTENT_DIR.

    A subprocess rather than an in-process tempdir because `config`
    reads CONTENT_DIR once at import: the only honest way to point a
    parse somewhere else is to start a process that imports it fresh.

    Streamed to this process's own stderr rather than captured. Three
    arms each print nothing until they return, and `main` prints its
    table only after all three, so a captured run shows an empty
    terminal whether it is working or wedged -- which is exactly how
    #698's hang came to be attributed to the first arm when it was the
    third. Only the one `BENCH_RESULT` line is captured, off stdout.
    """
    env = {**os.environ, "CONTENT_DIR": str(_seeded_content_dir())}
    print(f"  running {arm} ...", flush=True)
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--arm",
            arm,
            "--documents",
            str(args.documents),
            "--workers",
            str(args.workers),
            "--stall-timeout",
            str(args.stall_timeout),
            "--tag",
            args.tag,
        ],
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    for line in completed.stdout.splitlines():
        if line.startswith(RESULT_MARKER):
            return json.loads(line[len(RESULT_MARKER) :])
    raise SystemExit(
        f"arm {arm} produced no result (exit {completed.returncode}).\n"
        f"stdout tail:\n{completed.stdout[-2000:]}\n\n"
        "stderr went to this terminal as it happened, above."
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", required=True, help="names the results directory")
    parser.add_argument("--documents", type=int, default=12, help="PDFs per arm (default: 12)")
    parser.add_argument("--workers", type=int, default=4, help="pool workers (default: 4)")
    parser.add_argument(
        "--stall-timeout", type=float, default=60.0, help="seconds for the watchdog arm"
    )
    parser.add_argument(
        "--with-stall-arm",
        action="store_true",
        help="run the watchdog arm -- opt-in because it blocks a real worker for "
        "the full --stall-timeout, not because it hangs (issue #698, fixed)",
    )
    parser.add_argument("--arm", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    self_check()

    if args.arm == "uninterrupted":
        print(RESULT_MARKER + json.dumps(arm_parse(False, args.documents, args.workers)))
        return 0
    if args.arm == "worker-killed":
        print(RESULT_MARKER + json.dumps(arm_parse(True, args.documents, args.workers)))
        return 0
    if args.arm == "stall":
        print(
            RESULT_MARKER + json.dumps(arm_stall(args.documents, args.stall_timeout, args.workers))
        )
        return 0

    baseline = _run_arm_in_subprocess("uninterrupted", args)
    injected = _run_arm_in_subprocess("worker-killed", args)
    # Off by default: this arm deliberately blocks a real worker in a real
    # read for the full --stall-timeout, which is slow, not because it
    # hangs -- see this module's docstring for #698, which used to make
    # it hang and is now fixed.
    stall = _run_arm_in_subprocess("stall", args) if args.with_stall_arm else None
    ratio = overhead(baseline["seconds"], injected["seconds"])

    print(f"\n{'arm':>16}  {'docs':>4} {'parsed':>6} {'lost':>4} {'pools':>5} {'seconds':>8}")
    for row in (baseline, injected):
        print(
            f"{row['arm']:>16}  {row['documents']:>4} {row['parsed']:>6} "
            f"{row['lost']:>4} {row['pools_built']:>5} {row['seconds']:>8}"
        )
    print(f"\nrebuild overhead: {ratio}x wall clock")
    print(f"pool widths as it narrowed: {injected['worker_counts_per_build']}")
    print(f"documents lost to the kill: {injected['lost']} {injected['lost_citekeys']}")
    if stall is None:
        print(
            "\nstall watchdog: NOT MEASURED -- off by default because it blocks a "
            "real worker for the full --stall-timeout. Pass --with-stall-arm to "
            "measure it."
        )
    else:
        print(
            f"\nstall watchdog at {stall['stall_timeout']}s: returned in {stall['seconds']}s, "
            f"gave up on {len(stall['gave_up_on'])} document(s), "
            f"{stall['healthy_documents_parsed']} healthy parsed"
        )

    out_dir = REPO / "bench" / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "baseline": baseline,
        "injected": injected,
        "overhead_ratio": ratio,
        # null, not a zero-shaped record: "the watchdog cancels in 0s" and
        # "the watchdog arm was not run" must never read the same.
        "stall": stall,
        "stall_measured": stall is not None,
    }
    (out_dir / "pool_rebuild.json").write_text(json.dumps(payload, indent=2), "utf-8")
    print(f"\nwrote {out_dir / 'pool_rebuild.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
