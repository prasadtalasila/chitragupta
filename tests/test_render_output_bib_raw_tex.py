import json
import subprocess
import unicodedata
from pathlib import Path

import pytest

from chitragupta import config, ledger, render_output
from tests.conftest import (
    add_citable,
    content_draft,
    lualatex_available,
    pandoc_available,
    pdf_text,
    pdftotext_available,
)

_FILTER = "bib_raw_tex_as_text.lua"
_SECRET = "NOTFORTHEPDF"  # letters only: survives math italic recognisably


def _leaked(pdf) -> bool:
    folded = unicodedata.normalize("NFKD", pdf_text(pdf))
    return _SECRET in "".join(ch for ch in folded if ch.isalnum())


def _cited_draft(isolated_config, title: str) -> Path:
    con = ledger.connect()
    add_citable(con, "smith_2024", title="An Example Paper", year="2024")
    con.close()
    isolated_config.BIB_FILE_PATH.write_text(
        f"@article{{smith_2024,\n  title={{{title}}},\n  year={{2024}},\n}}\n",
        encoding="utf-8",
    )
    draft = content_draft(isolated_config, "draft.md")
    draft.write_text("# Title\n\nSome claim [@smith_2024].\n", encoding="utf-8")
    return draft


class TestArgv:
    def _cmd(self, fragment):
        cmd, _ = render_output._pandoc_command(
            Path("in.md"), Path("bib.bib"), Path("ieee.csl"), Path("out.pdf"), Path("in.md"),
            "pdf", "article", "12pt", "a4", "1in", [], fragment, False,
        )  # fmt: skip
        return cmd

    def test_the_filter_runs_before_citeproc_and_before_breakable_code(self):
        cmd = self._cmd(False)
        filters = [i for i, arg in enumerate(cmd) if arg.endswith(_FILTER)]
        assert len(filters) == 1
        breakable = next(
            i for i, arg in enumerate(cmd) if arg.endswith("breakable_inline_code.lua")
        )
        assert filters[0] < cmd.index("--citeproc") < breakable

    def test_a_fragment_has_no_reference_list_to_rewrite(self):
        assert not any(arg.endswith(_FILTER) for arg in self._cmd(True))


_BIB_FILTER = ["--lua-filter", str(config.shipped("assets", "pandoc", _FILTER))]
_BREAKABLE = ["--lua-filter", str(config.shipped("assets", "pandoc", "breakable_inline_code.lua"))]


def _latex_of(tmp_path, title, bib_filter, body="See [@smith_2024].\n"):
    (tmp_path / "x.bib").write_text(
        f"@article{{smith_2024,\n  title={{{title}}},\n"
        '  author={M{\\"u}ller, J{\\"o}rg},\n  year={2024},\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "x.md").write_text(body, encoding="utf-8")
    cmd = [
        "pandoc", "x.md", *(_BIB_FILTER if bib_filter else []), "--citeproc",
        "--csl", str(config.shipped("assets", "csl", "ieee.csl")),
        "--bibliography", "x.bib", "-t", "latex", *_BREAKABLE,
    ]  # fmt: skip
    return subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=True).stdout


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_the_bib_filter_is_a_no_op_on_a_normal_entry(tmp_path):
    title = (
        "{\\\"U}ber $\\alpha \\leq \\beta$ and \\emph{L\\'evy} flights in"
        " H$_2$O, see \\texttt{src/main.py} and {CO}\\textsubscript{2}"
    )
    breakable_only = _latex_of(tmp_path, title, bib_filter=False)
    assert "Müller" in breakable_only and "\\alpha" in breakable_only  # the fixture parsed
    assert "penalty0" in breakable_only  # the \texttt was split, a real break
    assert _latex_of(tmp_path, title, bib_filter=True) == breakable_only


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_a_directlua_inside_math_is_turned_to_text(tmp_path):
    latex = _latex_of(
        tmp_path,
        'Flow at $\\directlua{tex.print("X")}$ and $\\alpha \\leq \\beta$',
        bib_filter=True,
    )
    assert "\\(\\directlua" not in latex and "$\\directlua" not in latex
    assert "directlua" in latex  # present, but as escaped text
    assert "\\(\\alpha \\leq \\beta\\)" in latex  # real math untouched


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_the_authors_own_citation_prefix_and_suffix_are_left_alone(tmp_path):
    latex = _latex_of(
        tmp_path,
        'Flow \\directlua{tex.print("X")} here',
        bib_filter=True,
        body="See [\\emph{cf.} @smith_2024, eq. $\\alpha$; \\textbf{also}].\n",
    )
    assert "\\emph{cf.}" in latex and "\\textbf{also}" in latex
    assert "\\(\\alpha\\)" in latex
    assert "textbackslash{}emph" not in latex and "textbackslash{}textbf" not in latex
    assert "\\texttt{\\textbackslash{}directlua" in latex  # the .bib side still guarded


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_inline_yaml_references_are_rewritten_too(tmp_path):
    (tmp_path / "x.md").write_text(
        "---\nreferences:\n- id: smith_2024\n  type: article-journal\n"
        "  title: 'Flow `\\directlua{x}`{=latex} here'\n"
        "  issued: {date-parts: [[2024]]}\n---\n\nSee [@smith_2024].\n",
        encoding="utf-8",
    )
    cmd = [
        "pandoc", "x.md", *_BIB_FILTER, "--citeproc",
        "--csl", str(config.shipped("assets", "csl", "ieee.csl")), "-t", "latex",
    ]  # fmt: skip
    latex = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=True).stdout
    assert "directlua" in latex and "\\directlua{x}" not in latex.replace("\\textbackslash{}", "")


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_a_draft_without_a_bibliography_is_left_alone(tmp_path):
    (tmp_path / "x.md").write_text("No citations, `\\x`{=latex}.\n", encoding="utf-8")
    meta = json.loads(
        subprocess.run(
            ["pandoc", "x.md", *_BIB_FILTER, "-t", "json"],
            cwd=tmp_path, capture_output=True, text=True, check=True,
        ).stdout
    )["meta"]  # fmt: skip
    assert meta == {}


