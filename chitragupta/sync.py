"""Deterministic pipeline entrypoint: bib file -> ledger -> parsed text.

Safe to run unattended / on a schedule (idempotent, incremental):
    python -m chitragupta.corpus sync

A citekey that drops out of the bib file is only *reported* by default --
pass --remove-stale to actually delete its content/ledger.sqlite row (see
"Removing a paper" in README.md and chitragupta/ledger.py's find_stale/prune_missing).

This is the corpus layer: no generation, no LLM calls, just
bringing the shared corpus layer up to date with the bibliography (see
chitragupta/bib_reader.py -- the BibTeX-exported .bib file is the source of
truth for citekeys, not something this pipeline generates). Genre-specific
drafting (the drafting layer) is invoked separately, on demand, via the
Claude Code
skills in .claude/skills/.

Needs `bibtexparser` installed -- run scripts/install_full_pipeline.sh
first (creates .venv-full/ on a bare host), then run this via that
venv's python. python -m chitragupta.draft gate does not need it and still
runs with the bare system interpreter.

Split (#441) into four modules: this one keeps the top-level
orchestration (`run`/`main`) and the per-document ledger-write/tally
step, `chitragupta/sync_pool.py` holds the parse-dispatch engine,
`chitragupta/sync_decide.py` the two ledger-vs-bib-file decisions, and
`chitragupta/sync_report.py` the printed summary/warnings -- each a
one-way dependency of this module, none of the other three importing
back.
"""

import argparse
import logging
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import (
    bib_reader,
    config,
    ledger,
    logging_setup,
    pdf_text,
    runlock,
    sync_decide,
    sync_pool,
    sync_report,
)

# A fixed name, not __name__. Until 5.2.0 this module was itself the CLI
# entrypoint (python -m chitragupta.sync), and Python sets __name__ to
# "__main__" for whichever module is run that way -- not "chitragupta.sync". A
# logger named "__main__" would sit outside the "src" tree entirely, so
# logging_setup.configure()'s logging.getLogger("src").setLevel(...)
# would silently never apply to it. Confirmed against a real run, not
# assumed: every test in this suite imports sync as a plain submodule,
# where __name__ is already "chitragupta.sync" and the distinction is invisible.
# chitragupta/corpus.py is the entrypoint now, so __name__ here is always
# "chitragupta.sync" -- but the name stays pinned rather than tracking whatever
# imports it, because it is also the string that appears in every
# logs/pipeline.log line and in the grep docs/CLI.md tells a scheduler
# to use.
logger = logging.getLogger("chitragupta.sync")

# What running this module directly exits with. `EX_USAGE` from BSD's
# sysexits -- chosen for what it is *not*: none of the three codes
# docs/CLI.md publishes as `sync`'s API. See refuse_direct_invocation.
EXIT_COMMAND_REMOVED = 64


@dataclass
class _Tally:
    """One sync run's counters, threaded through the helpers below so
    each phase mutates one object instead of `run` juggling a dozen
    locals. Plain fields, no behaviour -- the summary reads them out."""

    parsed: int = 0
    failed: int = 0
    skipped: int = 0
    no_pdf: int = 0
    backend_unavailable: int = 0
    total_pages: int = 0
    parse_elapsed: float = 0.0
    workers: int = 1
    low_quality: list = field(default_factory=list)
    timed_out: list = field(default_factory=list)
    no_pdf_reasons: Counter = field(default_factory=Counter)


