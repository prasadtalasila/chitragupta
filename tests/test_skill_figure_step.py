import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
DRAWER = "figure-drawer"

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


def _drawer_and_references() -> str:
    folder = SKILLS_DIR / DRAWER
    paths = [folder / "SKILL.md", *sorted((folder / "references").rglob("*.md"))]
    return " ".join(re.sub(r"\s+", " ", p.read_text(encoding="utf-8")) for p in paths)


def test_the_drawer_carries_every_rider():
    text = _drawer_and_references()
    missing = [r for r in _RIDERS if r not in text]
    assert not missing, f"figure-drawer lost: {missing}"
    assert _NO_CITEKEY in _text(DRAWER)


def test_the_drawer_knows_both_placement_shapes():
    text = _text(DRAWER)
    assert _MARKDOWN_SHAPE in text and _THESIS_SHAPE in text


def test_the_drawer_hands_back_and_never_presents():
    text = _text(DRAWER)
    assert "never presents a draft" in text
    assert "`draft-reviser`" in text
    assert "6. Write the dossier back" in text and "7. Gate, reference, render" in text
    reviser = _text("draft-reviser")
    assert "### 6. Write the dossier back" in reviser
    assert "### 7. Gate, reference, render" in reviser


def test_the_drawer_runs_the_existing_checks_in_order():
    text = _text(DRAWER)
    order = [
        "kpsewhich tikz.sty",
        "python -m chitragupta.figure new",
        "python -m chitragupta.figure check",
        "python -m chitragupta.figure look",
    ]
    at = [text.find(s) for s in order]
    assert -1 not in at and at == sorted(at), dict(zip(order, at))


def test_the_drawer_resolves_or_allows_what_figure_check_reports():
    for copy in (
        REPO_ROOT / ".claude" / "skills" / DRAWER / "SKILL.md",
        REPO_ROOT / ".agents" / "skills" / DRAWER / "SKILL.md",
        REPO_ROOT / ".opencode" / "skills" / f"{DRAWER}-opencode" / "SKILL.md",
    ):
        text = re.sub(r"\s+", " ", copy.read_text(encoding="utf-8"))
        assert "`.claude/skills/figure-drawer/references/check.md`" in text, copy
        assert "cg-allow" in text, copy


def test_the_drawer_knows_figure_check_compares_the_twin():
    for copy in (
        REPO_ROOT / ".claude" / "skills" / DRAWER / "SKILL.md",
        REPO_ROOT / ".agents" / "skills" / DRAWER / "SKILL.md",
        REPO_ROOT / ".opencode" / "skills" / f"{DRAWER}-opencode" / "SKILL.md",
    ):
        text = re.sub(r"\s+", " ", copy.read_text(encoding="utf-8"))
        assert "Nothing checks that the two forms agree" not in text, copy
        assert "`t1-labels`" in text and "`twin-missing`" in text, copy


def test_the_reference_file_has_the_sections_the_procedure_points_at():
    ref = (SKILLS_DIR / DRAWER / "references" / "figures.md").read_text(encoding="utf-8")
    for heading in (
        "## 1. Choosing a metaphor",
        "## 2. Panels",
        "## 3. Fit without scaling",
        "## 4. An annotated exemplar",
        "## 5. Looking at a source's figures",
        "## 6. Libraries and compiling",
        "## 7. Looking at the render",
    ):
        assert heading in ref, heading


_GENRES = {
    "survey-writer": _MARKDOWN_SHAPE,
    "tutorial-writer": _MARKDOWN_SHAPE,
    "textbook-chapter-writer": _MARKDOWN_SHAPE,
    "thesis-chapter-writer": _THESIS_SHAPE,
}


def test_every_figure_genre_keeps_the_no_citekey_rule():
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
    found = {g: [r for r in _RIDERS if r in _text(g)] for g in _GENRES}
    found = {g: rs for g, rs in found.items() if rs}
    assert not found, f"riders belong only in figure-drawer: {found}"


_CAPTION_OPTIONAL = re.compile(
    r"needs? no caption|if (?:this|the) figure warrants|warrants (?:one|a caption)",
    re.IGNORECASE,
)


