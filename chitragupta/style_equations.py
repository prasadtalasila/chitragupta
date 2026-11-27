"""The `python -m chitragupta.draft style` findings about equations.

Plain Python, like `style_tables.py`: an equation no sentence refers to
is issue 457's checkable half. Which equations to number is an authoring
judgement (WRITING-STANDARDS.md §12), not decidable here. Advisory, not
part of `_math.py`'s `MathMappingError` gate: an unreferenced equation
still renders. There is no caption or id companion; the nearest is
`EquationOrphanMarker`, a marker with no `<!-- math -->` block below it.
Marker syntax lives in `render_output/_equation_captions.py`; `.tex`
fragments are out of scope, as for tables.

Fenced code is not blanked first, unlike tables and figures: an
equation's block is a fence, so blanking would erase every real one. A
tutorial showing equation markup as an example is therefore read as a
real equation; accepted, as no fence pattern avoids that.
"""

from pathlib import Path

from chitragupta import style_elements
from chitragupta.render_output import _equation_captions, _paths

RULES = {
    "orphan-marker": "chitragupta.EquationOrphanMarker",
    "duplicate-id": "chitragupta.EquationDuplicateId",
    "malformed-id": "chitragupta.EquationMalformedId",
    "unreferenced": "chitragupta.EquationUnreferenced",
    "unknown-ref": "chitragupta.EquationUnknownRef",
    "ref-outside-section": "chitragupta.EquationRefOutsideSection",
}


def _finding(rule: str, match: str, line: int, message: str) -> dict:
    """One finding in `style_check.collapse()`'s shape, bound to `RULES`."""
    return style_elements.finding(RULES, rule, match, line, message)


def _orphaned(text: str) -> "list[dict]":
    """An `equation:` marker naming no `<!-- math -->` block directly
    below it, so nothing numbers it.

    Computed by subtraction from `_equation_captions.equations()`'s
    matches. Separate from `_equation_captions.warnings`, which is a bare
    render-time stderr line; this carries a §-anchor.
    """
    declared_starts = {m.start() for m in _equation_captions._EQUATION_ASCII_RE.finditer(text)}
    found = []
    for marker in _equation_captions._MARKER_RE.finditer(text):
        if marker.start() in declared_starts:
            continue
        eq_id = marker.group("id")
        found.append(
            _finding(
                "orphan-marker",
                eq_id,
                _equation_captions.line_of(text, marker.start()),
                f"`{eq_id}` names no `<!-- math -->` block directly below it, "
                "so nothing numbers it (docs/writing-standards/mathematics.md §12).",
            )
        )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every equation finding for `draft`, ordered by where it is."""
    # `render`'s own Markdown test, so a draft is checked and rendered
    # under the same contract.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return []
    # Not blanked: see the module docstring.
    text = draft.read_text(encoding="utf-8")
    equations = _equation_captions.equations(text)
    found = (
        _orphaned(text)
        + style_elements.id_problems(RULES, equations, "equation", "eq")
        + style_elements.reference_problems(
            RULES,
            text,
            equations,
            _equation_captions.references(text),
            "equation",
            "docs/writing-standards/mathematics.md §12",
        )
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
