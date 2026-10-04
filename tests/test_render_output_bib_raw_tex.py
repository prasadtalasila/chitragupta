"""assets/pandoc/bib_raw_tex_as_text.lua: a `.bib` field's raw TeX prints
as text and never runs in LuaLaTeX (#996).

pandoc's BibTeX reader turns a command it does not understand into raw
LaTeX, and citeproc carries it into the reference list. Under LuaLaTeX
`\\directlua{...}` there runs Lua, which `openin_any=p` does not fence
(plans/996-unicode-pdf-engine.md, Q2). The fixture key is `smith_2024`,
the one tests/test_render_output.py already uses; no new key is made up.
"""

import subprocess
import unicodedata
from pathlib import Path

import pytest

from chitragupta import config, ledger, render_output
from tests.conftest import (
    content_draft,
    lualatex_available,
    make_reference,
    pandoc_available,
    pdf_text,
    pdftotext_available,
)

_FILTER = "bib_raw_tex_as_text.lua"
_SECRET = "NOTFORTHEPDF"  # letters only: survives math italic recognisably


def _leaked(pdf) -> bool:
    # A secret typeset in math mode comes back from pdftotext as
    # Mathematical Italic code points, so fold to ASCII before searching.
    folded = unicodedata.normalize("NFKD", pdf_text(pdf))
    return _SECRET in "".join(ch for ch in folded if ch.isalnum())


def _cited_draft(isolated_config, title: str) -> Path:
    con = ledger.connect()
    ledger.upsert_reference(
        con, make_reference(citekey="smith_2024", title="An Example Paper", year="2024")
    )
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

    def test_the_filter_runs_after_citeproc_and_before_breakable_code(self):
        # pandoc runs --citeproc and --lua-filter in argv order; this
        # filter rewrites citeproc's output, so before it there is nothing
        # to see. It must also run before breakable_inline_code.lua, which
        # inserts raw `\penalty0` nodes into a code span -- the other order
        # printed those as visible text in a `.bib` title's `\texttt`.
        cmd = self._cmd(False)
        filters = [i for i, arg in enumerate(cmd) if arg.endswith(_FILTER)]
        assert len(filters) == 1
        breakable = next(
            i for i, arg in enumerate(cmd) if arg.endswith("breakable_inline_code.lua")
        )
        assert cmd.index("--citeproc") < filters[0] < breakable

    def test_a_fragment_has_no_reference_list_to_rewrite(self):
        assert not any(arg.endswith(_FILTER) for arg in self._cmd(True))


_BIB_FILTER = ["--lua-filter", str(config.shipped("assets", "pandoc", _FILTER))]
_BREAKABLE = ["--lua-filter", str(config.shipped("assets", "pandoc", "breakable_inline_code.lua"))]


def _latex_of(tmp_path, title, filters):
    (tmp_path / "x.bib").write_text(
        f"@article{{smith_2024,\n  title={{{title}}},\n"
        '  author={M{\\"u}ller, J{\\"o}rg},\n  year={2024},\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "x.md").write_text("See [@smith_2024].\n", encoding="utf-8")
    cmd = [
        "pandoc", "x.md", "--citeproc",
        "--csl", str(config.shipped("assets", "csl", "ieee.csl")),
        "--bibliography", "x.bib", "-t", "latex", *filters,
    ]  # fmt: skip
    return subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True, check=True).stdout


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_the_bib_filter_is_a_no_op_on_a_normal_entry(tmp_path):
    # Accents, inline math (including a command like \alpha), \emph and
    # \textsubscript are parsed by the reader into ordinary nodes, and a
    # \texttt into a Code span. Compared against the breakable filter
    # alone (which every real render also runs), so this isolates the bib
    # filter's effect: it must add nothing. The order matters -- the bib
    # filter runs before breakable, so it never sees breakable's
    # \penalty0 nodes and cannot turn them into visible text.
    title = (
        "{\\\"U}ber $\\alpha \\leq \\beta$ and \\emph{L\\'evy} flights in"
        " H$_2$O, see \\texttt{src/main.py} and {CO}\\textsubscript{2}"
    )
    breakable_only = _latex_of(tmp_path, title, _BREAKABLE)
    assert "Müller" in breakable_only and "\\alpha" in breakable_only  # the fixture parsed
    assert "penalty0" in breakable_only  # the \texttt was split, a real break
    assert _latex_of(tmp_path, title, _BIB_FILTER + _BREAKABLE) == breakable_only


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_a_directlua_inside_math_is_turned_to_text(tmp_path):
    # pandoc keeps $...$ as a Math node whose source the LaTeX writer
    # prints verbatim, so the raw-TeX rewrite alone missed it. Ordinary
    # math beside it stays math.
    latex = _latex_of(
        tmp_path,
        'Flow at $\\directlua{tex.print("X")}$ and $\\alpha \\leq \\beta$',
        _BIB_FILTER + _BREAKABLE,
    )
    assert "\\(\\directlua" not in latex and "$\\directlua" not in latex
    assert "directlua" in latex  # present, but as escaped text
    assert "\\(\\alpha \\leq \\beta\\)" in latex  # real math untouched


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
            # ^^5c is TeX's input escape for a backslash, formed before any
            # control word, so the literal "\\directlua" never appears.
            '$^^5cdirectlua{tex.print(io.lines("%s")())}$',
        ],
    )
    def test_no_spelling_of_the_lua_primitives_in_math_leaks(
        self, isolated_config, tmp_path, spell
    ):
        # The denylist is complete under -no-shell-escape because the only
        # Lua primitives are \directlua/\latelua and the only name-builder
        # is \csname, all listed, and the ^^ input escape is rewritten
        # too. These spellings must all fail to read the file (filter
        # header; the denylist's own comment). The leaked secret would be
        # typeset in math italic, so the check is on the plain word.
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
