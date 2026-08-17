"""src/render_output/_figures.py: the ASCII/TikZ pair and the per-format swap.

Split from one test module to mirror `src/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `src/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

import shutil
import subprocess
import pytest
from src import render_output
from tests.conftest import ASCII_FIGURE, MARKED_FENCE, MARKED_INPUT, TIKZ_FIGURE, figure_pair


class TestLocalTexIncludeRefs:
    def test_extracts_input_and_include_paths(self):
        text = "\\input{figures/fig1.tex}\n\nSome text \\include{figures/fig2.tex}.\n"
        assert render_output._local_tex_include_refs(text) == [
            "figures/fig1.tex", "figures/fig2.tex",
        ]

    def test_matches_inside_a_raw_latex_fenced_block_too(self):
        # #222: a bare \input line and a ```{=latex} fence around the same
        # line reach pandoc's LaTeX writer identically, so this doesn't
        # special-case the fence.
        text = "```{=latex}\n\\input{figures/fig1.tex}\n```\n"
        assert render_output._local_tex_include_refs(text) == ["figures/fig1.tex"]

    def test_no_includes_returns_empty_list(self):
        assert render_output._local_tex_include_refs("Just text, no figures.\n") == []


class TestFigureRefs:
    def test_a_markdown_marker_is_a_figure_reference(self):
        # The marker is what makes the figure file visible to the copy
        # step and the \usepackage{tikz} gate, both of which read the
        # draft on disk rather than the substituted temp copy.
        assert render_output._figure_refs(MARKED_FENCE) == ["figures/fig1.tex"]

    def test_a_latex_input_is_a_figure_reference(self):
        assert render_output._figure_refs(MARKED_INPUT) == ["figures/fig1.tex"]

    def test_an_ascii_alt_marker_names_the_twin(self):
        assert render_output._ascii_alt_refs(MARKED_INPUT) == ["figures/fig1.txt"]

    def test_a_draft_with_no_figure_references_nothing(self):
        assert render_output._figure_refs("Just prose.\n") == []
        assert render_output._ascii_alt_refs("Just prose.\n") == []


class TestResolveSibling:
    def test_resolves_a_real_file_under_the_draft_directory(self, tmp_path):
        figure_pair(tmp_path)
        resolved = render_output._resolve_sibling(tmp_path, "figures/fig1.tex")
        assert resolved == tmp_path / "figures" / "fig1.tex"

    def test_refuses_absolute_and_parent_escaping_references(self, tmp_path):
        secret = tmp_path / "secret.tex"
        secret.write_text("marker")
        draft_dir = tmp_path / "drafts"
        draft_dir.mkdir()
        assert render_output._resolve_sibling(draft_dir, str(secret)) is None
        assert render_output._resolve_sibling(draft_dir, "../secret.tex") is None

    def test_returns_none_for_a_reference_that_is_not_a_file(self, tmp_path):
        assert render_output._resolve_sibling(tmp_path, "figures/absent.tex") is None


class TestSubstituteTikzForAscii:
    def test_a_marked_fence_becomes_an_input(self, tmp_path):
        figure_pair(tmp_path)
        out = render_output._substitute_tikz_for_ascii(MARKED_FENCE, tmp_path)
        assert "\\input{figures/fig1.tex}" in out
        # The fence goes too: leaving it in puts the ASCII diagram and the
        # TikZ picture in the same PDF, one under the other.
        assert "+-------+" not in out
        assert "```" not in out

    def test_a_marker_naming_a_missing_file_is_left_alone(self, tmp_path):
        out = render_output._substitute_tikz_for_ascii(MARKED_FENCE, tmp_path)
        assert out == MARKED_FENCE

    def test_a_tilde_fence_is_matched_too(self, tmp_path):
        figure_pair(tmp_path)
        text = "<!-- figure: figures/fig1 -->\n~~~\n" + ASCII_FIGURE + "~~~\n"
        assert "\\input{figures/fig1.tex}" in render_output._substitute_tikz_for_ascii(
            text, tmp_path
        )


class TestSubstituteAsciiForTikz:
    def test_an_input_with_a_twin_becomes_a_verbatim_block(self, tmp_path):
        figure_pair(tmp_path)
        out = render_output._substitute_ascii_for_tikz(MARKED_INPUT, tmp_path)
        assert "\\begin{verbatim}" in out
        assert "| model | ------> | solver |" in out
        assert "\\input{figures/fig1.tex}" not in out

    def test_a_twin_that_is_not_there_is_left_alone(self, tmp_path):
        out = render_output._substitute_ascii_for_tikz(MARKED_INPUT, tmp_path)
        assert out == MARKED_INPUT


class TestWithFiguresFor:
    def test_markdown_draft_to_pdf_takes_the_tikz_form(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        out = render_output._with_figures_for(MARKED_FENCE, draft, "pdf")
        assert "\\input{figures/fig1.tex}" in out

    def test_markdown_draft_to_docx_keeps_the_ascii(self, tmp_path):
        # pandoc cannot turn a tikzpicture into a Word drawing -- it drops
        # the environment, so substituting there loses the figure entirely.
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        assert render_output._with_figures_for(MARKED_FENCE, draft, "docx") == MARKED_FENCE

    def test_latex_draft_to_md_takes_the_ascii_form(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        out = render_output._with_figures_for(MARKED_INPUT, draft, "md")
        assert "\\begin{verbatim}" in out

    def test_latex_draft_to_pdf_keeps_its_input(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        assert render_output._with_figures_for(MARKED_INPUT, draft, "pdf") == MARKED_INPUT


class TestFigureHasCitekey:
    def test_detects_a_pandoc_citekey(self, tmp_path):
        fig = tmp_path / "fig.tex"
        fig.write_text("\\node {see [@smith_thing_2020]};\n")
        assert render_output._figure_has_citekey(fig) is True

    def test_detects_a_latex_cite(self, tmp_path):
        fig = tmp_path / "fig.tex"
        fig.write_text("\\node {see \\citep{smith_thing_2020}};\n")
        assert render_output._figure_has_citekey(fig) is True

    def test_a_clean_figure_has_none(self, tmp_path):
        fig = tmp_path / "fig.tex"
        fig.write_text(TIKZ_FIGURE)
        assert render_output._figure_has_citekey(fig) is False


class TestFigureWarnings:
    def test_a_clean_markdown_pair_warns_about_nothing(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        assert render_output._figure_warnings(MARKED_FENCE, draft) == []

    def test_a_clean_latex_pair_warns_about_nothing(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        assert render_output._figure_warnings(MARKED_INPUT, draft) == []

    def test_the_wrong_marker_for_the_draft_language_is_flagged(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.md"
        warnings = render_output._figure_warnings(MARKED_INPUT, draft)
        assert any("wrong kind for a Markdown draft" in w for w in warnings)

    def test_a_missing_figure_file_is_flagged(self, tmp_path):
        draft = tmp_path / "draft.md"
        warnings = render_output._figure_warnings(MARKED_FENCE, draft)
        assert any("not a readable file" in w for w in warnings)

    def test_a_citekey_in_a_figure_file_is_flagged(self, tmp_path):
        figure_pair(tmp_path)
        (tmp_path / "figures" / "fig1.tex").write_text("\\citep{smith_thing_2020}\n")
        draft = tmp_path / "draft.md"
        warnings = render_output._figure_warnings(MARKED_FENCE, draft)
        # The gate does not follow \input, so a citekey here is ungated --
        # forbidden by convention, warned about, deliberately not gated.
        assert any("ungated" in w for w in warnings)

    def test_an_input_with_no_ascii_twin_is_flagged(self, tmp_path):
        figure_pair(tmp_path)
        draft = tmp_path / "draft.tex"
        warnings = render_output._figure_warnings("\\input{figures/fig1.tex}\n", draft)
        assert any("no `%figure:` marker" in w for w in warnings)


class TestRequireTikz:
    def test_says_nothing_when_kpsewhich_is_absent(self, monkeypatch):
        # Cannot be probed, so it is not guessed: a TeX installation that
        # ships its own tooling would otherwise be refused a render.
        monkeypatch.setattr(shutil, "which", lambda name: None)
        render_output._require_tikz()

    def test_raises_when_the_probe_reports_tikz_missing(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/kpsewhich")
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(a[0] if a else [], 1, b"", b""),
        )
        with pytest.raises(render_output.MissingBinary, match="texlive-pictures"):
            render_output._require_tikz()

    def test_says_nothing_when_the_probe_finds_tikz(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/kpsewhich")
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(a[0] if a else [], 0, b"ok", b""),
        )
        render_output._require_tikz()
