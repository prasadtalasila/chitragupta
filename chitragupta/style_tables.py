"""The `python -m chitragupta.draft style` findings about tables.

Beside `chitragupta/style_acronym_drift.py`, the other finding in that
command computed in plain Python rather than by Vale -- and for the same
kind of reason. Vale matches patterns inside prose; the questions here
are about a table's *relationship* to the prose around it, which is not
a pattern:

- a table with no caption renders with no number, in every format
  (docs/WRITING-STANDARDS.md §13),
- a table no sentence refers to is one the reader has to interpret
  unaided, which is the second half of issue 395.

**Decidable, and only that.** That a sentence points at a table is
checkable; that it *explains* the table is not, and nothing here
pretends otherwise -- §9's decidable/not-decidable table records which
half is which, and the genre skills carry the other half.

**A `.tex` fragment is out of scope**, deliberately rather than by
omission. `thesis-chapter-writer` writes a real `\\begin{table}` with its
own `\\caption` and `\\label`, numbered by the thesis that `\\input`s it,
so the marker vocabulary this checks for does not exist there -- §13's
carve-out.

The marker syntax itself is not restated here: it lives in
`chitragupta/render_output/_tables.py`, which is what resolves it at
render time, and a second copy of those patterns is exactly the drift
docs/CODE-STANDARDS.md's "one place a fact is written" rules out.
"""

import re
from pathlib import Path

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

# A pipe table's first two lines: a row, then the separator that makes it
# a table rather than a line with pipes in it. Only the pair is matched,
# because the header row alone is what a finding points at.
_TABLE_HEAD_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*\n[ \t]*\|[ \t:|-]+\|[ \t]*$", re.MULTILINE)

# A caption line with nothing claimed to follow it. Used only to tell
# "no caption at all" from "a caption nobody can refer to".
_CAPTION_RE = re.compile(r"^[ \t]*:[ \t]*\S.*$", re.MULTILINE)

# A Markdown heading, only to bound a section. `review/_blocks.HEADING`
# already spells this, and is deliberately not imported: the review layer
# sits above this one in docs/ARCHITECTURE.md, so a drafting-layer check
# reaching into it would be a new dependency in the wrong direction for
# one three-token pattern.
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S.*$", re.MULTILINE)

# The id shape a `\\label{tab:<id>}` can carry without further escaping,
# and the one the figure markers already use for a base name.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _finding(rule: str, match: str, line: int, message: str) -> dict:
    """One finding in the shape `style_check.collapse()` produces from
    Vale's own, so `style_report.py` never has to know which check wrote
    which line."""
    return {
        "rule": RULES[rule],
        "match": match,
        "line": line,
        "message": message,
        "severity": "suggestion",
        "count": 1,
    }


def _section_starts(text: str) -> "list[int]":
    """The 1-based line of every heading, so a line can be placed in one.

    A draft with no headings has exactly one section, which is why the
    list may be empty and `_section_of` returns 0 for that case rather
    than failing.
    """
    return [_tables.line_of(text, m.start()) for m in _HEADING_RE.finditer(text)]


def _section_of(line: int, starts: "list[int]") -> int:
    """Which section `line` falls in, as an index into `starts`."""
    return sum(1 for start in starts if start <= line)


def _uncaptioned(text: str, tables: "list[_tables.Table]") -> "list[dict]":
    """A pipe table with no declared table attached to it.

    Reported as `no-id` where a caption *is* present, because "add a
    caption" is the wrong instruction for someone who wrote one and
    stopped -- the marker is what they left out.
    """
    declared = {table.line for table in tables}
    captions = {_tables.line_of(text, m.start()) for m in _CAPTION_RE.finditer(text)}
    heads = [_tables.line_of(text, m.start()) for m in _TABLE_HEAD_RE.finditer(text)]
    found = []
    for index, line in enumerate(heads):
        # Bounded by the next table, or a bare table would count the
        # caption belonging to the captioned table three paragraphs below
        # it and report nothing at all.
        next_head = heads[index + 1] if index + 1 < len(heads) else len(text.splitlines()) + 1
        following = {c for c in captions if line < c < next_head}
        if following & declared:
            continue
        if following:
            found.append(
                _finding(
                    "no-id",
                    text.splitlines()[line - 1].strip(),
                    min(following),
                    "this table's caption carries no `<!-- table: <id> -->` "
                    "marker under it, so no sentence can refer to it "
                    "(WRITING-STANDARDS.md §13).",
                )
            )
        else:
            found.append(
                _finding(
                    "no-caption",
                    text.splitlines()[line - 1].strip(),
                    line,
                    "this table has no caption line, so it renders with no "
                    "number in every format (WRITING-STANDARDS.md §13).",
                )
            )
    return found


def _id_problems(tables: "list[_tables.Table]") -> "list[dict]":
    """Ids that collide or that a `\\label{}` cannot carry."""
    ids = [table.id for table in tables]
    found = [
        _finding(
            "duplicate-id",
            table.id,
            table.line,
            f"`{table.id}` is claimed by more than one table. Both become "
            "`\\label{}`s in one LaTeX document, where a duplicate resolves "
            "silently to the wrong table.",
        )
        for table in tables
        if ids.count(table.id) > 1
    ]
    found += [
        _finding(
            "malformed-id",
            table.id,
            table.line,
            f"`{table.id}` is not a kebab-case id (lowercase, digits and "
            "hyphens), which is what `\\label{tab:<id>}` can carry unescaped.",
        )
        for table in tables
        if not _ID_RE.match(table.id)
    ]
    return found


def _reference_problems(text: str, tables: "list[_tables.Table]") -> "list[dict]":
    """A table nobody reads from, and a reference to a table that is not
    there.

    The second is also reported by the renderer at render time. It is
    repeated here deliberately: every genre skill runs `draft style`
    before it renders, so this is where the author is still writing.
    """
    starts = _section_starts(text)
    refs = _tables.references(text)
    ids = {table.id for table in tables}
    found = []
    for table in tables:
        lines = [line for ref_id, line in refs if ref_id == table.id]
        if not lines:
            found.append(
                _finding(
                    "unreferenced",
                    table.id,
                    table.line,
                    f"no sentence refers to `{table.id}`. A table the prose "
                    "never reads is one the reader has to explain to "
                    "themselves (WRITING-STANDARDS.md §13).",
                )
            )
        elif all(_section_of(line, starts) != _section_of(table.line, starts) for line in lines):
            found.append(
                _finding(
                    "ref-outside-section",
                    table.id,
                    table.line,
                    f"`{table.id}` is referred to, but only from another "
                    "section. The sentence that introduces a table belongs "
                    "beside it.",
                )
            )
    found += [
        _finding(
            "unknown-ref",
            ref_id,
            line,
            f"`{ref_id}` is referred to but no table declares it, so the "
            "marker survives into the rendered document.",
        )
        for ref_id, line in refs
        if ref_id not in ids
    ]
    return found


def findings(draft: Path) -> "list[dict]":
    """Every table finding for `draft`, ordered by where it is."""
    # `render`'s own answer to "is this a Markdown draft?", not a second
    # one: the carve-out below has to be the same set of suffixes the
    # renderer takes its Markdown path for, or a draft could be checked
    # under one contract and rendered under the other.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return []
    text = draft.read_text(encoding="utf-8")
    tables = _tables.tables(text)
    found = _uncaptioned(text, tables) + _id_problems(tables) + _reference_problems(text, tables)
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
