"""The fonts chitragupta's own pdf renders use (#996), in one place.

Standard library only, and importing nothing from `chitragupta` but
`programs` (itself standard library only), so `chitragupta/doctor.py`
can ask whether they are installed without loading the render stage or
its config. `render_output/_pandoc.py`
turns these into pandoc variables.

A pdf render runs LuaLaTeX with STIX Two for text and math -- the only
pair measured to print every character of #996's probe
(`CO₂ 𝑡 ℝ ≤ α 𝒶`), sub- and superscripts and math script letters
included. Code stays in Latin Modern Mono, so the 79-column width
`style_typeset.py` checks fenced code against is still the width it is
set at. plans/996-unicode-pdf-engine.md has the measurements.
"""

import subprocess

from chitragupta import programs

MAIN_FONT = "STIX Two Text"
MATH_FONT = "STIX Two Math"
MONO_FONT = "Latin Modern Mono"
# At its own size, as pdflatex set it. pandoc's template defaults every
# font to `Scale=MatchLowercase`, which grew Latin Modern Mono to STIX
# Two's larger x-height: the sample project's tutorial then wrapped three
# code lines where pdflatex wrapped one, and style_typeset.py's 79-column
# limit stopped being the width code is set at (measured).
MONO_OPTIONS = "Scale=1"

# What the main font falls back to, in order, for a character it lacks
# (luaotfload fallback syntax: `<family>:<features>`). Measured against
# every one of the 1,873 characters #948's chitragupta-unicode.sty prints
# under pdflatex, so a draft that rendered before #996 still renders
# (tests/test_render_output_fonts.py):
#
# - STIX Two Math: math letters (𝑡 𝒶 ℝ), operators (≤ ∈), Roman numerals,
#   circled numbers -- STIX Two Text has none of these.
# - Noto Serif, DejaVu Sans, Noto Sans Symbols 2: the remaining modifier
#   letters (ᴬ ₐ), Latin digraphs (Ǉ), Roman numerals Ⅼ-ⅿ, U+FB29 and the
#   segmented digits U+1FBF0-U+1FBF9.
# - Noto Serif Telugu/Devanagari/CJK SC: whole scripts, shaped with
#   HarfBuzz (`mode=harf`), so a vowel sign attaches and `ि` is reordered.
# - Unifont, Unifont Upper: last resort, reached by exactly six of the
#   1,873 (U+A7F2-U+A7F4, U+10783, U+107A2, U+107A5: Unicode 14 modifier
#   letters no other packaged font has).
#
# A character none of them has still stops the build, by name
# (assets/latex/chitragupta-lualatex.tex).
FONT_FALLBACKS = (
    "STIX Two Math:mode=node",
    "Noto Serif:mode=node",
    "DejaVu Sans:mode=node",
    "Noto Sans Symbols 2:mode=node",
    "Noto Serif Telugu:mode=harf;script=telu",
    "Noto Serif Devanagari:mode=harf;script=dev2",
    "Noto Serif CJK SC:mode=harf",
    "Unifont:mode=node",
    "Unifont Upper:mode=node",
)
# Code quotes the same characters prose does (`x ≤ y`). DejaVu Sans Mono
# first, so a fallback glyph in code stays monospaced where it can.
MONO_FALLBACKS = ("DejaVu Sans Mono:mode=node", *FONT_FALLBACKS)


# The three the shipped header sets with \setmainfont, \setmathfont and
# \setmonofont. Without any one of them every pdf render fails inside
# fontspec ("The font ... cannot be found", measured, #1022); the
# fallbacks only matter to a draft holding a character only they have.
REQUIRED_FONTS = (MAIN_FONT, MATH_FONT, MONO_FONT)


def font_installed(name: str) -> bool | None:
    """Whether LuaLaTeX's font loader finds the family `name`, or None
    when there is no `luaotfload-tool` on PATH to ask.

    `luaotfload-tool --find` exits 0 whether or not the font exists
    (measured, luaotfload 3.26); only its message tells them apart.
    """
    luaotfload = programs.resolve_program("luaotfload-tool")
    if luaotfload is None:
        return None
    probe = subprocess.run(
        [luaotfload, f"--find={name}"], capture_output=True, text=True, check=False
    )
    return f'Font "{name}" found!' in probe.stdout + probe.stderr


_FALLBACK = "chitraguptafallback"
_MONO_FALLBACK = "chitraguptamonofallback"


def _lua_list(specs) -> str:
    return ", ".join(f'"{spec}"' for spec in specs)


def latex_fonts() -> str:
    """The font setup as LaTeX, for the shipped LuaLaTeX header.

    Written out here rather than left to pandoc's `mainfont`,
    `mainfontfallback` and `monofontoptions` variables, because only
    newer templates know the fallback ones: Ubuntu 24.04's apt pandoc
    (3.1.3), which `os-deps` and CI install, has no `fallback` in its
    template at all and silently dropped the whole chain, so every
    character outside STIX Two Text failed the build. These lines come
    after the template's own font setup and override it, on any pandoc
    whose template loads `unicode-math` for LuaLaTeX.
    """
    return (
        f'\\directlua{{luaotfload.add_fallback("{_FALLBACK}", {{{_lua_list(FONT_FALLBACKS)}}})}}\n'
        f'\\directlua{{luaotfload.add_fallback("{_MONO_FALLBACK}", '
        f"{{{_lua_list(MONO_FALLBACKS)}}})}}\n"
        f"\\setmainfont{{{MAIN_FONT}}}[Ligatures=TeX,Scale=1,RawFeature={{fallback={_FALLBACK}}}]\n"
        f"\\setmathfont{{{MATH_FONT}}}\n"
        f"\\setmonofont{{{MONO_FONT}}}[{MONO_OPTIONS},RawFeature={{fallback={_MONO_FALLBACK}}}]\n"
    )


def family(spec: str) -> str:
    """`Noto Serif CJK SC` from `Noto Serif CJK SC:mode=harf`."""
    return spec.split(":", 1)[0]


def all_families() -> tuple[str, ...]:
    """Every font family a pdf render names, each once, in chain order."""
    names = [MAIN_FONT, MATH_FONT, MONO_FONT, *map(family, MONO_FALLBACKS)]
    return tuple(dict.fromkeys(names))
