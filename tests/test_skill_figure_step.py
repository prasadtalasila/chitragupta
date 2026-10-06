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
    ref = (SKILLS_DIR / DRAWER / "reference.md").read_text(encoding="utf-8")
    for heading in (
        "## 1. Choosing a metaphor",
        "## 2. Panels",
        "## 3. Fit without scaling",
        "## 4. An annotated exemplar",
    ):
        assert heading in ref, heading
    for section in ("§1", "§2", "§3", "§4"):
        assert f"reference.md {section}" in _text(DRAWER), section
