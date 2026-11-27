"""Shared logic behind the table/figure/equation reference checks.

Three modules needed the same id-validity and reference checks, which is
docs/CODE-STANDARDS.md's line for a pattern. Each kind's own "is this
declared" detection stays in its module, as the marker shapes differ.
Parameterised by a `noun` and a `\\label{}` `prefix` (`tab`, `fig`, `eq`).
"""

import re

from chitragupta.render_output._tables import line_of

# A Markdown heading, to bound a section. Not `review/_blocks.HEADING`:
# the review layer sits above this one (docs/ARCHITECTURE.md).
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S.*$", re.MULTILINE)

# The id shape a `\label{<prefix>:<id>}` can carry without further escaping.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def finding(
    rules: "dict[str, str]", rule: str, match: str, line: int, message: str, repair: str = "edit"
) -> dict:
    """One finding in `style_check.check()`'s shape, so `style_report.py`
    never knows which check wrote it.

    `repair` (issue 836): `"edit"` lets the agenda repair it unattended;
    `"review"` is for a rule whose right repair may be to leave the text."""
    return {
        "rule": rules[rule],
        "match": match,
        "line": line,
        "message": message,
        "severity": "suggestion",
        "count": 1,
        "repair": repair,
    }


def section_starts(text: str) -> "list[int]":
    """The 1-based line of every heading. Empty for a draft with no
    headings, which `section_of` treats as one section 0."""
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
    there. The renderer reports unknown refs too; repeated here because
    `draft style` runs while the author is still writing.
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
        elif all(section_of(line, starts) != section_of(element.line, starts) for line in lines):
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
