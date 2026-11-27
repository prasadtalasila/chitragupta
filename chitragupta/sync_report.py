"""A sync run's printed output: the up-front bibliography-quality
warnings, the one-line summary, and the per-cause WARNING lines.
Pure formatting, no ledger writes (#441).
"""

from chitragupta import bib_reader, config, dedup

# Timed-out citekeys named before "(+N more)": enough to name a handful of
# long documents in full, few enough that a wholesale timeout stays one line.
_MAX_NAMED_TIMEOUTS = 10


def _preflight_warnings(references) -> None:
    """The two bibliography-quality warnings a sync leads with."""
    incomplete = [r for r in references if not r.authors]
    if incomplete:
        print(
            f"  WARNING: {len(incomplete)} item(s) have no author metadata in the bib file "
            f"(likely a page saved as 'webpage' rather than proper item type) -- "
            f"citing them will produce a low-quality reference:"
        )
        for ref in incomplete:
            print(f"    {ref.citekey}: {ref.title[:80]!r}")
        print("  Fix the item type/metadata in your reference manager, re-export, and re-run sync.")

    duplicate_groups = dedup.find_duplicates(references)
    if duplicate_groups:
        print(
            f"  WARNING: {len(duplicate_groups)} possible duplicate group(s) -- same DOI or "
            f"near-identical title under different citekeys. A shared title doesn't always "
            f"mean the same source (e.g. a blog post and a webinar about the same named "
            f"report) -- check by hand before merging or removing either citekey:"
        )
        for group in duplicate_groups:
            citekeys = " / ".join(ref.citekey for ref in group)
            print(f"    {citekeys}: {group[0].title[:80]!r}")


def _summary_line(tally, kinds, stale_count, stale_label) -> str:
    """The one-line run summary the exit code below has to agree with."""
    summary = (
        f"Sync complete: {tally.parsed} parsed, {tally.skipped} unchanged, "
        f"{tally.no_pdf} without a PDF attachment, {tally.failed} failed, "
        f"{stale_count} {stale_label}."
    )
    # A deterministic failure is not retried but keeps every later run
    # exiting nonzero, so say what it is and what to do.
    if kinds["deterministic"]:
        # "Fix or remove the PDF" is wrong for a timeout, so defer to the
        # per-cause WARNING below whenever this run produced one.
        remedy = (
            "see the WARNING below for the fix, or re-run with --reparse"
            if tally.timed_out
            else "fix or remove the PDF, or re-run with --reparse"
        )
        summary += f" {kinds['deterministic']} needs attention (will not be retried -- {remedy})."
    if kinds["transient"]:
        summary += f" {kinds['transient']} will be retried next run."
    if tally.backend_unavailable:
        summary += f" {tally.backend_unavailable} skipped ({config.PARSER} unavailable)."
    # Each makes the run exit EXIT_BIB_INTEGRITY (issue 841), so it is
    # named on the last line, where a reader looks for why.
    if tally.bib_problems:
        summary += f" Bib file: {bib_reader.listed(tally.bib_problems)} -- see the WARNING above."
    # Skipped when nothing was parsed, where "0 pages/s" means nothing.
    # `workers` and the backend ride along, as a bare rate has no tuning value.
    if tally.parsed and tally.parse_elapsed > 0:
        summary += (
            f" {tally.total_pages} page(s) parsed in {tally.parse_elapsed:.1f}s "
            f"({tally.total_pages / tally.parse_elapsed:.2f} pages/s, "
            f"{tally.workers} worker(s), {config.PARSER})."
        )
    return summary


def _print_parse_warnings(tally) -> None:
    """The per-cause WARNING lines that follow the summary."""
    if tally.timed_out:
        # Its own line because the fix is a config value, not the PDF.
        # Named, since a few citekeys point at those documents while most of
        # the corpus points at the limit; capped at _MAX_NAMED_TIMEOUTS
        # because past that the count is the diagnosis.
        named = ", ".join(tally.timed_out[:_MAX_NAMED_TIMEOUTS])
        if len(tally.timed_out) > _MAX_NAMED_TIMEOUTS:
            named += f", (+{len(tally.timed_out) - _MAX_NAMED_TIMEOUTS} more)"
        print(
            f"  WARNING: {len(tally.timed_out)} document(s) hit the "
            f"{config.PARSER_DOCUMENT_TIMEOUT}s [parser].document_timeout and were "
            f"not parsed: {named}. Raise that setting (or switch it "
            "off) and re-run with --reparse -- a timeout is recorded as a "
            "deterministic failure, so it is not retried on its own."
        )
    if tally.low_quality:
        # Named in full: a few citekeys point at those documents, most of
        # the corpus at the backend.
        print(
            f"  WARNING: {len(tally.low_quality)} document(s) look like the parser lost "
            f"word boundaries: {', '.join(tally.low_quality)}. See config.toml's "
            f"[parser] quality-guard settings and docs/PDF-PARSER.md."
        )
    if tally.no_pdf_reasons:
        # The aggregate "without a PDF attachment" wording above is pinned
        # by callers and tests; this tells "never had a PDF" from a path
        # gone missing or an HTML-only snapshot, both worth fixing.
        breakdown = ", ".join(
            f"{tally.no_pdf_reasons[reason]} {label}"
            for reason, label in bib_reader.PDF_RESOLUTION_LABELS.items()
            if tally.no_pdf_reasons[reason]
        )
        print(f"  no-PDF breakdown: {breakdown}")
