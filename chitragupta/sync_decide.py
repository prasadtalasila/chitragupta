"""The two ledger-vs-bib-file decisions a sync run makes before it does
any parsing: which references still need work, and which ledger rows
the bib file no longer accounts for (#441). Never calls back into `sync`.
"""

from chitragupta import bib_reader, config, ledger, ledger_tables, sync_renames, sync_residue


def _to_parse(con, references, reparse, parser_available, tally) -> list:
    """The decide half of the decide/parse split: upsert every reference,
    count the ones that need no work, and return the rest.

    Every ledger call stays on the main thread (sqlite3 connections are
    not thread-safe, and sqlite has one writer); only the backend call is
    pooled. `[parser].workers` defaults to 1, as a routine sync parses
    few documents; a bulk first sync (~39 minutes serial for 501 PDFs) opts in.
    """
    to_parse = []
    try:
        for ref in references:
            # One transaction for the loop, not per reference (#511/m-75): a
            # no-op sync otherwise made 646 fsync'd writes, each a window
            # for the read-only inspector to see a half-written ledger.
            # `vanished` catches a PDF gone since the bib read (#556).
            vanished = []
            needs_parse = ledger.upsert_reference(
                con, ref, force=reparse, commit=False, on_missing_pdf=vanished.append
            )
            # The PDF was readable at bib-read time, so one lost since gets
            # the reason it would have got a moment earlier.
            resolution = _lost_pdf_reason(vanished[0]) if vanished else ref.pdf_resolution
            if vanished or not ref.pdf_path:
                tally.no_pdf += 1
                tally.no_pdf_reasons[resolution] += 1
                label = bib_reader.PDF_RESOLUTION_LABELS[resolution]
                print(f"  no-pdf  {ref.citekey}: {label}")
                continue
            if not needs_parse:
                tally.skipped += 1
                continue
            if not parser_available:
                tally.backend_unavailable += 1
                continue
            to_parse.append(ref)
    finally:
        # `finally` is what makes batching acceptable: docs/DESIGN.md
        # rests on incremental commit points surviving a crash or
        # interrupt, and committing on the way out keeps every finished
        # row on disk.
        con.commit()
    return to_parse


def _lost_pdf_reason(exc: OSError) -> str:
    """Which no-PDF reason an unreadable `ref.pdf_path` reports as,
    classified on the exception's type (DEVELOPER-AGENTS.md).

    A gone file (`NotADirectoryError` included) gets `bib_reader`'s own
    reason for that condition. Any other `OSError` (permissions, a failing
    disk) must not borrow it, as the documented remedy would be wrong
    (issue #556).
    """
    if isinstance(exc, (FileNotFoundError, NotADirectoryError)):
        return bib_reader.PDF_PATH_GONE
    return bib_reader.PDF_UNREADABLE


def _prune(con, seen_citekeys, notes=None) -> list[tuple[str, str | None]]:
    """The --remove-stale deletion itself, residue report first."""
    # Skipped when the bib yielded nothing: prune_missing is about to
    # refuse, and a whole-ledger residue report would bury that.
    if seen_citekeys:
        sync_residue.report([key for key, _path in ledger.find_stale(con, seen_citekeys)])
    pruned = ledger.prune_missing(con, seen_citekeys)
    for citekey, _parsed_path in pruned:
        print(f"  pruned  {citekey} {_gone(notes, citekey)}")
    return pruned


# Issue 841. Printed, not raised as `ledger.PruneRefused`, which would end
# the run before its summary and with the wrong exit code. Nothing is
# deleted until the read is whole.
def _refuse_prune(library, stale_count) -> None:
    """Say why --remove-stale deleted nothing this run."""
    print(
        f"  Refusing to prune: this read of {config.BIB_FILE_PATH.name} lost "
        f"{bib_reader.listed(library.unread)} (see the WARNING above), so a "
        "citekey missing from it may be "
        f"missing only from this read, not from your library. The {stale_count} "
        "stale item(s) below are reported, not deleted. Fix the bib file, "
        "re-export, and re-run with --remove-stale."
    )


def _plan(con, references, reparse, parser_available, tally) -> tuple[set[str], list]:
    """`(the ledger's citekeys before this sync, what to parse)`, the
    snapshot taken before anything is written."""
    had = ledger.known_citekeys(con)
    return had, _to_parse(con, references, reparse, parser_available, tally)


def _record_and_report(
    con, library, remove_stale, had=frozenset()
) -> tuple[list[tuple[str, str | None]], list[tuple[str, str | None]], bool]:
    """After ingest: record what the bib says beyond its entries, then
    prune or report stale rows (`_report_stale`).

    Collection names are rewritten whole, so a rename keeps its slug.
    Renames are recorded before any prune, and not at all on a read that
    lost entries (#841). A read with no citekey at all records nothing:
    it is the suspicious shape, and would mark every cited key a defect.
    """
    seen = library.seen_citekeys
    notes = {}
    if seen:
        ledger_tables.replace_collection_names(con, library.tables.collection_names)
        con.commit()
    if seen and not library.unread:
        stale = [key for key, _path in ledger.find_stale(con, seen)]
        declared = library.tables.declared_renames
        renames, shared = sync_renames.detect(con, stale, seen, declared, seen - had)
        ledger_tables.replace_stale(con, set(stale))
        sync_renames.record(con, renames, seen)
        notes = sync_renames.suffixes(renames, shared)
    return _report_stale(con, library, remove_stale, notes)


def _gone(notes, citekey) -> str:
    """A stale or pruned line's bracket, with what sync knows of a rename."""
    return f"(no longer in {config.BIB_FILE_PATH.name}{(notes or {}).get(citekey, '')})"


def _report_stale(
    con, library, remove_stale, notes=None
) -> tuple[list[tuple[str, str | None]], list[tuple[str, str | None]], bool]:
    """Prune or report ledger rows the bib file no longer has.

    Returns (pruned, stale, suspicious). Only the ledger row is removed
    (see `prune_missing`), and only with --remove-stale: a short bib is
    more often a botched export than a removal. A read that lost entries
    (#841) is only reported. `sync_residue` reports first (#763), so the
    report describes the corpus the person is asked about. Stale is
    judged against `library.seen_citekeys`, not the references (#840).
    """
    seen_citekeys = library.seen_citekeys
    if remove_stale and not library.unread:
        return _prune(con, seen_citekeys, notes), [], False

    stale = ledger.find_stale(con, seen_citekeys)
    suspicious = not seen_citekeys and bool(stale)
    if suspicious:
        # The shape prune_missing refuses on: an empty read against a full
        # ledger is a botched export, so don't suggest --remove-stale.
        print(
            f"  SUSPICIOUS: the bib file yielded 0 references, so all "
            f"{len(stale)} ledger item(s) show as stale. This usually "
            f"means the bib file is empty, corrupted, or BIB_FILE is "
            f"misconfigured -- not that every citekey was actually "
            f"removed. Fix the export/path and re-run sync rather than "
            f"passing --remove-stale (which would refuse on this exact "
            f"shape)."
        )
    else:
        # The --remove-stale instruction is printed once, in the summary,
        # so a truncated bib does not repeat it per item.
        if remove_stale and stale:
            _refuse_prune(library, len(stale))
        for citekey, _parsed_path in stale:
            print(f"  stale   {citekey} {_gone(notes, citekey)}")
        # Between the names and the invitation to act: this default run is
        # the moment the human confirms.
        sync_residue.report([citekey for citekey, _parsed_path in stale])
    return [], stale, suspicious
