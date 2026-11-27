"""Where a rendered figure may float, and which still land on a float-only page (#1065).

Settings and measurements live in `assets/latex/chitragupta-floats.tex`. A
standalone render gets it via `--include-in-header`; a fragment with a figure
gets it copied beside it plus a stderr line naming the `\\input` needed.
The report is advisory only. It travels in the pdf's Info dictionary because
pandoc deletes LuaLaTeX's log and kpathsea blocks files outside pandoc's temp dir.
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
    return config.shipped("assets", "latex", f"{NAME}.tex")


def preamble_args(
    output_format: str, fragment: bool, figure_refs: list[str], out_dir: Path
) -> list[str]:
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


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _figures(numbers: list[str]) -> str:
    """`Figure 2.5`, `Figures 3.1 and 3.2`. An empty number is an uncaptioned
    figure, which has no number of its own."""
    named = [number for number in numbers if number]
    uncaptioned = len(numbers) - len(named)
    parts = [f"Figure{'s' if len(named) > 1 else ''} {_join(named)}"] if named else []
    if uncaptioned:
        parts.append(
            "an uncaptioned figure" if uncaptioned == 1 else f"{uncaptioned} uncaptioned figures"
        )
    return " and ".join(parts)


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
