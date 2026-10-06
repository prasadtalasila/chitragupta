"""The LuaLaTeX font chain prints everything pdflatex printed (#996).

Under pdflatex, a draft's Greek, math letters, sub- and superscripts and
the rest printed through #948's chitragupta-unicode.sty. A pdf render now
runs LuaLaTeX, where that file is a no-op, so each of those characters
needs a glyph in STIX Two or a font in `chitragupta/pdf_fonts.py`'s
fallback chain -- otherwise a draft that rendered yesterday fails today
under `\\tracinglostchars=3`. This renders every one of them.
"""

from types import SimpleNamespace

import pytest

from chitragupta import pdf_fonts, render_output
from chitragupta.render_output import _unicode
from tests.conftest import content_draft, lualatex_available, pandoc_available

# Characters per paragraph: short enough that TeX can break the line
# between them, so no overfull box hides a glyph off the page.
_PER_LINE = 40


def test_the_required_fonts_are_the_three_the_preamble_sets():
    assert pdf_fonts.REQUIRED_FONTS == (
        pdf_fonts.MAIN_FONT, pdf_fonts.MATH_FONT, pdf_fonts.MONO_FONT,
    )  # fmt: skip


def test_font_installed_reads_the_message_not_the_exit_status(monkeypatch):
    # luaotfload-tool exits 0 whether or not the font exists (measured,
    # luaotfload 3.26).
    def fake_run(cmd, **kwargs):
        name = cmd[1].removeprefix("--find=")
        found = name == "STIX Two Text"
        message = f'Font "{name}" found!' if found else f'Cannot find "{name}" in index.'
        return SimpleNamespace(returncode=0, stdout="", stderr=message)

    monkeypatch.setattr(pdf_fonts.subprocess, "run", fake_run)
    assert pdf_fonts.font_installed("/usr/bin/luaotfload-tool", "STIX Two Text")
    assert not pdf_fonts.font_installed("/usr/bin/luaotfload-tool", "Noto Serif")


def test_the_chain_names_every_family_once_in_order():
    families = pdf_fonts.all_families()
    assert families[:3] == ("STIX Two Text", "STIX Two Math", "Latin Modern Mono")
    assert len(families) == len(set(families))
    assert families[-2:] == ("Unifont", "Unifont Upper")


def test_family_strips_the_feature_list():
    assert pdf_fonts.family("Noto Serif CJK SC:mode=harf") == "Noto Serif CJK SC"


def test_the_shipped_header_carries_the_generated_font_block():
    # The header sets the fonts itself (apt pandoc 3.1.3 knows no
    # mainfontfallback), so the block in it must match latex_fonts().
    from chitragupta import config

    header = config.shipped("assets", "latex", "chitragupta-lualatex.tex").read_text(
        encoding="utf-8"
    )
    block = header.split("% BEGIN chitragupta fonts\n", 1)[1].split("% END chitragupta fonts\n", 1)[
        0
    ]
    assert block == pdf_fonts.latex_fonts()


def test_the_font_block_names_the_whole_chain():
    block = pdf_fonts.latex_fonts()
    assert f"\\setmainfont{{{pdf_fonts.MAIN_FONT}}}" in block
    for spec in pdf_fonts.FONT_FALLBACKS:
        assert f'"{spec}"' in block


@pytest.mark.skipif(
    not (pandoc_available and lualatex_available), reason="pandoc/lualatex not installed"
)
def test_every_character_the_sty_prints_under_pdflatex_prints_under_lualatex(isolated_config):
    chars = sorted(_unicode.mapped_characters())
    assert len(chars) == 1873  # the table #948 shipped; a new entry needs a glyph too
    lines = [" ".join(chars[i : i + _PER_LINE]) for i in range(0, len(chars), _PER_LINE)]
    isolated_config.BIB_FILE_PATH.write_text("")
    draft = content_draft(isolated_config, "draft.md")
    draft.write_text("# Every mapped character\n\n" + "\n\n".join(lines) + "\n", encoding="utf-8")

    # A missing glyph is a build error (assets/latex/chitragupta-lualatex.tex),
    # so a render that returns is the assertion; the error, if any, names
    # the first character no font has.
    assert render_output.render(str(draft), output_format="pdf").exists()
