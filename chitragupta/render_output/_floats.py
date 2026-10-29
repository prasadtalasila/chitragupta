"""Where a rendered figure may float, and which ones still land on a
float-only page (#1065).

`assets/latex/chitragupta-floats.tex` holds the settings and the
LuaLaTeX hooks that notice such a page; its own header has the
measurement behind each number. This module only decides which render
gets the file and reads back what it noticed.

**A standalone LaTeX-bound render** gets it through `--include-in-header`,
so a `.tex` output carries it inline and compiles alone. **A fragment**
has no preamble, so a fragment whose unit draws a figure gets the file
copied beside it and one stderr line naming the `\\input` the assembling
document needs: the shape `[unicode]` and `[tikz-libraries]` already
print. A fragment with no figure needs neither.

**The report is advisory.** A figure taller than the text page allows
belongs on a page of its own, so this is a line for the author to read,
never a failure. It travels in the pdf's own Info dictionary, because
pandoc deletes LuaLaTeX's log and kpathsea refuses LuaLaTeX a file
outside pandoc's temp directory; the `.tex` file's header has the
measurements.
"""

import re
import shutil
import sys
from pathlib import Path

from chitragupta import config
from chitragupta.render_output._tables import _LATEX_BOUND

NAME = "chitragupta-floats"
# Hex, so a figure number can never end the PDF string early; LuaTeX
# writes the Info dictionary uncompressed, so the bytes are readable as is.
_INFO_RE = re.compile(rb"/ChitraguptaFloatPages\s*<([0-9A-Fa-f]*)>")


def path() -> Path:
    """The shipped file."""
    return config.shipped("assets", "latex", f"{NAME}.tex")


def preamble_args(
    output_format: str, fragment: bool, figure_refs: list[str], out_dir: Path
) -> list[str]:
    """pandoc's arguments for the file, copying it beside a fragment."""
    if output_format not in _LATEX_BOUND:
        return []
    if not fragment:
        return ["--include-in-header", str(path())]
    if figure_refs:
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path(), out_dir / f"{NAME}.tex")
        print(
            f"[floats] {NAME}.tex copied beside the fragment -- a fragment has no "
            f"preamble; \\input{{{NAME}}} in the assembling document's preamble",
            file=sys.stderr,
        )
    return []


def _figures(numbers: list[str]) -> str:
    """`Figure 2.5`, `Figures 3.1 and 3.2`, `Figures A.1, A.2 and A.3`."""
    if len(numbers) == 1:
        return f"Figure {numbers[0]}"
    return f"Figures {', '.join(numbers[:-1])} and {numbers[-1]}"


def print_report(pdf: Path) -> None:
    """One `[float-page]` line per float-only page `pdf` records."""
    found = _INFO_RE.search(pdf.read_bytes())
    if found is None:
        return
    pages: dict[str, list[str]] = {}
    for line in bytes.fromhex(found.group(1).decode("ascii")).decode("utf-8").splitlines():
        page, number = line.split("\t")
        pages.setdefault(page, []).append(number)
    for page, numbers in pages.items():
        print(
            f"[float-page] p. {page} holds {_figures(numbers)} and no text. A figure "
            "taller than 0.85 of the text height cannot share a page with text; a "
            "shorter one lands alone when figures queue up before a page break.",
            file=sys.stderr,
        )
