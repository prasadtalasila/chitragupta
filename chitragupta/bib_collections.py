"""Zotero collection labels: how they reach the ledger, and how they match.

Zotero organises a library into collections and subcollections, and a
paper's place in that tree is a judgement its owner has already made --
"these are the modelling papers" -- which this pipeline otherwise throws
away. #195 asked for it back, to scope a draft's retrieval to the subset
someone curated for it rather than to the whole library.

**Zotero's own BibTeX exporter drops collection membership entirely.**
There is nothing to parse unless the export came from
[Better BibTeX](https://retorque.re/zotero-better-bibtex/), whose
*Export -> Fields -> Export JabRef-specific fields* option writes
JabRef's `groups` field into every entry. docs/ZOTERO.md has the
click-path and the one cost worth knowing (it disables BBT's export
cache). A library exported without it parses to nothing here, and every
command behaves exactly as it did before -- an absent field is not an
error, because for most users it will simply be absent.

Two conventions come with that field, both JabRef's rather than ours:

- **Comma-separated** for an item in several collections.
- **`>` for nesting**, so a subcollection arrives as its path from the
  root, `Digital twins > Modelling`.

Whitespace around either separator is not reliable across exporters, so a
path is normalised on the way in -- segments stripped, rejoined with a
single ` > ` -- and matching is done on the normalised form. That is the
whole reason this is a module rather than a `split(",")` at each call
site: `parse` and `matches` have to agree about spacing, and there are
three call sites.

**Matching is prefix-by-segment, not substring.** Asking for `Modelling`
selects `Modelling` and `Modelling > Continuous`, because a parent
collection in Zotero visually contains its children and a user asking for
the parent means the subtree. It does not select `Modelling notes`, which
a `startswith` on the raw string would.
"""

from __future__ import annotations

import json

ITEM_SEPARATOR = ","
NESTING_SEPARATOR = ">"
_JOINED = f" {NESTING_SEPARATOR} "


def parse(value: str | None) -> tuple[str, ...]:
    """The collection paths in one entry's field value, normalised.

    Order is preserved and duplicates are dropped, so a re-export writes
    the same JSON for an unchanged entry and the ledger does not churn.
    """
    if not value:
        return ()
    paths = []
    for raw in value.split(ITEM_SEPARATOR):
        path = _normalise(raw)
        if path and path not in paths:
            paths.append(path)
    return tuple(paths)


def _normalise(raw: str) -> str:
    """One path with its segments stripped and rejoined predictably.

    An empty segment is dropped rather than preserved, so `A > > B` and a
    stray trailing `>` both normalise to something that still matches
    `A`; the alternative is a path no query could ever name.
    """
    segments = [seg.strip() for seg in raw.split(NESTING_SEPARATOR)]
    return _JOINED.join(seg for seg in segments if seg)


def matches(collections: "tuple[str, ...] | list[str]", wanted: str) -> bool:
    """Whether any of `collections` is `wanted` or sits beneath it.

    Case-insensitive, because a collection name is a label someone typed
    in a GUI and asking them to reproduce its capitalisation on a command
    line is a way to make a correct query return nothing.
    """
    target = _normalise(wanted).casefold()
    if not target:
        return False
    prefix = target + _JOINED.casefold()
    return any(
        path == target or path.startswith(prefix)
        for path in (c.casefold() for c in collections)
    )


def names(collections_by_citekey: "dict[str, tuple[str, ...]]") -> list[str]:
    """Every distinct collection path in the corpus, parents included.

    A path implies its ancestors -- an item in `A > B > C` is in `A` --
    but only the leaf path is stored, so listing what a user can filter on
    means expanding each path back out. Sorted, because this exists to be
    printed.
    """
    found = set()
    for paths in collections_by_citekey.values():
        for path in paths:
            segments = path.split(_JOINED)
            for depth in range(1, len(segments) + 1):
                found.add(_JOINED.join(segments[:depth]))
    return sorted(found)


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


def report(rows) -> list[str]:
    """The `--collections` listing, as printable lines.

    The empty case is guidance rather than a result: an empty list here
    almost always means the export lacked Better BibTeX's JabRef fields,
    not that the library has no collections.
    """
    paths = names({row["citekey"]: of_row(row) for row in rows})
    if not paths:
        return ["No collections recorded.",
                "Zotero's own BibTeX export drops them; see docs/ZOTERO.md for "
                "the Better BibTeX option that keeps them."]
    return [f"  {path}" for path in paths] + ["", f"  {len(paths)} collection(s)."]
