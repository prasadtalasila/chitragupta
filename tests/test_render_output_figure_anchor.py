"""chitragupta/render_output/_figure_anchor.py: the mark at each figure
in a pdf render, and reading its page back (#1052)."""

import shutil
import subprocess

import pytest

from chitragupta import render_output
from chitragupta.render_output import _figure_anchor, _figures
from tests.conftest import (
    MARKED_INPUT,
    MARKED_MD,
    content_draft,
    figure_pair,
    lualatex_available,
    pandoc_available,
    tikz_available,
)

needs_pdf_render = pytest.mark.skipif(
    not (pandoc_available and lualatex_available and tikz_available)
    or shutil.which("pdfinfo") is None
    or shutil.which("pdftotext") is None,
    reason="needs pandoc, lualatex with tikz.sty, and poppler-utils",
)

_PARAGRAPH = "word " * 90 + "\n\n"


class TestFigureBlock:
    def test_the_mark_follows_the_input_in_one_centred_raw_block(self):
        assert _figure_anchor.figure_block("figures/flow.tex", "figures/flow", True) == (
            "```{=latex}\n{\\centering\\input{figures/flow.tex}"
            "\\unskip\\pdfextension dest name{cgfig:figures/flow} xyz\\relax\\par}\n```\n"
        )

    def test_unmarked_it_is_the_centred_input_alone(self):
        assert _figure_anchor.figure_block("figures/flow.tex", "figures/flow", False) == (
            "```{=latex}\n{\\centering\\input{figures/flow.tex}\\par}\n```\n"
        )

    @pytest.mark.parametrize("base", ["figures/a#b", "figures/a%b", "figures/a{b}", "f\\x"])
    def test_a_base_tex_would_act_on_gets_no_mark(self, base):
        block = _figure_anchor.figure_block(f"{base}.tex", base, True)
        assert "pdfextension" not in block and f"\\input{{{base}.tex}}" in block

    def test_pages_reads_only_its_own_marks(self):
        dests = (
            "Page  Destination                 Name\n"
            '   1 [ XYZ  103  713 null      ] "Doc-Start"\n'
            '   2 [ XYZ  103  609 null      ] "cgfig:figures/flow"\n'
            '   4 [ XYZ  310  582 null      ] "cgfig:figures/stack"\n'
            '   4 [ XYZ  310  582 null      ] "figure.1"\n'
        )
        assert _figure_anchor.pages(dests) == {"figures/flow": 2, "figures/stack": 4}


class TestWhereTheMarkGoes:
    def test_a_markdown_draft_to_pdf_is_marked(self, tmp_path):
        draft = figure_pair(tmp_path) / "draft.md"
        out = render_output._with_figures_for(MARKED_MD, draft, "pdf")
        assert "\\pdfextension dest name{cgfig:figures/fig1} xyz\\relax" in out

    @pytest.mark.parametrize("fmt", ["tex", "latex"])
    def test_a_tex_output_is_not_marked(self, tmp_path, fmt):
        draft = figure_pair(tmp_path) / "draft.md"
        out = render_output._with_figures_for(MARKED_MD, draft, fmt)
        assert "\\input{figures/fig1.tex}\\par}" in out and "pdfextension" not in out

    def test_a_tex_draft_is_left_as_it_is(self, tmp_path):
        draft = figure_pair(tmp_path) / "draft.tex"
        assert render_output._with_figures_for(MARKED_INPUT, draft, "pdf") == MARKED_INPUT


def _labelled_figure(directory, name: str) -> None:
    (directory / "figures").mkdir(parents=True, exist_ok=True)
    picture = f"\\begin{{tikzpicture}}\\node[draw] {{{name.upper()}LABEL}};\\end{{tikzpicture}}%\n"
    (directory / "figures" / f"{name}.tex").write_text(picture, encoding="utf-8")
    (directory / "figures" / f"{name}.txt").write_text(f"[ {name} ]\n", encoding="utf-8")


def _draft(isolated_config, names: list[str], paragraphs_between: int):
    """A draft with each figure `paragraphs_between` paragraphs after the
    last, uncaptioned and captioned alternately, so some land at a page
    boundary and some float."""
    isolated_config.BIB_FILE_PATH.write_text("")
    draft = content_draft(isolated_config, "rag/survey.md")
    body = "---\ntitle: Anchors\n---\n\n"
    for index, name in enumerate(names):
        _labelled_figure(draft.parent, name)
        caption = f"\nFigure {name}.\n" if index % 2 else "\n"
        body += _PARAGRAPH * paragraphs_between + f"<!-- figure: figures/{name} -->{caption}\n"
    draft.write_text(body + _PARAGRAPH * 3, encoding="utf-8")
    return draft


def _page_text(pdf, page: int) -> str:
    args = ["pdftotext", "-f", str(page), "-l", str(page), str(pdf), "-"]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout


def _words(pdf) -> str:
    """Every word and its box, page by page. From `<body>` on, since the
    head carries the PDF's creation time."""
    args = ["pdftotext", "-bbox", str(pdf), "-"]
    html = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    return html[html.index("<body>") :]


@needs_pdf_render
class TestRealRender:
    def test_each_mark_names_the_page_its_figure_printed_on(self, isolated_config):
        names = ["one", "two", "three", "four"]
        out = render_output.render(str(_draft(isolated_config, names, 4)), output_format="pdf")
        dests = subprocess.run(
            ["pdfinfo", "-dests", str(out)], capture_output=True, text=True, check=True
        ).stdout
        pages = _figure_anchor.pages(dests)
        assert set(pages) == {f"figures/{name}" for name in names}
        assert len(set(pages.values())) > 1
        for name in names:
            assert f"{name.upper()}LABEL" in _page_text(out, pages[f"figures/{name}"])

    @pytest.mark.parametrize("between", [3, 4, 5])
    def test_the_marks_move_no_word_on_any_page(self, isolated_config, monkeypatch, between):
        draft = _draft(isolated_config, ["one", "two", "three", "four"], between)
        marked = _words(render_output.render(str(draft), output_format="pdf"))
        unmarked = _figure_anchor.figure_block
        monkeypatch.setattr(
            _figures, "figure_block", lambda ref, base, _: unmarked(ref, base, False)
        )
        assert _words(render_output.render(str(draft), output_format="pdf")) == marked
