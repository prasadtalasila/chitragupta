import re
import subprocess
from pathlib import Path

import pytest

from chitragupta import render_output
from chitragupta.render_output import _substitution
from tests.conftest import (
    CAPTIONED_MD,
    MARKED_MD,
    content_draft,
    lualatex_available,
    pandoc_available,
    pdftotext_available,
    tikz_available,
)


class TestFigures:
    def test_an_uncaptioned_marker_declares_nothing(self):
        assert render_output._figure_captions.figures(MARKED_MD) == []

    def test_a_captioned_marker_is_numbered_from_one(self):
        [figure] = render_output._figure_captions.figures(CAPTIONED_MD)
        assert figure.id == "fig1"
        assert figure.caption == "One reading path."
        assert figure.number == 1

    def test_numbering_skips_uncaptioned_markers_between_captioned_ones(self):
        text = (
            CAPTIONED_MD
            + "\n<!-- figure: figures/fig2 -->\n\n"
            + "<!-- figure: figures/fig3 -->\nA second caption.\n"
        )
        figures = render_output._figure_captions.figures(text)
        assert [f.id for f in figures] == ["fig1", "fig3"]
        assert [f.number for f in figures] == [1, 2]

    def test_a_caption_line_that_is_itself_a_marker_is_not_swallowed(self):
        text = "<!-- figure: figures/fig1 -->\n<!-- figure: figures/fig2 -->\nReal caption.\n"
        figures = render_output._figure_captions.figures(text)
        assert [f.id for f in figures] == ["fig2"]


class TestFigureReferences:
    def test_no_references_in_plain_prose(self):
        assert render_output._figure_captions.references("Just prose.\n") == []

    def test_a_figureref_marker_is_found_with_its_line(self):
        text = "Intro.\n\n<!-- figureref: fig1 --> shows the flow.\n"
        assert render_output._figure_captions.references(text) == [("fig1", 3)]


class TestSubstituteCaptions:
    def test_an_uncaptioned_marker_is_untouched(self):
        assert render_output._figure_captions.substitute_captions(MARKED_MD, "pdf") == MARKED_MD
        assert render_output._figure_captions.substitute_captions(MARKED_MD, "md") == MARKED_MD

    def test_latex_bound_wraps_the_marker_in_a_float(self):
        out = render_output._figure_captions.substitute_captions(CAPTIONED_MD, "pdf")
        assert "\\begin{figure}" in out
        assert "<!-- figure: figures/fig1 -->" in out
        assert "`\\caption{`{=latex}One reading path." in out
        assert "`}\\label{fig:fig1}`{=latex}" in out
        assert "\\end{figure}" in out
        assert out.count("One reading path.") == 1

    def test_latex_bound_leaves_the_caption_pandoc_visible_not_raw_interpolated(self):
        caption = "Throughput [@doe2020] rose 5% & fell"
        text = f"<!-- figure: figures/fig1 -->\n{caption}\n"

        out = render_output._figure_captions.substitute_captions(text, "pdf")

        assert caption in out
        assert "\\begin{figure}" in out
        assert "\\end{figure}" in out
        assert "`\\caption{`{=latex}" in out
        assert "`}\\label{fig:fig1}`{=latex}" in out

    def test_the_begin_and_end_are_each_their_own_raw_block(self):
        out = render_output._figure_captions.substitute_captions(CAPTIONED_MD, "pdf")
        assert "```{=latex}\n\\begin{figure}\n```" in out
        assert "```{=latex}\n\\end{figure}\n```" in out

    def test_a_captioned_figures_new_fences_do_not_confuse_later_math(self):
        draft_text = (
            "# Title\n\n" + CAPTIONED_MD + "\nWriting `W` for water, the model is:\n\n"
            "<!-- math -->\n```\ndW/dt = -W/tau\n```\n"
        )
        mapping = {"W": "W", "dW/dt = -W/tau": "\\frac{dW}{dt} = -\\frac{W}{\\tau}"}

        out = _substitution._substituted(
            draft_text, Path("content/drafts/dt/tutorial.md"), "pdf", mapping
        )

        assert "$$\n\\frac{dW}{dt} = -\\frac{W}{\\tau}\n$$" in out
        assert "$W$" in out

    def test_non_latex_gets_a_bold_numbered_paragraph(self):
        out = render_output._figure_captions.substitute_captions(CAPTIONED_MD, "md")
        assert "<!-- figure: figures/fig1 -->" in out
        assert "**Figure 1:** One reading path." in out
        assert "\\begin{figure}" not in out

    def test_docx_gets_the_same_bold_numbered_paragraph_as_md(self):
        out = render_output._figure_captions.substitute_captions(CAPTIONED_MD, "docx")
        assert "**Figure 1:** One reading path." in out


