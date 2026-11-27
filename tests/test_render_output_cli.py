import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
from chitragupta import render_output, tex_engine
from chitragupta.render_output._cli import _unicode_repair_hint
from tests.conftest import content_draft
from tests.conftest import MARKED_MD
from tests.conftest import lualatex_available, pandoc_available, pdflatex_available


class TestMainCli:
    def test_an_unresolvable_display_equation_prints_and_returns_1(
        self, isolated_config, monkeypatch, capsys
    ):
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
        not (pandoc_available and lualatex_available), reason="pandoc/lualatex not installed"
    )
    def test_called_process_error_prints_and_returns_1(
        self, isolated_config, tmp_path, monkeypatch, capsys
    ):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        monkeypatch.setattr(
            sys, "argv", ["render_output.py", str(draft), "--documentclass", "this is not valid \\"]
        )
        draft.write_text("text\n")
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "[error]" in out

    def test_an_unrelated_keyerror_is_not_swallowed(self, isolated_config, monkeypatch):
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("text\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft)])

        def _boom(*args, **kwargs):
            raise KeyError("not a citekey problem")

        monkeypatch.setattr(render_output, "render", _boom)
        with pytest.raises(KeyError, match="not a citekey problem"):
            render_output.main()

    def test_a_citekey_missing_from_the_ledger_prints_and_returns_1(
        self, isolated_config, ledger_con, monkeypatch, capsys
    ):
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("See [@fabricated2024].\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--format", "md"])
        rc = render_output.main()
        out = capsys.readouterr().out
        assert rc == 1
        assert "[error]" in out
        assert "fabricated2024" in out

    def test_a_key_that_leaves_the_ledger_mid_render_is_an_error_line(
        self, isolated_config, monkeypatch, capsys
    ):
        from chitragupta import reference_entries

        def _gone(*a, **k):
            raise reference_entries.MissingCitekey("citekey(s) cited ... missing: smith2024")

        monkeypatch.setattr(render_output, "render", _gone)
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("See [@smith2024].\n")
        monkeypatch.setattr(sys, "argv", ["render_output.py", str(draft), "--format", "md"])
        assert render_output.main() == 1
        assert "[error] citekey(s) cited ... missing: smith2024" in capsys.readouterr().out

    @pytest.mark.parametrize("fmt", ["docx", "pdf", "tex"])
    @pytest.mark.parametrize("fragment", [False, True])
    def test_every_format_refuses_an_unknown_key_before_pandoc(
        self, isolated_config, ledger_con, monkeypatch, capsys, fmt, fragment
    ):
        draft = content_draft(isolated_config, "drafts/bad.md")
        draft.write_text("A claim [@not_a_real_citekey_2026].\n")
        ran = []
        monkeypatch.setattr(render_output, "_run_pandoc", lambda *a, **k: ran.append(a))
        argv = ["render_output.py", str(draft), "--format", fmt]
        monkeypatch.setattr(sys, "argv", argv + (["--fragment"] if fragment else []))
        assert render_output.main() == 1
        out = capsys.readouterr().out
        assert "[error]" in out
        assert "not_a_real_citekey_2026" in out
        assert ran == []  # refused before pandoc, so it needs no pandoc to pass

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
    def test_names_the_figure_and_points_at_draft_reviser(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text(MARKED_MD)
        hint = render_output._cli._figure_repair_hint(str(draft))
        assert "figures/fig1.tex" in hint
        assert "draft-reviser" in hint

    def test_a_draft_with_no_figure_gets_no_hint(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("# Title\n\nJust prose.\n")
        assert render_output._cli._figure_repair_hint(str(draft)) == ""

    def test_an_unreadable_input_gets_no_hint(self, tmp_path):
        assert render_output._cli._figure_repair_hint(str(tmp_path / "absent.md")) == ""


class TestFragmentOutput:
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
        assert "--no-highlight" in cmd

    def test_fragment_defers_citations_to_natbib_instead_of_resolving_them(self):
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
        assert "--natbib" in cmd
        assert "--citeproc" not in cmd
        assert "--csl" not in cmd
        assert "--bibliography" in cmd, "bibtex still needs to be told which .bib"

    def test_a_normal_render_still_resolves_with_citeproc_and_the_csl(self):
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
            False,
        )
        assert "--citeproc" in cmd and "--csl" in cmd
        assert "--natbib" not in cmd

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
        paths = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--lua-filter"]
        breakable = [p for p in paths if Path(p).name == "breakable_inline_code.lua"]
        assert len(breakable) == 1
        assert Path(breakable[0]).is_file()

    def test_a_fragment_render_also_gets_it(self):
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


class TestBreakableCodeBlocks:
    def _cmd(self, figure_refs, has_code_block):
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
            figure_refs,
            False,
            has_code_block,
        )
        return cmd

    def _header_includes(self, cmd):
        return [
            cmd[i + 1]
            for i, flag in enumerate(cmd)
            if flag == "--variable"
            and cmd[i + 1].startswith("header-includes")
            and "LTcapwidth" not in cmd[i + 1]
        ]

    def test_a_draft_with_a_code_block_loads_fvextra(self):
        includes = self._header_includes(self._cmd([], True))
        assert len(includes) == 1
        assert r"\usepackage{fvextra}" in includes[0]
        assert "{verbatim}{Verbatim}{breaklines}" in includes[0]
        assert r"{Highlighting}{Verbatim}{commandchars=\\\{\},breaklines}" in includes[0]

    def test_a_draft_with_no_code_block_does_not(self):
        assert self._header_includes(self._cmd([], False)) == []

    def test_a_draft_with_both_a_figure_and_a_code_block_gets_both(self):
        includes = self._header_includes(self._cmd(["figures/fig1.tex"], True))
        assert len(includes) == 2
        assert any(r"\usepackage{tikz}" in inc for inc in includes)
        assert any(r"\usepackage{fvextra}" in inc for inc in includes)


