"""The `@comment` tab tables chitragupta-importer writes into a bib.

The importer puts small lookup tables at the top of `bibliography.bib`,
each an `@comment{<name> v<N>` block of tab-separated rows. Two exist:
`cg-collections` (slug path, the collection's own name; read by
`chitragupta/bib_collections.py`) and `cg-renames` (old citekey, new
citekey; read by `chitragupta/sync_renames.py`). BibTeX and biber ignore
comments, so the bib stays valid for every other tool, and chitragupta
keeps reading one file.

**Read from the raw text, not from bibtexparser.** bibtexparser 1.x
expands the tabs inside a comment into spaces, and a tab is the only
separator these rows have. So `comment_blocks` scans the raw bib for
`@comment{...}` itself, matching braces and skipping the `\\{`/`\\}`
escapes the importer writes inside a name.

**Tolerant of a newer importer.** Each row's first two tab-separated
fields are read whatever the block's version; further fields are
ignored, and a row whose first field the caller rejects is skipped and
kept for the warning. The version is returned rather than enforced: a
caller flags one other than `KNOWN_VERSION` (`chitragupta/bib_reader.py`
makes it a bib-integrity problem) instead of throwing away data that is
very likely still right.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

KNOWN_VERSION = "v1"

_BLOCK_START = re.compile(r"@\s*comment\s*\{", re.IGNORECASE)


@dataclass(frozen=True)
class TabTable:
    """One named table, merged across every block carrying its name."""

    name: str
    version: str
    rows: tuple[tuple[str, str], ...]
    skipped: tuple[str, ...]


def comment_blocks(raw_text: str) -> list[str]:
    """The body of every `@comment{...}` in `raw_text`, tabs intact.

    An unterminated block is dropped: its end cannot be told from the
    entries after it.
    """
    blocks = []
    for start in _BLOCK_START.finditer(raw_text):
        end = _closing_brace(raw_text, start.end())
        if end is not None:
            blocks.append(raw_text[start.end() : end])
    return blocks


def _closing_brace(text: str, index: int) -> int | None:
    """Index of the brace closing the one just before `index`."""
    depth = 1
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _unescape(value: str) -> str:
    return value.replace("\\{", "{").replace("\\}", "}").strip()


def read_tables(blocks: list[str], name: str, valid_key: Callable[[str], bool]) -> TabTable | None:
    """The `name` table across `blocks`, or None when no block has it.

    Two blocks of the same name are merged and the first row for a key
    wins. The version reported is the first one other than
    `KNOWN_VERSION`, so a mixed file is still flagged.
    """
    versions, rows, skipped, seen = [], [], [], set()
    for block in blocks:
        header, _newline, body = block.partition("\n")
        words = header.split()
        if not words or words[0] != name:
            continue
        versions.append(words[1] if len(words) > 1 else "")
        for line in body.splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            key = fields[0].strip()
            if len(fields) < 2 or not valid_key(key):
                skipped.append(line)
            elif key not in seen:
                seen.add(key)
                rows.append((key, _unescape(fields[1])))
    if not versions:
        return None
    version = next((v for v in versions if v != KNOWN_VERSION), KNOWN_VERSION)
    return TabTable(name, version, tuple(rows), tuple(skipped))
