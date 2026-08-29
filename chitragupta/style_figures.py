"""The `python -m chitragupta.draft style` findings about figures.

Beside `chitragupta/style_tables.py`, computed in plain Python for the
same reason: the questions here are about a figure's *relationship* to
the prose around it, which Vale cannot see -- a figure no sentence refers
to is the second half of issue 411, the same way an unreferenced table
was the second half of issue 395.

**`FigureNoCaption` yes, `FigureNoId` no**, and the two halves are
decided separately. Issue 421 amended `docs/WRITING-STANDARDS.md` §10,
which had accepted an uncaptioned figure as a design choice: it no
longer does, so the marker carrying no caption is a finding like its
`style_tables.py` analogue. `FigureNoId` still has none, and for the
reason that has not changed -- a figure marker always carries an id by
construction, since the id *is* the base name the marker names, so
there is no "marker with no id" state for this module to find.

The amendment is why this rule matters beyond tidiness: `prose` is an
**unattended** class in `docs/AUTO-IMPROVEMENT.md`'s item table, and
that rests on R3 -- every finding must be cleared by an edit a
deterministic re-run can confirm. Adding a caption line beneath the
marker takes this finding away on the next `draft style`, which is what
makes it a member of that class rather than a judgement.

**A `.tex` fragment is out of scope**, deliberately rather than by
omission -- the same carve-out `style_tables.py` states for tables.
`thesis-chapter-writer` hand-authors a real `\\begin{figure}` with its own
`\\caption` and `\\label`, numbered by the thesis that `\\input`s it, so
the marker vocabulary this checks for does not exist there.

The marker syntax itself is not restated here: it lives in
`chitragupta/render_output/_figure_captions.py`, which is what resolves it
at render time, and a second copy of those patterns is exactly the drift
`docs/CODE-STANDARDS.md`'s "one place a fact is written" rules out.

**Id validity and the reference checks are `chitragupta/style_elements.py`'s**,
shared with `style_tables.py` and, since issue 457, `style_equations.py`
-- see that module's own docstring for why a third copy of this logic is
the line docs/CODE-STANDARDS.md draws. What stays here is what is
genuinely figure-specific: a marker with no caption below it.
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
    """One finding in the shape `style_check.collapse()` produces from
    Vale's own -- a thin `RULES`-bound wrapper over the shared
    `style_elements.finding`, mirroring `style_tables._finding`."""
    return style_elements.finding(RULES, rule, match, line, message)


def _uncaptioned(text: str, figures: "list[_figure_captions.Figure]") -> "list[dict]":
    """A figure marker with no caption line under it.

    Computed by subtraction rather than by a second pattern:
    `_figure_captions.figures()` returns only the marker/caption *pairs*,
    so a marker line it did not claim is one that carries no caption.
    That keeps this module's promise not to restate the marker syntax --
    `_figures._FIGURE_MARKER_MD_RE` is the one place a bare Markdown
    marker is spelled, and it is read here rather than copied.

    Unlike the table analogue there is no `no-id` companion to fall
    through to, because a marker's id is its own base name; see the
    module docstring for why that half stays absent.
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
                "(WRITING-STANDARDS.md §10).",
            )
        )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every figure finding for `draft`, ordered by where it is."""
    # `render`'s own answer to "is this a Markdown draft?", not a second
    # one -- the carve-out below has to be the same set of suffixes the
    # renderer takes its Markdown path for, or a draft could be checked
    # under one contract and rendered under the other.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return []
    # Fenced code blanked first, the same call `style_tables.findings` and
    # `review/_claims.py` make for the same reason: a tutorial showing this
    # pipeline's own figure markup *as an example* would otherwise be read
    # as a real, declared figure. It blanks in place, character for
    # character, so every line number below still points where it says.
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
            "WRITING-STANDARDS.md §10",
        )
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