class TestTikzLibraryPreamble:
    def _header_includes(self, cmd):
        return [
            cmd[i + 1]
            for i, flag in enumerate(cmd)
            if flag == "--variable"
            and cmd[i + 1].startswith("header-includes")
            and "LTcapwidth" not in cmd[i + 1]
        ]

    def _cmd(self, tmp_path, figures, fragment=False):
        (tmp_path / "figures").mkdir(exist_ok=True)
        for name, body in figures:
            (tmp_path / "figures" / name).write_text(body, encoding="utf-8")
        cmd, _ = render_output._pandoc_command(
            tmp_path / "in.md",
            Path("bib.bib"),
            Path("ieee.csl"),
            tmp_path / "out.tex",
            tmp_path / "in.md",
            "tex",
            "article",
            "12pt",
            "a4",
            "1in",
            [f"figures/{name}" for name, _ in figures],
            fragment,
            False,
        )
        return cmd

    _POSITIONING = "\\usetikzlibrary{positioning}\n\\begin{tikzpicture}\\end{tikzpicture}\n"
    _FIT = "\\usetikzlibrary{fit}\n\\begin{tikzpicture}\\end{tikzpicture}\n"
    _BARE = "\\begin{tikzpicture}\\draw (0,0) circle (1);\\end{tikzpicture}\n"

    def test_the_union_is_loaded_after_the_package(self, tmp_path):
        cmd = self._cmd(tmp_path, [("a.tex", self._POSITIONING), ("b.tex", self._FIT)])
        assert self._header_includes(cmd) == [
            r"header-includes=\usepackage{tikz}\usetikzlibrary{fit,positioning}"
        ]

    def test_a_figure_with_no_library_gets_no_call(self, tmp_path):
        assert self._header_includes(self._cmd(tmp_path, [("a.tex", self._BARE)])) == [
            r"header-includes=\usepackage{tikz}"
        ]

    def test_a_draft_with_no_figure_loads_nothing(self, tmp_path):
        assert self._header_includes(self._cmd(tmp_path, [])) == []

    def test_one_variable_not_two(self, tmp_path):
        cmd = self._cmd(tmp_path, [("a.tex", self._POSITIONING)])
        assert len(self._header_includes(cmd)) == 1

    def test_a_fragment_reports_the_union_it_cannot_load(self, tmp_path, capsys):
        self._cmd(
            tmp_path,
            [("a.tex", self._POSITIONING), ("b.tex", self._FIT)],
            fragment=True,
        )
        err = capsys.readouterr().err
        assert err.count("[tikz-libraries]") == 1
        assert "[tikz-libraries] fit,positioning" in err

    def test_a_standalone_render_reports_nothing(self, tmp_path, capsys):
        self._cmd(tmp_path, [("a.tex", self._POSITIONING)])
        assert "[tikz-libraries]" not in capsys.readouterr().err

    def test_a_fragment_whose_figures_load_nothing_reports_nothing(self, tmp_path, capsys):
        self._cmd(tmp_path, [("a.tex", self._BARE)], fragment=True)
        assert "[tikz-libraries]" not in capsys.readouterr().err

    def test_a_docx_fragment_reports_nothing(self, tmp_path, capsys):
        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "a.tex").write_text(self._POSITIONING, encoding="utf-8")
        render_output._pandoc_command(
            tmp_path / "in.md",
            Path("bib.bib"),
            Path("ieee.csl"),
            tmp_path / "out.docx",
            tmp_path / "in.md",
            "docx",
            "article",
            "12pt",
            "a4",
            "1in",
            ["figures/a.tex"],
            True,
            False,
        )
        assert "[tikz-libraries]" not in capsys.readouterr().err


