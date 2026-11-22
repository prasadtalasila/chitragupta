"""A `.tex` draft's own preview shows what the thesis will show (#1164,
#1120): its figures, its table widths, numbered headings for `\\ref`, a
references heading, and the author's preamble file.

The rewrite and the pandoc arguments are tested here without pandoc; the
renders that need it are skipped where it is missing.
"""

import re
import subprocess

import pytest

from chitragupta import config, ledger, render_output
from chitragupta.render_output._tex_preview import (
    pandoc_args,
    preamble_file,
    rewrite,
    undefined_command_hint,
    widths_as_fractions,
    without_grouped_declarations,
)

from tests.conftest import (
    add_citable,
    figure_pair,
    lualatex_available,
    needs_tikz,
    pandoc_available,
)

TITLE = ["--metadata", "reference-section-title=References"]

needs_pandoc = pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
needs_lualatex = pytest.mark.skipif(
    not (pandoc_available and lualatex_available), reason="pandoc/lualatex not installed"
)

FIGURE = (
    "\\section{A}\n\\begin{figure}[t]\\centering\n\\input{figures/fig1.tex}\n"
    "\\caption{C.}\\label{fig:c}\n\\end{figure}\n"
)
# Issue 1120's reproduction, without its citation.
CHAPTER = (
    "\\chapter{Background}\\label{ch:bg}\n\n\\section{Framing}\\label{sec:framing}\n"
    "Prior surveys group the frameworks by purpose.\n\n"
    "\\section{Method}\\label{sec:method}\n"
    "Section~\\ref{sec:framing} sets out the grouping this section uses.\n"
)
TABLE = (
    "\\begin{tabular}{p{2.6cm}p{4.5cm}p{6cm}}\n"
    "A & B & a long cell that should wrap across several lines \\\\\n\\end{tabular}\n"
)


def _draft(cfg, name, text):
    """A draft under `content/drafts/`, with an empty bibliography."""
    if not cfg.BIB_FILE_PATH.exists():
        cfg.BIB_FILE_PATH.write_text("", encoding="utf-8")
    cfg.DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    path = cfg.DRAFTS_DIR / name
    path.write_text(text, encoding="utf-8")
    return path


def _tex(cfg, name, text, **kwargs):
    out = render_output.render(str(_draft(cfg, name, text)), output_format="tex", **kwargs)
    return out.read_text(encoding="utf-8")


class TestWidths:
    def test_absolute_widths_become_fractions_of_the_text_width(self):
        spec = "\\begin{tabular}{p{2.6cm}p{4.5cm}p{6cm}}\nA & B & C \\\\\n\\end{tabular}"

        out = widths_as_fractions(spec, 452.97)

        assert "{p{0.1633\\linewidth}p{0.2827\\linewidth}p{0.3769\\linewidth}}" in out

    def test_relative_widths_and_cell_text_are_left_alone(self):
        text = (
            "\\begin{tabular}{p{0.2\\linewidth}l}\n\\parbox{2cm}{x} & "
            "\\rule{3cm}{1pt} \\\\\n\\end{tabular}"
        )

        assert widths_as_fractions(text, 452.97) == text

    def test_tabularx_and_longtable_specs_are_read_after_their_arguments(self):
        tabularx = "\\begin{tabularx}{\\linewidth}[t]{p{1in}p{1in}}\\end{tabularx}"
        longtable = "\\begin{longtable}[c]{m{10mm}b{72.27pt}}\\end{longtable}"

        assert "{p{0.1595\\linewidth}p{0.1595\\linewidth}}" in widths_as_fractions(tabularx, 452.97)
        assert "{m{0.0628\\linewidth}b{0.1595\\linewidth}}" in widths_as_fractions(
            longtable, 452.97
        )

    def test_a_spec_mixing_in_an_unsized_column_is_left_alone(self):
        """pandoc gives an `l`, `c` or `r` column zero width once any other
        column has one, so `lp{6cm}` would print its first column a
        letter wide (measured); left as `ll`, it stays readable."""
        for spec in ("{lp{6cm}}", "{|p{2cm}|>{\\raggedright\\arraybackslash}p{3cm}|c|}"):
            text = f"\\begin{{tabular}}{spec}\\end{{tabular}}"
            assert widths_as_fractions(text, 452.97) == text

    def test_a_decorated_all_paragraph_spec_is_rewritten(self):
        text = (
            "\\begin{tabular}{|>{\\raggedright\\arraybackslash}p{2.6cm}|@{}p{1in}|}\\end{tabular}"
        )

        out = widths_as_fractions(text, 452.97)

        assert "p{0.1633\\linewidth}" in out and "p{0.1595\\linewidth}" in out

    def test_a_repeated_column_spec_is_left_alone(self):
        text = "\\begin{tabular}{*{3}{p{2cm}}}\\end{tabular}"

        assert widths_as_fractions(text, 452.97) == text

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


