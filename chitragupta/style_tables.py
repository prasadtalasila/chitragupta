"""The `python -m chitragupta.draft style` findings about tables.

Plain Python, since a table's relationship to the prose is not a Vale
pattern: a table with no caption renders unnumbered (WRITING-STANDARDS.md
§13), and one no sentence refers to is left to the reader (issue 395).
Only decidable checks: that a sentence explains a table is not.

A `.tex` fragment is out of scope (§13's carve-out): it carries a real
`\\begin{table}`. The marker syntax lives only in `render_output/_tables.py`,
and id and reference checks are `style_elements.py`'s.
"""

import re
from pathlib import Path

from chitragupta import citation_gate, style_elements
from chitragupta.render_output import _paths, _tables

RULES = {
    "no-caption": "chitragupta.TableNoCaption",
    "no-id": "chitragupta.TableNoId",
    "duplicate-id": "chitragupta.TableDuplicateId",
    "malformed-id": "chitragupta.TableMalformedId",
    "unreferenced": "chitragupta.TableUnreferenced",
    "unknown-ref": "chitragupta.TableUnknownRef",
    "ref-outside-section": "chitragupta.TableRefOutsideSection",
}

# A pipe table's row plus separator; the header row is what a finding
# points at.
_TABLE_HEAD_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*\n[ \t]*\|[ \t:|-]+\|[ \t]*$", re.MULTILINE)

# Used only to tell "no caption" from "a caption nobody can refer to".
_CAPTION_RE = re.compile(r"^[ \t]*:[ \t]*\S.*$", re.MULTILINE)


def _finding(rule: str, match: str, line: int, message: str) -> dict:
    """One finding in `style_check.collapse()`'s shape, bound to `RULES`."""
    return style_elements.finding(RULES, rule, match, line, message)


def _uncaptioned(text: str, tables: "list[_tables.Table]") -> "list[dict]":
    """A pipe table with no declared table attached to it.

    `no-id` where a caption is present: "add a caption" is the wrong
    instruction for someone who wrote one and left out the marker.
    """
    declared = {table.line for table in tables}
    captions = {_tables.line_of(text, m.start()) for m in _CAPTION_RE.finditer(text)}
    heads = [_tables.line_of(text, m.start()) for m in _TABLE_HEAD_RE.finditer(text)]
    # Split once, not per table (#511/m-77): O(document) per table on a
    # 178k-word book.
    lines = text.splitlines()
    found = []
    for index, line in enumerate(heads):
        # Bounded by the next table, or a bare table would claim a later
        # table's caption.
        next_head = heads[index + 1] if index + 1 < len(heads) else len(lines) + 1
        following = {c for c in captions if line < c < next_head}
        if following & declared:
            continue
        if following:
            found.append(
                _finding(
                    "no-id",
                    lines[line - 1].strip(),
                    min(following),
                    "this table's caption carries no `<!-- table: <id> -->` "
                    "marker under it, so no sentence can refer to it "
                    "(docs/writing-standards/tables.md §13).",
                )
            )
        else:
            found.append(
                _finding(
                    "no-caption",
                    lines[line - 1].strip(),
                    line,
                    "this table has no caption line, so it renders with no "
                    "number in every format (docs/writing-standards/tables.md §13).",
                )
            )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every table finding for `draft`, ordered by where it is."""
    # `render`'s own Markdown test, so a draft is checked and rendered
    # under the same contract.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return []
    # Fenced code blanked in place, so a tutorial's example table is not
    # reported and line numbers stay true.
    text = citation_gate._blank_code(draft.read_text(encoding="utf-8"))
    tables = _tables.tables(text)
    found = (
        _uncaptioned(text, tables)
        + style_elements.id_problems(RULES, tables, "table", "tab")
        + style_elements.reference_problems(
            RULES,
            text,
            tables,
            _tables.references(text),
            "table",
            "docs/writing-standards/tables.md §13",
        )
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
