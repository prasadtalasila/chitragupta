"""Shared logic behind the table/figure/equation reference checks.

`chitragupta/style_tables.py` and `chitragupta/style_figures.py` used to
carry near-identical copies of id-validity, duplicate-id and
unreferenced/unknown-ref/ref-outside-section checking -- tolerated as
coincidence at two call sites. Issue 457's `chitragupta/style_equations.py`
makes a third, which is
[docs/CODE-STANDARDS.md](../docs/CODE-STANDARDS.md)'s stated line for
"needless repetition": two similar blocks are a coincidence, three are a
pattern. This module is the one place that logic is written now.

**What does not move here.** Each kind's own "is this declared at all"
detection -- a pipe-table/caption-line scan for a table, a
marker-then-caption pairing gap for a figure, a marker-then-fence pairing
gap for an equation -- stays in its own module. The three only look
alike; each reads a different marker shape, and forcing them into one
function would be the wrong abstraction. What genuinely is identical
across all three -- once an element is declared, is its id well-formed,
and does the prose read it -- lives here, parameterised by a `noun` (for
the sentence a finding prints) and a `prefix` (the `\\label{}` namespace
a malformed id would corrupt: `tab`, `fig`, `eq`).
"""

import re

from chitragupta.render_output._tables import line_of

# A Markdown heading, only to bound a section. Not `review/_blocks.HEADING`:
# the review layer sits above the drafting layer in docs/ARCHITECTURE.md,
# so a drafting-layer check reaching into it would be a dependency in the
# wrong direction for one three-token pattern -- the same reason
# `style_tables.py`/`style_figures.py` each kept their own copy before
# this module existed.
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S.*$", re.MULTILINE)

# The id shape a `\label{<prefix>:<id>}` can carry without further escaping.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def finding(rules: "dict[str, str]", rule: str, match: str, line: int, message: str) -> dict:
    """One finding in the shape `style_check.collapse()` produces from
    Vale's own, so `style_report.py` never has to know which check wrote
    which line."""
    return {
        "rule": rules[rule],
        "match": match,
        "line": line,
        "message": message,
        "severity": "suggestion",
        "count": 1,
    }


def section_starts(text: str) -> "list[int]":
    """The 1-based line of every heading, so a line can be placed in one.

    A draft with no headings has exactly one section, which is why the
    list may be empty and `section_of` returns 0 for that case rather
    than failing.
    """
    return [line_of(text, m.start()) for m in _HEADING_RE.finditer(text)]


def section_of(line: int, starts: "list[int]") -> int:
    """Which section `line` falls in, as an index into `starts`."""
    return sum(1 for start in starts if start <= line)


def id_problems(rules: "dict[str, str]", elements: list, noun: str, prefix: str) -> "list[dict]":
    """Ids that collide or that a `\\label{<prefix>:<id>}` cannot carry."""
    ids = [element.id for element in elements]
    found = [
        finding(
            rules,
            "duplicate-id",
            element.id,
            element.line,
            f"`{element.id}` is claimed by more than one {noun}. Both become "
            "`\\label{}`s in one LaTeX document, where a duplicate resolves "
            f"silently to the wrong {noun}.",
        )
        for element in elements
        if ids.count(element.id) > 1
    ]
    found += [
        finding(
            rules,
            "malformed-id",
            element.id,
            element.line,
            f"`{element.id}` is not a kebab-case id (lowercase, digits and "
            f"hyphens), which is what `\\label{{{prefix}:<id>}}` can carry unescaped.",
        )
        for element in elements
        if not _ID_RE.match(element.id)
    ]
    return found


def reference_problems(
    rules: "dict[str, str]",
    text: str,
    elements: list,
    references: "list[tuple[str, int]]",
    noun: str,
    standards_anchor: str,
) -> "list[dict]":
    """An element nobody reads from, and a reference to one that is not
    there -- shared by every `style_*.py` reference check.

    The unknown-ref half is also reported by the renderer at render time.
    It is repeated here deliberately: every genre skill runs `draft style`
    before it renders, so this is where the author is still writing.
    """
    starts = section_starts(text)
    ids = {element.id for element in elements}
    found = []
    for element in elements:
        lines = [line for ref_id, line in references if ref_id == element.id]
        if not lines:
            found.append(
                finding(
                    rules,
                    "unreferenced",
                    element.id,
                    element.line,
                    f"no sentence refers to `{element.id}`. A {noun} the prose "
                    "never reads is one the reader has to explain to themselves "
                    f"({standards_anchor}).",
                )
            )
        elif all(
            section_of(line, starts) != section_of(element.line, starts) for line in lines
        ):
            found.append(
                finding(
                    rules,
                    "ref-outside-section",
                    element.id,
                    element.line,
                    f"`{element.id}` is referred to, but only from another "
                    f"section. The sentence that introduces a {noun} belongs "
                    "beside it.",
                )
            )
    found += [
        finding(
            rules,
            "unknown-ref",
            ref_id,
            line,
            f"`{ref_id}` is referred to but no {noun} declares it, so the "
            "marker survives into the rendered document.",
        )
        for ref_id, line in references
        if ref_id not in ids
    ]
    return found