class TestPdfEngineHardening:
    def _cmd(self, output_format):
        return render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path(f"out.{output_format}"),
            Path("in.md"),
            output_format,
            "article",
            "12pt",
            "a4",
            "1in",
            [],
            False,
            False,
        )

    def test_a_pdf_render_turns_shell_escape_off(self):
        cmd, _ = self._cmd("pdf")
        assert "--pdf-engine-opt=-no-shell-escape" in cmd

    def test_a_pdf_render_runs_lualatex_and_no_other_engine(self):
        cmd, _ = self._cmd("pdf")
        engines = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--pdf-engine"]
        assert engines == ["lualatex"]

    def test_a_pdf_render_runs_the_engine_behind_the_read_fence(self):
        cmd, env = self._cmd("pdf")
        assert env["openin_any"] == "r"
        assert f"--pdf-engine-opt=--lua={tex_engine.READ_FENCE}" in cmd
        assert "--pdf-engine-opt=-no-shell-escape" in cmd

    def test_a_pdf_render_includes_the_strict_glyph_and_font_header_last(self):
        cmd, _ = self._cmd("pdf")
        assert not any(v.startswith("mainfontfallback=") for v in cmd)
        assert not any(v.startswith("mainfont=") for v in cmd)
        headers = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--include-in-header"]
        assert headers[-1].endswith("chitragupta-lualatex.tex")

    def test_the_sty_directory_is_not_on_a_pdf_render_s_search_path(self):
        _, env = self._cmd("pdf")
        assert env["TEXINPUTS"] == f"{Path('in.md').resolve().parent}{os.pathsep}"

    def test_texinputs_ends_in_the_hosts_own_path_separator(self, monkeypatch):
        monkeypatch.setattr(os, "pathsep", ";")
        _, env = self._cmd("pdf")
        assert env["TEXINPUTS"] == f"{Path('in.md').resolve().parent};"

    def test_the_hosts_own_openin_any_does_not_win(self, monkeypatch):
        monkeypatch.setenv("openin_any", "a")
        _, env = self._cmd("pdf")
        assert env["openin_any"] == "r"

    @pytest.mark.parametrize("output_format", ["html", "docx", "tex"])
    def test_a_format_that_runs_no_engine_is_untouched(self, output_format):
        cmd, env = self._cmd(output_format)
        assert env is None
        assert not any(flag.startswith("--pdf-engine") for flag in cmd)
        assert not any(arg.startswith("mainfont") for arg in cmd)

    def test_pandoc_itself_is_not_sandboxed(self):
        for output_format in ("pdf", "docx"):
            cmd, _ = self._cmd(output_format)
            assert "--sandbox" not in cmd


class TestRequirePdfToolchain:
    def _which(self, monkeypatch, present):
        monkeypatch.setattr(
            render_output._pandoc.programs,
            "resolve_program",
            lambda b: f"/usr/bin/{b}" if b in present else None,
        )

    def _kpsewhich(self, monkeypatch, returncode):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, returncode, stdout=b"", stderr=b"")

        monkeypatch.setattr(render_output._pandoc.subprocess, "run", fake_run)
        return calls

    def test_no_lualatex_is_a_missing_binary(self, monkeypatch):
        self._which(monkeypatch, {"kpsewhich"})
        with pytest.raises(render_output.MissingBinary, match="lualatex"):
            render_output._pandoc._require_pdf_toolchain()

    def test_no_font_loader_names_the_package(self, monkeypatch):
        self._which(monkeypatch, {"lualatex", "kpsewhich"})
        calls = self._kpsewhich(monkeypatch, 1)
        with pytest.raises(render_output.MissingBinary, match="texlive-luatex"):
            render_output._pandoc._require_pdf_toolchain()
        assert calls == [["/usr/bin/kpsewhich", "luaotfload.sty"]]

    def test_a_complete_toolchain_passes(self, monkeypatch):
        self._which(monkeypatch, {"lualatex", "kpsewhich"})
        self._kpsewhich(monkeypatch, 0)
        render_output._pandoc._require_pdf_toolchain()  # must not raise

    def test_a_missing_required_font_refuses_before_pandoc_runs(self, monkeypatch):
        self._which(monkeypatch, {"lualatex", "kpsewhich", "luaotfload-tool"})
        self._kpsewhich(monkeypatch, 0)
        monkeypatch.setattr(
            render_output._pandoc.pdf_fonts,
            "font_installed",
            lambda name: name != "STIX Two Math",
        )
        with pytest.raises(render_output.MissingBinary, match="STIX Two Math") as exc:
            render_output._pandoc._require_pdf_toolchain()
        assert "STIX Two Text" not in str(exc.value)
        assert "chitragupta install os-deps" in str(exc.value)

    def test_every_required_font_present_passes(self, monkeypatch):
        self._which(monkeypatch, {"lualatex", "kpsewhich", "luaotfload-tool"})
        self._kpsewhich(monkeypatch, 0)
        asked = []
        monkeypatch.setattr(
            render_output._pandoc.pdf_fonts,
            "font_installed",
            lambda name: asked.append(name) or True,
        )
        render_output._pandoc._require_pdf_toolchain()
        assert asked == list(render_output._pandoc.pdf_fonts.REQUIRED_FONTS)

    def test_a_host_with_no_kpsewhich_is_not_second_guessed(self, monkeypatch):
        self._which(monkeypatch, {"lualatex"})
        calls = self._kpsewhich(monkeypatch, 1)
        render_output._pandoc._require_pdf_toolchain()
        assert calls == []


