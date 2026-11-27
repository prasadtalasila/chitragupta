"""Which renders get `assets/latex/chitragupta-unicode.sty` (#948), and
how a project's own `content/unicode-extra.tex` reaches the preamble.

Only for output someone else compiles: our own pdf runs LuaLaTeX (#996), where
the `.sty` is a no-op, but `.tex` outputs and fragments are often compiled with
pdflatex thesis templates. Loaded only when the draft contains a mapped
character, so a `.tex` gains no `\\usepackage` it cannot resolve.

The overlay works on every engine: `\\DeclareUnicodeCharacter` is pdflatex-only
and stopped a LuaLaTeX build, so a shim defines it on `newunicodechar` where missing.
"""

import re
import shutil
import sys
import unicodedata
from functools import cache
from pathlib import Path

from chitragupta import config
from chitragupta.render_output._tables import _LATEX_BOUND

STY_NAME = "chitragupta-unicode"
# The pdf render's font setup (#996), shipped for a fragment's assembler.
FONT_HEADER = "chitragupta-lualatex"
EXTRA_NAME = "unicode-extra.tex"
# One entry per line, as scripts/generate_unicode_sty.py writes it:
# `\chitragupta@char{<char>}{<HEX>}{<LaTeX>}`.
_ENTRY_RE = re.compile(r"^\\chitragupta@char\{(.)\}", re.MULTILINE)


def sty_path() -> Path:
    return config.shipped("assets", "latex", f"{STY_NAME}.sty")


@cache
def font_header_path() -> Path:
    """The pdf render's LuaLaTeX font header, shipped with a fragment (#1037)."""
    return config.shipped("assets", "latex", f"{FONT_HEADER}.tex")


def mapped_characters() -> frozenset[str]:
    """Every character the `.sty` maps, read from the file so the generator's
    output is the one runtime truth."""
    return frozenset(_ENTRY_RE.findall(sty_path().read_text(encoding="utf-8")))


def needs_sty(text: str) -> bool:
    """Whether `text` holds a character the shipped `.sty` maps.

    Asked after NFC, as pandoc receives it: NFC turns U+2126 OHM SIGN (kernel
    prints it) into U+03A9 (only the `.sty` does)."""
    return not mapped_characters().isdisjoint(unicodedata.normalize("NFC", text))


def _extra_path() -> Path | None:
    path = config.CONTENT_DIR / EXTRA_NAME
    return path if path.is_file() else None


# `\DeclareUnicodeCharacter` for engines lacking it, on `newunicodechar`
# (texlive-latex-extra). `\lowercase` with `\lccode`~` turns the hex into the
# character `\newunicodechar` takes. Skipped where the command exists.
_DECLARE_SHIM = (
    "\\ifdefined\\DeclareUnicodeCharacter\\else\n"
    "  \\usepackage{newunicodechar}\n"
    "  \\newcommand\\DeclareUnicodeCharacter[2]{%\n"
    '    \\begingroup\\lccode`\\~="#1\\relax\n'
    "    \\lowercase{\\endgroup\\newunicodechar{~}}{#2}}\n"
    "\\fi\n"
)


def _overlay_header(extra: Path, tmp_dir: Path) -> Path:
    """The shim, then the project's file verbatim, as a copy in `tmp_dir` so
    the project's file is never rewritten."""
    header = tmp_dir / "unicode-extra-header.tex"
    header.write_text(_DECLARE_SHIM + extra.read_text(encoding="utf-8"), encoding="utf-8")
    return header


def preamble_files(
    text: str, output_format: str, fragment: bool, tmp_dir: Path, out_dir: Path
) -> list[Path]:
    """Files for pandoc's `--include-in-header`, in order. Copies the
    `.sty` beside a `.tex` output, and prints the fragment notice."""
    if output_format not in _LATEX_BOUND:
        return []
    # A pdf is compiled here by LuaLaTeX, which needs no `.sty` (#996); a `.tex`
    # may later meet pdflatex, so it takes its own copy.
    needed = output_format != "pdf" and needs_sty(text)
    if needed:
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sty_path(), out_dir / f"{STY_NAME}.sty")
    if fragment:
        # pandoc's -H implies --standalone, so a fragment gets none. The font
        # header goes too (LuaLaTeX recommended, #1037); the `.sty` stays for pdflatex.
        if needed:
            shutil.copyfile(font_header_path(), out_dir / f"{FONT_HEADER}.tex")
            print(
                f"[unicode] {FONT_HEADER}.tex and {STY_NAME}.sty copied beside the "
                "fragment -- a fragment has no preamble; in the assembling document, "
                "under lualatex: \\usepackage{fontspec}\\usepackage{unicode-math}"
                f"\\input{{{FONT_HEADER}}}; under pdflatex: \\usepackage{{{STY_NAME}}}",
                file=sys.stderr,
            )
        return []
    files = []
    if needed:
        header = tmp_dir / f"{STY_NAME}-header.tex"
        header.write_text(f"\\usepackage{{{STY_NAME}}}\n", encoding="utf-8")
        files.append(header)
    extra = _extra_path()
    if extra is not None:
        files.append(_overlay_header(extra, tmp_dir))
    return files
