"""The two ledger-vs-bib-file decisions a sync run makes before it does
any parsing: which references still need work, and which ledger rows
the bib file no longer accounts for.

Split from `chitragupta/sync.py` (#441): both functions take the open
ledger connection and the bib-parsed `references` list a caller already
has, and neither calls back into `chitragupta.sync` -- `chitragupta/sync.py`
calls these, not the reverse.
"""

from chitragupta import bib_reader, config, ledger


def _to_parse(con, references, reparse, parser_available, tally) -> list:
    """The decide half of the decide/parse split: upsert every reference,
    count the ones that need no work, and return the rest.

    Split from the parse half rather than one loop doing both.
    Every ledger call stays here, on the main thread, because a
    sqlite3 connection is not safe to share across threads and
    sqlite has a single writer regardless -- only the backend call
    (pdftotext/docling, per config.PARSER) is ever handed to a pool.

    Whether there is a pool at all is [parser].workers, which
    defaults to 1: a routine sync parses zero-to-few documents
    (chitragupta/ledger.py's (size, mtime)-before-hash skip), so paying pool
    setup by default would cost more than it saves. It is a bulk or
    first-time sync that needs this -- 501 PDFs at one audit, ~39
    minutes serial with docling -- and that case is opt-in.
    """
    to_parse = []
    try:
        for ref in references:
            # One transaction for the whole loop rather than one per
            # reference (#511/m-75). `last_synced` moves on every row on
            # every run, so a *no-op* sync rewrote all of them -- 646
            # fsync'd write transactions on the corpus this was measured
            # against, and 646 windows in which the read-only inspector
            # could see a half-written ledger.
            needs_parse = ledger.upsert_reference(con, ref, force=reparse, commit=False)
            if not ref.pdf_path:
                tally.no_pdf += 1
                tally.no_pdf_reasons[ref.pdf_resolution] += 1
                label = bib_reader.PDF_RESOLUTION_LABELS[ref.pdf_resolution]
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
        # `finally`, not a plain call after the loop, and this is the
        # whole reason the batching is acceptable. docs/DESIGN.md rejects
        # locking the ledger precisely because it "would force a run into
        # one transaction, discarding the incremental commit points on a
        # crash". Committing on the way out keeps that guarantee at batch
        # granularity: every row written is a whole row, so what finished
        # is still on disk. The raise path this used to name -- a PDF
        # moved between the bib read and `_stat_pdf`, m-71 -- is closed
        # now (`ledger_upsert._pdf_identity` catches the `OSError` and
        # records the row as no-PDF), so the nearest live one is an
        # interrupt or a `sqlite3` error from the write itself. The
        # `finally` is not conditional on which: it is what makes the
        # batching acceptable at all, and dropping it would trade a
        # measured win for the guarantee docs/DESIGN.md rests on.
        con.commit()
    return to_parse


def _report_stale(
    con, references, remove_stale
) -> tuple[list[tuple[str, str | None]], list[tuple[str, str | None]], bool]:
    """Prune or report ledger rows the bib file no longer has.

    Returns (pruned, stale, suspicious). Only the ledger row is ever
    removed -- see prune_missing's own docstring for why the
    corresponding content/parsed/<citekey>.txt is deliberately left in
    place. Deletion only happens with --remove-stale (default off): a
    bib file that comes back short a citekey is far more often a mistake
    (a botched re-export, BIB_FILE pointing at the wrong path) than an
    intentional removal, so the default is to report it and let a human
    confirm rather than delete on every routine sync.
    """
    pruned: list[tuple[str, str | None]] = []
    stale: list[tuple[str, str | None]] = []
    suspicious = False
    seen_citekeys = {r.citekey for r in references}
    if remove_stale:
        pruned = ledger.prune_missing(con, seen_citekeys)
        for citekey, _parsed_path in pruned:
            print(f"  pruned  {citekey} (no longer in {config.BIB_FILE_PATH.name})")
        return pruned, stale, suspicious

    stale = ledger.find_stale(con, seen_citekeys)
    suspicious = not seen_citekeys and bool(stale)
    if suspicious:
        # Same shape prune_missing's guard refuses on -- don't
        # tell the user to run a command that's just going to
        # raise. references came back completely empty against a
        # non-empty ledger, so this is far more likely a botched
        # re-export or BIB_FILE pointing at the wrong path than
        # every citekey being legitimately removed at once.
        print(
            f"  SUSPICIOUS: the bib file yielded 0 references, so all "
            f"{len(stale)} ledger item(s) show as stale. This usually "
            f"means the bib file is empty, corrupted, or BIB_FILE is "
            f"misconfigured -- not that every citekey was actually "
            f"removed. Fix the export/path and re-run sync rather than "
            f"passing --remove-stale (which would refuse and raise on "
            f"this exact shape)."
        )
    else:
        # The "pass --remove-stale" instruction is printed once,
        # in the summary line below, rather than repeated on every
        # item here -- a bib file truncated from 200 entries to 3
        # survivors would otherwise print that instruction 197
        # times, which reads as routine per-item noise rather than
        # the "review this list before deleting" signal it's
        # meant to be.
        for citekey, _parsed_path in stale:
            print(f"  stale   {citekey} (no longer in {config.BIB_FILE_PATH.name})")
    return pruned, stale, suspicious
