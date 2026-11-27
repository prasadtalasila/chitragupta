"""The fonts chitragupta's own pdf renders use (#996), in one place.

Imports only `programs` from `chitragupta`, so `doctor.py` can check
them without loading the render stage or its config. STIX Two for text
and math is the only pair measured to print all of #996's probe; code
stays Latin Modern Mono so `style_typeset.py`'s 79-column width holds.
plans/996-unicode-pdf-engine.md has the measurements.
"""

import subprocess

from chitragupta import programs

MAIN_FONT = "STIX Two Text"
MATH_FONT = "STIX Two Math"
MONO_FONT = "Latin Modern Mono"
# At its own size: pandoc's default `Scale=MatchLowercase` grew it to STIX
# Two's x-height and broke the 79-column limit (measured).
MONO_OPTIONS = "Scale=1"

# The main font's fallbacks, in order (luaotfload `<family>:<features>`).
# Measured against all 1,873 characters #948's chitragupta-unicode.sty
# prints, so a draft that rendered before #996 still renders
# (tests/test_render_output_fonts.py). Scripts are shaped with HarfBuzz
# (`mode=harf`); Unifont is the last resort for six Unicode 14 modifier
# letters. A character none has stops the build by name
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
# DejaVu Sans Mono first, so a fallback glyph in code stays monospaced.
MONO_FALLBACKS = ("DejaVu Sans Mono:mode=node", *FONT_FALLBACKS)


# Without any one of these three every pdf render fails inside fontspec
# (#1022); the fallbacks matter only to a draft that needs them.
REQUIRED_FONTS = (MAIN_FONT, MATH_FONT, MONO_FONT)


def font_installed(name: str) -> bool | None:
    """Whether LuaLaTeX's font loader finds the family `name`, or None
    when there is no `luaotfload-tool` on PATH to ask.

    `luaotfload-tool --find` exits 0 either way (luaotfload 3.26); only
    its message tells them apart.
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

    Not pandoc's `mainfontfallback` variables: Ubuntu 24.04's pandoc
    3.1.3, which `os-deps` and CI install, silently drops them. These
    lines come after the template's own font setup and override it.
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