def test_nothing_a_markdown_figure_genre_reads_makes_its_caption_optional():
    paths = [
        *(SKILLS_DIR / g / "SKILL.md" for g, shape in _GENRES.items() if shape == _MARKDOWN_SHAPE),
        SKILLS_DIR / DRAWER / "SKILL.md",
        *sorted((SKILLS_DIR / DRAWER / "references").rglob("*.md")),
        REPO_ROOT / "docs" / "FIGURE-DRAWER.md",
    ]
    found = {
        str(p.relative_to(REPO_ROOT)): hits
        for p in paths
        if (hits := _CAPTION_OPTIONAL.findall(re.sub(r"\s+", " ", p.read_text(encoding="utf-8"))))
    }
    assert not found, f"every figure has a caption (figures.md §10, FigureNoCaption): {found}"


def test_deep_research_draws_no_figure_and_names_no_drawer():
    assert f"`{DRAWER}`" not in _text("deep-research")


def test_draft_reviser_hands_redrawing_to_the_drawer():
    text = _text("draft-reviser")
    assert f"`{DRAWER}`" in text
    assert "Touch a figure, touch both forms" in text
    assert not [r for r in _RIDERS if r in text]


def test_every_stub_probes_for_tikz_and_guards_originality_itself():
    for g in _GENRES:
        text = _text(g)
        missing = [
            p for p in ("kpsewhich tikz.sty", "compiles", "redrawn from a source") if p not in text
        ]
        assert not missing, f"{g} stub lacks {missing}"


def test_the_drawer_covers_what_direct_use_has_no_genre_step_for():
    assert "`.claude/skills/figure-drawer/references/placement.md`" in _text(DRAWER)
    text = _drawer_and_references()
    for needle in (
        "a `verbatim` environment",
        "## 3. A flat draft",
        "[tikz-libraries]",
        "[unicode]",
        "\\renewcommand{\\thefigure}",
    ):
        assert needle in text, needle


def test_the_drawer_checks_the_figure_in_the_real_render():
    text = _text(DRAWER)
    assert "python -m chitragupta.figure look" in text and "--draft" in text
    at_check = text.find("python -m chitragupta.figure check")
    at_look = text.find("python -m chitragupta.figure look")
    at_return = text.find("**Return.**")
    assert -1 < at_check < at_look < at_return, (at_check, at_look, at_return)
    assert "LuaLaTeX" in _drawer_and_references()


def test_the_drawer_starts_a_figure_with_figure_new():
    text = _text(DRAWER)
    assert "python -m chitragupta.figure new" in text
    assert "cp assets/tikz" not in text


def test_the_render_check_says_what_to_do_without_the_tools():
    references = _drawer_and_references()
    assert "[missing-binary]" in references and "pdftoppm" in references
    text = _text(DRAWER)
    assert "say so in chat" in text[text.find("python -m chitragupta.figure look") :]


_TEX_CAPTION_OPTIONAL = re.compile(r"a captioned figure|when captioned", re.IGNORECASE)
_THESIS = "thesis-chapter-writer"


def test_nothing_a_latex_figure_genre_reads_makes_its_caption_optional():
    paths = [
        SKILLS_DIR / _THESIS / "SKILL.md",
        *sorted((SKILLS_DIR / _THESIS / "references").rglob("*.md")),
        SKILLS_DIR / DRAWER / "SKILL.md",
        *sorted((SKILLS_DIR / DRAWER / "references").rglob("*.md")),
        REPO_ROOT / "docs" / "FIGURE-DRAWER.md",
        REPO_ROOT / "docs" / "writing-standards" / "genres" / "thesis-chapter.md",
    ]
    found = {
        str(p.relative_to(REPO_ROOT)): hits
        for p in paths
        if (hits := _TEX_CAPTION_OPTIONAL.findall(re.sub(r"\s+", " ", p.read_text("utf-8"))))
    }
    assert not found, f"every thesis figure is a captioned float: {found}"


def test_the_thesis_fragment_advice_names_the_lualatex_preamble():
    text = (REPO_ROOT / "docs" / "FIGURE-DRAWER.md").read_text("utf-8")
    section = text[text.index("## 🎓 Thesis fragments") :]
    section = section[: section.index("\n## ", 5)]
    assert "chitragupta-lualatex.tex" in section
    assert "LuaLaTeX" in section
