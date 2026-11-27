r"""One figure as it will print, cropped to itself: `chitragupta figure
look` (#1052).

For what no `figure check` rule measures (bad wraps, cramped layouts): a
picture to look at.

**Set as the render sets it**: on the figure's own page (`page.page_for`,
#1140), with the probe's fonts and the TikZ libraries in the preamble (#781;
inside the box they add stray width, #1046). Source is inlined, not `\input`,
so the read fence has no second file to admit.

**Cropped to the figure**: box plus `BORDER_PT` via LuaTeX's `\pagewidth` and
`\pageheight`, by hand since `_require_tikz` does not check `standalone.cls`.
A too-wide figure gets a hairline at the text width. The 10pt border keeps
the house shadow, drawn outside the bounding box (#1127).

**Only what changed is rebuilt**, via a digest in `<stem>.look.json`.
"""

import hashlib
import json
import re
import struct
import tempfile

# `_run` is this module's one patch point for external launches (#854), as in
# the probe and the renderer.
from subprocess import CompletedProcess
from subprocess import run as _run
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config, pdf_fonts, programs, tex_engine
from chitragupta.page import ARTICLE, Page, page_for
from chitragupta._atomic_write import write_atomically
from chitragupta.render_output import _target_dir
from chitragupta.render_output._paths import _output_dir
from chitragupta.render_output._tikz_libraries import libraries_in
from chitragupta.review.figure_layout._probe import _compile_error_detail

DPI = 300
BORDER_PT = 10.0

# Part of the digest: raise it when `document()` changes what it draws,
# so every look built by the old document is rebuilt.
DOCUMENT_VERSION = 2

