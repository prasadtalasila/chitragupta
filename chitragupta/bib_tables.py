"""What chitragupta-importer writes into a bib besides the entries.

The importer's two `@comment` tables (via `bib_comments`) and notices
for a bib or config still set up for the `groups` field 7.0.0 stopped
reading (plans/1211-cg-collections-and-renames.md). Warnings are
printed here, during sync, so each problem is named once per run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from chitragupta import bib_collections, bib_comments, config
from chitragupta.citekey_safety import citekey_problem


@dataclass
class Tables:
    """The two tables, plus `{table: version}` for any version not known."""

    collection_names: dict[str, str] = field(default_factory=dict)
    declared_renames: dict[str, str] = field(default_factory=dict)
    unknown: dict[str, str] = field(default_factory=dict)

    def problems(self) -> dict[str, int]:
        """An unknown table version as a bib-integrity problem, so sync
        exits EXIT_BIB_INTEGRITY: its rows were read, but a column may now
        mean something this code does not know."""
        return {
            f"{name} table {version or '(no version)'} (this chitragupta reads "
            f"{bib_comments.KNOWN_VERSION})": 1
            for name, version in self.unknown.items()
        }


COLLECTIONS_FIELD = "cg-collections"
RENAMES_TABLE = "cg-renames"
# What a Better BibTeX export with JabRef fields wrote collections into,
# read until 7.0.0. Only looked for so sync can say it is no longer read.
LEGACY_GROUPS_FIELD = "groups"


def _is_citekey(value: str) -> bool:
    return citekey_problem(value) is None


def _table(blocks, name, bib_name, unknown, valid_key, valid_value=None) -> dict[str, str]:
    """One importer table as a dict, warning about what it could not use."""
    table = bib_comments.read_tables(blocks, name, valid_key)
    if table is None:
        return {}
    if table.version != bib_comments.KNOWN_VERSION:
        unknown[name] = table.version
        print(
            f"  WARNING: {bib_name} has a {name} {table.version or '(no version)'} "
            f"table; this chitragupta reads {bib_comments.KNOWN_VERSION}. Read the "
            "first two fields of each row; upgrade chitragupta to read the rest."
        )
    rows = dict(table.rows)
    if valid_value is not None:
        rows = {key: value for key, value in table.rows if valid_value(value)}
    skipped = [*table.skipped, *(f"{k}\t{v}" for k, v in table.rows if k not in rows)]
    if skipped:
        print(
            f"  WARNING: {len(skipped)} row(s) of the {name} table skipped "
            f"(not a valid key): {skipped[0]!r}"
        )
    return rows


def _warn_legacy_collections(entries, bib_name) -> None:
    """Say once that `groups` and `collections_field` are no longer read."""
    if config.LEGACY_COLLECTIONS_FIELD:
        print(
            "  config: [bib] collections_field is no longer read (collections now "
            "come from cg-collections); remove it from config.toml"
        )
    has_groups = any(e.get(LEGACY_GROUPS_FIELD) for e in entries)
    if has_groups and not any(e.get(COLLECTIONS_FIELD) for e in entries):
        print(
            f"  WARNING: {bib_name} has `groups` fields but no `cg-collections`: "
            "chitragupta no longer reads `groups`, so no paper is in a collection. "
            "Collections now come from chitragupta-importer (docs/ZOTERO.md)."
        )


def collections(entry: dict) -> tuple[str, ...]:
    """One entry's slug paths, from its `cg-collections` field."""
    return bib_collections.parse(entry.get(COLLECTIONS_FIELD))


def read(raw_text: str, entries: list[dict], bib_name: str) -> Tables:
    """Both importer tables from the raw bib text, with every warning."""
    _warn_legacy_collections(entries, bib_name)
    blocks = bib_comments.comment_blocks(raw_text)
    unknown: dict[str, str] = {}
    names = _table(
        blocks, bib_collections.TABLE_NAME, bib_name, unknown, bib_collections.is_slug_path
    )
    renames = _table(blocks, RENAMES_TABLE, bib_name, unknown, _is_citekey, _is_citekey)
    return Tables(names, renames, unknown)