def _dispatch_and_apply(con, to_parse, tally) -> None:
    """The parse half: fan the documents out, then apply every result.

    Timing brackets dispatch plus the result loop, not just the pool
    itself: the ledger writes and prints in that loop are
    microseconds against a parse that is (for docling) minutes, so
    including them costs nothing and avoids pushing timing into
    _parse_serial/_parse_parallel for a difference that's noise.
    `tally.workers` keeps the resolved count for the summary's pages/s
    figure (see pdf_text.resolve_workers on why that -- not the
    requested value -- is the number worth reporting).
    """
    workers, complaint = pdf_text.resolve_workers(
        len(to_parse), docling=(config.PARSER == "docling")
    )
    if complaint:
        logger.warning(complaint)
    tally.workers = workers
    parse_started = time.monotonic()
    if workers > 1:
        print(f"  parsing {len(to_parse)} document(s) with {workers} workers")
        results = sync_pool._parse_parallel(to_parse, workers, pdf_text.docling_threads(workers))
    else:
        results = sync_pool._parse_serial(to_parse)

    # Applied in bib order, not completion order: futures finish in
    # whatever order they finish, and letting that reach stdout would
    # make two identical runs print differently and stop anyone
    # diffing them.
    for _ref, (citekey, out_path, exc) in zip(to_parse, results):
        _record_result(con, citekey, out_path, exc, tally)
    tally.parse_elapsed = time.monotonic() - parse_started


def _record_result(con, citekey, out_path, exc, tally) -> None:
    """One document's outcome, written to the ledger and counted."""
    if exc is None:
        out_path = Path(out_path)
        ledger.mark_parsed(con, citekey, out_path)
        tally.parsed += 1
        print(f"  parsed  {citekey}")
        # Read once, used twice: the quality guard below and the
        # page count feeding the summary's pages/s figure both
        # want this document's full text, and it's already being
        # read off disk regardless -- no reason to do it twice.
        text = out_path.read_text(encoding="utf-8", errors="replace")
        tally.total_pages += pdf_text.page_count(text)
        # Reported per document rather than only in the summary:
        # the fix is usually per document (a scan, an unusual
        # font) or global (the wrong backend), and seeing which
        # citekeys trip it is what tells the two apart.
        warning = pdf_text.quality_warning(text)
        if warning:
            tally.low_quality.append(citekey)
            logger.warning("WARNING %s: %s", citekey, warning)
    elif isinstance(exc, pdf_text.BackendUnavailable):
        # The up-front probe passed, but the backend vanished
        # (pdftotext dropped from PATH, or the docling
        # package became uninstallable) between then and this
        # specific item -- count and report it the same as the
        # up-front case instead of letting it crash sync
        # uncaught, which is exactly the failure mode probing
        # exists to prevent. str(exc) carries the same actionable
        # install hint as the up-front WARNING (both come from
        # pdf_text.unavailable_reason()), not just "unavailable".
        tally.backend_unavailable += 1
        logger.warning("no-%s  %s: %s", config.PARSER, citekey, exc)
    else:
        # getattr, not isinstance: the marker rides on the
        # exception instance because it is set by whoever knows
        # the *cause*, which is the pool, not the raiser.
        ledger.mark_parse_failed(con, citekey, str(exc), transient=getattr(exc, "transient", False))
        tally.failed += 1
        # Collected rather than marked transient above: what
        # expired is a *setting*, so a document that ran out of
        # time will run out of it again next run, and retrying
        # automatically would spend the same minutes every run
        # without ever converging. Naming it in the summary with
        # the fix that applies is the useful thing to do
        # instead -- see the report after the summary.
        if getattr(exc, "timed_out", False):
            tally.timed_out.append(citekey)
        logger.error("FAILED  %s: %s", citekey, exc)


def _parser_available() -> bool:
    """Probe the parse backend once, warning up front when it is absent."""
    available = pdf_text.is_available()
    if not available:
        print(
            f"  WARNING: {pdf_text.unavailable_reason()} Parsing will be skipped "
            "for every item that needs it this run. Bibliographic metadata is "
            "still synced to the ledger."
        )
    return available


