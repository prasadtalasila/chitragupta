"""Sweep the REAL `python -m chitragupta.corpus sync` across worker/GPU/OCR settings.

This is the harness that produces trustworthy pool-level numbers, and it
exists because the two older tools cannot:

  bench_docling.py   times Docling directly, one process, no pool.
  run_parallel.py    launches N *independent* processes over G cards --
                     it predates `[parser].workers` and shares none of
                     the pool's machinery (no shared counter, no pool
                     initialiser, no start method).

Neither answers "what does the shipped pipeline cost", which is the only
question a user actually has. This runs the shipped pipeline.

Three things it does that a hand-rolled `time python -m chitragupta.corpus sync` does not:

1. **A fresh CONTENT_DIR per run.** The ledger skips any PDF whose bytes
   haven't changed, so a second run over the same output directory times
   the skip logic rather than the parse. Every run here starts empty.

2. **Reports the *resolved* worker count, not the requested one.**
   `worker_ceiling()` clamps to `allowed_cpus // _CPUS_PER_DOCLING_WORKER`,
   so asking for 32 on a 48-CPU machine silently gives you 12. That clamp
   hid a measured 1.41x for an entire release: every run looked like it
   honoured the setting. When the two differ, this says so, loudly.

3. **Samples CPU and GPU during the run**, so a flat spot in the scaling
   curve can be attributed instead of guessed at. `/proc/stat` covers the
   *host's* CPUs, which on a container is not what the process may use --
   the reported percentage is against `len(os.sched_getaffinity(0))`.

Usage:
    python bench/sweep_sync.py --workers 1,4,8,12 --gpus 4 --tag scaling
    python bench/sweep_sync.py --workers 12 --gpus 1,2,4 --tag gpus
    python bench/sweep_sync.py --workers 12,24 --ocr on,off --tag ocr

Each run parses the whole corpus, so a serial pass over a few hundred
PDFs is tens of minutes. Budget accordingly; --dry-run prints the plan.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# "  [12/501] citekey" -- chitragupta/sync.py's per-completion progress line.
PROGRESS_RE = re.compile(r"^\s*\[\d+/\d+\]\s")

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCH_DIR = REPO_ROOT / "bench"


def allowed_cpus() -> int:
    getaffinity = getattr(os, "sched_getaffinity", None)
    return len(getaffinity(0)) if getaffinity else (os.cpu_count() or 1)


class ResourceSampler:
    """Mean CPU-busy and per-GPU utilisation across a run.

    A thread rather than a subprocess so it stops exactly when the run
    does, and so a failed run still yields whatever it sampled.
    """

    def __init__(self, interval: float = 3.0):
        self.interval = interval
        self._stop = threading.Event()
        self._cpu_samples: list[float] = []
        self._gpu_samples: list[list[int]] = []
        self._thread: threading.Thread | None = None

    @staticmethod
    def _cpu_totals() -> tuple[int, int] | None:
        try:
            first = Path("/proc/stat").read_text().splitlines()[0]
        except OSError:
            return None
        fields = [int(x) for x in first.split()[1:]]
        if len(fields) < 5:
            return None
        return sum(fields), fields[3] + fields[4]  # total, idle+iowait

    @staticmethod
    def _gpu_util() -> list[int]:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10, check=False)
        except (OSError, subprocess.SubprocessError):
            return []
        if out.returncode != 0:
            return []
        return [int(x) for x in out.stdout.split() if x.strip().isdigit()]

    def _run(self) -> None:
        prev = self._cpu_totals()
        while not self._stop.wait(self.interval):
            cur = self._cpu_totals()
            if prev and cur and cur[0] > prev[0]:
                d_total, d_idle = cur[0] - prev[0], cur[1] - prev[1]
                self._cpu_samples.append(100.0 * (d_total - d_idle) / d_total)
            prev = cur
            gpu = self._gpu_util()
            if gpu:
                self._gpu_samples.append(gpu)

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self.interval + 5)
        return False

    def summary(self) -> dict:
        host_cpus = os.cpu_count() or 1
        mean_host = (sum(self._cpu_samples) / len(self._cpu_samples)
                     if self._cpu_samples else None)
        # /proc/stat is host-wide; express it against what we may use.
        busy_cpus = mean_host * host_cpus / 100 if mean_host is not None else None
        per_gpu = None
        if self._gpu_samples:
            # Host-wide, like the CPU figures: nvidia-smi ignores
            # CUDA_VISIBLE_DEVICES and reports every card on the machine,
            # including load this run did not cause. Rows can also come
            # back short on a driver hiccup, so take the narrowest rather
            # than indexing off the first -- a transient blip should not
            # IndexError away an otherwise good run.
            n = min(len(row) for row in self._gpu_samples)
            per_gpu = [round(sum(row[i] for row in self._gpu_samples) / len(self._gpu_samples), 1)
                       for i in range(n)]
        # Named "host_" because that is what /proc/stat measures: every
        # process on the box, not this run. On an otherwise-idle machine
        # the two coincide; on a shared one this is an upper bound, and
        # can exceed 100% when another tenant uses CPUs we may not.
        return {
            "host_cpu_busy_cores": round(busy_cpus, 1) if busy_cpus is not None else None,
            "host_cpu_pct_of_allowed": (round(100 * busy_cpus / allowed_cpus(), 1)
                                        if busy_cpus is not None else None),
            "gpu_util_mean_per_card": per_gpu,
            "samples": len(self._cpu_samples),
        }


def read_sync_output(out: str, err: str, workers: int) -> dict:
    """What `sync` printed, read back as parsed/failed/resolved-workers.

    Split out of `one_run` so `self_check` can put fabricated output
    through the same three patterns the real run's numbers come out of.
    Every one of them fails silently: a pattern that no longer matches
    does not raise, it returns zero parsed, zero failed and a serial
    worker count -- which is what a small clean run looks like.

    `sync` prints per-document failures to *stderr* and the totals to
    stdout. Counting only stdout reported every run as clean, which is
    the exact failure mode this harness exists to catch -- so prefer the
    authoritative summary line and fall back to counting across both
    streams.
    """
    parsed = len(re.findall(r"^ {2}parsed ", out, flags=re.M))
    summary = re.search(r"Sync complete: \d+ parsed, .*?, (\d+) failed", out)
    # Unanchored on the left, because where that line comes from moved:
    # since 3.4.0 a per-document failure is `logger.error("FAILED  %s: …")`
    # through the stderr console handler, whose formatter is bare
    # `%(message)s` -- no leading indent. The two-space form this looked
    # for was the older `print("  FAILED  …")`, so the fallback had
    # quietly counted nothing since. Kept tolerant of both rather than
    # re-pinned to today's, since the count is a fallback either way.
    failed = (int(summary.group(1)) if summary
              else len(re.findall(r"^ *FAILED ", out + err, flags=re.M)))
    pool = re.search(r"parsing \d+ document\(s\) with (\d+) workers", out)
    if pool:
        resolved = int(pool.group(1))
    else:
        # A serial run never prints the pool line; anything else is a
        # run that died before dispatch, where the count is unknown.
        resolved = 1 if workers == 1 else None
    return {"parsed": parsed, "failed": failed, "workers_resolved": resolved}


def self_check() -> None:
    """Prove this harness can see a failure and a clamp before it reports
    neither.

    `bench/` sits outside CI's coverage targets (--cov=chitragupta
    --cov=scripts), so nothing in the test suite will ever catch a
    regression here. This runs on every invocation instead, following
    `repro_check.py`'s convention (see `bench/README.md`), and it guards
    the specific way this script goes quiet: every number it publishes is
    read back out of `sync`'s printed output by a regex, and a regex that
    stops matching does not raise. It returns "0 failed", "0 parsed", "1
    worker" -- a clean serial run.

    What that costs to check, and what it cannot check, are worth keeping
    apart. The fixtures below are copied from `chitragupta/sync.py`'s
    real lines (`_summary_line`, `_record_result`'s `  parsed  `, the
    pool line, and the `FAILED  ` the stderr console handler emits), so
    they prove the patterns can tell a lost document from a clean run
    today. They are **constants in this file**, so they cannot notice
    `sync` rewording those lines tomorrow: both would then agree with
    each other and disagree with reality. Deriving them by importing
    `chitragupta.sync` would close that, and would tie this harness to
    the stack being importable in *its* interpreter rather than in
    `--python`'s, which is the one thing `--python` exists to keep
    separate. So this guards the reader, not the wording, and the wording
    stays a thing to re-check by hand when `sync`'s output changes.

    Three arms, because each publishes a different number:

      the failure    -- a run with a failed document must not be read as
                        clean. Counting only stdout once did exactly
                        that, which is why the summary line is preferred
                        and both streams are the fallback.
      the clamp      -- the resolved worker count must come from what
                        `sync` said it used, never from what was asked
                        for. That clamp hid a measured 1.41x for a whole
                        release.
      the aggregation -- `--repeat > 1` reports a median, and a median
                        that is silently the best run is a different,
                        rosier benchmark.
    """
    clean = ("  parsing 2 document(s) with 12 workers\n"
             "  parsed  alice_paper_2024\n"
             "  parsed  bose_paper_2023\n"
             "Sync complete: 2 parsed, 0 unchanged, 0 without a PDF attachment, "
             "0 failed, 0 stale.\n")
    good = read_sync_output(clean, "", 12)
    assert good == {"parsed": 2, "failed": 0, "workers_resolved": 12}, good

    # The same run with one document lost: the summary is the only place
    # that says so on stdout, and the FAILED line is on stderr.
    broke = read_sync_output(
        clean.replace("2 parsed", "1 parsed").replace("0 failed", "1 failed"),
        "FAILED  bose_paper_2023: docling returned PARTIAL_SUCCESS\n", 12)
    assert broke["failed"] == 1, (
        f"a run that lost a document reads as clean: {broke}")
    # And with no summary at all -- a run that died before printing one,
    # where the stderr count is all there is.
    assert read_sync_output("", "FAILED  bose_paper_2023: boom\n", 12)["failed"] == 1, (
        "the stderr fallback counts no failures, so a run that died mid-parse "
        "reports the same 0 failed a clean one does")

    clamped = read_sync_output(clean, "", 32)
    assert clamped["workers_resolved"] == 12, (
        f"32 workers were asked for and `sync` said it used 12: {clamped}")

    runs = [{"seconds": 30.0}, {"seconds": 10.0}, {"seconds": 20.0}]
    assert _median_run(runs)["seconds"] == 20.0, "_median_run reports the best run"


def one_run(workers: int, gpus: int, ocr: bool, python: str,
            keep_output: bool = False) -> dict:
    """One full `chitragupta.corpus sync` over the whole corpus, from an empty ledger."""
    content_dir = Path(tempfile.mkdtemp(prefix="bench-content-"))
    env = {
        **os.environ,
        "CONTENT_DIR": str(content_dir),
        "PARSER": "docling",
        "PARSER_OCR": "true" if ocr else "false",
        "PARSER_WORKERS": str(workers),
        "CUDA_VISIBLE_DEVICES": ",".join(str(i) for i in range(gpus)) if gpus else "",
        # A stall watchdog firing mid-benchmark would silently truncate
        # the run and report a fast, wrong number.
        "PARSER_STALL_TIMEOUT": "off",
    }
    try:
        with ResourceSampler() as sampler:
            started = time.perf_counter()
            # Streamed rather than captured wholesale so each completion can
            # be timestamped as it arrives. `sync` prints "  [n/N] citekey"
            # to stderr per document, which turns "what is this run
            # actually spending its time on" into an answerable question:
            # time to the *first* completion is pool startup plus the
            # fastest document's parse -- an upper bound on startup, not a
            # measurement of it -- time after the *last* is the tail one
            # long document imposes, and the gaps between are the
            # steady-state rate.
            proc = subprocess.Popen(
                [python, "-m", "chitragupta.corpus", "sync"], cwd=str(REPO_ROOT), env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            completions: list[float] = []
            err_lines: list[str] = []

            def drain_stderr():
                for line in proc.stderr:
                    err_lines.append(line)
                    if PROGRESS_RE.match(line):
                        completions.append(time.perf_counter() - started)

            reader = threading.Thread(target=drain_stderr, daemon=True)
            reader.start()
            out = proc.stdout.read()
            proc.wait()
            reader.join(timeout=30)
            elapsed = time.perf_counter() - started
        counts = read_sync_output(out, "".join(err_lines), workers)
        timeline = {}
        if completions:
            first, last = completions[0], completions[-1]
            timeline = {
                # Everything before the first document lands: process
                # start, imports, model load, pool construction -- and
                # whichever document finished first, since sync submits
                # biggest-first and something has to complete before this
                # can be timed. Read it as an upper bound on startup. Its
                # *growth* with worker count is the startup part, since a
                # single document's parse does not get slower because the
                # pool got bigger.
                "startup_s": round(first, 1),
                "startup_pct": round(100 * first / elapsed, 1),
                # Everything after the last: nothing left to overlap with,
                # so this is the tail a single long document imposes.
                "drain_s": round(elapsed - last, 1),
                "drain_pct": round(100 * (elapsed - last) / elapsed, 1),
                # Throughput while the pool is actually full. n
                # completions span n-1 intervals, not n: the one at
                # `first` bounds the window rather than falling inside it.
                "steady_docs_per_s": (round((len(completions) - 1) / (last - first), 2)
                                      if last > first and len(completions) > 1
                                      else None),
                "completions": len(completions),
            }
        return {
            "record": "run", "workers_requested": workers,
            "workers_resolved": counts["workers_resolved"], "gpus": gpus, "ocr": ocr,
            "seconds": round(elapsed, 1), "parsed": counts["parsed"],
            "failed": counts["failed"],
            "returncode": proc.returncode, **timeline, **sampler.summary(),
        }
    finally:
        if not keep_output:
            shutil.rmtree(content_dir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workers", default="1,4,8,12",
                    help="comma-separated worker counts (default: 1,4,8,12)")
    ap.add_argument("--gpus", default="4", help="comma-separated GPU counts (default: 4)")
    ap.add_argument("--ocr", default="off", help="comma-separated: on,off (default: off)")
    ap.add_argument("--repeat", type=int, default=1,
                    help="runs per configuration; the median is reported (default: 1)")
    ap.add_argument("--tag", required=True, help="names the output file")
    ap.add_argument("--python", default=".venv-full/bin/python",
                    help="interpreter with the enrich group installed")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and exit")
    args = ap.parse_args()

    # Before the plan, so `--dry-run` exercises it too: a sweep is tens of
    # minutes per configuration, and the one cheap way to run this script
    # is the one that should still say whether its detectors work.
    self_check()
    plan, gpus = _validated_plan(ap, args)

    print(f"{len(plan)} configuration(s) x {args.repeat} run(s); "
          f"each parses the whole corpus from an empty ledger.", flush=True)
    print(f"machine: {allowed_cpus()} CPUs available to this process "
          f"(host reports {os.cpu_count()})\n")
    if args.dry_run:
        for w, g, o in plan:
            print(f"  workers={w} gpus={g} ocr={'on' if o else 'off'}")
        return 0

    python = args.python
    if not Path(python).exists() and not shutil.which(python):
        print(f"error: {python} not found -- run "
              f"`bash scripts/install_full_pipeline.sh python-deps` first", file=sys.stderr)
        return 2

    out_path = BENCH_DIR / "results" / f"sweep-{args.tag}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    records = _run_plan(plan, args.repeat, python, out_path)
    _print_summary(records, gpus, out_path)
    return 0


def _validated_plan(ap, args):
    """The (workers, gpus, ocr) grid, or an argparse usage error.

    Validated rather than coerced: an unrecognised --ocr token used to
    fall through to "off", which silently runs a different benchmark than
    the one asked for and reports it under the requested name.
    """
    if args.repeat < 1:
        ap.error(f"--repeat must be at least 1, got {args.repeat}")
    ON, OFF = {"on", "true", "1", "yes"}, {"off", "false", "0", "no"}
    ocrs = []
    for token in args.ocr.split(","):
        t = token.strip().lower()
        if t in ON:
            ocrs.append(True)
        elif t in OFF:
            ocrs.append(False)
        else:
            ap.error(f"--ocr: {token!r} is neither on nor off "
                     f"(accepted: {', '.join(sorted(ON | OFF))})")
    try:
        workers = [int(w) for w in args.workers.split(",")]
        gpus = [int(g) for g in args.gpus.split(",")]
    except ValueError as exc:
        ap.error(f"--workers and --gpus take comma-separated integers: {exc}")
    if any(w < 1 for w in workers):
        ap.error(f"--workers must all be at least 1, got {args.workers!r}")
    if any(g < 0 for g in gpus):
        ap.error(f"--gpus must all be non-negative, got {args.gpus!r}")
    return [(w, g, o) for o in ocrs for g in gpus for w in workers], gpus


def _median_run(runs: list[dict]) -> dict:
    """The median run of a configuration's repeats, by wall clock.

    The upper of the two at an even `--repeat`, which is the pessimistic
    half of the pair and the right way round for a benchmark: reporting
    the faster of two runs as "the median" flatters whatever was
    measured.
    """
    return sorted(runs, key=lambda r: r["seconds"])[len(runs) // 2]


def _run_plan(plan, repeat, python, out_path):
    """Every configuration, every repeat, appended to `out_path` as it
    lands; the median run of each configuration is what is kept."""
    records: list[dict] = []
    with out_path.open("w") as fh:
        for w, g, o in plan:
            runs = []
            for rep in range(repeat):
                rec = one_run(w, g, o, python)
                rec["repeat"] = rep
                runs.append(rec)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                _print_run_line(w, g, o, rec)
            records.append(_median_run(runs))
    return records


def _print_run_line(w, g, o, rec):
    clamp = ""
    if rec["workers_resolved"] and rec["workers_resolved"] != w:
        clamp = (f"  !! CLAMPED to {rec['workers_resolved']}"
                 f" -- see worker_ceiling()")
    status = "" if rec["returncode"] == 0 and rec["failed"] == 0 else \
             f"  !! rc={rec['returncode']} failed={rec['failed']}"
    extra = ""
    if rec.get("startup_s") is not None:
        extra = (f"  startup={rec['startup_s']}s({rec['startup_pct']}%)"
                 f" tail={rec['drain_s']}s({rec['drain_pct']}%)")
    # flush: these runs are tens of minutes each, and stdout
    # is block-buffered when redirected to a file -- without
    # this a `> sweep.log` shows nothing until the very end.
    print(f"  workers={w:<3} gpus={g} ocr={'on ' if o else 'off'} "
          f"{rec['seconds']:8.1f}s  parsed={rec['parsed']:<4}"
          f"  host_cpu={rec['host_cpu_pct_of_allowed']}%{extra}{clamp}{status}",
          flush=True)


def _print_summary(records, gpus, out_path):
    """The speedup/efficiency table against the 1-worker OCR-off baseline."""
    baseline = next((r for r in records
                     if r["workers_resolved"] == 1 and not r["ocr"]
                     and r["gpus"] == max(gpus)), None)
    print(f"\nwrote {out_path}")
    print(f"\n{'req':>4} {'got':>4} {'gpus':>4} {'ocr':>4} {'wall':>9} "
          f"{'speedup':>8} {'eff':>5} {'host cpu%':>9}")
    for r in records:
        got = r["workers_resolved"] or "?"
        sp = eff = ""
        if baseline and isinstance(got, int) and got:
            sp = f"{baseline['seconds']/r['seconds']:7.2f}x"
            eff = f"{baseline['seconds']/r['seconds']/got:4.0%}"
        print(f"{r['workers_requested']:>4} {str(got):>4} {r['gpus']:>4} "
              f"{'on' if r['ocr'] else 'off':>4} {r['seconds']:8.1f}s {sp:>8} {eff:>5} "
              f"{str(r['host_cpu_pct_of_allowed']):>9}")
    if not baseline:
        print("\n(no 1-worker OCR-off run in this sweep, so no speedup column -- "
              "add `1` to --workers for a baseline)")
    clamped = [r for r in records
               if r["workers_resolved"] and r["workers_resolved"] != r["workers_requested"]]
    if clamped:
        print(f"\n!! {len(clamped)} configuration(s) were clamped below what was asked "
              f"for. Those rows measure the clamp, not the setting.")


if __name__ == "__main__":
    raise SystemExit(main())
