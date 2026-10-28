"""chitragupta/tex_engine.py: the one way this codebase starts a TeX
engine on draft text (#823, #1037).

TeX Live 2024 changed `openin_any=p` to restrict absolute paths to
TEXMFOUTPUT, which `luaotfload` trips over on every LuaLaTeX run (it opens
`ScriptExtensions.txt` by absolute path), and TeX Live 2026 drops the read
check altogether. So the fence that keeps a draft from reading a file
outside it is a LuaTeX `find_read_file` callback, loaded with `--lua`,
and `openin_any` is `r`. These tests pin both halves: what the engine is
told, and what a real engine then refuses.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta import tex_engine
from tests.conftest import lualatex_available

needs_lualatex = pytest.mark.skipif(not lualatex_available, reason="needs lualatex")


class TestWhatTheEngineIsTold:
    def test_reads_are_restricted_even_if_the_host_says_otherwise(self, monkeypatch):
        monkeypatch.setenv("openin_any", "a")
        assert tex_engine.engine_env()["openin_any"] == "r"

    def test_the_hosts_environment_still_reaches_the_engine(self, monkeypatch):
        monkeypatch.setenv("A_MARKER_ONLY_THE_HOST_SETS", "yes")
        assert tex_engine.engine_env()["A_MARKER_ONLY_THE_HOST_SETS"] == "yes"

    def test_extra_variables_are_merged_in(self):
        env = tex_engine.engine_env({"TEXINPUTS": "/d:"})
        assert env["TEXINPUTS"] == "/d:"
        assert env["openin_any"] == "r"

    def test_extra_variables_cannot_loosen_reads(self):
        assert tex_engine.engine_env({"openin_any": "a"})["openin_any"] == "r"

    def test_shell_escape_is_off_and_the_fence_is_loaded(self):
        opts = tex_engine.engine_opts()
        assert "-no-shell-escape" in opts
        fence = [o for o in opts if o.startswith("--lua=")]
        assert len(fence) == 1
        assert Path(fence[0].removeprefix("--lua=")).is_file()


def _compile(directory: Path, body: str) -> tuple[subprocess.CompletedProcess, str]:
    """`body` in a minimal LuaLaTeX document, run as the pipeline runs one:
    the main file named absolutely (as pandoc names `input.tex`), under
    `engine_env()` and `engine_opts()`."""
    main = directory / "doc.tex"
    main.write_text(
        "\\documentclass{article}\\usepackage{fontspec}\\usepackage{tikz}\n"
        f"\\begin{{document}}\n{body}\n\\end{{document}}\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            shutil.which("lualatex"),
            *tex_engine.engine_opts(),
            "-interaction=nonstopmode",
            str(main),
        ],
        cwd=directory,
        env=tex_engine.engine_env({"TEXINPUTS": f"{directory}{os.pathsep}"}),
        capture_output=True,
        text=True,
        check=False,
    )
    log = (directory / "doc.log").read_text(encoding="utf-8", errors="replace")
    return result, log


@needs_lualatex
class TestARealEngine:
    def test_a_document_with_the_render_s_fonts_compiles(self, tmp_path):
        """The regression: under `openin_any=p` on TeX Live 2025 this died
        in luaotfload's multiscript loader before TeX printed a line."""
        result, _ = _compile(tmp_path, "x \u2264 y")
        assert result.returncode == 0, result.stdout[-1500:]

    def test_a_figure_under_the_draft_still_loads(self, tmp_path):
        (tmp_path / "figures").mkdir()
        (tmp_path / "figures" / "x.tex").write_text("\\node (a) {FIGOK};\n", encoding="utf-8")
        result, _ = _compile(
            tmp_path,
            "\\begin{tikzpicture}\\input{figures/x}\\end{tikzpicture}\n"
            "\\begin{tikzpicture}\\input{./figures/x.tex}\\end{tikzpicture}",
        )
        assert result.returncode == 0, result.stdout[-1500:]

    def test_an_absolute_name_inside_the_compile_directory_loads(self, tmp_path):
        """pandoc copies a draft's images into its own temp directory and
        names them absolutely; `openin_any=p` admitted them through
        TEXMFOUTPUT, and the fence keeps that boundary."""
        (tmp_path / "x.tex").write_text("INSIDEOK\n", encoding="utf-8")
        result, _ = _compile(tmp_path, f"\\input{{{tmp_path / 'x.tex'}}}")
        assert result.returncode == 0, result.stdout[-1500:]

    def test_climbing_out_of_the_compile_directory_is_refused(self, tmp_path):
        (tmp_path / "secret.txt").write_text("TOPSECRETWORD\n", encoding="utf-8")
        draft = tmp_path / "draft"
        draft.mkdir()
        _, log = _compile(draft, f"\\input{{{draft}/../secret.txt}}")
        assert "chitragupta: refused TeX read of" in log
        assert "TOPSECRETWORD" not in log

    @pytest.mark.parametrize(
        "body",
        [
            "\\input{../secret.txt}",
            "\\input{SECRETABS}",
            "\\openin1=SECRETABS \\read1 to\\got \\typeout{GOT:\\got}",
        ],
    )
    def test_a_read_outside_the_draft_is_refused_and_logged(self, tmp_path, body):
        """The fence itself, and the sentinel for TeX Live 2026, where
        `openin_any` no longer refuses any read and this alone would."""
        secret = tmp_path / "secret.txt"
        secret.write_text("TOPSECRETWORD\n", encoding="utf-8")
        draft = tmp_path / "draft"
        draft.mkdir()
        _, log = _compile(draft, body.replace("SECRETABS", str(secret)))
        assert "chitragupta: refused TeX read of" in log
        assert "TOPSECRETWORD" not in log
