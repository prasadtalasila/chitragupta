"""Deterministic pipeline entrypoint: bib file -> ledger -> parsed text.

Safe to run unattended / on a schedule (idempotent, incremental):
    python -m chitragupta.corpus sync

A citekey that drops out of the bib file is only *reported* unless
--remove-stale is passed. No generation and no LLM calls: the bib file is
the source of truth for citekeys. Needs `bibtexparser` (.venv-full).

This module keeps `run`/`main` and the per-document ledger write; the
parse pool, the ledger-vs-bib decisions, the report and the residue scan
live in `sync_pool`, `sync_decide`, `sync_report` and `sync_residue`.
"""

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
from chitragupta.help_format import ClickParser
from chitragupta.progname import prog_for

# A fixed name, not __name__: it is the string in every logs/pipeline.log
# line and in the grep docs/CLI.md gives schedulers.
logger = logging.getLogger("chitragupta.sync")

# `EX_USAGE` from sysexits, chosen because it is none of the codes
# docs/CLI.md publishes. See refuse_direct_invocation.
EXIT_COMMAND_REMOVED = 64

# A completed run's two nonzero codes, split by remedy (#696): with one
# code, a caller could not tell a clean parse with a bibliography problem
# from lost documents. 3, because 2 is EXIT_ALREADY_RUNNING.
EXIT_PARSE_FAILURE = 1
EXIT_BIB_INTEGRITY = 3


@dataclass
class _Tally:
    """One sync run's counters, mutated by each phase and read by the summary."""

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
    # `bib_reader.Library.integrity_problems`: what the bib read lost.
    bib_problems: dict = field(default_factory=dict)


def _dispatch_and_apply(con, to_parse, tally) -> None:
    """The parse half: fan the documents out, then apply every result.

    `tally.workers` keeps the *resolved* count for the pages/s figure.
    """
    workers, complaint = pdf_text.resolve_workers(
        len(to_parse), docling=(config.PARSER == "docling")
    )
    if complaint:
        logger.warning(complaint)
    tally.workers = workers
    parse_started = time.monotonic()

    def commit(citekey, out_path, exc) -> None:
        _commit_result(con, citekey, out_path, exc)

    if workers > 1:
        print(f"  parsing {len(to_parse)} document(s) with {workers} workers")
        threads = pdf_text.docling_threads(workers)
        results = sync_pool._parse_parallel(to_parse, workers, threads, commit)
    else:
        results = sync_pool._parse_serial(to_parse, commit)

    # Reported in bib order, so two identical runs print identically. The
    # ledger already has each row: `commit` wrote it on arrival (#961).
    for _ref, (citekey, out_path, exc) in zip(to_parse, results):
        _report_result(citekey, out_path, exc, tally)
    tally.parse_elapsed = time.monotonic() - parse_started


def _commit_result(con, citekey, out_path, exc) -> None:
    """One document's outcome, written to the ledger the moment it lands."""
    if exc is None:
        ledger.mark_parsed(con, citekey, Path(out_path))
    elif not isinstance(exc, pdf_text.BackendUnavailable):
        # getattr: the pool, which knows the cause, sets the marker.
        ledger.mark_parse_failed(con, citekey, str(exc), transient=getattr(exc, "transient", False))


