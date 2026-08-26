"""chitragupta/render_output/_figure_captions.py: issue 411's caption,
numbering and `figureref` contract.

Split from `tests/test_render_output_figures.py` to mirror
`chitragupta/render_output/`'s own split (the ASCII/TikZ pair versus the
caption that wraps around it), the way `tests/test_enrich_*.py` mirrors
`chitragupta/enrich/`.
"""

from chitragupta import render_output
from tests.conftest import CAPTIONED_MD, MARKED_MD


class TestFigures:
    def test_an_uncaptioned_marker_declares_nothing(self):
        assert render_output._figure_captions.figures(MARKED_MD) == []

    def test_a_captioned_marker_is_numbered_from_one(self):
        [figure] = render_output._figure_captions.figures(CAPTIONED_MD)
        assert figure.id == "fig1"
        assert figure.caption == "One reading path."
        assert figure.number == 1

    def test_numbering_skips_uncaptioned_markers_between_captioned_ones(self):
        # The middle marker is uncaptioned (blank line follows it), so it
        # must not be counted.
        text = (
            CAPTIONED_MD
            + "\n<!-- figure: figures/fig2 -->\n\n"
            + "<!-- figure: figures/fig3 -->\nA second caption.\n"
        )
        figures = render_output._figure_captions.figures(text)
        assert [f.id for f in figures] == ["fig1", "fig3"]
        assert [f.number for f in figures] == [1, 2]

    def test_a_caption_line_that_is_itself_a_marker_is_not_swallowed(self):
        # Two figures back to back, no blank line between them: the second
        # marker must not be read as the first figure's caption.
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
        assert "\\caption{One reading path.}" in out
        assert "\\label{fig:fig1}" in out
        assert "\\end{figure}" in out
        # The original caption paragraph is consumed into \caption{}, not
        # left behind as a second copy of the sentence.
        assert out.count("One reading path.") == 1

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
