"""chitragupta/render_output/_unicode.py: which renders load
chitragupta-unicode.sty, and what a fragment is told (#948)."""

import subprocess

import pytest

from chitragupta import render_output
from chitragupta.render_output import _unicode
from tests.conftest import content_draft, pandoc_available, pdflatex_available


class TestMappedCharacters:
    def test_reads_the_shipped_sty(self):
        assert {"𝑡", "₂", "≤", "ℎ"} <= _unicode.mapped_characters()

    def test_ascii_is_never_mapped(self):
        assert not _unicode.needs_sty("Plain ASCII, R2 and H2O.")

    def test_a_mapped_character_is_noticed(self):
        assert _unicode.needs_sty("the 𝑡 statistic")

    def test_the_check_reads_the_text_after_nfc(self):
        # U+2126 OHM SIGN is printed by the kernel and not mapped, but
        # _sanitize_for_latex's NFC turns it into U+03A9 GREEK CAPITAL
        # OMEGA, which pdflatex cannot print without the .sty.
        assert "Ω" not in _unicode.mapped_characters()
        assert _unicode.needs_sty("10 kΩ")


class TestPreambleFiles:
    def test_a_pdf_with_a_mapped_character_gets_a_usepackage(self, tmp_path):
        files = _unicode.preamble_files("CO₂", "pdf", False, tmp_path, tmp_path / "out")
        assert [f.read_text(encoding="utf-8") for f in files] == [
            "\\usepackage{chitragupta-unicode}\n"
        ]

    def test_a_draft_without_one_gets_nothing(self, tmp_path):
        assert _unicode.preamble_files("CO2", "pdf", False, tmp_path, tmp_path / "out") == []

    @pytest.mark.parametrize("fmt", ["html", "docx", "md"])
    def test_a_format_that_is_not_latex_gets_nothing(self, tmp_path, fmt):
        assert _unicode.preamble_files("CO₂", fmt, False, tmp_path, tmp_path / "out") == []

    def test_a_tex_output_gets_the_sty_beside_it(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        files = _unicode.preamble_files("CO₂", "tex", False, tmp_path, out)
        assert (out / "chitragupta-unicode.sty").read_bytes() == _unicode.sty_path().read_bytes()
        assert len(files) == 1

    def test_a_fragment_gets_the_sty_and_a_notice_but_no_preamble(self, tmp_path, capsys):
        out = tmp_path / "out"
        out.mkdir()
        assert _unicode.preamble_files("CO₂", "tex", True, tmp_path, out) == []
        assert (out / "chitragupta-unicode.sty").is_file()
        err = capsys.readouterr().err
        assert err.startswith("[unicode] ")
        assert "\\usepackage{chitragupta-unicode}" in err

    def test_a_fragment_without_a_mapped_character_is_silent(self, tmp_path, capsys):
        out = tmp_path / "out"
        out.mkdir()
        assert _unicode.preamble_files("CO2", "tex", True, tmp_path, out) == []
        assert capsys.readouterr().err == ""
        assert not (out / "chitragupta-unicode.sty").exists()

    def test_the_project_s_own_extra_file_comes_last(self, isolated_config, tmp_path):
        extra = isolated_config.CONTENT_DIR / "unicode-extra.tex"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_text("\\DeclareUnicodeCharacter{2603}{*}\n", encoding="utf-8")
        files = _unicode.preamble_files("CO₂ ☃", "pdf", False, tmp_path, tmp_path / "out")
        assert files[-1] == extra
        # Loaded even when the draft has nothing the shipped .sty maps:
        # the user's own characters are the reason the file exists.
        assert _unicode.preamble_files("☃", "pdf", False, tmp_path, tmp_path / "out") == [extra]


@pytest.mark.skipif(
    not (pandoc_available and pdflatex_available), reason="pandoc/pdflatex not installed"
)
class TestRenderReal:
    _DRAFT = (
        "# CO₂ budget for 𝑡\n\n"  # Review Focus 1: a heading goes into PDF bookmarks
        "Phase Ⅳ, step ①, R², 5 µm, ½, the 𝑡 statistic, Planck ℎ, $α ≤ β$, café.\n\n"
        "Inline `x ≤ y`.\n\n"  # Review Focus 2: code
        "```python\nα = 1  # ≤\n```\n"
    )

    def test_948_s_characters_render_to_pdf(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(self._DRAFT, encoding="utf-8")
        assert render_output.render(str(draft), output_format="pdf").exists()

    def test_an_unmapped_character_still_fails_naming_itself(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("A snowman ☃ here.\n", encoding="utf-8")
        with pytest.raises(subprocess.CalledProcessError) as exc:
            render_output.render(str(draft), output_format="pdf")
        assert "U+2603" in exc.value.stderr

    def test_a_tex_render_loads_the_sty_it_ships_beside_itself(self, isolated_config):
        isolated_config.BIB_FILE_PATH.write_text("")
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("CO₂\n", encoding="utf-8")
        out = render_output.render(str(draft), output_format="tex")
        assert "\\usepackage{chitragupta-unicode}" in out.read_text(encoding="utf-8")
        assert (out.parent / "chitragupta-unicode.sty").is_file()


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
def test_an_html_render_keeps_every_character_as_written(isolated_config):
    # Review Focus 5: a browser prints all of these; nothing may change them.
    isolated_config.BIB_FILE_PATH.write_text("")
    draft = content_draft(isolated_config, "draft.md")
    draft.write_text("R² H₂O 5 µm 𝑡 Ⅳ ①\n", encoding="utf-8")
    html = render_output.render(str(draft), output_format="html").read_text(encoding="utf-8")
    assert "R² H₂O 5 µm 𝑡 Ⅳ ①" in html


def test_each_preamble_file_becomes_an_include_in_header(tmp_path):
    # Without a real pandoc, so the Windows leg (no os-deps) reaches the
    # loop too; the real renders above only run where pdflatex does.
    header, extra = tmp_path / "header.tex", tmp_path / "unicode-extra.tex"
    cmd, _ = render_output._pandoc_command(
        *(tmp_path / name for name in ("in.md", "bib.bib", "ieee.csl", "out.tex", "in.md")),
        "tex", "article", "12pt", "a4", "1in", [], False, False, [header, extra],
    )  # fmt: skip
    flagged = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "--include-in-header"]
    assert flagged == [str(header), str(extra)]
