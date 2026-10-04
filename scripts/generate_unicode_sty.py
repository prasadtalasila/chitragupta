"""Writes `assets/latex/chitragupta-unicode.sty`: how pdflatex prints the
Unicode characters a draft carries but its default fonts cannot (#948).

Run it, never edit its output: `python -m scripts.generate_unicode_sty`.
`tests/test_unicode_sty.py` fails when the committed file differs from
what this writes, so a hand edit to the `.sty` is reverted by the next
person to run it, and a change here without a rerun fails CI.

Every line maps one code point to the LaTeX command that draws it, and
nothing here changes the text of a draft: the draft keeps the character,
LaTeX decides how to print it. Five generated groups, derived from
Python's own `unicodedata` tables rather than typed out, plus one short
hand table (`SYMBOLS`) for the math operators no Unicode name spells as a
LaTeX command.

A character LaTeX already prints is never redefined: the `.sty` guards
each line with the kernel's own `u8:` lookup, so `²`, `µ`, `×` and `½`
keep the glyphs the user's LaTeX gives them. A character in none of the
groups is not mapped at all, and pdflatex still stops on it, naming it.
"""

import sys
import unicodedata
from pathlib import Path

STY_PATH = Path(__file__).resolve().parent.parent / "assets" / "latex" / "chitragupta-unicode.sty"

# Greek letter names as `unicodedata` spells them (note LAMDA), to the
# math command amsmath/amssymb draw them with. U+03C6 GREEK SMALL LETTER
# PHI is the loopy form, which LaTeX calls \varphi; U+03D5 PHI SYMBOL is
# the straight one, \phi. Epsilon is the same swap.
GREEK_SMALL = {
    "ALPHA": r"\alpha", "BETA": r"\beta", "GAMMA": r"\gamma", "DELTA": r"\delta",
    "EPSILON": r"\varepsilon", "ZETA": r"\zeta", "ETA": r"\eta", "THETA": r"\theta",
    "IOTA": r"\iota", "KAPPA": r"\kappa", "LAMDA": r"\lambda", "MU": r"\mu", "NU": r"\nu",
    "XI": r"\xi", "OMICRON": "o", "PI": r"\pi", "RHO": r"\rho", "FINAL SIGMA": r"\varsigma",
    "SIGMA": r"\sigma", "TAU": r"\tau", "UPSILON": r"\upsilon", "PHI": r"\varphi",
    "CHI": r"\chi", "PSI": r"\psi", "OMEGA": r"\omega",
    "EPSILON SYMBOL": r"\epsilon", "LUNATE EPSILON SYMBOL": r"\epsilon",
    "THETA SYMBOL": r"\vartheta", "KAPPA SYMBOL": r"\varkappa", "PHI SYMBOL": r"\phi",
    "RHO SYMBOL": r"\varrho", "PI SYMBOL": r"\varpi", "NABLA": r"\nabla",
    "PARTIAL DIFFERENTIAL": r"\partial", "DIGAMMA": r"\digamma",
}  # fmt: skip
# Capitals with no command of their own are the Latin letter they look
# like, which is how every LaTeX math font draws them anyway.
GREEK_CAPITAL = {
    "GAMMA": r"\Gamma", "DELTA": r"\Delta", "THETA": r"\Theta", "LAMDA": r"\Lambda",
    "XI": r"\Xi", "PI": r"\Pi", "SIGMA": r"\Sigma", "UPSILON": r"\Upsilon", "PHI": r"\Phi",
    "PSI": r"\Psi", "OMEGA": r"\Omega", "THETA SYMBOL": r"\Theta",
    "ALPHA": "A", "BETA": "B", "EPSILON": "E", "ZETA": "Z", "ETA": "H", "IOTA": "I",
    "KAPPA": "K", "MU": "M", "NU": "N", "OMICRON": "O", "RHO": "P", "TAU": "T", "CHI": "X",
}  # fmt: skip
DIGIT_NAMES = "ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE".split()

