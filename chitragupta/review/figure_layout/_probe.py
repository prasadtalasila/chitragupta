r"""Getting a figure's real geometry out of TeX.

**Why a compile is needed at all**, since "just parse the source" is the
obvious cheaper thought: a node's box depends on the font, the label's
rendered width and TikZ's own layout, none of which exists until TeX has
run. `\node (a) at (0,0) {A}` says where a node's *anchor* is, never how
big it turned out.

**And why the compile is instrumented**, since "just compile it and read
the PDF" is the next one: a compiled figure's PDF retains no node names
at all. Verified -- its content stream is anonymous drawing operators
(`1 0 0 1 155.769 660.474 cm`, `[(A)]TJ`), because TikZ knows a name only
while it is running and the PDF has already forgotten. A bare compile can
answer "does this compile?" and nothing else. The `\typeout` below is
what makes TeX write the name-to-box mapping down while it still knows
it.

The emitted document is `article`-based and reads coordinates through
pgf's public `\pgfgetlastxy`; `scaffold()`'s own docstring has the
reasoning for both, and both were arrived at by compiling rather than by
reading documentation.
"""

import re
from dataclasses import dataclass

# `_run` is the one patch point for this module's external launches
# (#854), in the shape `render_output._pandoc._run_pandoc` set: a test
# fakes it here and so fakes this module's subprocess and nobody
# else's. Patching the global `subprocess.run` reached every launch in
# the process.
from subprocess import run as _run
import tempfile
from pathlib import Path

from chitragupta import pdf_fonts, programs, tex_engine
from chitragupta.render_output._tikz_libraries import libraries_in
from chitragupta.review.figure_layout._geometry import BBOX_NAME, Box
from chitragupta.review.figure_layout._source import _NODE_KEYWORD, strip_comments

# What the scaffold prints per node, and what this module parses back.
# One node per line, `pt`-suffixed as TeX writes dimensions.
_CGBOX_RE = re.compile(
    r"^CGBOX (?P<name>.+?) "
    r"(?P<x1>-?[\d.]+)pt (?P<y1>-?[\d.]+)pt "
    r"(?P<x2>-?[\d.]+)pt (?P<y2>-?[\d.]+)pt\s*$",
    re.MULTILINE,
)

# The boxed scaffold's one extra line: the width of the box the whole
# figure file was set in.
_CGWIDTH_RE = re.compile(r"^CGWIDTH (?P<wd>-?[\d.]+)pt\s*$", re.MULTILINE)

# `\node[opts] (name) at (x,y) {label}`, for finding what to probe. The
# same shape `_source.py` parses for its own checks; the pattern stays
# separate because the two want different things from it -- this one only
# ever needs the name -- while the declaration's own spelling comes from
# there, so widening it stays one edit rather than two that can drift.
_NODE_NAME_RE = re.compile(_NODE_KEYWORD + r"\s*(?:\[[^\]]*\])?\s*\((?P<name>[^)]+)\)")


class FigureCompileError(RuntimeError):
    """One figure's own TikZ did not compile.

    Distinct from `render_output.MissingBinary`, and the distinction is
    the whole of this aid's failure policy. `MissingBinary` says *the
    host* cannot compile any figure -- one fact, checked once, reported
    once. This says *this figure* is broken while others may be fine, so
    the caller catches it per figure and carries on checking the rest.
    """


def node_names(source: str) -> list[str]:
    """Every node name the figure defines, in source order.

    The scaffold needs these up front: `\\pgfpointanchor` is asked for
    one named node at a time, so the probe has to know what to ask for
    before it can ask.

    **Getting this wrong fails loudly and in the wrong direction**,
    which is why comments are stripped and why the `child` spelling
    counts (#404). A name found where no node was drawn makes
    `\\pgfpointanchor` raise ``No shape named ... is known`` and takes
    the whole compile down, so the aid reports the *figure* as broken. A
    name missed leaves that node unmeasured, and `protrudes()` then
    reads the band it occupies as empty -- a seven-node tree drawn with
    `child` reported one node and a protrusion it did not have.

    A name holding `#` is skipped: that is TeX's macro-parameter
    character, so the declaration sits inside a macro's definition and
    names a node only once a caller fills it in (#1012's
    `\\cglegenditem`, whose `(#1)` took the compile down).
    """
    matches = _NODE_NAME_RE.finditer(strip_comments(source))
    names = (match.group("name").strip() for match in matches)
    return [name for name in names if "#" not in name]