class TestTexReadableTmpdir:
    def test_a_dot_directory_in_the_temp_path_is_named(self, tmp_path, monkeypatch):
        dotted = tmp_path / ".cache" / "tmp"
        dotted.mkdir(parents=True)
        monkeypatch.setattr(render_output._pandoc.tempfile, "tempdir", str(dotted))
        with pytest.raises(render_output.MissingBinary, match="TMPDIR"):
            render_output._pandoc._require_tex_readable_tmpdir()

    def test_an_ordinary_temp_path_passes(self, tmp_path, monkeypatch):
        plain = tmp_path / "tmp"
        plain.mkdir()
        monkeypatch.setattr(render_output._pandoc.tempfile, "tempdir", str(plain))
        render_output._pandoc._require_tex_readable_tmpdir()  # must not raise


class TestLongtableCaptionWidth:
    def _includes(self, output_format):
        cmd, _ = render_output._pandoc_command(
            Path("in.md"),
            Path("bib.bib"),
            Path("ieee.csl"),
            Path(f"out.{output_format}"),
            Path("in.md"),
            output_format,
            "article",
            "12pt",
            "a4",
            "1in",
            [],
            False,
            False,
        )
        return [
            cmd[i + 1]
            for i, flag in enumerate(cmd)
            if flag == "--variable" and cmd[i + 1].startswith("header-includes")
        ]

    @pytest.mark.parametrize("output_format", ["tex", "latex", "pdf"])
    def test_a_latex_bound_render_widens_the_caption(self, output_format):
        includes = self._includes(output_format)
        assert len(includes) == 1
        assert r"\setlength{\LTcapwidth}{\textwidth}" in includes[0]

    def test_the_setlength_is_guarded(self):
        assert self._includes("tex")[0].startswith(r"header-includes=\ifdefined\LTcapwidth")

    @pytest.mark.parametrize("output_format", ["html", "docx", "md"])
    def test_a_non_latex_render_gets_nothing(self, output_format):
        assert self._includes(output_format) == []


class TestHasCodeBlock:
    def test_a_markdown_fence(self):
        assert render_output._has_code_block("# T\n\n```\nx\n```\n") is True

    def test_a_tilde_fence(self):
        assert render_output._has_code_block("# T\n\n~~~\nx\n~~~\n") is True

    def test_a_latex_verbatim_environment(self):
        assert render_output._has_code_block("\\begin{verbatim}\nx\n\\end{verbatim}\n") is True

    def test_prose_alone(self):
        assert render_output._has_code_block("# T\n\nJust prose with `a span`.\n") is False

    def test_an_unterminated_fence_still_loads_it(self):
        assert render_output._has_code_block("# T\n\n```\nx\n") is True


class TestOutputDirFlag:
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


class TestUnicodeRepairHint:
    _LUALATEX = (
        "! Missing character: There is no \U0002fffd (U+2FFFD) in font "
        "STIXTwoText:mode=node;script=latn;language=dflt;+tlig; or any of its fallbacks.\n"
        "<argument> ...not:N \\tex_shipout:D"
    )

    def test_names_the_character_and_both_fixes(self):
        hint = _unicode_repair_hint(self._LUALATEX)
        assert hint.startswith("\n[unicode] ")
        assert "\U0002fffd (U+2FFFD)" in hint
        assert "the first such character" in hint
        assert "unicode-extra.tex" in hint
        assert "\\DeclareUnicodeCharacter{2FFFD}" in hint

    def test_pdflatexs_own_message_is_not_what_a_render_prints_any_more(self):
        assert _unicode_repair_hint("! LaTeX Error: Unicode character ☃ (U+2603)") == ""

    @pytest.mark.parametrize("stderr", [None, "", "! Undefined control sequence."])
    def test_says_nothing_about_another_failure(self, stderr):
        assert _unicode_repair_hint(stderr) == ""
