"""A `.tex` draft's own preview shows what the thesis will show (#1164,
#1120): its figures, its table widths, numbered headings for `\\ref`, a
references heading, and the author's preamble file.

The rewrite and the pandoc arguments are tested here without pandoc; the
renders that need it are skipped where it is missing.
"""

from chitragupta.render_output._tex_preview import (
    pandoc_args,
    preamble_file,
    rewrite,
    widths_as_fractions,
    without_lone_centering,
)

TITLE = ["--metadata", "reference-section-title=References"]


class TestWidths:
    def test_absolute_widths_become_fractions_of_the_text_width(self):
        spec = "\\begin{tabular}{p{2.6cm}p{4.5cm}l}\nA & B & C \\\\\n\\end{tabular}"

        out = widths_as_fractions(spec, 452.97)

        assert "{p{0.1633\\linewidth}p{0.2827\\linewidth}l}" in out

    def test_relative_widths_and_cell_text_are_left_alone(self):
        text = (
            "\\begin{tabular}{p{0.2\\linewidth}l}\n\\parbox{2cm}{x} & "
            "\\rule{3cm}{1pt} \\\\\n\\end{tabular}"
        )

        assert widths_as_fractions(text, 452.97) == text

    def test_tabularx_and_longtable_specs_are_read_after_their_arguments(self):
        tabularx = "\\begin{tabularx}{\\linewidth}[t]{p{1in}X}\\end{tabularx}"
        longtable = "\\begin{longtable}[c]{m{10mm}b{72.27pt}}\\end{longtable}"

        assert "{p{0.1595\\linewidth}X}" in widths_as_fractions(tabularx, 452.97)
        assert "{m{0.0628\\linewidth}b{0.1595\\linewidth}}" in widths_as_fractions(
            longtable, 452.97
        )

    def test_em_and_ex_widths_are_left_alone(self):
        """Their size depends on the thesis's font, which the preview
        does not know."""
        text = "\\begin{tabular}{p{10em}p{4ex}}\\end{tabular}"

        assert widths_as_fractions(text, 452.97) == text

    def test_a_spec_left_open_or_missing_is_left_alone(self):
        for text in (
            "\\begin{tabular}{p{2cm}",
            "\\begin{tabular}x",
            "\\begin{tabularx}{\\linewidth",
        ):
            assert widths_as_fractions(text, 452.97) == text

    def test_space_before_the_spec_is_skipped(self):
        text = "\\begin{tabular} {p{2.6cm}}"

        assert widths_as_fractions(text, 452.97) == "\\begin{tabular} {p{0.1633\\linewidth}}"


class TestCentering:
    def test_a_figures_centering_is_dropped_and_others_kept(self):
        text = (
            "\\begin{figure}[t]\\centering\n\\input{figures/f.tex}\n\\end{figure}\n"
            "\\begin{table}\\centering x\\end{table}\n"
            "\\begin{figure*}\n  \\centering\n  y\n\\end{figure*}"
        )

        out = without_lone_centering(text)

        assert "\\begin{figure}[t]\\input{figures/f.tex}" in out
        assert "\\begin{table}\\centering x" in out
        assert "\\begin{figure*}\n  y" in out

    def test_a_figure_left_open_is_left_alone(self):
        text = "\\begin{figure}\\centering x"

        assert without_lone_centering(text) == text


class TestRewrite:
    def test_markdown_and_fragments_are_left_alone(self, tmp_path):
        text = "\\begin{tabular}{p{2cm}}\\end{tabular}"

        assert rewrite(text, tmp_path / "a.md", "pdf", False) == text
        assert rewrite(text, tmp_path / "a.tex", "pdf", True) == text

    def test_every_format_gets_the_widths_and_only_latex_the_centering(self, tmp_path):
        text = "\\begin{tabular}{p{2cm}}\\end{tabular}\\begin{figure}\\centering x\\end{figure}"
        tex = tmp_path / "a.tex"

        docx = rewrite(text, tex, "docx", False)
        pdf = rewrite(text, tex, "pdf", False)

        assert "\\linewidth" in docx and "\\centering" in docx
        assert "\\linewidth" in pdf and "\\centering" not in pdf


class TestPreambleFile:
    def test_the_drafts_own_preamble_beats_the_shared_one(self, tmp_path):
        draft = tmp_path / "ch.tex"
        assert preamble_file(draft) is None

        (tmp_path / "preamble.tex").write_text("", encoding="utf-8")
        assert preamble_file(draft) == tmp_path / "preamble.tex"

        (tmp_path / "ch.preamble.tex").write_text("", encoding="utf-8")
        assert preamble_file(draft) == tmp_path / "ch.preamble.tex"


class TestPandocArgs:
    def test_markdown_and_fragments_get_none(self, tmp_path):
        assert pandoc_args(tmp_path / "a.md", "pdf", False) == []
        assert pandoc_args(tmp_path / "ch.tex", "pdf", True) == []

    def test_a_non_latex_format_gets_only_the_references_title(self, tmp_path):
        assert pandoc_args(tmp_path / "ch.tex", "md", False) == TITLE

    def test_a_latex_bound_format_reads_raw_tex_and_numbers_headings(self, tmp_path):
        args = pandoc_args(tmp_path / "ch.tex", "pdf", False)

        assert args == [*TITLE, "-f", "latex+raw_tex", "--number-sections"]

    def test_the_preamble_file_is_included_when_there_is_one(self, tmp_path):
        (tmp_path / "ch.preamble.tex").write_text("", encoding="utf-8")

        args = pandoc_args(tmp_path / "ch.tex", "tex", False)

        assert args[-2:] == ["--include-in-header", str(tmp_path / "ch.preamble.tex")]