class TestSubstituteRefs:
    def test_latex_bound_becomes_a_raw_ref_span(self):
        text = CAPTIONED_MD + "\n<!-- figureref: fig1 --> shows the flow.\n"
        out = render_output._figure_captions.substitute_refs(text, "pdf")
        assert "`Figure~\\ref{fig:fig1}`{=latex} shows the flow." in out

    def test_non_latex_becomes_a_literal_figure_number(self):
        text = CAPTIONED_MD + "\n<!-- figureref: fig1 --> shows the flow.\n"
        out = render_output._figure_captions.substitute_refs(text, "md")
        assert "Figure 1 shows the flow." in out

    def test_a_reference_to_an_unknown_id_is_left_alone(self):
        text = "<!-- figureref: ghost --> shows the flow.\n"
        out = render_output._figure_captions.substitute_refs(text, "pdf")
        assert out == text

    def test_a_reference_to_an_uncaptioned_figure_is_left_alone(self):
        text = MARKED_MD + "\n<!-- figureref: fig1 --> shows the flow.\n"
        out = render_output._figure_captions.substitute_refs(text, "pdf")
        assert "<!-- figureref: fig1 -->" in out


class TestWarnings:
    def test_a_clean_captioned_figure_warns_about_nothing(self):
        assert render_output._figure_captions.warnings(CAPTIONED_MD) == []

    def test_two_captioned_figures_sharing_an_id_is_flagged(self):
        text = CAPTIONED_MD + "\n<!-- figure: figures/fig1 -->\nA second caption.\n"
        warnings = render_output._figure_captions.warnings(text)
        assert any("fig1" in w and "more than one figure" in w for w in warnings)

    def test_a_figureref_naming_no_declared_figure_is_flagged(self):
        text = CAPTIONED_MD + "\n<!-- figureref: ghost -->\n"
        warnings = render_output._figure_captions.warnings(text)
        assert any("ghost" in w and "no figure declares it" in w for w in warnings)

    def test_a_caption_with_no_blank_line_before_the_next_prose_is_flagged(self):
        text = "<!-- figure: figures/fig1 -->\nOne reading path.\nover two lines.\n"
        warnings = render_output._figure_captions.warnings(text)
        assert any(
            "fig1" in w and "over two lines." in w and "non-blank line" in w for w in warnings
        )

    def test_a_caption_followed_by_a_blank_line_is_not_flagged(self):
        assert render_output._figure_captions.warnings(CAPTIONED_MD) == []

    def test_a_caption_with_no_trailing_newline_at_all_is_not_flagged(self):
        text = "<!-- figure: figures/fig1 -->\nOne reading path."
        warnings = render_output._figure_captions.warnings(text)
        assert not any("non-blank line" in w for w in warnings)

    def test_a_caption_immediately_followed_by_a_new_marker_is_not_flagged(self):
        text = (
            "<!-- figure: figures/fig1 -->\nOne reading path.\n"
            "<!-- figure: figures/fig2 -->\nA second caption.\n"
        )
        warnings = render_output._figure_captions.warnings(text)
        assert not any("non-blank line" in w for w in warnings)


@pytest.mark.slow
@pytest.mark.skipif(
    not (pandoc_available and lualatex_available and tikz_available and pdftotext_available),
    reason="needs pandoc, lualatex with tikz.sty, and pdftotext",
)
@pytest.mark.parametrize("caption", ["One node.\n", ""], ids=["captioned", "uncaptioned"])
def test_a_figure_is_centred_on_the_text_block(isolated_config, caption):
    isolated_config.BIB_FILE_PATH.write_text("")
    draft = content_draft(isolated_config, "drafts/rag/survey.md")
    (draft.parent / "figures").mkdir()
    picture = "\\begin{tikzpicture}\\node[draw] {CENTREME};\\end{tikzpicture}%\n"
    (draft.parent / "figures" / "one.tex").write_text(picture, encoding="utf-8")
    (draft.parent / "figures" / "one.txt").write_text("[ CENTREME ]\n", encoding="utf-8")
    draft.write_text(f"Text.\n\n<!-- figure: figures/one -->\n{caption}\nMore.\n", encoding="utf-8")
    pdf = render_output.render(str(draft), output_format="pdf")
    html = subprocess.run(
        ["pdftotext", "-bbox", str(pdf), "-"], capture_output=True, text=True, check=True
    ).stdout
    words = re.findall(r'xMin="([\d.]+)" yMin="[\d.]+" xMax="([\d.]+)" yMax="[\d.]+">(\w+)<', html)
    [label] = [(float(x0), float(x1)) for x0, x1, word in words if word == "CENTREME"]
    assert (label[0] + label[1]) / 2 == pytest.approx(595.28 / 2, abs=1.0)