_LOOK_RE = re.compile(
    r"^CGLOOK (?P<wd>[\d.]+)pt (?P<ht>[\d.]+)pt (?P<dp>[\d.]+)pt (?P<tw>[\d.]+)pt",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Look:
    """What `look` did for one figure, and what it measured.

    `action` is `wrote`, `current` or `failed`; sizes are TeX points,
    `height` including depth.
    """

    pdf: Path
    png: Path
    record: Path
    action: str
    width: float = 0.0
    height: float = 0.0
    text_width: float = 0.0
    pixels: tuple[int, int] = (0, 0)
    detail: str = ""

    @property
    def past_text_width(self) -> bool:
        return self.width > self.text_width


def document(source: str, on: Page = ARTICLE) -> str:
    """The page `source` is set on: see this module's docstring."""
    libraries = libraries_in(source)
    return (
        on.preamble + "\\usepackage{fontspec}\n"
        "\\usepackage{unicode-math}\n"
        f"{pdf_fonts.latex_fonts()}"
        "\\usepackage{tikz}\n"
        + (f"\\usetikzlibrary{{{','.join(libraries)}}}\n" if libraries else "")
        + "\\newbox\\cgfigbox\n"
        f"\\newdimen\\cgborder \\cgborder={BORDER_PT}pt\n"
        "\\begin{document}\n"
        # TeX's own box, not `\sbox`, which would read the figure as a
        # macro argument and freeze the catcode `matrix` changes for `&`.
        f"\\setbox\\cgfigbox=\\hbox{{%\n{source}%\n}}%\n"
        "\\typeout{CGLOOK \\the\\wd\\cgfigbox\\space\\the\\ht\\cgfigbox"
        "\\space\\the\\dp\\cgfigbox\\space\\the\\textwidth}%\n"
        "\\dimen0=\\ht\\cgfigbox \\dimen2=\\dp\\cgfigbox \\dimen4=\\wd\\cgfigbox\n"
        "\\ifdim\\wd\\cgfigbox>\\textwidth\n"
        "  \\setbox\\cgfigbox=\\hbox to \\dimen4{\\rlap{\\box\\cgfigbox}\\kern\\textwidth"
        "\\textcolor{red}{\\vrule width 0.4pt height \\dimen0 depth \\dimen2}\\hss}%\n"
        "\\fi\n"
        "\\pagewidth=\\dimexpr\\dimen4+2\\cgborder\\relax\n"
        "\\pageheight=\\dimexpr\\dimen0+\\dimen2+2\\cgborder\\relax\n"
        "\\hoffset=-1in \\voffset=-1in\n"
        "\\shipout\\vbox{\\kern\\cgborder\\moveright\\cgborder\\box\\cgfigbox}%\n"
        "\\end{document}\n"
    )


class NoHome(ValueError):
    """A figure whose look has no place of its own: nothing was written."""


def require_home(figure: Path, output_dir: Path | None) -> None:
    """Raises `NoHome` for a figure outside `content/drafts/` with no
    `output_dir`, and `OutsideContentDir` for an `output_dir` outside
    `content/`. A flat fallback let alike-named figures overwrite each other (#1123)."""
    if output_dir is not None:
        _target_dir(figure, output_dir)
    elif not config.resolves_inside(figure, config.DRAFTS_DIR):
        raise NoHome(
            f"{figure} is not under {config.DRAFTS_DIR}, so its look has no mirrored place "
            "in content/rendered/. Pass --output-dir DIR, a directory under content/."
        )


def digest(source: str, on: Page = ARTICLE) -> str:
    parts = (str(DOCUMENT_VERSION), str(DPI), pdf_fonts.latex_fonts(), on.preamble, source)
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _png_size(path: Path) -> tuple[int, int]:
    width, height = struct.unpack(">II", path.read_bytes()[16:24])
    return width, height


def _paths(figure: Path, out_dir: Path | None) -> tuple[Path, Path, Path]:
    out = _output_dir(figure) if out_dir is None else out_dir
    return tuple(out / f"{figure.stem}.look.{suffix}" for suffix in ("pdf", "png", "json"))


def _current(figure: Path, key: str, out_dir: Path | None) -> Look | None:
    pdf, png, record = _paths(figure, out_dir)
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("digest") != key:
        return None
    if not (pdf.is_file() and png.is_file()):
        return None
    # A record of any other shape was not written here and is rebuilt, not
    # trusted: a pdf render calls this and must not fail on it.
    try:
        sizes = (float(data["width"]), float(data["height"]), float(data["text_width"]))
        columns, rows = data["pixels"]
    except (KeyError, TypeError, ValueError):
        return None
    return Look(pdf, png, record, "current", *sizes, (int(columns), int(rows)))


def _failed(figure: Path, detail: str, out_dir: Path | None) -> Look:
    """A failure, with every old `.look.*` gone so none outlives it."""
    paths = _paths(figure, out_dir)
    for path in paths:
        path.unlink(missing_ok=True)
    return Look(*paths, "failed", detail=detail)


def _engine(tmp: Path, program: str, *args: str) -> CompletedProcess[str]:
    """Run `program`, resolved on PATH, in `tmp`."""
    # Draft text may be someone else's (#823): use the pdf render's engine flags,
    # read fence and environment, as the probe does.
    return _run(
        [programs.require_program(program), *args],
        cwd=tmp,
        capture_output=True,
        text=True,
        check=False,
        env=tex_engine.engine_env(),
    )


def _build(figure: Path, source: str, key: str, out_dir: Path | None, on: Page) -> Look:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "look.tex").write_text(document(source, on), encoding="utf-8")
        opts = ("-interaction=nonstopmode", "-halt-on-error", "look.tex")
        result = _engine(work, "lualatex", *tex_engine.engine_opts(), *opts)
        match = _LOOK_RE.search(result.stdout)
        if result.returncode != 0 or match is None:
            return _failed(figure, _compile_error_detail(result.stdout), out_dir)
        raster = _engine(
            work, "pdftoppm", "-r", str(DPI), "-png", "-singlefile", "look.pdf", "look"
        )
        if raster.returncode != 0:
            return _failed(figure, f"pdftoppm: {raster.stderr.strip()}", out_dir)
        sizes = (float(match["wd"]), float(match["ht"]) + float(match["dp"]), float(match["tw"]))
        pdf, png, record = _paths(figure, out_dir)
        pdf.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(pdf, (work / "look.pdf").read_bytes())
        write_atomically(png, (work / "look.png").read_bytes())
    pixels = _png_size(png)
    fields = dict(zip(("width", "height", "text_width"), sizes, strict=True))
    write_atomically(record, json.dumps({"digest": key, **fields, "pixels": pixels}, indent=2))
    return Look(pdf, png, record, "wrote", *sizes, pixels)


def look(figure: Path, out_dir: Path | None = None, page: Page | None = None) -> Look:
    """`figure`'s look, rebuilt only if anything it is built from changed.

    Written to `out_dir` (confined by the caller) or the mirrored rendered
    directory; each holds its own look (#1114). Set on the figure's own page
    by default, which every caller uses so the record holds one page (#1140).
    Raises `OSError`/`UnicodeDecodeError` for an unreadable figure and
    `OutsideContentDir` for an escaping directory: neither is a finding.
    """
    source = figure.read_text(encoding="utf-8")
    on = page or page_for(figure)[0]
    key = digest(source, on)
    return _current(figure, key, out_dir) or _build(figure, source, key, out_dir, on)


def lines(result: Look, figure: Path) -> list[str]:
    """What a look reports: one line per file, or one for a failure."""
    if result.action == "failed":
        return [f"failed   {figure}: {result.detail}"]
    width, height, text_width = result.width, result.height, result.text_width
    fit = (
        f"{width - text_width:.0f}pt past the text width, line drawn"
        if result.past_text_width
        else f"text width {text_width:.0f}pt"
    )
    columns, rows = result.pixels
    return [
        f"{result.action:<8} {result.pdf}   ({width:.0f} x {height:.0f}pt; {fit})",
        f"{result.action:<8} {result.png}   ({columns} x {rows} px at {DPI} dpi)",
    ]