def run(remove_stale: bool = False, reparse: bool = False) -> int:
    # Before the bibliography, not after: on a docling run with a worker
    # pool this starts the forkserver importing torch and docling in the
    # background, and reading a 646-entry bib file is the ~2.5s that
    # would otherwise be spent doing nothing else. A no-op for every
    # other configuration, including the default one.
    pdf_text.prestart_pool()

    print(f"Reading bibliography from {config.BIB_FILE_PATH} ...")
    references = bib_reader.read_library()
    print(f"  found {len(references)} bibliographic item(s)")
    sync_report._preflight_warnings(references)

    parser_available = _parser_available()
    tally = _Tally()
    with ledger.connection() as con:
        to_parse = sync_decide._to_parse(con, references, reparse, parser_available, tally)
        _dispatch_and_apply(con, to_parse, tally)
        pruned, stale, suspicious = sync_decide._report_stale(con, references, remove_stale)
        # Read while the connection is still open -- the summary below
        # runs after it is closed.
        kinds = ledger.failure_counts(con)

    stale_count = len(pruned) if remove_stale else len(stale)
    stale_label = "pruned" if remove_stale else "stale (not removed)"
    summary = sync_report._summary_line(tally, kinds, stale_count, stale_label)
    print(summary)
    # Also emitted through the logger -- landing in logs/pipeline.log even
    # though it's already on stdout -- so a rotated log file is a
    # self-contained run history without needing stdout alongside it.
    # Built from the same counters the return code below uses, not a
    # second independent tally, so the log and the exit status can never
    # disagree about whether this run had trouble.
    #
    # extra={"file_only": True} keeps this out of logging_setup.configure()'s
    # console handler specifically -- without it, a real `python -m
    # chitragupta.sync` run prints this line twice (once from the print() above,
    # once from the console handler catching this same record), which is
    # exactly the double-printing "stdout stays untouched" was meant to
    # avoid. Confirmed against a real run, not assumed.
    logger.log(
        logging.WARNING
        if (tally.failed or tally.backend_unavailable or kinds["deterministic"])
        else logging.INFO,
        "%s",
        summary,
        extra={"file_only": True},
    )
    sync_report._print_parse_warnings(tally)
    if stale_count and not remove_stale and not suspicious:
        print(
            f"Review the {stale_count} stale item(s) above, then re-run with "
            "--remove-stale to delete them from the ledger."
        )
    print(f"Ledger:      {config.LEDGER_PATH}")
    print(f"Parsed text: {config.PARSED_DIR}/")
    # A deterministic failure keeps the run nonzero on *every* run until
    # it is resolved, not just the run that produced it. It is not
    # retried, so `failed` (which counts this run's attempts) is zero for
    # it -- and a corpus with a hole in it must never report success.
    # `suspicious` (the bib file yielding 0 references against a non-empty
    # ledger) is included for the same reason: sync's exit code is an
    # unattended caller's only documented API (docs/CLI.md), so a broken
    # export must not read as "clean" indefinitely.
    #
    # `bib_reader.PDF_LOST_REASONS` joins them for that same reason
    # (issue #556): a PDF this export claims and this host cannot
    # produce -- gone, or present and unreadable -- is a document
    # silently missing from the corpus, and reporting it in the summary
    # while exiting 0 made it silent to exactly the caller that cannot
    # read a summary. Gated on those reasons rather than on
    # `tally.no_pdf`, because the other three describe an item that
    # never had a PDF here: an ordinary state of a bibliography, not a
    # hole. That list lives in `bib_reader` beside the reasons
    # themselves, so adding a reason cannot silently miss this gate.
    return (
        1
        if (
            tally.failed
            or tally.backend_unavailable
            or kinds["deterministic"]
            or suspicious
            or any(tally.no_pdf_reasons[reason] for reason in bib_reader.PDF_LOST_REASONS)
        )
        else 0
    )