# Longest first: "SANS-SERIF BOLD ITALIC" must match before "SANS-SERIF".
STYLES = (
    "SANS-SERIF BOLD ITALIC", "SANS-SERIF BOLD", "SANS-SERIF ITALIC", "SANS-SERIF",
    "BOLD ITALIC", "BOLD SCRIPT", "BOLD FRAKTUR", "BOLD", "ITALIC", "SCRIPT", "FRAKTUR",
    "DOUBLE-STRUCK", "MONOSPACE",
)  # fmt: skip

# The 24 reserved slots in U+1D400-U+1D7FF. Their letters were encoded in
# Letterlike Symbols before the math block existed, so Unicode points the
# block's gap at the older character: a math-italic h is U+210E PLANCK
# CONSTANT, not U+1D455. Same style rule as the block.
HOLES = {
    0x210E: ("ITALIC", "h"),
    0x212C: ("SCRIPT", "B"), 0x2130: ("SCRIPT", "E"), 0x2131: ("SCRIPT", "F"),
    0x210B: ("SCRIPT", "H"), 0x2110: ("SCRIPT", "I"), 0x2112: ("SCRIPT", "L"),
    0x2133: ("SCRIPT", "M"), 0x211B: ("SCRIPT", "R"), 0x212F: ("SCRIPT", "e"),
    0x210A: ("SCRIPT", "g"), 0x2134: ("SCRIPT", "o"),
    0x212D: ("FRAKTUR", "C"), 0x210C: ("FRAKTUR", "H"), 0x2111: ("FRAKTUR", "I"),
    0x211C: ("FRAKTUR", "R"), 0x2128: ("FRAKTUR", "Z"),
    0x2102: ("DOUBLE-STRUCK", "C"), 0x210D: ("DOUBLE-STRUCK", "H"),
    0x2115: ("DOUBLE-STRUCK", "N"), 0x2119: ("DOUBLE-STRUCK", "P"),
    0x211A: ("DOUBLE-STRUCK", "Q"), 0x211D: ("DOUBLE-STRUCK", "R"),
    0x2124: ("DOUBLE-STRUCK", "Z"),
}  # fmt: skip

# Math operators an LLM writes as a character. No Unicode name spells the
# LaTeX command, so these are the one hand-kept table; each is the command
# in amsmath/amssymb, which pandoc's template and this .sty both load.
# Some (→, ←, ⟨, …) are already printed by recent kernels; the guard then
# skips them, and an older TeX Live still gets them.
SYMBOLS = {
    0x2264: r"\leq", 0x2265: r"\geq", 0x2260: r"\neq", 0x2248: r"\approx",
    0x2261: r"\equiv", 0x223C: r"\sim", 0x2243: r"\simeq", 0x2245: r"\cong",
    0x221D: r"\propto", 0x226A: r"\ll", 0x226B: r"\gg", 0x227A: r"\prec",
    0x227B: r"\succ", 0x2208: r"\in", 0x2209: r"\notin", 0x220B: r"\ni",
    0x2282: r"\subset", 0x2283: r"\supset", 0x2286: r"\subseteq", 0x2287: r"\supseteq",
    0x222A: r"\cup", 0x2229: r"\cap", 0x2205: r"\emptyset", 0x2216: r"\setminus",
    0x2200: r"\forall", 0x2203: r"\exists", 0x2204: r"\nexists", 0x2227: r"\wedge",
    0x2228: r"\vee", 0x22A4: r"\top", 0x22A5: r"\perp", 0x22A2: r"\vdash",
    0x22A8: r"\models", 0x2234: r"\therefore", 0x2235: r"\because",
    0x2192: r"\rightarrow", 0x2190: r"\leftarrow", 0x2194: r"\leftrightarrow",
    0x21A6: r"\mapsto", 0x21D2: r"\Rightarrow", 0x21D0: r"\Leftarrow",
    0x21D4: r"\Leftrightarrow", 0x2191: r"\uparrow", 0x2193: r"\downarrow",
    0x27F6: r"\longrightarrow", 0x221E: r"\infty", 0x2211: r"\sum", 0x220F: r"\prod",
    0x222B: r"\int", 0x222E: r"\oint", 0x221A: r"\surd", 0x2213: r"\mp",
    0x22C5: r"\cdot", 0x2218: r"\circ", 0x2217: r"\ast", 0x2295: r"\oplus",
    0x2297: r"\otimes", 0x2225: r"\parallel", 0x2223: r"\mid", 0x2220: r"\angle",
    0x2032: r"{}^{\prime}", 0x2033: r"{}^{\prime\prime}", 0x2212: "-",
    0x210F: r"\hbar", 0x2113: r"\ell", 0x2118: r"\wp", 0x2135: r"\aleph",
    0x27E8: r"\langle", 0x27E9: r"\rangle", 0x2308: r"\lceil", 0x2309: r"\rceil",
    0x230A: r"\lfloor", 0x230B: r"\rfloor", 0x220E: r"\blacksquare",
    0x25A1: r"\square", 0x22EF: r"\cdots",
}  # fmt: skip

