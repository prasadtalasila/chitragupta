"""The `python -m chitragupta.draft style` findings about equations.

Beside `chitragupta/style_tables.py` and `chitragupta/style_figures.py`,
computed in plain Python for the same reason: the question here is a
numbered equation's *relationship* to the prose around it, which Vale
cannot see -- an equation no sentence refers to is issue 457's
mechanically-checkable half. **Which equations should be numbered at
all -- standalone, the final step of a derivation, reused by a later
equation -- is not decidable, and nothing here pretends otherwise**;
that is an authoring judgement `docs/WRITING-STANDARDS.md` §12 states,
and the marker's presence is the only part a machine can act on.

**Id validity and the reference checks are `chitragupta/style_elements.py`'s**,
shared with `style_tables.py` and `style_figures.py` -- see that module's
own docstring for why three near-identical copies of this logic earned
one shared home.

**No `EquationNoCaption`/`EquationNoId` companion.** An equation has no
caption text at all -- unlike a table or figure, nothing here describes
it inline -- and its id is only ever declared by the marker itself, so
there is no "described but not declared" state to detect, the same
reasoning `style_figures.py` gives for skipping `FigureNoId`. The
nearest equivalent is `EquationOrphanMarker`: an `equation:` marker
naming no `<!-- math -->` block directly below it, so nothing numbers it.

These are **soft, advisory findings**, not wired into
`chitragupta/render_output/_math.py`'s `MathMappingError` gate: that gate is
about a block being unrenderable as mathematics at all, and an
unreferenced or duplicate-id equation still renders correctly -- it is a
prose-alignment defect, the same category `TableUnreferenced`/
`FigureUnreferenced` already sit in.

The marker syntax itself is not restated here: it lives in
`chitragupta/render_output/_equation_captions.py`, which is what resolves
it at render time, and a second copy of those patterns is exactly the
drift `docs/CODE-STANDARDS.md`'s "one place a fact is written" rules out.

**A `.tex` fragment is out of scope**, the same carve-out `style_tables.py`
and `style_figures.py` state -- `thesis-chapter-writer` writes
`\\[...\\]`/`\\(...\\)` directly and has no marker vocabulary at all.

**Fenced code is not blanked first, unlike `style_tables.py`/`style_figures.py`.**
Both of those blank a fence before scanning, so a tutorial demonstrating
this pipeline's own table/figure markup as an example is not read as a
real declaration -- `citation_gate._blank_code` replaces a whole
`` ``` ``...`` ``` `` region, delimiters included, with equal-length
blanks. An equation's own marked block *is* a fenced region, so blanking
would erase the very fence `_equation_captions.equations()` needs to
recognise a real declaration, misreporting every genuine equation as an
orphaned marker. **What this leaves unhandled**: a tutorial showing
`<!-- equation: id -->`/`<!-- math -->` markup as a literal example is
read as a real, declared equation -- the same class of false finding
blanking exists to prevent for the other two kinds, accepted here rather
than solved, because there is no fence pattern this module could blank
that would not also blank the equations it exists to find.
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
    """One finding in the shape `style_check.collapse()` produces from
    Vale's own -- a thin `RULES`-bound wrapper over the shared
    `style_elements.finding`, mirroring `style_tables._finding`."""
    return style_elements.finding(RULES, rule, match, line, message)


def _orphaned(text: str) -> "list[dict]":
    """An `equation:` marker naming no `<!-- math -->` block directly
    below it, so nothing numbers it.

    Computed by subtraction, the same way `style_figures._uncaptioned`
    tells a bare marker from a paired one: a marker whose start position
    is not where a full `_equation_captions.equations()` match begins is
    one with no valid block after it. Deliberately a second, differently
    worded check from `_equation_captions.warnings`'s own -- that one is
    a bare stderr line at render time; this one carries a §-anchor and the
    finding shape `draft style` reports, the same split `style_tables.py`'s
    own docstring states for its `unknown-ref` half.
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
                "so nothing numbers it (WRITING-STANDARDS.md §12).",
            )
        )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every equation finding for `draft`, ordered by where it is."""
    # `render`'s own answer to "is this a Markdown draft?", not a second
    # one -- the carve-out below has to be the same set of suffixes the
    # renderer takes its Markdown path for, or a draft could be checked
    # under one contract and rendered under the other.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return []
    # Not blanked -- see the module docstring for why blanking a fence
    # here would erase the equations this module exists to find.
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
            "WRITING-STANDARDS.md §12",
        )
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
