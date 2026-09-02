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

**Id validity and the reference checks are `chitragupta/style_elements.py`'s**,
shared with `style_figures.py` and, since issue 457, `style_equations.py`
-- three near-identical copies of that logic is the "needless repetition"
line docs/CODE-STANDARDS.md draws. What stays here is what is genuinely
table-specific: telling a bare pipe table from a captioned one.
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

# A pipe table's first two lines: a row, then the separator that makes it
# a table rather than a line with pipes in it. Only the pair is matched,
# because the header row alone is what a finding points at.
_TABLE_HEAD_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*\n[ \t]*\|[ \t:|-]+\|[ \t]*$", re.MULTILINE)

# A caption line with nothing claimed to follow it. Used only to tell
# "no caption at all" from "a caption nobody can refer to".
_CAPTION_RE = re.compile(r"^[ \t]*:[ \t]*\S.*$", re.MULTILINE)


def _finding(rule: str, match: str, line: int, message: str) -> dict:
    """One finding in the shape `style_check.collapse()` produces from
    Vale's own -- a thin `RULES`-bound wrapper over the shared
    `style_elements.finding`, kept so the calls below read the same as
    they did before that module existed."""
    return style_elements.finding(RULES, rule, match, line, message)


def _uncaptioned(text: str, tables: "list[_tables.Table]") -> "list[dict]":
    """A pipe table with no declared table attached to it.

    Reported as `no-id` where a caption *is* present, because "add a
    caption" is the wrong instruction for someone who wrote one and
    stopped -- the marker is what they left out.
    """
    declared = {table.line for table in tables}
    captions = {_tables.line_of(text, m.start()) for m in _CAPTION_RE.finditer(text)}
    heads = [_tables.line_of(text, m.start()) for m in _TABLE_HEAD_RE.finditer(text)]
    # Split once, not per table (#511/m-77). Both uses below were
    # `text.splitlines()` inside the loop, so the cost was O(document) per
    # table -- on the 178k-word book this module was tuned against, that
    # is the whole document re-split for every table in it.
    lines = text.splitlines()
    found = []
    for index, line in enumerate(heads):
        # Bounded by the next table, or a bare table would count the
        # caption belonging to the captioned table three paragraphs below
        # it and report nothing at all.
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
                    "(WRITING-STANDARDS.md §13).",
                )
            )
        else:
            found.append(
                _finding(
                    "no-caption",
                    lines[line - 1].strip(),
                    line,
                    "this table has no caption line, so it renders with no "
                    "number in every format (WRITING-STANDARDS.md §13).",
                )
            )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every table finding for `draft`, ordered by where it is."""
    # `render`'s own answer to "is this a Markdown draft?", not a second
    # one: the carve-out below has to be the same set of suffixes the
    # renderer takes its Markdown path for, or a draft could be checked
    # under one contract and rendered under the other.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return []
    # Fenced code blanked first, the same call `review/_claims.py` makes
    # for the same reason: a tutorial showing a pipe table *as an
    # example* -- including one demonstrating this section's own markup --
    # would otherwise be reported as a real table with no caption. That
    # is a false finding per example, on a report whose usefulness is
    # entirely a question of noise. It blanks in place, character for
    # character, so every line number below still points where it says.
    text = citation_gate._blank_code(draft.read_text(encoding="utf-8"))
    tables = _tables.tables(text)
    found = (
        _uncaptioned(text, tables)
        + style_elements.id_problems(RULES, tables, "table", "tab")
        + style_elements.reference_problems(
            RULES, text, tables, _tables.references(text), "table", "WRITING-STANDARDS.md §13"
        )
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
