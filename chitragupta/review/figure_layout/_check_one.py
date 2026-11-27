"""One figure, checked: the body `review figure` runs per figure of a
draft and `chitragupta figure check` (#1053) runs on one file.
"""

import re
from pathlib import Path

from chitragupta.review.figure_layout._drawn import Drawn
from chitragupta.review.figure_layout._geometry import Box
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
    host cannot compile. A compile failure becomes `failed` on the result,
    so a draft's other figures are still checked. `boxed`: see
    `_probe.scaffold`.
    """
    source = path.read_text(encoding="utf-8")
    result = FigureResult(
        path=path,
        overlong=overlong_nodes(source),
        edges=edge_list(source),
        stranded=stranded_arrowheads(source),
        by_hand=loads_library_by_hand(source),
        # Recorded with `measure()`'s own call so the report can say how
        # much was measurable (#405). Macro-spelled names: #1072, #1112.
        declared=node_names(source),
        skipped=skipped,
    )
    # Unreachable with no TeX (CI's Windows leg sets `skipped`).
    if not skipped:  # pragma: no cover-windows
        try:
            measured = measure(path, boxed=boxed)
        except FigureCompileError as exc:
            result.failed = str(exc)
        else:
            result.boxes = measured.boxes
            result.input_width = measured.input_width
            result.drawn = measured.drawn
            if measured.drawn:
                result.declared = _expand_loops(result.declared, result.boxes, measured.drawn)
    return result


# A control sequence in a declared name: `\i` in `(s\i)`.
_MACRO_RE = re.compile(r"\\[a-zA-Z@]+|\\.")


def _expand_loops(declared: list[str], boxes: dict[str, Box], drawn: Drawn) -> list[str]:
    """`declared` with each macro-spelled name (`s\\i` from a `\\foreach`)
    replaced by the drawn nodes it names, whose boxes join `boxes` (#1112).
    Each macro matches at least one character; names another declaration
    claims, coordinates, and `cgu-`/`@` names are excluded. A node named
    apart that fits the pattern is counted too. A name with no literal
    part (`(\\i)`) would match every node, so it stays unmeasured."""
    expanded = []
    for name in declared:
        literal = _MACRO_RE.sub("", name)
        if "\\" not in name or not literal.strip():
            expanded.append(name)
            continue
        pattern = re.compile(".+".join(map(re.escape, _MACRO_RE.split(name))))
        found = [
            drawn_name
            for drawn_name in drawn.nodes
            if pattern.fullmatch(drawn_name)
            and drawn_name not in declared + expanded
            and not drawn_name.startswith("cgu-")
            and drawn.nodes[drawn_name].shape != "coordinate"
            and "@" not in drawn_name
        ]
        for drawn_name in found:
            boxes[drawn_name] = drawn.nodes[drawn_name].box
        expanded += found or [name]
    return expanded
