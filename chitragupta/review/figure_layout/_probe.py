r"""Getting a figure's real geometry out of TeX.

A compile is needed because a node's box depends on fonts and TikZ's
layout, which do not exist until TeX runs. It is instrumented because the
PDF keeps no node names (its content stream is anonymous operators), so
the injected `\typeout` records name-to-box while TikZ still knows it.
"""

import re
from dataclasses import dataclass

# `_run` is this module's one patch point for external launches (#854):
# patching the global `subprocess.run` reached every launch in the process.
from subprocess import run as _run
import tempfile
from pathlib import Path

from chitragupta import config, pdf_fonts, programs, tex_engine
from chitragupta.render_output._tikz_libraries import libraries_in
from chitragupta.review.figure_layout._drawn import Drawn, parse_drawn
from chitragupta.review.figure_layout._geometry import BBOX_NAME, Box
from chitragupta.review.figure_layout._source import named_nodes

_CGBOX_RE = re.compile(
    r"^CGBOX (?P<name>.+?) "
    r"(?P<x1>-?[\d.]+)pt (?P<y1>-?[\d.]+)pt "
    r"(?P<x2>-?[\d.]+)pt (?P<y2>-?[\d.]+)pt\s*$",
    re.MULTILINE,
)

# The boxed scaffold's width of the box the whole figure was set in.
_CGWIDTH_RE = re.compile(r"^CGWIDTH (?P<wd>-?[\d.]+)pt\s*$", re.MULTILINE)


class FigureCompileError(RuntimeError):
    """One figure's own TikZ did not compile.

    Unlike `MissingBinary` (the host cannot compile anything, reported
    once), this is per figure: the caller catches it and checks the rest.
    """


def node_names(source: str) -> list[str]:
    """Every node name the figure defines, in source order.

    Wrong in either direction fails badly, hence comment stripping and
    `child` (#404): a spurious name makes `\\pgfpointanchor` kill the
    compile; a missed one reads its band as empty, a false protrusion.
    Names holding `#` sit in a macro definition and are skipped (#1012).
    The name may follow the position (#1112).
    """
    return [name for name, _ in named_nodes(source) if "#" not in name]


# A node's box as min/max over its four side anchors: corners lie on the
# curve for a circle (~30% too small, #1054), and a quarter-turned node's
# `west`/`east` share an x (#1064). `cg-figure-probe.tex` uses it too.
_SIDES = (
    "\\def\\cgside#1#2{\\pgfpointanchor{#1}{#2}\\pgfgetlastxy{\\cgpx}{\\cgpy}%\n"
    "  \\ifdim\\cgpx<\\cgx\\relax\\let\\cgx\\cgpx\\fi\n"
    "  \\ifdim\\cgpx>\\cgxx\\relax\\let\\cgxx\\cgpx\\fi\n"
    "  \\ifdim\\cgpy<\\cgy\\relax\\let\\cgy\\cgpy\\fi\n"
    "  \\ifdim\\cgpy>\\cgyy\\relax\\let\\cgyy\\cgpy\\fi}\n"
    "\\def\\cgsides#1{\\pgfpointanchor{#1}{west}\\pgfgetlastxy{\\cgx}{\\cgy}%\n"
    "  \\let\\cgxx\\cgx\\let\\cgyy\\cgy\n"
    "  \\cgside{#1}{south}\\cgside{#1}{east}\\cgside{#1}{north}}\n"
)


def scaffold(source: str, names: list[str], *, boxed: bool = False) -> str:
    """A minimal document that compiles `source` and prints its geometry.

    `boxed` (`figure check`, #1053) preloads the figure's libraries as the
    renderer does (#781) and sets it in a box printed as `CGWIDTH`;
    together, or a library's load spaces count as width (#1046). The box
    is `\\setbox...\\hbox{}`: `\\sbox` freezes `&`'s catcode (breaks
    `matrix`), and `lrbox` trims the trailing space a stray would set. It
    is shipped because LuaTeX refuses a run with PDF objects and no page
    (#1037). `boxed` also inlines the drawing hook (#1054).

    `article`, not `standalone`: `standalone.cls` is in
    `texlive-latex-extra`, a dependency `_require_tikz()` does not check
    (#226). Coordinates via public `\\pgfgetlastxy`: `\\pgf@x` without
    `\\makeatletter` silently prints literal text while exiting 0.
    Fonts and 12pt match the pdf render (#1037), via
    `pdf_fonts.latex_fonts()`, since a box is its label's width.

    **Probes go inside the figure's own `tikzpicture`**: node anchors
    survive into a later picture, but `current bounding box` there is
    TikZ's empty sentinel (+-16000pt), which read as "100% empty".
    """
    # A macro-spelled name (`(s\i)`) is undefined after the loop and kills
    # the compile (#1072): left out here, kept in `names` as unmeasured.
    probes = "\n".join(
        f"\\cgsides{{{name}}}%\n"
        f"\\typeout{{CGBOX {name} \\cgx\\space\\cgy\\space\\cgxx\\space\\cgyy}}%"
        for name in [*names, BBOX_NAME]
        if "\\" not in name
    )
    if boxed:
        probes += "\n\\cgdumpnodes%"
    figure = _with_probes_inside(source, probes)
    libraries = libraries_in(source) if boxed else []
    if boxed:
        figure = (
            f"\\setbox\\cgfigbox=\\hbox{{%\n{figure}%\n}}%\n"
            "\\typeout{CGWIDTH \\the\\wd\\cgfigbox}%\n"
            "\\noindent\\usebox\\cgfigbox"
        )
    return (
        "\\documentclass[12pt]{article}\n"
        "\\usepackage{fontspec}\n"
        "\\usepackage{unicode-math}\n"
        f"{pdf_fonts.latex_fonts()}"
        "\\usepackage{tikz}\n"
        + (f"\\usetikzlibrary{{{','.join(libraries)}}}\n" if libraries else "")
        + (_drawing_hook() if boxed else "")
        + _SIDES
        + ("\\newsavebox\\cgfigbox\n" if boxed else "")
        + "\\begin{document}\n"
        f"{figure}\n"
        "\\end{document}\n"
    )