def _report_result(citekey, out_path, exc, tally) -> None:
    """One document's outcome, counted and printed."""
    if exc is None:
        out_path = Path(out_path)
        tally.parsed += 1
        print(f"  parsed  {citekey}")
        text = out_path.read_text(encoding="utf-8", errors="replace")
        tally.total_pages += pdf_text.page_count(text)
        # Per document: which citekeys trip it tells a bad scan from the
        # wrong backend.
        warning = pdf_text.quality_warning(text)
        if warning:
            tally.low_quality.append(citekey)
            logger.warning("WARNING %s: %s", citekey, warning)
    elif isinstance(exc, pdf_text.BackendUnavailable):
        # The backend vanished after the up-front probe passed: count it
        # like the up-front case rather than crash.
        tally.backend_unavailable += 1
        logger.warning("no-%s  %s: %s", config.PARSER, citekey, exc)
    else:
        tally.failed += 1
        # Not marked transient: a timeout is a setting and would recur on
        # every retry. The summary names the fix instead.
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
    # Before the bib read, so a docling pool warms up during it.
    pdf_text.prestart_pool()

    print(f"Reading bibliography from {config.BIB_FILE_PATH} ...")
    library = bib_reader.read_library()
    references = library.references
    print(f"  found {len(references)} bibliographic item(s)")
    sync_report._preflight_warnings(references)

    parser_available = _parser_available()
    tally = _Tally(bib_problems=library.integrity_problems)
    with ledger.connection() as con:
        had, to_parse = sync_decide._plan(con, references, reparse, parser_available, tally)
        _dispatch_and_apply(con, to_parse, tally)
        pruned, stale, suspicious = sync_decide._record_and_report(con, library, remove_stale, had)
        kinds = ledger.failure_counts(con)

    # A lossy bib read turns --remove-stale into a report (issue 841).
    pruning = remove_stale and not library.unread
    stale_count = len(pruned) if pruning else len(stale)
    stale_label = "pruned" if pruning else "stale (not removed)"
    summary = sync_report._summary_line(tally, kinds, stale_count, stale_label)
    print(summary)
    # Also logged (file only, as stdout already has it) so a rotated log is a
    # self-contained run history; the level uses the exit code's counters.
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
    return _exit_code(tally, kinds, suspicious)


# Nonzero until resolved, on every run:
# - a deterministic failure: never retried, so `failed` is zero for it.
# - `suspicious` (0 references against a non-empty ledger): a broken export
#   must not read as clean.
# - a PDF in `bib_reader.PDF_LOST_REASONS` (#556): a hole in the corpus.
#   The other no-PDF reasons are an ordinary bibliography, not a hole.
# - `tally.bib_problems` (840, 841): a duplicated citekey, a dropped entry
#   or an unusable filename; papers the bib holds and this run did not read.
# A parse failure wins when both apply: it is the more actionable one, so
# EXIT_BIB_INTEGRITY also asserts that every requested parse succeeded.
def _exit_code(tally, kinds, suspicious) -> int:
    """What a completed run reports, split by remedy (issue #696)."""
    if tally.failed or tally.backend_unavailable or kinds["deterministic"]:
        return EXIT_PARSE_FAILURE
    lost = any(tally.no_pdf_reasons[reason] for reason in bib_reader.PDF_LOST_REASONS)
    if suspicious or lost or tally.bib_problems:
        return EXIT_BIB_INTEGRITY
    return 0


def main(argv: "list[str] | None" = None) -> int:
    """`python -m chitragupta.corpus sync`, reached through chitragupta/corpus.py."""
    parser = ClickParser(
        prog=f"{prog_for('corpus')} sync",
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
    # Held only at the entrypoint, so run() stays callable in-process.
    try:
        with runlock.pipeline_lock():
            # Inside the lock: see logging_setup's module docstring.
            logging_setup.configure()
            return run(remove_stale=args.remove_stale, reparse=args.reparse)
    except runlock.AlreadyRunning as exc:
        # A bare print: the loser must not write to the winner's log file.
        print(f"  {exc}", file=sys.stderr)
        return runlock.EXIT_ALREADY_RUNNING
    except ledger.PruneRefused as exc:
        # A typed refusal, so an unrelated bug in run() still raises.
        print(f"  {exc}", file=sys.stderr)
        return 1


def refuse_direct_invocation() -> int:
    """`python -m chitragupta.sync` is not a command any more -- say so.

    Removed in 5.2.0, after which it silently exited 0. That mattered here
    alone, since sync runs from crontabs where the exit code is all anyone
    reads (#151: two bench harnesses timed a sync that never ran). Parses
    nothing, takes no lock, syncs nothing.

    **Exit 64, not 2.** docs/CLI.md publishes `2` as "another run holds
    the lock", which a scheduler treats as harmless. stderr, so the
    documented stdout stays empty.
    """
    print(
        "python -m chitragupta.sync was removed in 5.2.0 and does nothing. "
        "Use: chitragupta corpus sync",
        file=sys.stderr,
    )
    return EXIT_COMMAND_REMOVED


if __name__ == "__main__":
    raise SystemExit(refuse_direct_invocation())