_HEADER = r"""%% Generated by scripts/generate_unicode_sty.py -- do not edit (#948).
%% How pdflatex prints Unicode characters its default fonts cannot.
%% A thesis or book that \input-s a chitragupta fragment loads this with
%% \usepackage{chitragupta-unicode}. Under XeLaTeX or LuaLaTeX it does
%% nothing: those engines read Unicode themselves.
\NeedsTeXFormat{LaTeX2e}
\ProvidesPackage{chitragupta-unicode}[2026/10/04 chitragupta, issue 948]
\RequirePackage{iftex}
\ifPDFTeX\else\expandafter\endinput\fi
\RequirePackage{amsmath,amssymb}
%% Never redefine a character LaTeX already prints: the kernel's own
%% u8: entry wins, so a user's existing glyph for it is untouched.
\newcommand\chitragupta@char[3]{%
  \ifcsname u8:\detokenize{#1}\endcsname\else\DeclareUnicodeCharacter{#2}{#3}\fi}
"""


def _styled(style: str, base: str, *, latin_capital: bool, greek: bool) -> str:
    """`base` in `style`, with the commands pdflatex's default math fonts
    have. Where a style has no pdflatex font for this letter (lowercase
    script or double-struck), the letter is kept and only the style is
    lost -- the same trade #389 made, now limited to these two cases."""
    bold = "BOLD" in style
    if "SANS-SERIF" in style:
        inner = base if greek else rf"\mathsf{{{base}}}"
    elif style == "MONOSPACE":
        return rf"\mathtt{{{base}}}"
    elif "FRAKTUR" in style:
        inner = rf"\mathfrak{{{base}}}"
    elif "SCRIPT" in style:
        inner = rf"\mathcal{{{base}}}" if latin_capital else base
    elif style == "DOUBLE-STRUCK":
        return rf"\mathbb{{{base}}}" if latin_capital else base
    elif style == "BOLD":
        return rf"\boldsymbol{{{base}}}" if greek else rf"\mathbf{{{base}}}"
    elif style == "BOLD ITALIC":
        return rf"\boldsymbol{{{base}}}"
    else:  # ITALIC: math mode is italic already, except upright Greek capitals
        return rf"\mathit{{{base}}}" if greek and base[1].isupper() else base
    return rf"\boldsymbol{{{inner}}}" if bold else inner


def _greek(key: str, capital: bool) -> tuple[str, bool] | None:
    """(command, is_a_greek_command) for a Greek letter name, or None."""
    command = (GREEK_CAPITAL if capital else GREEK_SMALL).get(key)
    return None if command is None else (command, command.startswith("\\"))


