"""Which renders get `assets/latex/chitragupta-unicode.sty` (#948), and
how a project's own `content/unicode-extra.tex` reaches the preamble.

`_sanitize_for_latex` no longer folds a draft's characters into ones
pdflatex can print; this `.sty` teaches pdflatex to print them instead.

**Only for output someone else compiles.** chitragupta's own pdf
renders run LuaLaTeX (#996), which prints a character when a font in
its fallback chain has it, and the `.sty` is a no-op there
(`\\ifPDFTeX`). So a pdf render no longer loads it. A `.tex` output or a
`--fragment` is compiled later by the user's own document, and most
university thesis templates are pdflatex, so those still get the file
copied beside them. Loaded only for a draft that contains a mapped
character, the same rule `_pandoc_command` applies to `tikz` and
`fvextra`: a `.tex` output does not gain a `\\usepackage` it cannot
resolve.

A fragment has no preamble, so it gets the file copied beside it and
one stderr line naming what the assembling document must load -- the
shape `[tikz-libraries]` already prints, for a skill reading the
render's output.

**The overlay works on every engine.** `\\DeclareUnicodeCharacter` is a
pdflatex-only kernel command, so an overlay line written for #948
stopped a LuaLaTeX build with `Undefined control sequence` (measured).
The overlay is therefore handed to pandoc behind a two-line shim that,
where the command is missing, defines it on top of `newunicodechar`:
the same `\\DeclareUnicodeCharacter{1681}{...}` line then prints under
LuaLaTeX and XeLaTeX too, and under pdflatex the kernel's own command
is used unchanged.
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
EXTRA_NAME = "unicode-extra.tex"
# One entry per line, as scripts/generate_unicode_sty.py writes it:
# `\chitragupta@char{<char>}{<HEX>}{<LaTeX>}`. The character itself is
# the first argument, so the file can be read back without decoding hex.
_ENTRY_RE = re.compile(r"^\\chitragupta@char\{(.)\}", re.MULTILINE)


def sty_path() -> Path:
    """The shipped `.sty`; its directory goes on `TEXINPUTS`."""
    return config.shipped("assets", "latex", f"{STY_NAME}.sty")


@cache
def mapped_characters() -> frozenset[str]:
    """Every character the shipped `.sty` maps, read from the file itself
    so the generator's output is the one runtime truth."""
    return frozenset(_ENTRY_RE.findall(sty_path().read_text(encoding="utf-8")))


def needs_sty(text: str) -> bool:
    """Whether `text` holds a character the shipped `.sty` maps.

    Asked of `text` after NFC, which is what `_sanitize_for_latex` hands
    pandoc: NFC turns U+2126 OHM SIGN, which the kernel prints, into
    U+03A9 GREEK CAPITAL OMEGA, which only the `.sty` does."""
    return not mapped_characters().isdisjoint(unicodedata.normalize("NFC", text))


def _extra_path() -> Path | None:
    """The project's own additions, `content/unicode-extra.tex`, if any."""
    path = config.CONTENT_DIR / EXTRA_NAME
    return path if path.is_file() else None


# `\DeclareUnicodeCharacter` for an engine whose kernel lacks it
# (LuaLaTeX, XeLaTeX), built on `newunicodechar` (texlive-latex-extra,
# which os-deps installs). `\lowercase` with `\lccode`~` turns the hex
# argument into the character itself, which is what `\newunicodechar`
# takes. Skipped wherever the command exists, so pdflatex keeps the
# kernel's.
_DECLARE_SHIM = (
    "\\ifdefined\\DeclareUnicodeCharacter\\else\n"
    "  \\usepackage{newunicodechar}\n"
    "  \\newcommand\\DeclareUnicodeCharacter[2]{%\n"
    '    \\begingroup\\lccode`\\~="#1\\relax\n'
    "    \\lowercase{\\endgroup\\newunicodechar{~}}{#2}}\n"
    "\\fi\n"
)


def _overlay_header(extra: Path, tmp_dir: Path) -> Path:
    """The overlay as pandoc should include it: the shim, then the
    project's file verbatim. A copy in `tmp_dir`, so the project's own
    file is never rewritten."""
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
    # A pdf is compiled here, by LuaLaTeX, which needs no `.sty` (#996).
    # A `.tex` is compiled by someone else, later, perhaps with pdflatex,
    # so it takes its own copy.
    needed = output_format != "pdf" and needs_sty(text)
    if needed:
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sty_path(), out_dir / f"{STY_NAME}.sty")
    if fragment:
        # pandoc's -H implies --standalone, so a fragment must get none.
        if needed:
            print(
                f"[unicode] {STY_NAME}.sty copied beside the fragment -- a fragment has "
                f"no preamble; load it in the assembling document: \\usepackage{{{STY_NAME}}}",
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
