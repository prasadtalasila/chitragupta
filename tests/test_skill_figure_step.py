"""Figure drawing is one skill the genre skills hand off to (#1027).

Before #1027 each of the four figure-drawing genre skills carried the
same ~70 lines of figure riders, in three harness copies each, and
#1012 had to change one sentence in twelve files. Those riders now live
once, in `figure-drawer`. This text scan keeps it that way. It pins
that the shared skill carries every rider, that each genre skill keeps
only the stub whose loss would be unsafe if a harness skipped the
handoff, and that no rider drifts back into a genre skill.

It exercises no behaviour: `tests/test_tikz_scaffolds.py`,
`tests/test_figure_layout.py` and `tests/test_tikz_subcaptions.py` own
that. `tests/test_skill_harness_copies.py` makes a check against
`.claude/skills/` hold for the other two copies.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DRAWER = "figure-drawer"

# The riders that moved, by a phrase each one cannot be stated without.
_RIDERS = (
    "Commit to a layout metaphor",
    "pre-flight defect list",
    "lettered sub-captions",
    "tikz@node@reset@hook",
    "as original as the ASCII",
    "chitragupta.figure sync",
)
_NO_CITEKEY = "No citekey inside either figure file"
_MARKDOWN_SHAPE = "<!-- figure: figures/<name> -->"
_THESIS_SHAPE = "%figure: figures/<name>"


def _text(name: str) -> str:
    return re.sub(r"\s+", " ", (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8"))


def test_the_drawer_carries_every_rider():
    text = _text(DRAWER)
    missing = [r for r in _RIDERS + (_NO_CITEKEY,) if r not in text]
    assert not missing, f"figure-drawer lost: {missing}"


def test_the_drawer_knows_both_placement_shapes():
    # Direct use has no genre skill loaded, so the drawer is the only
    # thing telling it a .tex draft takes \input and a .md one the marker.
    text = _text(DRAWER)
    assert _MARKDOWN_SHAPE in text and _THESIS_SHAPE in text


def test_the_drawer_hands_back_and_never_presents():
    # The gate, render, scan and stamp stay with the caller. On direct
    # use that is draft-reviser's write-back and gate, named by heading.
    text = _text(DRAWER)
    assert "never presents a draft" in text
    assert "`draft-reviser`" in text
    assert "6. Write the dossier back" in text and "7. Gate, reference, render" in text
    reviser = _text("draft-reviser")
    assert "### 6. Write the dossier back" in reviser
    assert "### 7. Gate, reference, render" in reviser


def test_the_drawer_runs_the_existing_checks_in_order():
    text = _text(DRAWER)
    order = ["kpsewhich tikz.sty", "run `pdflatex` on it", "python -m chitragupta.review figure"]
    at = [text.find(s) for s in order]
    assert -1 not in at and at == sorted(at), dict(zip(order, at))


def test_the_reference_file_has_the_sections_the_procedure_points_at():
    ref = (SKILLS_DIR / DRAWER / "references" / "figures.md").read_text(encoding="utf-8")
    for heading in (
        "## 1. Choosing a metaphor",
        "## 2. Panels",
        "## 3. Fit without scaling",
        "## 4. An annotated exemplar",
    ):
        assert heading in ref, heading
    for section in ("§1", "§2", "§3", "§4"):
        assert f"references/figures.md` {section}" in _text(DRAWER), section


_GENRES = {
    "survey-writer": _MARKDOWN_SHAPE,
    "tutorial-writer": _MARKDOWN_SHAPE,
    "textbook-chapter-writer": _MARKDOWN_SHAPE,
    "thesis-chapter-writer": _THESIS_SHAPE,
}


def test_every_figure_genre_keeps_the_no_citekey_rule():
    # The one rule whose loss is unsafe if a harness skips the handoff:
    # the gate does not follow \input (SOUL.md). It must not be trimmed
    # out of a stub on the grounds that figure-drawer also says it.
    missing = [g for g in _GENRES if _NO_CITEKEY not in _text(g)]
    assert not missing, f"no-citekey rule missing from: {missing}"


def test_every_figure_genre_keeps_its_own_shape():
    wrong = [g for g, shape in _GENRES.items() if shape not in _text(g)]
    assert not wrong, wrong
    assert _MARKDOWN_SHAPE not in _text("thesis-chapter-writer")


def test_every_figure_genre_hands_off():
    missing = [g for g in _GENRES if f"`{DRAWER}`" not in _text(g)]
    assert not missing, f"no handoff to figure-drawer in: {missing}"


def test_no_rider_has_drifted_back_into_a_genre_skill():
    # #1012 edited twelve files for one sentence. A rider that reappears
    # here is that duplication coming back one copy at a time.
    found = {g: [r for r in _RIDERS if r in _text(g)] for g in _GENRES}
    found = {g: rs for g, rs in found.items() if rs}
    assert not found, f"riders belong only in figure-drawer: {found}"


def test_deep_research_draws_no_figure_and_names_no_drawer():
    assert f"`{DRAWER}`" not in _text("deep-research")


def test_draft_reviser_hands_redrawing_to_the_drawer():
    text = _text("draft-reviser")
    assert f"`{DRAWER}`" in text
    # The revision-only rule stays here: both forms change together, and
    # the change is logged. That is not a drawing rule.
    assert "Touch a figure, touch both forms" in text
    assert not [r for r in _RIDERS if r in text]


def test_every_stub_probes_for_tikz_and_guards_originality_itself():
    # If the handoff is skipped, the stub alone must still look for TikZ
    # before falling back, and still forbid redrawing a source's figure.
    # Neither may depend on figure-drawer having been loaded.
    for g in _GENRES:
        text = _text(g)
        missing = [
            p for p in ("kpsewhich tikz.sty", "compiles", "redrawn from a source") if p not in text
        ]
        assert not missing, f"{g} stub lacks {missing}"


def test_the_drawer_covers_what_direct_use_has_no_genre_step_for():
    # On direct use the caller is draft-reviser, which has no figure step,
    # so the drawer itself must name the TikZ fallback per shape, the flat
    # draft case and the thesis fragment's preamble warnings.
    text = _text(DRAWER)
    for needle in (
        "a `verbatim` environment",
        "A flat draft** (",
        "[tikz-libraries]",
        "[unicode]",
        "\\renewcommand{\\thefigure}",
    ):
        assert needle in text, needle


def test_the_drawer_checks_the_figure_in_the_real_render():
    # The probe sets the figure in a bare article class under pdflatex; the
    # pipeline's own pdf is LuaLaTeX at the document's body font, where
    # labels wrap and gaps close differently. A figure that passed the
    # probe came out with a hyphenated label and an arrow through a zone
    # title in a real render (#1027), so the drawer must look at the page.
    text = _text(DRAWER)
    assert "python -m chitragupta.draft render" in text
    at_probe = text.find("run `pdflatex` on it")
    at_render = text.find("python -m chitragupta.draft render")
    at_return = text.find("**Return.**")
    assert at_probe < at_render < at_return, (at_probe, at_render, at_return)
    assert "LuaLaTeX" in text


def test_the_render_check_says_what_to_do_without_the_tools():
    # The look needs pandoc, LuaLaTeX and pdftoppm, which a bare pip
    # install does not bring, and a harness that can view an image. Without
    # them the step must degrade to the probe and say so, never block.
    text = _text(DRAWER)
    assert "[missing-binary]" in text and "pdftoppm" in text
    assert "say so in chat" in text[text.find("Look at it in the real render") :]