def _math_alphanumeric(style: str, rest: str) -> str | None:
    """The command for one MATHEMATICAL <style> <rest> character."""
    if rest in ("SMALL DOTLESS I", "SMALL DOTLESS J"):
        return r"\imath" if rest.endswith("I") else r"\jmath"
    if rest.startswith("DIGIT "):
        digit = str(DIGIT_NAMES.index(rest.removeprefix("DIGIT ")))
        return _styled(style, digit, latin_capital=False, greek=False)
    case, _, letter = rest.partition(" ")
    if len(letter) == 1:
        capital = case == "CAPITAL"
        base = letter if capital else letter.lower()
        return _styled(style, base, latin_capital=capital, greek=False)
    capital = case == "CAPITAL"
    found = _greek(letter if case in ("CAPITAL", "SMALL") else rest, capital)
    if found is None:
        return None
    command, greek = found
    return _styled(style, command, latin_capital=False, greek=greek)


def _math_block() -> dict[int, str]:
    out = {}
    for cp in range(0x1D400, 0x1D800):
        name = unicodedata.name(chr(cp), "").removeprefix("MATHEMATICAL ")
        style = next((s for s in STYLES if name.startswith(s + " ")), None)
        command = _math_alphanumeric(style, name[len(style) + 1 :]) if style else None
        if command is not None:
            out[cp] = rf"\ensuremath{{{command}}}"
    for cp, (style, letter) in HOLES.items():
        command = _styled(style, letter, latin_capital=letter.isupper(), greek=False)
        out[cp] = rf"\ensuremath{{{command}}}"
    return out


def _greek_block() -> dict[int, str]:
    out = {}
    codepoints = [*range(0x0391, 0x03AA), *range(0x03B1, 0x03CA), 0x03D1, 0x03D5, 0x03D6]
    for cp in [*codepoints, 0x03F0, 0x03F1, 0x03F5]:
        name = unicodedata.name(chr(cp), "").removeprefix("GREEK ")
        capital = name.startswith("CAPITAL LETTER ")
        key = name.removeprefix("CAPITAL LETTER ").removeprefix("SMALL LETTER ")
        found = _greek(key, capital)
        if found is not None:
            command, greek = found
            out[cp] = rf"\ensuremath{{{command}}}" if greek else rf"\textup{{{command}}}"
    return out


def _decomposed(cp: int) -> tuple[str, str]:
    """(tag, the characters it decomposes to) -- ("<sub>", "2") for ₂."""
    tag, *rest = unicodedata.decomposition(chr(cp)).split() or [""]
    return tag, "".join(chr(int(h, 16)) for h in rest)


def _scripts_numerals_circles() -> dict[int, str]:
    out = {}
    for cp in [*range(0x2070, 0x20A0), *range(0x1D2C, 0x1D6B), 0xB2, 0xB3, 0xB9]:
        tag, text = _decomposed(cp)
        command = {"<sub>": "textsubscript", "<super>": "textsuperscript"}.get(tag)
        arg = r"\textminus" if text == "\u2212" else text
        if command and (
            arg == r"\textminus" or (arg.isascii() and (arg.isalnum() or arg in "+=()"))
        ):
            out[cp] = rf"\{command}{{{arg}}}"
    for cp in range(0x2160, 0x2180):
        out[cp] = rf"\textup{{{_decomposed(cp)[1]}}}"
    # Circled 1-20, A-Z, a-z and 0: every one decomposes as <circle>.
    for cp in [*range(0x2460, 0x2474), *range(0x24B6, 0x24EB)]:
        out[cp] = rf"\textcircled{{\scriptsize {_decomposed(cp)[1]}}}"
    return out


def entries() -> dict[int, str]:
    """Every mapped code point to the LaTeX that prints it."""
    symbols = {cp: rf"\ensuremath{{{command}}}" for cp, command in SYMBOLS.items()}
    return {**_math_block(), **_greek_block(), **_scripts_numerals_circles(), **symbols}


def render() -> str:
    """The whole `.sty`, one line per code point, in code-point order."""
    lines = [
        rf"\chitragupta@char{{{chr(cp)}}}{{{cp:04X}}}{{{tex}}}"
        for cp, tex in sorted(entries().items())
    ]
    return _HEADER + "\n".join(lines) + "\n\\endinput\n"


def main() -> int:
    STY_PATH.parent.mkdir(parents=True, exist_ok=True)
    STY_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {len(entries())} characters to {STY_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