def _drawing_hook() -> str:
    """`assets/latex/cg-figure-probe.tex`, inlined: the probe compiles
    behind the `openin_any=p` read fence (#823), so it cannot `\\input`
    a file outside its own directory (#1054)."""
    return config.shipped("assets", "latex", "cg-figure-probe.tex").read_text(encoding="utf-8")


# Before the last `\end{tikzpicture}`, while that picture is still open.
_PICTURE_END_RE = re.compile(r"\\end\{tikzpicture\}")


def _with_probes_inside(source: str, probes: str) -> str:
    """`source` with `probes` spliced in before its final picture ends,
    so a multi-picture figure is measured whole. With no `tikzpicture`,
    the probes are appended and honestly find nothing.
    """
    matches = list(_PICTURE_END_RE.finditer(source))
    if not matches:
        return f"{source}\n{probes}"
    cut = matches[-1].start()
    return f"{source[:cut]}{probes}\n{source[cut:]}"


def parse_boxes(log: str) -> dict[str, Box]:
    """`{node name: (x1, y1, x2, y2)}` from the scaffold's own output."""
    return {
        match.group("name"): (
            float(match.group("x1")),
            float(match.group("y1")),
            float(match.group("x2")),
            float(match.group("y2")),
        )
        for match in _CGBOX_RE.finditer(log)
    }


def parse_input_width(log: str) -> float | None:
    """The boxed scaffold's `CGWIDTH`, or `None` where it printed none."""
    match = _CGWIDTH_RE.search(log)
    return float(match.group("wd")) if match else None


@dataclass
class Measurement:
    """One compile's node boxes, and the width of the box the file was
    set in (`None` unless `boxed`)."""

    boxes: dict[str, Box]
    input_width: float | None = None
    # What TikZ drew (#1054), from the boxed compile's hook only.
    drawn: Drawn | None = None


def node_boxes(figure_path: Path) -> dict[str, Box]:
    """`measure(figure_path)`'s boxes: what `review figure` reads."""
    return measure(figure_path).boxes  # pragma: no cover-windows


def measure(figure_path: Path, *, boxed: bool = False) -> Measurement:
    """Compile `figure_path` in a temp directory and return its geometry.

    Every artefact stays in the `TemporaryDirectory`, so a review never
    litters beside a draft. Raises `FigureCompileError` for a figure that
    does not compile: a finding, not a crash.
    """
    # Needs a real lualatex, which CI's Windows leg does not install.
    source = figure_path.read_text(encoding="utf-8")  # pragma: no cover-windows
    with tempfile.TemporaryDirectory() as tmp:  # pragma: no cover-windows
        probe = Path(tmp) / "probe.tex"
        probe.write_text(scaffold(source, node_names(source), boxed=boxed), encoding="utf-8")
        result = _run(
            [
                programs.require_program("lualatex"),
                *tex_engine.engine_opts(),
                "-interaction=nonstopmode",
                "-halt-on-error",
                probe.name,
            ],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
            # Draft text may be someone else's (#823): the pdf render's
            # flags, read fence and env; `max_print_line` keeps CGBOX whole (#496).
            env=tex_engine.engine_env(),
        )
        if result.returncode != 0:
            raise FigureCompileError(_compile_error_detail(result.stdout))
        log = result.stdout
        drawn = parse_drawn(log) if boxed else None
        return Measurement(parse_boxes(log), parse_input_width(log), drawn)


def _compile_error_detail(log: str) -> str:
    """The first TeX error line (`!`) from a failed run, for the report."""
    for line in log.splitlines():
        if line.startswith("!"):
            return line.strip()
    return "lualatex failed without reporting an error line"
