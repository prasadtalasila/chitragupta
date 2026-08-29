"""Read-only ledger inspection: `python -m chitragupta.corpus ledger`.

Split from `chitragupta/ledger.py` (#441): the library crossed the
250-code-line limit docs/CODE-STANDARDS.md sets, and this CLI was
already its own architectural seam there -- reached only through
`ledger.failure_counts`/`ledger.all_items`/public reads, never through
`ledger._migrate`/`ledger.upsert_reference`.

Its own entrypoint rather than a `sync --inspect` flag, for two reasons
that are both about what a *reader* needs. `sync` takes the pipeline
write lock, so an inspect flag on it would exit 2 exactly when you most
want to look -- during a run; this takes no lock at all, which is the
property `chitragupta/runlock.py`'s separate lock file exists to
preserve. And `sync` needs bibtexparser, while reading the ledger needs
only sqlite3, so this runs under the bare system interpreter like
`citation_gate` and `references` do.

No `config.require_inside_content` call here, unlike those two: its
arguments below are `--list` (a flag), `--status` (a status name) and
`--citekey` (a citekey looked up in the DB) -- none is a filesystem path,
so the tier-1 confinement rule applies vacuously rather than needing a
check.
"""

import sqlite3

from chitragupta import bib_collections, config, ledger

_STATUS_LABELS = {
    "parsed": "parsed",
    "no_pdf": "no PDF attachment",
    "discovered": "found, not yet parsed",
    "parse_failed": "failed",
}


def _print_item(row) -> None:
    print(f"  {row['citekey']}")
    for field in (
        "status",
        "failure_kind",
        "item_type",
        "year",
        "doi",
        "pdf_path",
        "parsed_path",
        "parse_error",
        "last_synced",
    ):
        value = row[field] if field in row.keys() else None
        if value:
            print(f"      {field:<13} {value}")


def main(argv: "list[str] | None" = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.corpus ledger",
        description="Show what the corpus layer holds. Read-only, takes no lock, "
        "and runs with the bare system python3.",
    )
    parser.add_argument("--list", action="store_true", help="List every item")
    parser.add_argument(
        "--status", help=f"List only items with this status ({', '.join(_STATUS_LABELS)})"
    )
    parser.add_argument("--citekey", help="Show one item in full")
    parser.add_argument(
        "--collection",
        metavar="NAME",
        help="List only items in this Zotero collection, or one beneath it (docs/ZOTERO.md)",
    )
    parser.add_argument(
        "--collections",
        action="store_true",
        help="List every collection the corpus holds, and stop",
    )
    args = parser.parse_args(argv)

    if not config.LEDGER_PATH.exists():
        print(f"No ledger at {config.LEDGER_PATH}.")
        print("Run `python -m chitragupta.corpus sync` to build it from your bib file.")
        return 0

    # Opened read-only, NOT via ledger.connect(): connect() runs the schema and
    # migrations and commits, which takes a write lock and can bump
    # PRAGMA user_version. That would contradict this command's whole
    # reason for existing -- inspecting without interfering, including
    # while a sync is mid-run.
    con = sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=0)
    # connect() leaves rows as tuples; this CLI addresses columns by name
    # so that adding one doesn't silently shift the output.
    con.row_factory = sqlite3.Row
    try:
        if args.collections:
            return _list_collections(con)
        if args.citekey:
            return _show_item(con, args.citekey)
        if args.status or args.list or args.collection:
            return _list_items(con, args.status, args.collection)
        return _show_summary(con)
    finally:
        con.close()


def _show_item(con, citekey) -> int:
    """`--citekey`: one item in full, or exit 1 for a key the ledger lacks."""
    row = con.execute("SELECT * FROM items WHERE citekey = ?", (citekey,)).fetchone()
    if row is None:
        print(f"{citekey} is not in the ledger.")
        return 1
    _print_item(row)
    return 0


def _list_items(con, status, collection=None) -> int:
    """`--list`/`--status`/`--collection`: matching items, then the count.

    The collection filter is applied in Python rather than in SQL because
    matching is hierarchical -- `Modelling` selects `Modelling >
    Continuous` too -- and expressing that as a LIKE would have to
    reproduce bib_collections' normalisation in a second place.
    """
    rows = con.execute(
        "SELECT * FROM items WHERE (? IS NULL OR status = ?) ORDER BY citekey",
        (status, status),
    ).fetchall()
    if collection is not None:
        rows = [r for r in rows if bib_collections.matches(bib_collections.of_row(r), collection)]
    if not rows:
        print(
            f"No items with status {status!r}."
            if collection is None
            else f"No items in collection {collection!r}."
        )
    else:
        for row in rows:
            _print_item(row)
        print(f"\n  {len(rows)} item(s).")
    return 0


def _list_collections(con) -> int:
    """`--collections`: what a `--collection` filter can be given."""
    rows = con.execute("SELECT citekey, collections FROM items").fetchall()
    for line in bib_collections.report(rows):
        print(line)
    return 0


def _show_summary(con) -> int:
    """The no-flag default: per-status counts, then what needs attention."""
    counts = dict(con.execute("SELECT status, count(*) FROM items GROUP BY status"))
    total = sum(counts.values())
    if not total:
        print(f"Ledger at {config.LEDGER_PATH} is empty.")
        print("Run `python -m chitragupta.corpus sync` to populate it from your bib file.")
    else:
        _print_summary_counts(con, counts, total)
    return 0


def _print_summary_counts(con, counts, total) -> None:
    print(f"Ledger: {config.LEDGER_PATH}   ({total} item(s) from {config.BIB_FILE_PATH.name})\n")
    for status, label in _STATUS_LABELS.items():
        if counts.get(status):
            print(f"  {counts[status]:>4}  {label}")

    try:
        kinds = ledger.failure_counts(con)
    except sqlite3.OperationalError:
        # A ledger written before failure_kind existed. Read-only, so
        # it cannot be migrated here -- `python -m chitragupta.corpus sync` does that.
        kinds = {"deterministic": 0, "transient": 0}
    if kinds["deterministic"]:
        print(
            f"\n  {kinds['deterministic']} item(s) need attention -- not retried "
            "automatically.\n  Fix or remove the PDF, or re-run "
            "`python -m chitragupta.corpus sync --reparse`."
        )
        print("  See which: python -m chitragupta.corpus ledger --status parse_failed")
    elif kinds["transient"]:
        print(
            f"\n  {kinds['transient']} item(s) failed for a transient reason "
            "and will be retried on the next sync."
        )
    else:
        print("\n  Nothing needs attention.")
