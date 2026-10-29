"""Every figure of a draft just rendered to pdf: its look, and a picture
of the page it printed on (#1052).

`draft render` calls `refresh` after a pdf render succeeds, and so does
`figure look --draft`, so a draft's looks are as current as its last
render. A look is rebuilt only where its figure changed (`_look`'s
digest); a page picture is rebuilt every time, because any edit to the
text can move a figure to another page or reflow the text around it.

**Nothing here can fail the render.** The render has already written
its PDF; what this adds is for looking at, so every outcome, a missing
tool included, comes back as data for a note and never as an exception.

The page comes from the mark `render_output._figure_anchor` put after
each figure. A figure with no mark in the PDF -- one whose marker did
not resolve, or one in a `.tex` draft, which carries none -- gets no
page picture, and an old one is deleted so it cannot pass for current.
"""

import tempfile

# This module's one patch point for its external launches (#854).
from subprocess import run as _run
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import programs
from chitragupta._atomic_write import write_atomically
from chitragupta.config_path import OutsideContentDir
from chitragupta.figure._look import DPI, Look, _png_size, look
from chitragupta.render_output._figure_anchor import pages
from chitragupta.render_output._figures import _figure_refs, _resolve_sibling
from chitragupta.render_output._paths import _output_dir

_INSTALL = "chitragupta install os-deps"
NO_MARK = "no page PNG: the PDF does not mark where it printed"


@dataclass(frozen=True)
class Page:
    """A figure's page in the rendered PDF, as a PNG."""

    png: Path
    number: int
    pixels: tuple[int, int]


@dataclass(frozen=True)
class DraftFigure:
    """One figure's look and page; `note` says what is missing and why."""

    figure: Path
    look: Look | None = None
    page: Page | None = None
    note: str = ""


@dataclass(frozen=True)
class Refresh:
    """Every figure's outcome, and why a whole step was skipped."""

    figures: list[DraftFigure] = field(default_factory=list)
    skipped: str = ""


def draft_figures(draft: Path) -> dict[str, Path]:
    """`{marker base: figure file}` for every TikZ figure `draft` names
    that resolves to a file inside the draft's own directory."""
    found = {}
    for ref in _figure_refs(draft.read_text(encoding="utf-8")):
        base = ref.removesuffix(".tex")
        path = _resolve_sibling(draft.parent, f"{base}.tex")
        if path is not None:
            found[base] = path
    return found


def _marks(pdf: Path) -> dict[str, int] | None:
    """`{base: page}` from the PDF, or `None` with no `pdfinfo` to ask."""
    pdfinfo = programs.resolve_program("pdfinfo")
    if pdfinfo is None:
        return None
    result = _run([pdfinfo, "-dests", str(pdf)], capture_output=True, text=True, check=False)
    return pages(result.stdout) if result.returncode == 0 else {}


def _page(pdf: Path, number: int, png: Path) -> Page | str:
    """Page `number` of `pdf` at `DPI`, written to `png`; or why not."""
    pdftoppm = programs.require_program("pdftoppm")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "page"
        page = str(number)
        args = ["-f", page, "-l", page, "-r", str(DPI), "-png", "-singlefile"]
        command = [pdftoppm, *args, str(pdf), str(root)]
        result = _run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            png.unlink(missing_ok=True)
            return f"no page PNG: pdftoppm: {result.stderr.strip()}"
        png.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(png, root.with_suffix(".png").read_bytes())
    return Page(png, number, _png_size(png))


def _page_of(base: str, figure: Path, pdf: Path, marks: dict[str, int]) -> Page | str:
    """`figure`'s page picture, or why there is none."""
    png = _output_dir(figure) / f"{figure.stem}.page.png"
    if base not in marks:
        png.unlink(missing_ok=True)
        return NO_MARK
    return _page(pdf, marks[base], png)


def _one(base: str, figure: Path, pdf: Path, marks: dict[str, int] | None) -> DraftFigure:
    """The look and the page are independent: one failing is no reason
    to go without the other."""
    notes = []
    try:
        result = look(figure)
    except (OSError, UnicodeDecodeError, OutsideContentDir) as exc:
        result = None
        notes.append(f"no look: {exc}")
    page = None
    if marks is not None:
        try:
            found = _page_of(base, figure, pdf, marks)
        except (OSError, OutsideContentDir) as exc:
            found = f"no page PNG: {exc}"
        if isinstance(found, Page):
            page = found
        else:
            notes.append(found)
    return DraftFigure(figure, result, page, "; ".join(notes))


def refresh(draft: Path, pdf: Path) -> Refresh:
    """Every figure `draft` names: its look refreshed, its page pictured."""
    try:
        found = draft_figures(draft)
    except (OSError, UnicodeDecodeError):
        return Refresh()
    if not found:
        return Refresh()
    if programs.resolve_program("pdftoppm") is None:
        return Refresh(skipped=f"pdftoppm not found on PATH ({_INSTALL})")
    marks = _marks(pdf)
    figures = [_one(base, figure, pdf, marks) for base, figure in found.items()]
    skipped = "" if marks is not None else f"page PNGs: pdfinfo not found on PATH ({_INSTALL})"
    return Refresh(figures, skipped)


def notes(refreshed: Refresh) -> list[str]:
    """The `[figure-look]` lines a pdf render prints to stderr."""
    if not refreshed.figures:
        return [f"[figure-look] skipped: {refreshed.skipped}"] if refreshed.skipped else []
    actions = [item.look.action for item in refreshed.figures if item.look]
    counts = ", ".join(f"{actions.count(a)} {a}" for a in ("wrote", "current", "failed") if a in actions)
    paged = sum(item.page is not None for item in refreshed.figures)
    lines = [f"[figure-look] {counts or 'no looks'}; {paged} page PNGs"]
    for item in refreshed.figures:
        if item.look and item.look.action == "failed":
            lines.append(f"[figure-look] failed {item.figure}: {item.look.detail}")
        if item.note:
            lines.append(f"[figure-look] {item.figure}: {item.note}")
    if refreshed.skipped:
        lines.append(f"[figure-look] skipped {refreshed.skipped}")
    return lines


def page_line(page: Page, pdf: Path) -> str:
    """What `figure look --draft` prints for a figure's page."""
    columns, rows = page.pixels
    return f"wrote    {page.png}   (page {page.number} of {pdf.name}; {columns} x {rows} px)"
