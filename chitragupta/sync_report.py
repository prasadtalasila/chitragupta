"""A sync run's printed output: the up-front bibliography-quality
warnings, the one-line summary, and the per-cause WARNING lines that
follow it.

Split from `chitragupta/sync.py` (#441): pure formatting over data a
caller already has (`references`, a `_Tally`, the failure-kind counts)
-- no ledger writes, no parsing, and no call back into
`chitragupta.sync`.
"""

from chitragupta import bib_reader, config, dedup

# How many timed-out citekeys the summary names before falling back to
# "(+N more)". Enough that the case worth naming -- a handful of long
# documents against a limit that is right for the rest of the corpus --
# is always named in full, and small enough that a corpus-wide timeout
# stays one readable line.
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
    # A deterministic failure is not retried, so it would otherwise
    # vanish from view after the run that produced it while still making
    # every later run exit nonzero. Say what it is and what to do.
    if kinds["deterministic"]:
        # "fix or remove the PDF" is the right remedy for the usual
        # deterministic failure and the wrong one for a timeout, where
        # the PDF is fine and a setting is too low. Rather than print
        # both and let them contradict each other, this line defers to
        # the per-cause WARNING below whenever this run produced one --
        # the summary keeps saying what the state is, and the thing that
        # knows the cause says what to do about it.
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
    # Skipped on a no-op run (parsed == 0, the common case once a corpus
    # is caught up) rather than reporting a meaningless "0 pages/s" --
    # and only after `parsed` is known to be nonzero is `parse_elapsed`
    # guaranteed to reflect real work rather than a dispatch that found
    # nothing to do. `workers` is the resolved count pdf_text.resolve_workers
    # returned, and both it and the
    # backend ride along because a bare rate has no tuning value without
    # them. bench/sweep_sync.py doesn't parse this figure yet -- today it
    # only regexes the [n/N] progress lines and a raw document count --
    # but could pick it up the same way, to normalize by document size
    # rather than compare corpora on raw counts alone.
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
        # Reported on its own line because the "needs attention" advice
        # above is wrong for this one failure: the fix is a config value,
        # not the PDF, and a reader following "fix or remove the PDF" on
        # a document that is merely long has nothing to fix.
        #
        # Named rather than counted, because a couple of citekeys points
        # at those documents (a large scan, OCR on) while most of the
        # corpus tripping it points at the limit being too low for this
        # host -- and the list is what tells the two apart.
        #
        # Capped, unlike the low_quality list below, because that
        # distinction is already made by the first handful: past
        # _MAX_NAMED_TIMEOUTS the count is the diagnosis, and naming all
        # 646 of a corpus that timed out wholesale would bury it in a
        # single line no terminal or log aggregator wants. Same
        # "(+N more)" idiom pdf_text uses on docling's per-page errors,
        # and the count stays exact either way.
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
        # Named in full rather than counted: a handful of citekeys points
        # at those documents, while most of the corpus tripping it points
        # at the backend, and the list is what distinguishes the two.
        print(
            f"  WARNING: {len(tally.low_quality)} document(s) look like the parser lost "
            f"word boundaries: {', '.join(tally.low_quality)}. See config.toml's "
            f"[parser] quality-guard settings and docs/PDF-PARSER.md."
        )
    if tally.no_pdf_reasons:
        # Least-churn fix for the masking this bucket used to cause: the
        # aggregate "N without a PDF attachment" count above is unchanged
        # (existing callers/tests depend on that exact wording), but an
        # audit no longer has to guess whether that N is "never had a
        # PDF" (routine) or "PDF path silently went missing"/"only an
        # HTML snapshot, invisible to retrieval" (both worth fixing).
        breakdown = ", ".join(
            f"{tally.no_pdf_reasons[reason]} {label}"
            for reason, label in bib_reader.PDF_RESOLUTION_LABELS.items()
            if tally.no_pdf_reasons[reason]
        )
        print(f"  no-PDF breakdown: {breakdown}")
