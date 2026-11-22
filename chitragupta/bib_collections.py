"""Collection membership: slug paths, their names, and how they match.

A reference manager's collections are a judgement its owner has already
made -- "these are the modelling papers" -- and #195 asked for it back,
to scope a draft's retrieval to the shelf someone curated for it rather
than to the whole library.

**Where they come from.** chitragupta-importer reads the reference
manager's own storage and writes two things into `bibliography.bib`:

- each entry's `cg-collections` field, the slug path of every collection
  the item is directly in (`digital-twin.dt-platforms, a.b`); ancestors
  are implied, so an item in `a.b.c` is in `a` and `a.b`;
- one `@comment{cg-collections v1 ...}` table mapping each slug path to
  the collection's own name (read by `chitragupta/bib_comments.py`).

A bib written any other way carries no collections, and every command
behaves as it does without them: an absent field is not an error.

**Why slugs.** A slug segment is lower-case `[a-z0-9-]`, frozen by the
importer per collection id, so a collection renamed in the reference
manager keeps its slug and a `scope.md` that recorded it keeps working.
Two siblings with the same name get distinct slugs (`medical`,
`medical-1`), so they can never be mixed. Slugs need no escaping and no
shell quoting; names, which may hold `/`, `>` or `,`, are never split.

**Matching is subtree, per segment.** Asking for `a.b` selects `a.b` and
`a.b.c`, because a parent collection contains its children, but not
`a.bc`. A user may also name a collection by its display path, the names
from the root joined with `/`; `resolve` turns either form into one slug
path or refuses, so a typo or an old `groups` path fails loudly instead
of silently matching nothing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable

ITEM_SEPARATOR = ","
SEGMENT_SEPARATOR = "."
DISPLAY_JOINER = " / "
TABLE_NAME = "cg-collections"

_SEGMENT = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_SLUG_PATH = re.compile(rf"{_SEGMENT}(?:\.{_SEGMENT})*")


class UnknownCollection(ValueError):
    """`resolve` found no collection by that slug path or display path."""

    def __init__(self, wanted: str) -> None:
        self.wanted = wanted
        # `>` was the old `groups` nesting separator; a value holding one
        # is almost certainly a scope recorded before slug paths.
        self.old_syntax = ">" in wanted
        super().__init__(f"no collection {wanted!r}")


class AmbiguousCollection(ValueError):
    """`resolve` found several collections with that display path."""

    def __init__(self, wanted: str, slugs: list[str]) -> None:
        self.wanted = wanted
        self.slugs = slugs
        super().__init__(f"{wanted!r} names {len(slugs)} collections")


def is_slug_path(value: str) -> bool:
    """Whether `value` is a well-formed slug path."""
    return bool(_SLUG_PATH.fullmatch(value))


def parse(value: str | None) -> tuple[str, ...]:
    """The slug paths in one entry's `cg-collections` value.

    A malformed path is dropped, not repaired. Order is preserved and
    duplicates are dropped, so a re-export writes the same JSON for an
    unchanged entry and the ledger does not churn.
    """
    if not value:
        return ()
    paths: list[str] = []
    for raw in value.split(ITEM_SEPARATOR):
        path = raw.strip()
        if is_slug_path(path) and path not in paths:
            paths.append(path)
    return tuple(paths)


def _with_ancestors(path: str) -> list[str]:
    segments = path.split(SEGMENT_SEPARATOR)
    return [SEGMENT_SEPARATOR.join(segments[:depth]) for depth in range(1, len(segments) + 1)]


def display_paths(names: dict[str, str], paths: Iterable[str]) -> dict[str, str]:
    """Every known slug path, ancestors included, mapped to its display path.

    Known means named in the table or used by an entry. A level the
    table has no row for shows its own slug segment.
    """
    known = {a for path in [*names, *paths] for a in _with_ancestors(path)}
    return {
        path: DISPLAY_JOINER.join(
            names.get(prefix, prefix.rsplit(SEGMENT_SEPARATOR, 1)[-1])
            for prefix in _with_ancestors(path)
        )
        for path in sorted(known)
    }


def matches(collections: "tuple[str, ...] | list[str]", wanted: str) -> bool:
    """Whether any of `collections` is the slug path `wanted` or beneath it."""
    if not wanted:
        return False
    prefix = wanted + SEGMENT_SEPARATOR
    return any(path == wanted or path.startswith(prefix) for path in collections)


def _normalised_display(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    return re.sub(r" ?/ ?", "/", collapsed).casefold()


def resolve(wanted: str, names: dict[str, str], paths: Iterable[str]) -> str:
    """The one slug path `wanted` names, as a slug path or a display path.

    A slug path is tried first. A display path is compared whole against
    every rebuilt display path (case, and spacing around `/`, ignored),
    never split, so a name holding `/` still resolves. Raises
    `AmbiguousCollection` when it fits several and `UnknownCollection`
    when it fits none.
    """
    shown = display_paths(names, paths)
    slug = wanted.strip().casefold()
    if slug in shown:
        return slug
    target = _normalised_display(wanted)
    hits = [path for path, display in shown.items() if _normalised_display(display) == target]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise AmbiguousCollection(wanted, hits)
    raise UnknownCollection(wanted)


def of_row(row) -> tuple[str, ...]:
    """One row's collection paths, for a row from any schema version.

    Reads NULL, an absent column, malformed JSON, and a row fetched
    without `sqlite3.Row` alike as "none recorded". A ledger is not a
    place to raise from: a row written by a future version, hand-edited,
    or fetched by a caller that left the default tuple row factory in
    place should narrow a filter rather than stop a search.
    """
    try:
        value = row["collections"]
    except (IndexError, KeyError, TypeError):
        return ()
    try:
        loaded = json.loads(value) if value else []
    except (TypeError, ValueError):
        return ()
    return tuple(str(p) for p in loaded) if isinstance(loaded, list) else ()


def report(rows, names: dict[str, str]) -> list[str]:
    """The `--collections` listing: slug path, display path, paper count.

    A count includes the papers in every collection beneath it, and a
    named collection holding no papers is listed with 0, so the listing
    is the whole tree a `--collection` filter can be given.
    """
    by_citekey = [of_row(row) for row in rows]
    shown = display_paths(names, [path for paths in by_citekey for path in paths])
    if not shown:
        return [
            "No collections recorded.",
            "Collections come from the cg-collections field chitragupta-importer "
            "writes; see docs/ZOTERO.md.",
        ]
    slug_width = max(map(len, shown))
    display_width = max(map(len, shown.values()))
    lines = [
        f"  {path:<{slug_width}}  {display:<{display_width}}  "
        f"{sum(matches(paths, path) for paths in by_citekey)}"
        for path, display in shown.items()
    ]
    return lines + ["", f"  {len(shown)} collection(s)."]
