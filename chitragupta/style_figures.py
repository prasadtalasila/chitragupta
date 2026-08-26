"""The `python -m chitragupta.draft style` findings about figures.

Beside `chitragupta/style_tables.py`, computed in plain Python for the
same reason: the questions here are about a figure's *relationship* to
the prose around it, which Vale cannot see -- a figure no sentence refers
to is the second half of issue 411, the same way an unreferenced table
was the second half of issue 395.

**Deliberately no `FigureNoCaption` or `FigureNoId`.** Both have table
analogues and neither applies here: `docs/WRITING-STANDARDS.md` §10
already accepts an uncaptioned figure as a design choice, not a defect,
and a figure marker always carries an id by construction -- it names the
figure's base name, so there is no "marker with no id" state for this
module to find. Reporting either would contradict §10's own accepted
case.

**A `.tex` fragment is out of scope**, deliberately rather than by
omission -- the same carve-out `style_tables.py` states for tables.
`thesis-chapter-writer` hand-authors a real `\\begin{figure}` with its own
`\\caption` and `\\label`, numbered by the thesis that `\\input`s it, so
the marker vocabulary this checks for does not exist there.

The marker syntax itself is not restated here: it lives in
`chitragupta/render_output/_figure_captions.py`, which is what resolves it
at render time, and a second copy of those patterns is exactly the drift
`docs/CODE-STANDARDS.md`'s "one place a fact is written" rules out.
"""

import re
from pathlib import Path

from chitragupta import citation_gate
from chitragupta.render_output import _figure_captions, _paths, _tables

RULES = {
    "duplicate-id": "chitragupta.FigureDuplicateId",
    "malformed-id": "chitragupta.FigureMalformedId",
    "unreferenced": "chitragupta.FigureUnreferenced",
    "unknown-ref": "chitragupta.FigureUnknownRef",
    "ref-outside-section": "chitragupta.FigureRefOutsideSection",
}

# A Markdown heading, only to bound a section -- the same pattern
# `style_tables._HEADING_RE` uses and the same reason it is not imported
# from the review layer: a drafting-layer check reaching up into it would
# be a dependency in the wrong direction for one three-token pattern.
_HEADING_RE = re.compile(r"^#{1,6}[ \t]+\S.*$", re.MULTILINE)

# The id shape a `\\label{fig:<id>}` can carry without further escaping.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def _finding(rule: str, match: str, line: int, message: str) -> dict:
    """One finding in the shape `style_check.collapse()` produces from
    Vale's own, mirroring `style_tables._finding`."""
    return {
        "rule": RULES[rule],
        "match": match,
        "line": line,
        "message": message,
        "severity": "suggestion",
        "count": 1,
    }


def _section_starts(text: str) -> "list[int]":
    """The 1-based line of every heading, so a line can be placed in one."""
    return [_tables.line_of(text, m.start()) for m in _HEADING_RE.finditer(text)]


def _section_of(line: int, starts: "list[int]") -> int:
    """Which section `line` falls in, as an index into `starts`."""
    return sum(1 for start in starts if start <= line)


def _id_problems(figures: "list[_figure_captions.Figure]") -> "list[dict]":
    """Ids that collide or that a `\\label{}` cannot carry."""
    ids = [figure.id for figure in figures]
    found = [
        _finding(
            "duplicate-id",
            figure.id,
            figure.line,
            f"`{figure.id}` is claimed by more than one figure. Both become "
            "`\\label{}`s in one LaTeX document, where a duplicate resolves "
            "silently to the wrong figure.",
        )
        for figure in figures
        if ids.count(figure.id) > 1
    ]
    found += [
        _finding(
            "malformed-id",
            figure.id,
            figure.line,
            f"`{figure.id}` is not a kebab-case id (lowercase, digits and "
            "hyphens), which is what `\\label{fig:<id>}` can carry unescaped.",
        )
        for figure in figures
        if not _ID_RE.match(figure.id)
    ]
    return found


def _reference_problems(text: str, figures: "list[_figure_captions.Figure]") -> "list[dict]":
    """A figure nobody reads from, and a reference to a figure that is not
    there -- mirroring `style_tables._reference_problems`.

    The unknown-ref half is also reported by the renderer at render time.
    It is repeated here deliberately: every genre skill runs `draft style`
    before it renders, so this is where the author is still writing.
    """
    starts = _section_starts(text)
    refs = _figure_captions.references(text)
    ids = {figure.id for figure in figures}
    found = []
    for figure in figures:
        lines = [line for ref_id, line in refs if ref_id == figure.id]
        if not lines:
            found.append(
                _finding(
                    "unreferenced",
                    figure.id,
                    figure.line,
                    f"no sentence refers to `{figure.id}`. A figure the prose "
                    "never reads is one the reader has to explain to "
                    "themselves (WRITING-STANDARDS.md §10).",
                )
            )
        elif all(_section_of(line, starts) != _section_of(figure.line, starts) for line in lines):
            found.append(
                _finding(
                    "ref-outside-section",
                    figure.id,
                    figure.line,
                    f"`{figure.id}` is referred to, but only from another "
                    "section. The sentence that introduces a figure belongs "
                    "beside it.",
                )
            )
    found += [
        _finding(
            "unknown-ref",
            ref_id,
            line,
            f"`{ref_id}` is referred to but no figure declares it, so the "
            "marker survives into the rendered document.",
        )
        for ref_id, line in refs
        if ref_id not in ids
    ]
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
    found = _id_problems(figures) + _reference_problems(text, figures)
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
