"""Which renders load `assets/latex/chitragupta-unicode.sty` (#948).

`_sanitize_for_latex` no longer folds a draft's characters into ones
pdflatex can print; this `.sty` teaches pdflatex to print them instead.
Loaded only for a LaTeX-bound render of a draft that contains one, the
same rule `_pandoc_command` applies to `tikz` and `fvextra`: a draft
without one renders exactly as before, and its `.tex` output does not
gain a `\\usepackage` it cannot resolve.

A fragment has no preamble, so it gets the file copied beside it and
one stderr line naming what the assembling document must load -- the
shape `[tikz-libraries]` already prints, for a skill reading the
render's output.
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


def preamble_files(
    text: str, output_format: str, fragment: bool, tmp_dir: Path, out_dir: Path
) -> list[Path]:
    """Files for pandoc's `--include-in-header`, in order. Copies the
    `.sty` beside a `.tex` output, and prints the fragment notice."""
    if output_format not in _LATEX_BOUND:
        return []
    needed = needs_sty(text)
    # A pdf is compiled here, with the shipped directory on TEXINPUTS; a
    # `.tex` is compiled by someone else, later, so it takes its own copy.
    if needed and output_format != "pdf":
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
        files.append(extra)
    return files
