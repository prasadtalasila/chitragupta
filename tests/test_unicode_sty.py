"""assets/latex/chitragupta-unicode.sty against the script that writes it (#948).

The `.sty` is generated output. This file pins it to its generator, so
a hand edit fails here, and checks that what the generator emits
compiles: every entry, in one pdflatex run.
"""

import subprocess
import unicodedata

import pytest

from scripts import generate_unicode_sty as gen
from tests.conftest import pdflatex_available, pdftotext_available


def test_the_committed_sty_is_what_the_generator_writes():
    assert gen.STY_PATH.read_text(encoding="utf-8") == gen.render(), (
        "assets/latex/chitragupta-unicode.sty is stale or hand-edited. "
        "Run `python -m scripts.generate_unicode_sty` and commit the result."
    )


@pytest.mark.parametrize("char", ["𝑡", "𝐀", "ℎ", "ℝ", "₂", "Ⅳ", "①", "≤", "α", "Ω"])
def test_the_characters_948_named_are_mapped(char):
    assert ord(char) in gen.entries()


def _folded_to_ascii_before_948():
    """Code points the old NFKC fold turned into printable ASCII, so a
    draft carrying one compiled on 6.130.0. Those NFC still changes never
    reach LaTeX as themselves, so they are left out."""
    for cp in range(0x80, 0x110000):
        char = chr(cp)
        if 0xD800 <= cp <= 0xDFFF or unicodedata.category(char)[0] in "CM":
            continue
        folded = unicodedata.normalize("NFKC", char)
        if (
            folded != char
            and unicodedata.is_normalized("NFC", char)
            and folded.isascii()
            and folded.isprintable()
        ):
            yield cp


def test_every_character_nfkc_folded_to_ascii_is_still_printed():
    # Measured, not in the plan: dropping NFKC also stopped folding a
    # thin space, `（`, `⑴` and `‼`, which pdflatex cannot print. Each
    # compiled before #948, so each needs an entry or it is a regression.
    entries = gen.entries()
    missing = [f"U+{cp:04X}" for cp in _folded_to_ascii_before_948() if cp not in entries]
    assert missing == []


@pytest.mark.parametrize(
    "char", [" ", " ", "（", "ｆ", "⑴", "‼", "ſ", "⅓", "ⅆ", "Ŀ", "℉", "￡", "￫", "﹘"]
)
def test_the_characters_the_review_measured_failing_are_mapped(char):
    assert ord(char) in gen.entries()


def test_the_holes_are_exactly_the_math_block_s_reserved_letter_slots():
    # Unicode left 24 slots of U+1D400-U+1D6A3 empty because those
    # letters already existed in Letterlike Symbols. HOLES must name one
    # character per empty slot, each the plain letter it stands for.
    empty = [cp for cp in range(0x1D400, 0x1D6A4) if not unicodedata.name(chr(cp), "")]
    assert len(empty) == len(gen.HOLES) == 24
    for cp, (_, letter) in gen.HOLES.items():
        assert unicodedata.normalize("NFKC", chr(cp)) == letter


def test_only_capital_digamma_in_the_math_block_is_left_unmapped():
    # No pdflatex font has a capital digamma. Left unmapped on purpose,
    # so it fails loudly rather than printing as something else.
    unmapped = [
        cp
        for cp in range(0x1D400, 0x1D800)
        if unicodedata.name(chr(cp), "") and cp not in gen.entries()
    ]
    assert unmapped == [0x1D7CA]


def test_a_style_pdflatex_lacks_keeps_the_letter():
    # Lowercase double-struck has no amssymb glyph: the letter is kept
    # and only the style is lost.
    assert gen.entries()[0x1D552] == r"\ensuremath{a}"  # MATHEMATICAL DOUBLE-STRUCK SMALL A


def test_main_writes_the_file(tmp_path, monkeypatch, capsys):
    target = tmp_path / "latex" / "chitragupta-unicode.sty"
    monkeypatch.setattr(gen, "STY_PATH", target)
    assert gen.main() == 0
    assert target.read_text(encoding="utf-8") == gen.render()
    assert "characters" in capsys.readouterr().out


def _compile_every_entry(tmp_path):
    """One pdflatex run over every entry, with a user glyph for ≤ declared
    before the package loads. Returns the finished process."""
    body = " ".join(chr(cp) for cp in sorted(gen.entries()))
    (tmp_path / "chitragupta-unicode.sty").write_text(gen.render(), encoding="utf-8")
    (tmp_path / "all.tex").write_text(
        "\\documentclass{article}\\usepackage[T1]{fontenc}\\usepackage{lmodern}\n"
        "\\DeclareUnicodeCharacter{2264}{USERLEQ}\n"
        "\\usepackage{chitragupta-unicode}\n"
        f"\\begin{{document}}\n{body}\n\\end{{document}}\n",
        encoding="utf-8",
    )
    return subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "all.tex"],
        cwd=tmp_path, capture_output=True, text=True, errors="replace", check=False,
    )  # fmt: skip


@pytest.mark.skipif(not pdflatex_available, reason="pdflatex not installed")
def test_every_entry_compiles_with_no_missing_glyph(tmp_path):
    result = _compile_every_entry(tmp_path)
    assert result.returncode == 0, result.stdout[-2000:]
    log = (tmp_path / "all.log").read_text(encoding="utf-8", errors="replace")
    assert "Missing character" not in log


@pytest.mark.skipif(
    not (pdflatex_available and pdftotext_available), reason="pdflatex/pdftotext not installed"
)
def test_a_glyph_the_user_declared_first_is_kept(tmp_path):
    # Review Focus 4: the guard. The user declared ≤ before loading the
    # package, so their glyph must survive it.
    assert _compile_every_entry(tmp_path).returncode == 0
    text = subprocess.run(
        ["pdftotext", "all.pdf", "-"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout
    assert "USERLEQ" in text
