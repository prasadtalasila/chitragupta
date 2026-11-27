"""Every figure of a draft just rendered to pdf: its look, and a picture
of the page it printed on (#1052).

Called after a successful pdf render. Looks are rebuilt only when the figure
changed; page pictures every time, since any text edit can move a figure.
**Nothing here can fail the render**: every outcome is data for a note.
Pages come from `render_output._figure_anchor`'s marks; a figure without one
gets no page picture and its old one is deleted so it cannot pass as current.
Output follows the PDF, below any `--output-dir` (#1114).
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
    """`{marker base: figure file}` for every TikZ figure `draft` names that
    resolves inside the draft's own directory."""
    found = {}
    for ref in _figure_refs(draft.read_text(encoding="utf-8")):
        base = ref.removesuffix(".tex")
        path = _resolve_sibling(draft.parent, f"{base}.tex")
        if path is not None:
            found[base] = path
    return found


def _marks(pdf: Path) -> dict[str, int] | None:
    pdfinfo = programs.resolve_program("pdfinfo")
    if pdfinfo is None:
        return None
    result = _run([pdfinfo, "-dests", str(pdf)], capture_output=True, text=True, check=False)
    return pages(result.stdout) if result.returncode == 0 else {}


def _page(pdf: Path, number: int, png: Path) -> Page | str:
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


def _dir(figure: Path, look_dir: Path | None) -> Path:
    return _output_dir(figure) if look_dir is None else look_dir


def _drop_page(figure: Path, look_dir: Path | None) -> None:
    """Delete `figure`'s stale page picture; failing to is no failure."""
    try:
        (_dir(figure, look_dir) / f"{figure.stem}.page.png").unlink(missing_ok=True)
    except (OSError, OutsideContentDir):
        pass


def _page_of(
    base: str, figure: Path, pdf: Path, marks: dict[str, int], look_dir: Path | None
) -> Page | str:
    png = _dir(figure, look_dir) / f"{figure.stem}.page.png"
    if base not in marks:
        png.unlink(missing_ok=True)
        return NO_MARK
    return _page(pdf, marks[base], png)


def _one(
    base: str, figure: Path, pdf: Path, marks: dict[str, int] | None, look_dir: Path | None
) -> DraftFigure:
    """The look and the page are independent: one failing is no reason
    to go without the other."""
    notes = []
    try:
        result = look(figure, look_dir)
    except (OSError, UnicodeDecodeError, OutsideContentDir) as exc:
        result = None
        notes.append(f"no look: {exc}")
    page = None
    if marks is None:
        _drop_page(figure, look_dir)
    else:
        try:
            found = _page_of(base, figure, pdf, marks, look_dir)
        except (OSError, OutsideContentDir) as exc:
            found = f"no page PNG: {exc}"
        if isinstance(found, Page):
            page = found
        else:
            notes.append(found)
    return DraftFigure(figure, result, page, "; ".join(notes))


def look_dir(draft: Path, figure: Path, output_dir: Path | None) -> Path | None:
    """Where `figure`'s look and page go for a render into `output_dir`: its
    mirrored place below the draft's directory, or `output_dir` itself for a
    figure outside it; `None` (the default) without one.

    Absolute, not resolved, so paths match the render's and symlink spellings
    are kept."""
    if output_dir is None:
        return None
    try:
        return output_dir / figure.absolute().parent.relative_to(draft.absolute().parent)
    except ValueError:
        return output_dir


def refresh(draft: Path, pdf: Path, output_dir: Path | None = None) -> Refresh:
    """Every figure `draft` names: its look refreshed, its page pictured.
    `output_dir` is already confined to `content/` by `render`."""
    try:
        found = draft_figures(draft)
    except (OSError, UnicodeDecodeError):
        return Refresh()
    if not found:
        return Refresh()
    if programs.resolve_program("pdftoppm") is None:
        for figure in found.values():
            _drop_page(figure, look_dir(draft, figure, output_dir))
        return Refresh(skipped=f"pdftoppm not found on PATH ({_INSTALL})")
    marks = _marks(pdf)
    figures = [
        _one(base, figure, pdf, marks, look_dir(draft, figure, output_dir))
        for base, figure in found.items()
    ]
    skipped = "" if marks is not None else f"page PNGs: pdfinfo not found on PATH ({_INSTALL})"
    return Refresh(figures, skipped)


def notes(refreshed: Refresh) -> list[str]:
    """The `[figure-look]` lines a pdf render prints to stderr."""
    if not refreshed.figures:
        return [f"[figure-look] skipped: {refreshed.skipped}"] if refreshed.skipped else []
    actions = [item.look.action for item in refreshed.figures if item.look]
    kinds = [kind for kind in ("wrote", "current", "failed") if kind in actions]
    counts = ", ".join(f"{actions.count(kind)} {kind}" for kind in kinds)
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
    columns, rows = page.pixels
    return f"wrote    {page.png}   (page {page.number} of {pdf.name}; {columns} x {rows} px)"
