"""The `python -m chitragupta.draft style` findings about figures.

Plain Python, like `style_tables.py`: a figure's relationship to the
prose is not a Vale pattern (issue 411). `FigureNoCaption` exists since
issue 421 amended WRITING-STANDARDS.md §10, and adding a caption clears
it on re-run, which is what lets `prose` be an unattended class. There is
no `FigureNoId`: a marker's id is its base name, so it always has one.

A `.tex` fragment is out of scope, as for tables. The marker syntax lives
only in `render_output/_figure_captions.py`, and id and reference checks
are `style_elements.py`'s.
"""

from pathlib import Path

from chitragupta import citation_gate, style_elements
from chitragupta.render_output import _figure_captions, _figures, _paths, _tables

RULES = {
    "no-caption": "chitragupta.FigureNoCaption",
    "duplicate-id": "chitragupta.FigureDuplicateId",
    "malformed-id": "chitragupta.FigureMalformedId",
    "unreferenced": "chitragupta.FigureUnreferenced",
    "unknown-ref": "chitragupta.FigureUnknownRef",
    "ref-outside-section": "chitragupta.FigureRefOutsideSection",
}


def _finding(rule: str, match: str, line: int, message: str) -> dict:
    """One finding in `style_check.collapse()`'s shape, bound to `RULES`."""
    return style_elements.finding(RULES, rule, match, line, message)


def _uncaptioned(text: str, figures: "list[_figure_captions.Figure]") -> "list[dict]":
    """A figure marker with no caption line under it.

    Computed by subtraction from `_figure_captions.figures()`'s pairs, so
    the marker syntax is read from `_FIGURE_MARKER_MD_RE`, never copied.
    """
    captioned = {figure.line for figure in figures}
    found = []
    for match in _figures._FIGURE_MARKER_MD_RE.finditer(text):
        line = _tables.line_of(text, match.start())
        if line in captioned:
            continue
        found.append(
            _finding(
                "no-caption",
                _figure_captions._figure_id(match.group(1)),
                line,
                "this figure has no caption. Put one on the line directly "
                "below the marker: a figure the reader meets without one "
                "carries no number and nothing can refer to it "
                "(docs/writing-standards/figures.md §10).",
            )
        )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every figure finding for `draft`, ordered by where it is."""
    # `render`'s own Markdown test, so a draft is checked and rendered
    # under the same contract.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return []
    # Fenced code blanked in place, so a tutorial's example figure markup is
    # not read as a real figure and line numbers stay true.
    text = citation_gate._blank_code(draft.read_text(encoding="utf-8"))
    figures = _figure_captions.figures(text)
    found = (
        _uncaptioned(text, figures)
        + style_elements.id_problems(RULES, figures, "figure", "fig")
        + style_elements.reference_problems(
            RULES,
            text,
            figures,
            _figure_captions.references(text),
            "figure",
            "docs/writing-standards/figures.md §10",
        )
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
