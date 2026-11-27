"""Read-only ledger inspection: `python -m chitragupta.corpus ledger`.

Split from `chitragupta/ledger.py` (#441). Not a `sync --inspect` flag:
`sync` holds the write lock (an inspect would exit 2 mid-run) and needs
bibtexparser, while this takes no lock and runs under bare python3.
No argument is a filesystem path, so no content confinement is needed.
"""

import sqlite3
import sys

from chitragupta import bib_collections, collection_filter, config, ledger, ledger_tables
from chitragupta.progname import prog_for

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

    from chitragupta.help_format import ClickParser

    parser = ClickParser(
        prog=f"{prog_for('corpus')} ledger",
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

    # Read-only, not ledger.connect(), which migrates and takes the write
    # lock: inspecting must not interfere with a running sync.
    # No ledger, or one needing a sync, exits 0 with the instruction: a
    # stage, not a fault, and the session-start hook reads non-zero as
    # "will not start". An unreadable ledger is a fault: exit 3 (#1066).
    try:
        con = ledger.read_connection()
    except ledger.UnreadableLedger as exc:
        print(exc, file=sys.stderr)
        return ledger.EXIT_UNREADABLE
    except ledger.NoLedger as exc:
        print(exc)
        return 0
    # Columns by name, so adding one cannot shift the output.
    con.row_factory = sqlite3.Row
    try:
        return _show(con, args)
    except sqlite3.Error as exc:
        # A damaged page the first read missed (#1066): same refusal.
        print(ledger.UnreadableLedger(config.LEDGER_PATH, exc), file=sys.stderr)
        return ledger.EXIT_UNREADABLE
    finally:
        con.close()


def _show(con, args) -> int:
    """The one view `args` asks for."""
    if args.collections:
        return _list_collections(con)
    if args.citekey:
        return _show_item(con, args.citekey)
    if args.status or args.list or args.collection:
        return _list_items(con, args.status, args.collection)
    return _show_summary(con)


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

    The collection filter runs in Python: values resolve through the name
    table and match a subtree. Naming none or several exits 2.
    """
    rows = con.execute(
        "SELECT * FROM items WHERE (? IS NULL OR status = ?) ORDER BY citekey",
        (status, status),
    ).fetchall()
    if collection is not None:
        try:
            collection = collection_filter.slug_for(con, collection)
        except (bib_collections.UnknownCollection, bib_collections.AmbiguousCollection) as exc:
            print("\n".join(collection_filter.refusal(exc)), file=sys.stderr)
            return collection_filter.REFUSED
        members = collection_filter.members(con, rows, collection)
        rows = [r for r in rows if r["citekey"] in members]
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
    for line in bib_collections.report(rows, ledger_tables.collection_names(con)):
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
        # Predates failure_kind; read-only, so sync migrates it.
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
