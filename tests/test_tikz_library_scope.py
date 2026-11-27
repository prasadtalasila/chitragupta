import shutil
import subprocess
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("lualatex") is None, reason="needs a TeX Live installation"
)

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
        ["lualatex", "-interaction=nonstopmode", "doc.tex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )


def _node_positions(run):
    return [line for line in run.stdout.splitlines() if line.startswith("BX=")]


def test_two_floats_place_the_node_identically(tmp_path):
    run = _compile(tmp_path, DOCUMENT)
    assert run.returncode == 0, run.stdout[-2000:]
    positions = _node_positions(run)
    assert len(positions) == 2
    assert positions[0] == positions[1]


def test_the_preamble_load_leaves_no_overfull_box(tmp_path):
    _compile(tmp_path, DOCUMENT)
    log = (tmp_path / "doc.log").read_text(encoding="utf-8", errors="replace")
    assert "Overfull" not in log


def test_loading_only_inside_the_floats_breaks_the_second(tmp_path):
    run = _compile(tmp_path, FLOAT_ONLY_DOCUMENT)
    assert run.returncode != 0
    assert "Unknown operator" in run.stdout


def test_clearing_the_flag_per_float_multiplies_the_shift(tmp_path):
    run = _compile(tmp_path, RELOADING_DOCUMENT)
    assert run.returncode == 0, "the symptom is that this build succeeds"
    positions = _node_positions(run)
    assert len(positions) == 3
    assert len(set(positions)) == 3, positions