@pytest.mark.slow
@pytest.mark.skipif(
    not (pandoc_available and lualatex_available and pdftotext_available),
    reason="pandoc/lualatex/pdftotext not installed",
)
class TestRenderReal:
    def test_a_lua_read_in_a_bib_title_prints_as_text(self, isolated_config, tmp_path):
        secret = tmp_path / "outside" / "secret.txt"
        secret.parent.mkdir()
        secret.write_text(_SECRET + "\n")
        draft = _cited_draft(
            isolated_config,
            f'See \\directlua{{tex.print(io.open("{secret}"):read("*l"))}} here',
        )

        pdf = render_output.render(str(draft), output_format="pdf")

        assert not _leaked(pdf)
        assert "\\directlua{tex.print(io.open(" in pdf_text(pdf)

    def test_a_lua_write_in_a_bib_title_writes_nothing(self, isolated_config, tmp_path):
        target = tmp_path / "outside" / "written.txt"
        target.parent.mkdir()
        draft = _cited_draft(
            isolated_config,
            f'See \\directlua{{local f=io.open("{target}","w") f:write("x") f:close()}} here',
        )

        text = pdf_text(render_output.render(str(draft), output_format="pdf"))

        assert not target.exists()
        assert "\\directlua{local f=io.open(" in text

    @pytest.mark.parametrize(
        "spell",
        [
            '$\\directlua{tex.print(io.lines("%s")())}$',
            '$\\csname directlua\\endcsname{tex.print(io.lines("%s")())}$',
            '$\\latelua{tex.print(io.lines("%s")())}$',
            '$\\let\\z\\directlua\\z{tex.print(io.lines("%s")())}$',
            '$^^5cdirectlua{tex.print(io.lines("%s")())}$',
        ],
    )
    def test_no_spelling_of_the_lua_primitives_in_math_leaks(
        self, isolated_config, tmp_path, spell
    ):
        secret = tmp_path / "outside" / "secret.txt"
        secret.parent.mkdir()
        secret.write_text(_SECRET + "\n")
        draft = _cited_draft(isolated_config, spell % secret)
        assert not _leaked(render_output.render(str(draft), output_format="pdf"))

    def test_a_lua_read_inside_math_in_a_bib_title_prints_as_text(self, isolated_config, tmp_path):
        secret = tmp_path / "outside" / "secret.txt"
        secret.parent.mkdir()
        secret.write_text(_SECRET + "\n")
        draft = _cited_draft(
            isolated_config,
            f'Flow $\\directlua{{tex.print(io.open("{secret}"):read("*l"))}}$ end',
        )

        pdf = render_output.render(str(draft), output_format="pdf")

        assert not _leaked(pdf)
        assert "directlua" in pdf_text(pdf)
