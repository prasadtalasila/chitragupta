"""One figure, checked: the body `review figure` runs per figure of a
draft and `chitragupta figure check` (#1053) runs on one file.

Its own module because `__init__.py` was at the 250-code-line ceiling
when the second caller arrived, and "one figure" against "a draft's
figures" is the seam that module already had.
"""

from pathlib import Path

from chitragupta.review.figure_layout._probe import FigureCompileError, measure, node_names
from chitragupta.review.figure_layout._result import FigureResult
from chitragupta.review.figure_layout._source import (
    edge_list,
    loads_library_by_hand,
    overlong_nodes,
    stranded_arrowheads,
)


def check_figure(path: Path, skipped: str, *, boxed: bool = False) -> FigureResult:
    """Every check on `path`, geometry included unless `skipped` says the
    host cannot compile (the caller probes the toolchain once, not once
    per figure).

    A figure whose own TikZ does not compile becomes `failed` on its
    result rather than an exception, so a draft's other figures are
    still checked. `boxed` is `figure check`'s probe; `_probe.scaffold`
    has what it changes.
    """
    source = path.read_text(encoding="utf-8")
    result = FigureResult(
        path=path,
        overlong=overlong_nodes(source),
        edges=edge_list(source),
        stranded=stranded_arrowheads(source),
        by_hand=loads_library_by_hand(source),
        # What the probe will ask TeX about, recorded so the report can
        # say how much of the figure was measurable (#405). The same call
        # `measure()` makes internally over the same file, so the two
        # cannot disagree about what was attempted -- which is the whole
        # point of recording it. (A name spelled with a macro is declared
        # here and never probed, so it reads as unmeasured: #1072.)
        declared=node_names(source),
        skipped=skipped,
    )
    # Unreachable on a host with no TeX, where `skipped` is always set by
    # the caller -- CI's Windows leg, which installs no `os-deps`.
    if not skipped:  # pragma: no cover-windows
        try:
            measured = measure(path, boxed=boxed)
        except FigureCompileError as exc:
            result.failed = str(exc)
        else:
            result.boxes = measured.boxes
            result.input_width = measured.input_width
    return result
