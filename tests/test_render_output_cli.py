"""chitragupta/render_output/_cli.py: the `python -m chitragupta.draft render` entry point.

Split from one test module to mirror `chitragupta/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `chitragupta/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

import argparse
import shutil
import sys
from pathlib import Path
import pytest
from chitragupta import render_output
from tests.conftest import content_draft
from tests.conftest import ASCII_FIGURE, MARKED_MD, MARKED_INPUT, TIKZ_FIGURE, figure_pair
from tests.conftest import pandoc_available, pdflatex_available, tikz_available


class TestMainCli:
    def test_an_unresolvable_display_equation_prints_and_returns_1(
        self, isolated_config, monkeypatch, capsys
    ):
        # A `<!-- math -->` marker with no mapping is certain, not
        # heuristic: the render would emit verbatim text where the author
        # said an equation goes. Non-zero, because a genre skill's
        # documented reaction to a warning is to carry on -- which would
        # ship exactly the defect §12 exists to prevent.
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("<!-- math -->\n```\ndW/dt = -W/tau\n```\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--format", "tex"])
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "[error]" in out
        assert "renamed or moved" in out

    def test_missing_binary_prints_and_returns_1(
        self, isolated_config, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("text\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft)])
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "[missing-binary]" in out

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available), reason="pandoc/pdflatex not installed"
    )
    def test_called_process_error_prints_and_returns_1(
        self, isolated_config, tmp_path, monkeypatch, capsys
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        # Malformed LaTeX documentclass argument to force pandoc to fail.
        monkeypatch.setattr(
            sys, "argv", ["render_output.py", str(draft), "--documentclass", "this is not valid \\"]
        )
        draft.write_text("text\n")
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "[error]" in out

    @pytest.mark.skipif(
        not (pandoc_available and pdflatex_available), reason="pandoc/pdflatex not installed"
    )
    def test_success_prints_output_path_and_returns_0(
        self, isolated_config, tmp_path, monkeypatch, capsys
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("# Title\n\nNo citations here.\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--format", "tex"])
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert str(isolated_config.RENDERED_DIR / "draft.tex") in out


class TestFormatArg:
    """`--format` takes one format, not a list. `--format md,tex,pdf`
    used to build the file extension from the whole string and write
    `<stem>.md,tex,pdf` -- exit 0, and no `.pdf` ever produced (#389)."""

    def test_a_single_format_passes_through(self):
        assert render_output._cli._format_arg("pdf") == "pdf"

    def test_a_comma_list_is_a_usage_error(self):
        with pytest.raises(argparse.ArgumentTypeError) as exc:
            render_output._cli._format_arg("md,tex,pdf")
        assert "md,tex,pdf" in str(exc.value)
        assert "--formats" in str(exc.value)

    def test_the_cli_rejects_a_comma_list_with_exit_code_2(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc:
            render_output._cli.main(["--format", "md,tex,pdf", str(tmp_path / "x.md")])
        assert exc.value.code == 2
        assert "md,tex,pdf" in capsys.readouterr().err


class TestFigureRepairHint:
    """A malformed TikZ figure fails the whole pdf, and pdflatex's error
    names a file without saying what to do about it."""

    def test_names_the_figure_and_points_at_draft_reviser(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text(MARKED_MD)
        hint = render_output._cli._figure_repair_hint(str(draft))
        assert "figures/fig1.tex" in hint
        assert "draft-reviser" in hint

    def test_a_draft_with_no_figure_gets_no_hint(self, tmp_path):
        # An unrelated pandoc failure must not send the user chasing a
        # figure that isn't there.
        draft = tmp_path / "draft.md"
        draft.write_text("# Title\n\nJust prose.\n")
        assert render_output._cli._figure_repair_hint(str(draft)) == ""

    def test_an_unreadable_input_gets_no_hint(self, tmp_path):
        assert render_output._cli._figure_repair_hint(str(tmp_path / "absent.md")) == ""


class TestFragmentOutput:
    """`--fragment` is what makes a unit assemblable into a book: no
    preamble to collide with the book's own, and its top heading becomes
    the book's chapter. Everything else -- citeproc, the IEEE style, the
    citekey aliasing -- is unchanged, which is the whole reason this
    lives here rather than being restated in the assembly skill."""

    def test_fragment_drops_standalone_and_makes_the_top_heading_a_chapter(self):
        cmd, _ = render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path("out.tex"),
            Path("in.md"),
            "tex",
            "article",
            "12pt",
            "a4",
            "1in",
            [],
            True,
        )
        assert "--standalone" not in cmd
        assert "--top-level-division=chapter" in cmd
        # Highlighted code would need `Shaded`/`Highlighting`, which only
        # the standalone template defines -- a fragment that emitted them
        # would fail to compile in the book that \input-s it.
        assert "--no-highlight" in cmd

    def test_a_normal_render_is_still_standalone(self):
        cmd, _ = render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path("out.tex"),
            Path("in.md"),
            "tex",
            "article",
            "12pt",
            "a4",
            "1in",
            [],
        )
        assert "--standalone" in cmd
        assert "--top-level-division=chapter" not in cmd

    def test_the_flag_reaches_render(self, monkeypatch, tmp_path):
        seen = {}
        monkeypatch.setattr(
            render_output,
            "render",
            lambda *args, **kwargs: seen.update(kwargs) or tmp_path / "out.tex",
        )
        assert (
            render_output._cli.main(["--fragment", "--format", "tex", str(tmp_path / "x.md")]) == 0
        )
        assert seen["fragment"] is True


class TestBreakableInlineCodeFilter:
    """A standalone render and a book-assembler `--fragment` render both
    build their pandoc argv from this one function, so wiring the filter
    in here -- rather than in either caller -- is what makes it reach
    every LaTeX/PDF render, not just the book path (docs/BOOKS.md)."""

    def test_the_filter_is_always_passed(self):
        cmd, _ = render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path("out.tex"),
            Path("in.md"),
            "tex",
            "article",
            "12pt",
            "a4",
            "1in",
            [],
        )
        assert "--lua-filter" in cmd
        filter_path = cmd[cmd.index("--lua-filter") + 1]
        assert Path(filter_path).name == "breakable_inline_code.lua"
        assert Path(filter_path).is_file()

    def test_a_fragment_render_also_gets_it(self):
        # `--lua-filter` lives in the base `cmd` list, before `shape`'s
        # fragment/standalone branch -- structurally guaranteed, but
        # worth pinning directly since a book unit's `--fragment` render
        # is exactly the case that carries no preamble to fall back on.
        cmd, _ = render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path("out.tex"),
            Path("in.md"),
            "tex",
            "article",
            "12pt",
            "a4",
            "1in",
            [],
            True,
        )
        assert "--lua-filter" in cmd


class TestOutputDirFlag:
    """`--output-dir` exposes the parameter `chitragupta/review/__init__.py`
    already passes programmatically. A book's units need it: `\\input`
    paths are relative to book.tex, so a fragment has to land in the
    book's own directory rather than in the mirrored render tree."""

    def test_the_flag_reaches_render(self, monkeypatch, tmp_path):
        seen = {}

        def fake_render(*args, **kwargs):
            seen["positional"] = args
            seen.update(kwargs)
            return tmp_path / "out.tex"

        monkeypatch.setattr(render_output, "render", fake_render)
        assert (
            render_output._cli.main(
                ["--format", "tex", "--output-dir", str(tmp_path), str(tmp_path / "x.md")]
            )
            == 0
        )
        assert str(tmp_path) in seen["positional"]
