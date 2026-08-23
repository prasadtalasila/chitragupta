"""chitragupta/render_output/_cli.py: the `python -m chitragupta.draft render` entry point.

Split from one test module to mirror `chitragupta/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `chitragupta/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

import shutil
import sys
from pathlib import Path
import pytest
from chitragupta import render_output
from tests.conftest import content_draft
from tests.conftest import ASCII_FIGURE, MARKED_MD, MARKED_INPUT, TIKZ_FIGURE, figure_pair
from tests.conftest import pandoc_available, pdflatex_available, tikz_available


class TestMainCli:
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