def main(argv: "list[str] | None" = None) -> int:
    """`python -m chitragupta.corpus sync`. Reached only through chitragupta/corpus.py,
    which is why this file has no `__main__` block of its own."""
    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.corpus sync",
        description="Sync content/ledger.sqlite from the bib file "
        "(the corpus layer -- deterministic).",
    )
    parser.add_argument(
        "--reparse",
        action="store_true",
        help="Re-extract every PDF, ignoring the ledger's record of what is already parsed "
        "(use when output is recorded as fine but you have reason to doubt it)",
    )
    parser.add_argument(
        "--remove-stale",
        action="store_true",
        help="Delete ledger rows for citekeys no longer in the bib file "
        "(default: report only, don't delete)",
    )
    args = parser.parse_args(argv)
    # Held for the whole run, and only at the entrypoint: run() itself
    # stays callable in-process (the tests do that) without fighting a
    # lock, and only an actual invocation contends for it.
    try:
        with runlock.pipeline_lock():
            # Inside the lock, not before it: two overlapping scheduled
            # invocations would otherwise both attach a
            # RotatingFileHandler to the same logs/pipeline.log before
            # either acquires the lock -- and RotatingFileHandler isn't
            # safe for two processes to hold open on the same file at
            # once (a rotation from one can land mid-write from the
            # other). The lock already serializes actual sync work; this
            # makes it serialize handler creation too, so at most one
            # process ever has a live handler on the file. The same
            # constraint is why chitragupta/enrich/__main__.py -- which shares both
            # this lock and this log file -- configures in the same
            # place; see chitragupta/logging_setup.py's own docstring.
            logging_setup.configure()
            return run(remove_stale=args.remove_stale, reparse=args.reparse)
    except runlock.AlreadyRunning as exc:
        # Deliberately still a bare print, not the logger: this is the
        # losing side of the race above and must not touch
        # logs/pipeline.log itself, which the winner may already be
        # writing to. Losing the lock is an expected, harmless outcome
        # under any real schedule (see docs/CLI.md's "Running sync on a
        # schedule"), not a failure worth persisting.
        print(f"  {exc}", file=sys.stderr)
        return runlock.EXIT_ALREADY_RUNNING
    except ledger.PruneRefused as exc:
        # ledger.prune_missing's guard (--remove-stale against a bib file
        # that yielded 0 references) raises rather than silently wiping
        # the ledger. main() is the unattended entrypoint (docs/CLI.md),
        # so that refusal must reach the caller as a message and a
        # nonzero exit, not an uncaught traceback. A distinct exception
        # type, not bare RuntimeError, so an unrelated internal bug
        # elsewhere in run() doesn't get misread as this well-understood
        # refusal.
        print(f"  {exc}", file=sys.stderr)
        return 1


def refuse_direct_invocation() -> int:
    """`python -m chitragupta.sync` is not a command any more -- say so.

    It was one until 5.2.0, which moved it behind `python -m chitragupta.corpus
    sync` and dropped this module's `__main__` block. Dropping it did not
    make the old spelling an error: `python -m chitragupta.sync` still imported
    the module and exited 0, having done nothing. Everywhere else in this
    project that trap is silent and harmless (docs/ARCHITECTURE.md
    accepts it as the price of one `--help` per layer), and here it was
    not: this is the one command in this project that plausibly runs
    unattended, from a crontab or a systemd unit, where "exited 0" is the
    only thing anyone ever reads.

    #151 measured the cost. `bench/repro_check.py` and
    `bench/sweep_sync.py` kept invoking the old spelling for a whole
    release: both timed a sync that never ran, parsed no progress lines
    out of its empty stdout, and recorded that as a result. A measurement
    harness that succeeds having done nothing produces *wrong* data, not
    missing data.

    This is not a second entry point and does not reopen the invariant.
    It parses no arguments, offers no `--help`, takes no lock and syncs
    nothing -- there is still exactly one way into this layer.

    **The exit code is 64, and the number is the point.** docs/CLI.md
    publishes `sync`'s three codes as an API an unattended caller reads:
    `0` clean, `1` a document failed, `2` another run holds the lock. The
    obvious choice here -- `2`, argparse's usage error -- is the one
    number that must not be used, because a scheduler that consults that
    table reads `2` as "expected, do nothing" and goes on ignoring a
    crontab line that has not synced anything since 5.2.0. That is the
    failure this whole change exists to end, reintroduced by its own fix.
    64 is `EX_USAGE` from BSD's sysexits, and matters here only for what
    it is not: none of the three, and non-zero, so every wrapper that
    checks at all sees a failure.

    stderr rather than stdout for a related reason -- `sync`'s stdout is
    a documented, diffable contract, and a reader parsing it should find
    it empty rather than find a line that reads like a result.
    """
    print(
        "python -m chitragupta.sync was removed in 5.2.0 and does nothing. "
        "Use: chitragupta corpus sync",
        file=sys.stderr,
    )
    return EXIT_COMMAND_REMOVED


if __name__ == "__main__":
    raise SystemExit(refuse_direct_invocation())
