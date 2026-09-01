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

import os
import re
import subprocess
import tempfile
from pathlib import Path

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

# `\node[opts] (name) at (x,y) {label}`, for finding what to probe. The
# same shape `_source.py` parses for its own checks; the pattern stays
# separate because the two want different things from it -- this one only
# ever needs the name -- while the declaration's own spelling comes from
# there, so widening it stays one edit rather than two that can drift.
_NODE_NAME_RE = re.compile(_NODE_KEYWORD + r"\s*(?:\[[^\]]*\])?\s*\((?P<name>[^)]+)\)")


# pdflatex wraps every log line -- `\typeout`'s CGBOX lines included --
# at `max_print_line` (~79 columns by default), which breaks the
# one-line `_CGBOX_RE` parse for a node whose name runs long (#496): the
# node then reads as declared but not measured, and can raise a false
# protrusion finding on a figure that compiled fine. kpathsea overrides
# a texmf.cnf setting with a same-named environment variable, so setting
# this in the subprocess env (below) is enough -- no texmf.cnf edit, and
# no `-max-print-line` flag, which pdflatex/web2c does not offer. 1000 is
# comfortably past any real node name this project's figures use.
_MAX_PRINT_LINE = "1000"


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
    """
    return [match.group("name").strip() for match in _NODE_NAME_RE.finditer(strip_comments(source))]


def scaffold(source: str, names: list[str]) -> str:
    """A minimal document that compiles `source` and prints its geometry.

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
    while pdflatex still exits 0 -- a wrong answer that looks like a
    right one.

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
    probes = "\n".join(
        f"\\pgfpointanchor{{{name}}}{{south west}}\\pgfgetlastxy{{\\cgx}}{{\\cgy}}%\n"
        f"\\pgfpointanchor{{{name}}}{{north east}}\\pgfgetlastxy{{\\cgxx}}{{\\cgyy}}%\n"
        f"\\typeout{{CGBOX {name} \\cgx\\space\\cgy\\space\\cgxx\\space\\cgyy}}%"
        for name in [*names, BBOX_NAME]
    )
    return (
        "\\documentclass{article}\n"
        "\\usepackage{tikz}\n"
        "\\newdimen\\cgx \\newdimen\\cgy \\newdimen\\cgxx \\newdimen\\cgyy\n"
        "\\begin{document}\n"
        f"{_with_probes_inside(source, probes)}\n"
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


def node_boxes(figure_path: Path) -> dict[str, Box]:
    """Compile `figure_path` in a temp directory and return its geometry.

    **The compile is a side effect and must not litter.** Everything
    pdflatex writes -- `.aux`, `.log`, `.pdf` -- lands in a
    `TemporaryDirectory` and is gone when this returns, so running a
    review aid never leaves build artefacts beside a user's draft.

    Raises `FigureCompileError` if this figure does not compile. That is
    a finding for the caller to report, not a crash: the draft's other
    figures are still worth checking.
    """
    # Every line below needs a real pdflatex, which CI's Windows leg does
    # not install (`os-deps` is apt-only) -- the same `no cover-windows`
    # marking render_output.py's own toolchain tail carries, and for the
    # same reason. The Linux leg measures all of it for real.
    source = figure_path.read_text(encoding="utf-8")  # pragma: no cover-windows
    with tempfile.TemporaryDirectory() as tmp:  # pragma: no cover-windows
        probe = Path(tmp) / "probe.tex"
        probe.write_text(scaffold(source, node_names(source)), encoding="utf-8")
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", probe.name],
            cwd=tmp,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "max_print_line": _MAX_PRINT_LINE},
        )
        if result.returncode != 0:
            raise FigureCompileError(_compile_error_detail(result.stdout))
        return parse_boxes(result.stdout)


def _compile_error_detail(log: str) -> str:
    """The first TeX error line from a failed run, for the report.

    A whole pdflatex log is far too much to put in a review report, and
    its first `!` line is the one a human would look at anyway.
    """
    for line in log.splitlines():
        if line.startswith("!"):
            return line.strip()
    return "pdflatex failed without reporting an error line"
