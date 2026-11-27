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


@pytest.mark.slow
@needs_lualatex
class TestARealEngine:
    def test_a_document_with_the_render_s_fonts_compiles(self, tmp_path):
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
        secret = tmp_path / "secret.txt"
        secret.write_text("TOPSECRETWORD\n", encoding="utf-8")
        draft = tmp_path / "draft"
        draft.mkdir()
        _, log = _compile(draft, body.replace("SECRETABS", str(secret)))
        assert "chitragupta: refused TeX read of" in log
        assert "TOPSECRETWORD" not in log