class TestDeclarations:
    """Under `raw_tex` an alignment or size declaration pandoc does not
    keep inside its group reaches the page bare and changes every later
    paragraph; one inside a figure splits it into half-width minipages
    (all measured, pandoc 3.1.11). Only grouped ones go: a top-level one
    changes the rest of the thesis too, so the preview keeps it."""

    def test_a_floats_centering_and_size_are_dropped(self):
        text = (
            "\\begin{figure}[t]\\centering\n\\input{figures/f.tex}\n\\end{figure}\n"
            "\\begin{table}[h]\n\\centering\\small\n\\caption{T.}\\end{table}\n"
        )

        out = without_grouped_declarations(text)

        assert "\\begin{figure}[t]\n\\input{figures/f.tex}" in out
        assert "\\begin{table}[h]\n\n\\caption{T.}" in out
        assert "\\small" not in out

    def test_a_brace_group_or_center_block_loses_its_centering(self):
        text = "{\\centering a line\\par}\n\\begin{center}\\centering z\\end{center}"

        out = without_grouped_declarations(text)

        assert out == "{a line\\par}\n\\begin{center}z\\end{center}"

    def test_a_top_level_declaration_stays(self):
        text = "\\small Text.\n\\centering More."

        assert without_grouped_declarations(text) == text

    def test_a_commented_declaration_is_left_and_the_next_line_kept(self):
        """A `% \\centering` once ate its newline and commented out the
        `\\input` below it, so the figure vanished again."""
        text = "\\begin{figure}\n% \\centering\n\\input{figures/fig1.tex}\n\\end{figure}"

        assert without_grouped_declarations(text) == text

    def test_an_escaped_brace_and_a_longer_name_are_text(self):
        text = "\\begin{figure}\\{ \\centeringx \\% \\centering\n\\end{figure}"

        assert without_grouped_declarations(text) == (
            "\\begin{figure}\\{ \\centeringx \\% \n\\end{figure}"
        )


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

    def test_a_preamble_symlinked_out_of_the_drafts_directory_is_refused(self, tmp_path):
        """pandoc reads the file it is handed with no fence, and inlines it
        into the preview's preamble, so `ch.preamble.tex -> ~/.netrc`
        would carry that file into the pdf (the figures' #823 rule)."""
        outside = tmp_path / "outside.tex"
        outside.write_text("NOT-FOR-THE-PDF\n", encoding="utf-8")
        drafts = tmp_path / "drafts"
        drafts.mkdir()
        (drafts / "ch.preamble.tex").symlink_to(outside)

        with pytest.raises(config.OutsideContentDir, match="ch.preamble.tex"):
            preamble_file(drafts / "ch.tex")

    def test_a_symlink_inside_the_directory_is_followed(self, tmp_path):
        (tmp_path / "shared.tex").write_text("", encoding="utf-8")
        (tmp_path / "preamble.tex").symlink_to(tmp_path / "shared.tex")

        assert preamble_file(tmp_path / "ch.tex") == tmp_path / "preamble.tex"


class TestPandocArgs:
    def test_markdown_and_fragments_get_none(self, tmp_path):
        assert pandoc_args(tmp_path / "a.md", "pdf", False) == []
        assert pandoc_args(tmp_path / "ch.tex", "pdf", True) == []

    def test_a_non_latex_format_gets_only_the_references_title(self, tmp_path):
        assert pandoc_args(tmp_path / "ch.tex", "md", False) == TITLE

    def test_a_latex_bound_format_reads_raw_tex_and_numbers_headings(self, tmp_path):
        args = pandoc_args(tmp_path / "ch.tex", "pdf", False)

        assert args == [*TITLE, "-f", "latex+raw_tex", "--number-sections"]

    def test_the_preamble_file_is_included_and_named(self, tmp_path, capsys):
        """Named, so a shared `preamble.tex` the draft never asked for
        is not loaded silently."""
        (tmp_path / "ch.preamble.tex").write_text("", encoding="utf-8")

        args = pandoc_args(tmp_path / "ch.tex", "tex", False)

        assert args[-2:] == ["--include-in-header", str(tmp_path / "ch.preamble.tex")]
        assert f"[preamble] {tmp_path / 'ch.preamble.tex'}" in capsys.readouterr().err


