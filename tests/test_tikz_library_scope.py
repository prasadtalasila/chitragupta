r"""#781: two `figure` floats inputting the same positioning-based figure
must place their nodes identically.

The bug this pins was invisible to every other test here. Each figure
renders correctly *on its own*, so a single-chapter PDF looks right; and
in the shape that actually reached this project's book, `pdflatex` exits
0 and the only trace is `Overfull \hbox` in a log nobody reads.

Three documents, because the defect has two faces:

- `DOCUMENT` is the fix -- library in the preamble, loaded once,
  ungrouped.
- `FLOAT_ONLY_DOCUMENT` is what a figure file's own load does unaided: a
  float is a group, so the macros are defined locally and die with it
  while `\tikz@library@<name>@loaded` is set globally, and the second
  float finds the flag set and the macros gone.
- `RELOADING_DOCUMENT` is the first-generation workaround, and the one
  that produced the *reported* symptom: clearing the flag per float makes
  `positioning` append its placement transform to the **global**
  `\tikz@node@reset@hook` on every load, so the Nth figure shifts every
  node N times, silently.

TeX-guarded, so it skips where TeX Live is absent -- which is most of
this aid's test hosts. It is therefore an *extra* on top of
`tests/test_render_output_tikz_libraries.py` and
`tests/test_render_output_cli.py`, never the only cover for any branch.
"""

import shutil
import subprocess
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("pdflatex") is None, reason="needs a TeX Live installation"
)

# `\typeout` rather than a written file: it lands in pdflatex's stdout,
# so the measurement needs no auxiliary parsing and no second run.
FIGURE = textwrap.dedent(
    r"""
    \usetikzlibrary{positioning}
    \begin{tikzpicture}
      \node[draw] (a) {A};
      \node[draw,right=20mm of a] (b) {B};
      \pgfpointanchor{b}{center}\pgfgetlastxy{\bx}{\by}
      \typeout{BX=\bx}
    \end{tikzpicture}
    """
)

DOCUMENT = textwrap.dedent(
    r"""
    \documentclass{book}
    \usepackage{tikz}
    \usetikzlibrary{positioning}
    \begin{document}
    \begin{figure}\input{fig}\end{figure}
    \begin{figure}\input{fig}\end{figure}
    \end{document}
    """
)

FLOAT_ONLY_DOCUMENT = textwrap.dedent(
    r"""
    \documentclass{book}
    \usepackage{tikz}
    \begin{document}
    \begin{figure}\input{fig}\end{figure}
    \begin{figure}\input{fig}\end{figure}
    \end{document}
    """
)

RELOADING_DOCUMENT = textwrap.dedent(
    r"""
    \documentclass{book}
    \usepackage{tikz}
    \makeatletter
    \def\cgreload{\expandafter\let\csname tikz@library@positioning@loaded\endcsname\relax}
    \makeatother
    \begin{document}
    \begin{figure}\cgreload\input{fig}\end{figure}
    \begin{figure}\cgreload\input{fig}\end{figure}
    \begin{figure}\cgreload\input{fig}\end{figure}
    \end{document}
    """
)


def _compile(tmp_path, document):
    (tmp_path / "fig.tex").write_text(FIGURE, encoding="utf-8")
    (tmp_path / "doc.tex").write_text(document, encoding="utf-8")
    return subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "doc.tex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _node_positions(run):
    return [line for line in run.stdout.splitlines() if line.startswith("BX=")]


def test_two_floats_place_the_node_identically(tmp_path):
    # The whole fix in one assertion: with the library loaded once in the
    # preamble, the second float's node sits exactly where the first
    # one's does.
    run = _compile(tmp_path, DOCUMENT)
    assert run.returncode == 0, run.stdout[-2000:]
    positions = _node_positions(run)
    assert len(positions) == 2
    assert positions[0] == positions[1]


def test_the_preamble_load_leaves_no_overfull_box(tmp_path):
    # The only symptom the original bug left in a build that succeeded.
    _compile(tmp_path, DOCUMENT)
    log = (tmp_path / "doc.log").read_text(encoding="utf-8", errors="replace")
    assert "Overfull" not in log


def test_loading_only_inside_the_floats_breaks_the_second(tmp_path):
    # Not a test of our code -- a test that the grouping mechanism the
    # fix is built on is real. If this ever starts passing, the preamble
    # hoist has become unnecessary and TIKZ-STYLE.md's explanation is
    # wrong rather than merely redundant.
    run = _compile(tmp_path, FLOAT_ONLY_DOCUMENT)
    assert run.returncode != 0
    assert "Unknown operator" in run.stdout


def test_clearing_the_flag_per_float_multiplies_the_shift(tmp_path):
    # The reported symptom, and the reason `review figure`'s
    # `loads-library-by-hand` check exists: this build *succeeds* and
    # every figure after the first is wrong.
    run = _compile(tmp_path, RELOADING_DOCUMENT)
    assert run.returncode == 0, "the symptom is that this build succeeds"
    positions = _node_positions(run)
    assert len(positions) == 3
    assert len(set(positions)) == 3, positions
