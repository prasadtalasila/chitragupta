"""`--collection`, resolved once against the ledger and applied the same
way by every command that takes it.

A value naming no collection, or several, exits 2 rather than returning
nothing, which would read as "no such paper" after a typo or an old
`groups` path.
"""

from __future__ import annotations

import sqlite3
import sys

from chitragupta import bib_collections, ledger, ledger_tables

REFUSED = 2


def slug_for(con: sqlite3.Connection, collection: str) -> str:
    """The slug path `collection` names in this ledger, or a raise of
    `UnknownCollection` / `AmbiguousCollection`."""
    paths = [
        path
        for (value,) in con.execute("SELECT collections FROM items")
        for path in bib_collections.of_row({"collections": value})
    ]
    names = ledger_tables.collection_names(con)
    return bib_collections.resolve(collection, names, paths)


def members(con: sqlite3.Connection, items, collection: str | None) -> set[str] | None:
    """The citekeys of `items` in `collection` or beneath it; None for no
    filter. Raises as `slug_for` does."""
    if collection is None:
        return None
    slug = slug_for(con, collection)
    return {
        item["citekey"]
        for item in items
        if bib_collections.matches(bib_collections.of_row(item), slug)
    }


def refusal(exc: ValueError) -> list[str]:
    """What a command prints, to stderr, for a value `resolve` refused."""
    if isinstance(exc, bib_collections.AmbiguousCollection):
        return [f"{exc.wanted!r} names {len(exc.slugs)} collections; pass one slug path:"] + [
            f"  {slug}" for slug in exc.slugs
        ]
    lines = [f"no collection {exc.wanted!r}; run `chitragupta corpus ledger --collections`"]
    if getattr(exc, "old_syntax", False):
        lines.append(
            "collection paths are now slug paths (digital-twin.dt-platforms) or display "
            "paths with '/' (\"Digital Twin/DT Platforms\")"
        )
    return lines


def resolve_args(args) -> bool:
    """Replace `args.collection` with its slug path, in place; False, with
    the refusal printed, when it names none or several. Resolved before
    the search so `--log` records the slug actually used.
    """
    collection = getattr(args, "collection", None)
    if collection is None:
        return True
    try:
        with ledger.reading() as con:
            args.collection = slug_for(con, collection)
    except (bib_collections.UnknownCollection, bib_collections.AmbiguousCollection) as exc:
        print("\n".join(refusal(exc)), file=sys.stderr)
        return False
    return True