@needs_pandoc
class TestTheTexRender:
    """The rendered `.tex` of a `.tex` draft, read directly (#1164, #1120)."""

    def test_a_tex_drafts_figure_reaches_the_tex_output(self, isolated_config):
        figure_pair(isolated_config.DRAFTS_DIR)

        tex = _tex(isolated_config, "fig.tex", FIGURE)

        assert "\\input{figures/fig1.tex}" in tex
        assert "minipage" not in tex

    def test_a_tex_drafts_ref_is_left_to_latex_and_headings_are_numbered(self, isolated_config):
        tex = _tex(isolated_config, "th.tex", CHAPTER)

        assert "\\ref{sec:framing}" in tex
        assert "hyperref[sec:framing]" not in tex
        assert "secnumdepth}{-\\maxdimen}" not in tex

    def test_a_tex_drafts_absolute_widths_survive_as_fractions(self, isolated_config):
        tex = _tex(isolated_config, "t.tex", TABLE)

        assert "@{}lll@{}" not in tex
        assert "\\real{0.1633}" in tex

    def test_a_tex_drafts_reference_list_has_a_heading(self, isolated_config):
        con = ledger.connect()
        add_citable(con, "smith_2024", title="An Example Paper", year="2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_2024,\n  author={Smith, Jane},\n  title={An Example Paper},\n"
            "  journal={J. Examples},\n  year={2024},\n}\n",
            encoding="utf-8",
        )

        tex = _tex(isolated_config, "c.tex", "\\section{A}\nA claim~\\citep{smith_2024}.\n")

        heading = re.search(r"\\(?:sub)*section\*?\{References\}", tex)
        assert heading is not None
        assert heading.start() < tex.index("\\begin{CSLReferences}")

    def test_a_markdown_draft_and_a_fragment_render_as_before(self, isolated_config):
        markdown = _tex(isolated_config, "m.md", "# A\n\nSee [the method](#b).\n\n# B\n")
        fragment = _tex(isolated_config, "f.tex", CHAPTER, fragment=True)

        assert "secnumdepth}{-\\maxdimen}" in markdown
        assert "reference-section-title" not in markdown and "References" not in markdown
        assert "hyperref[sec:framing]" in fragment
        assert "References" not in fragment


@needs_lualatex
@pytest.mark.slow
class TestThePdfRender:
    @needs_tikz
    def test_a_tex_drafts_pdf_renders_with_its_figure(self, isolated_config):
        figure_pair(isolated_config.DRAFTS_DIR)
        draft = _draft(isolated_config, "fig.tex", FIGURE)

        assert render_output.render(str(draft), output_format="pdf").exists()

    def test_the_read_fence_still_refuses_an_input_outside_the_draft(self, isolated_config):
        draft = _draft(isolated_config, "esc.tex", "\\section{A}\n\\input{/etc/hostname}\n")

        with pytest.raises(subprocess.CalledProcessError):
            render_output.render(str(draft), output_format="pdf")

    def test_a_thesis_macro_renders_once_the_preamble_defines_it(self, isolated_config):
        draft = _draft(isolated_config, "mac.tex", "\\section{A}\nText \\todo{fix this}.\n")
        with pytest.raises(subprocess.CalledProcessError):
            render_output.render(str(draft), output_format="pdf")

        (isolated_config.DRAFTS_DIR / "mac.preamble.tex").write_text(
            "\\newcommand{\\todo}[1]{}\n", encoding="utf-8"
        )

        assert render_output.render(str(draft), output_format="pdf").exists()


class TestUndefinedCommandHint:
    """A `.tex` preview reads raw TeX, so a command only the thesis's
    preamble defines stops the pdf; the hint names the command and the
    file that would define it. The logs are LuaLaTeX's own."""

    _TODO = "! Undefined control sequence.\nl.4 Plain \\todo\n                       {} here.\n"
    # `\todo` defined, `\citep` not: TeX shows the argument's context
    # first, before the `l.` line.
    _CITE = (
        "! Undefined control sequence.\n<argument> see \\citep \n           {k}\n"
        "l.2 Text \\todo{see \\citep{k}}\n                            more.\n"
    )

    def test_names_the_command_and_the_drafts_preamble_file(self, tmp_path):
        hint = undefined_command_hint(self._TODO, str(tmp_path / "ch.tex"))

        assert hint.startswith("\n[preamble] ")
        assert "\\todo" in hint
        assert str(tmp_path / "ch.preamble.tex") in hint
        assert "preamble.tex beside the draft" in hint
        assert "an agent reports this line and leaves the file alone" in hint

    def test_a_citation_inside_a_raw_command_is_told_to_move(self, tmp_path):
        hint = undefined_command_hint(self._CITE, str(tmp_path / "ch.tex"))

        assert "\\citep" in hint
        assert "move the citation out" in hint
        assert "preamble.tex" not in hint

    def test_without_a_context_line_the_file_is_still_named(self, tmp_path):
        hint = undefined_command_hint("! Undefined control sequence.", str(tmp_path / "ch.tex"))

        assert "the undefined command" in hint
        assert str(tmp_path / "ch.preamble.tex") in hint

    @pytest.mark.parametrize(
        ("stderr", "name"),
        [(_TODO, "x.md"), (None, "ch.tex"), ("", "ch.tex"), ("! Missing $ inserted.", "ch.tex")],
    )
    def test_says_nothing_for_markdown_or_another_failure(self, tmp_path, stderr, name):
        assert undefined_command_hint(stderr, str(tmp_path / name)) == ""