def scaffold(source: str, names: list[str], *, boxed: bool = False) -> str:
    """A minimal document that compiles `source` and prints its geometry.

    `boxed` is `figure check`'s variant (#1053), and changes two things
    together. The figure's own libraries load in the preamble, as the
    renderer loads them (#781), and the figure is set in a box whose
    width is printed as `CGWIDTH`. Together because a box measured
    without the preload reports a library's load spaces as width
    (#1046), which is the one stray width that is not the figure's
    fault. The box is TeX's own `\\setbox...\\hbox{}`, and both LaTeX
    spellings fail it: `\\sbox` reads the figure as a macro argument,
    which freezes the catcode of `&` that a TikZ `matrix` changes (the
    `map` scaffold did not compile), and `lrbox` trims the trailing
    space a `\\end{tikzpicture}` with no `%` sets, the commonest stray
    there is. The box is shipped, not dropped: LuaTeX refuses a run that
    wrote PDF objects (the `shadows.blur` fadings) and shipped no page
    (#1037). The default call is `review figure`'s, and emits exactly
    what it always has.

    `article`, deliberately, not `standalone`: `standalone.cls` lives in
    `texlive-latex-extra` while `tikz.sty` lives in `texlive-pictures`,
    so building on it would add a toolchain dependency
    `_require_tikz()` does not check -- reintroducing #226's bug in a new
    place. This is also the same minimal wrapper
    docs/WRITING-STANDARDS.md §10 already tells an author to verify a
    figure with, so a figure that compiles here compiles there.

    Coordinates come back through `\\pgfgetlastxy`, pgf's public
    accessor, rather than the internal `\\pgf@x`/`\\pgf@y` registers.
    Reading those directly needs `\\makeatletter`, and *without* it the
    `\\typeout` silently degrades to the literal text `\\the \\pgf`
    while the engine still exits 0 -- a wrong answer that looks like a
    right one.

    **It sets type as the pdf render does (#1037)**: `article` at
    12pt, with `chitragupta-lualatex.tex`'s fonts, written from
    `pdf_fonts.latex_fonts()` so the two cannot drift, under LuaLaTeX.
    A node's box is its label's width, so a box measured in pdflatex's
    10pt Computer Modern was a box the reader never saw, and a label
    only the render's font chain can set (`≤`, `α`) did not compile at
    all without chitragupta-unicode.sty.

    The picture's own extent is read the same way, from TikZ's
    `current bounding box` pseudo-node, so protrusion and emptiness need
    no second mechanism.

    **The probes are injected inside the figure's own `tikzpicture`, not
    appended in a second one**, and this is not a stylistic preference.
    A node's anchors survive into a later picture, so appending *looks*
    like it works -- every node box comes back correct. `current bounding
    box` does not: it is a property of the picture being built, so a
    fresh empty picture reports TikZ's empty-box sentinel
    (16000pt, 16000pt, -16000pt, -16000pt) instead of the figure's real
    extent. That sentinel has a vast positive area, so emptiness came out
    as "100% empty" for every real figure, which is how this was found.
    """
    # A name spelled with a macro (`(s\i)` in a `\foreach`) names a node
    # only while that macro is defined; at the probes, after the loop,
    # it is not, and the compile dies on `Missing \endcsname` (#1072).
    # Left out here but kept in `names`, so it reads as declared but not
    # measured rather than vanishing from the report.
    probes = "\n".join(
        f"\\pgfpointanchor{{{name}}}{{south west}}\\pgfgetlastxy{{\\cgx}}{{\\cgy}}%\n"
        f"\\pgfpointanchor{{{name}}}{{north east}}\\pgfgetlastxy{{\\cgxx}}{{\\cgyy}}%\n"
        f"\\typeout{{CGBOX {name} \\cgx\\space\\cgy\\space\\cgxx\\space\\cgyy}}%"
        for name in [*names, BBOX_NAME]
        if "\\" not in name
    )
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
        + "\\newdimen\\cgx \\newdimen\\cgy \\newdimen\\cgxx \\newdimen\\cgyy\n"
        + ("\\newsavebox\\cgfigbox\n" if boxed else "")
        + "\\begin{document}\n"
        f"{figure}\n"
        "\\end{document}\n"
    )


# Where the probes go: immediately before the figure's last
# `\end{tikzpicture}`, so they run while that picture is still open.
_PICTURE_END_RE = re.compile(r"\\end\{tikzpicture\}")


def _with_probes_inside(source: str, probes: str) -> str:
    """`source` with `probes` spliced in before its final picture ends.

    The *last* `\\end{tikzpicture}`, so a figure built from several
    pictures is measured as the whole thing a reader sees rather than as
    its first component.

    A figure with no `tikzpicture` at all cannot be measured, and gets
    the probes appended instead -- they will find nothing, which is the
    honest answer for a figure file that draws no picture.
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
    """What one compile of a figure returned: its node boxes, and the
    width of the box the whole file was set in (`None` unless the
    compile was `boxed`)."""

    boxes: dict[str, Box]
    input_width: float | None = None


def node_boxes(figure_path: Path) -> dict[str, Box]:
    """`measure(figure_path)`'s boxes: what `review figure` reads."""
    return measure(figure_path).boxes  # pragma: no cover-windows


def measure(figure_path: Path, *, boxed: bool = False) -> Measurement:
    """Compile `figure_path` in a temp directory and return its geometry.

    **The compile is a side effect and must not litter.** Everything
    the engine writes -- `.aux`, `.log`, `.pdf` -- lands in a
    `TemporaryDirectory` and is gone when this returns, so running a
    review aid never leaves build artefacts beside a user's draft.

    Raises `FigureCompileError` if this figure does not compile. That is
    a finding for the caller to report, not a crash: the draft's other
    figures are still worth checking.
    """
    # Every line below needs a real lualatex, which CI's Windows leg does
    # not install (`os-deps` is apt-only) -- the same `no cover-windows`
    # marking render_output.py's own toolchain tail carries, and for the
    # same reason. The Linux leg measures all of it for real.
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
            # The figure file is draft text, and a shared tree's draft
            # text is someone else's (#823): the same engine flags, read
            # fence and environment as the pdf render (`tex_engine`),
            # whose `max_print_line` also keeps a long node name's CGBOX
            # line whole (#496).
            env=tex_engine.engine_env(),
        )
        if result.returncode != 0:
            raise FigureCompileError(_compile_error_detail(result.stdout))
        return Measurement(parse_boxes(result.stdout), parse_input_width(result.stdout))


def _compile_error_detail(log: str) -> str:
    """The first TeX error line from a failed run, for the report.

    A whole TeX log is far too much to put in a review report, and
    its first `!` line is the one a human would look at anyway.
    """
    for line in log.splitlines():
        if line.startswith("!"):
            return line.strip()
    return "lualatex failed without reporting an error line"
