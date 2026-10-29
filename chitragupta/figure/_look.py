r"""One figure as it will print, cropped to itself: `chitragupta figure
look` (#1052).

`figure check` measures what a rule can name; this is for what no rule
measures -- a label that wrapped badly, an arrow through a zone title, a
figure that reads as cramped -- which only a look catches. So it writes
a picture to look at, and measures only what it needs to say about it.

**Set as the render sets it.** The document is `render()`'s house page,
`article` at 12pt on A4 with 1in margins, so `\textwidth` is the 453pt
the figure will be set in, with the fonts the probe sets
(`pdf_fonts.latex_fonts()`) and the figure's own TikZ libraries loaded
in the preamble as the renderer loads them (#781). A library loaded
inside the box would add stray width the render does not have (#1046).
The figure's source is inlined rather than `\input`, as the probe's
is, so the read fence has no second file to admit.

**Cropped to the figure.** The page is the figure's box plus
`BORDER_PT` on every side, set through LuaTeX's `\pagewidth` and
`\pageheight` with the box shipped at the page's corner -- the job the
`standalone` class does, done by hand because `standalone.cls` is not
something `_require_tikz` checks for (the probe's reason too). A figure
wider than the text width gets a hairline at the text width, measured
from the figure's left edge, which is where a too-wide figure in a
centred float starts to stick out; one that fits gets none.

**Only what changed is rebuilt.** `<stem>.look.json` records a digest
of every input and what was measured, so an unchanged figure costs a
file read rather than a LuaLaTeX run.
"""

import hashlib
import json
import re
import struct
import tempfile

# `_run` is this module's one patch point for its external launches
# (#854), in the shape the probe and the renderer use.
from subprocess import CompletedProcess
from subprocess import run as _run
from dataclasses import dataclass
from pathlib import Path

from chitragupta import pdf_fonts, programs, tex_engine
from chitragupta._atomic_write import write_atomically
from chitragupta.render_output._paths import _output_dir
from chitragupta.render_output._tikz_libraries import libraries_in
from chitragupta.review.figure_layout._probe import _compile_error_detail

DPI = 300
BORDER_PT = 1.0

# Part of the digest: raise it when `document()` changes what it draws,
# so every look built by the old document is rebuilt.
DOCUMENT_VERSION = 1

# The document's one line of output, among everything else TeX prints.
_LOOK_RE = re.compile(
    r"^CGLOOK (?P<wd>[\d.]+)pt (?P<ht>[\d.]+)pt (?P<dp>[\d.]+)pt (?P<tw>[\d.]+)pt",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Look:
    """What `look` did for one figure, and what it measured.

    `action` is `wrote`, `current` or `failed`; `detail` says why a
    failure failed. Sizes are TeX points, `height` including depth.
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


def document(source: str) -> str:
    """The page `source` is set on: see this module's docstring."""
    libraries = libraries_in(source)
    return (
        "\\documentclass[12pt,a4paper]{article}\n"
        "\\usepackage[margin=1in]{geometry}\n"
        "\\usepackage{fontspec}\n"
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


def digest(source: str) -> str:
    """Everything a look is built from, in one hash."""
    parts = (str(DOCUMENT_VERSION), str(DPI), pdf_fonts.latex_fonts(), source)
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _png_size(path: Path) -> tuple[int, int]:
    """A PNG's pixel size, from its IHDR chunk."""
    width, height = struct.unpack(">II", path.read_bytes()[16:24])
    return width, height


def _paths(figure: Path) -> tuple[Path, Path, Path]:
    out = _output_dir(figure)
    return tuple(out / f"{figure.stem}.look.{suffix}" for suffix in ("pdf", "png", "json"))


def _current(figure: Path, key: str) -> Look | None:
    """The recorded look, if it was built from `key` and is all there."""
    pdf, png, record = _paths(figure)
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("digest") != key:
        return None
    if not (pdf.is_file() and png.is_file()):
        return None
    # A record of any other shape is one this module did not write, and is
    # rebuilt rather than trusted: a pdf render calls this after its PDF
    # is written, and must not fail on it.
    try:
        sizes = (float(data["width"]), float(data["height"]), float(data["text_width"]))
        columns, rows = data["pixels"]
    except (KeyError, TypeError, ValueError):
        return None
    return Look(pdf, png, record, "current", *sizes, (int(columns), int(rows)))


def _failed(figure: Path, detail: str) -> Look:
    """A failure, with every old `.look.*` gone so none outlives it."""
    paths = _paths(figure)
    for path in paths:
        path.unlink(missing_ok=True)
    return Look(*paths, "failed", detail=detail)


def _engine(tmp: Path, program: str, *args: str) -> CompletedProcess[str]:
    """Run `program`, resolved on PATH, in `tmp`."""
    # The figure file is draft text, and a shared tree's draft text is
    # someone else's (#823): the pdf render's own engine flags, read fence
    # and environment, as the probe uses.
    return _run(
        [programs.require_program(program), *args],
        cwd=tmp,
        capture_output=True,
        text=True,
        check=False,
        env=tex_engine.engine_env(),
    )


def _build(figure: Path, source: str, key: str) -> Look:
    """Compile and rasterize in a temporary directory, then move both in."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "look.tex").write_text(document(source), encoding="utf-8")
        opts = ("-interaction=nonstopmode", "-halt-on-error", "look.tex")
        result = _engine(work, "lualatex", *tex_engine.engine_opts(), *opts)
        match = _LOOK_RE.search(result.stdout)
        if result.returncode != 0 or match is None:
            return _failed(figure, _compile_error_detail(result.stdout))
        raster = _engine(
            work, "pdftoppm", "-r", str(DPI), "-png", "-singlefile", "look.pdf", "look"
        )
        if raster.returncode != 0:
            return _failed(figure, f"pdftoppm: {raster.stderr.strip()}")
        sizes = (float(match["wd"]), float(match["ht"]) + float(match["dp"]), float(match["tw"]))
        pdf, png, record = _paths(figure)
        pdf.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(pdf, (work / "look.pdf").read_bytes())
        write_atomically(png, (work / "look.png").read_bytes())
    pixels = _png_size(png)
    fields = dict(zip(("width", "height", "text_width"), sizes, strict=True))
    write_atomically(record, json.dumps({"digest": key, **fields, "pixels": pixels}, indent=2))
    return Look(pdf, png, record, "wrote", *sizes, pixels)


def look(figure: Path) -> Look:
    """`figure`'s look, rebuilt only if anything it is built from changed.

    Raises `OSError` or `UnicodeDecodeError` for a figure it cannot read,
    and `render_output.OutsideContentDir` where the rendered directory
    resolves outside the content directory: neither is a finding.
    """
    source = figure.read_text(encoding="utf-8")
    key = digest(source)
    return _current(figure, key) or _build(figure, source, key)


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
