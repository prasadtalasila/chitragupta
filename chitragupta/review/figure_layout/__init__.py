"""TikZ layout check: what a figure's own geometry says about it.

The mechanical half of docs/TIKZ-STYLE.md (#314, D2). A review aid,
never a gate, no write lock, exit 0 whatever it finds. Node overlap,
protrusion and "nothing measurable" need lualatex; text overload, the
edge list, stranded arrowheads and hand-loaded libraries (#781) do not.
What was measurable is reported, never inferred (#405). Corner emptiness
is continuous and consumed by nothing (R3). Arrow crossings are not
checked: a bad approximation would be worse than none.

**This package measures; it never places.** TikZ owns the layout; every
coordinate enters through `_probe.py`'s injected `\\pgfpointanchor`, and
nothing in `_geometry.py` returns a position. Computing one would make
this a second, worse layout engine that silently disagrees with TikZ.

The edge list is the cheapest faithfulness check: diagram failures are
mostly wrong or missing edges, invisible to any pixel check.

Usage:
    python -m chitragupta.review figure <draft.md>
    python -m chitragupta.review figure <draft.md> --json
    python -m chitragupta.review figure <draft.md> --write
"""

# The thresholds in `_geometry.py` are this module's calibration for an
# advisory report, generous so ordinary layouts pass: a finding to agree
# or disagree with, not a number to drive down.

import argparse
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, review
from chitragupta.review import _emit
from chitragupta.render_output._errors import MissingBinary, _require
from chitragupta.render_output._figures import (
    _figure_refs,
    _require_tikz,
    _resolve_sibling,
)
from chitragupta.review.figure_layout._geometry import (
    BBOX_NAME,
    Box,
    edge_gap,
    emptiness,
    leaves,
    contains,
    intersects,
    overlaps,
    protrudes,
)
from chitragupta.review.figure_layout._check_one import check_figure
from chitragupta.review.figure_layout._drawn import Drawn, DrawnLine, DrawnNode, Point
from chitragupta.review.figure_layout._result import FigureResult
from chitragupta.review.figure_layout._report import (
    EMPTINESS_LABEL,
    format_report,
    payload,
    render_markdown,
)
from chitragupta.review.figure_layout._probe import (
    FigureCompileError,
    Measurement,
    measure,
    node_boxes,
    node_names,
    parse_boxes,
    parse_input_width,
    scaffold,
)
from chitragupta.review.figure_layout._source import (
    MAX_NODE_WORDS,
    ambiguous_edges,
    edge_list,
    loads_library_by_hand,
    overlong_nodes,
    stranded_arrowheads,
)
from chitragupta.help_format import ClickParser

# Re-exported as one import; `_source` compiles nothing, `_geometry` is
# arithmetic, and only `_probe` shells out to lualatex.
__all__ = [
    "BBOX_NAME",
    "Box",
    "Drawn",
    "DrawnLine",
    "DrawnNode",
    "EMPTINESS_LABEL",
    "FigureCompileError",
    "FigureResult",
    "MAX_NODE_WORDS",
    "ambiguous_edges",
    "Measurement",
    "MissingBinary",
    "Point",
    "check_draft",
    "check_figure",
    "edge_gap",
    "contains",
    "edge_list",
    "emptiness",
    "figures_in",
    "format_report",
    "leaves",
    "intersects",
    "loads_library_by_hand",
    "measure",
    "node_boxes",
    "node_names",
    "overlaps",
    "overlong_nodes",
    "parse_boxes",
    "parse_input_width",
    "payload",
    "protrudes",
    "render_markdown",
    "scaffold",
    "stranded_arrowheads",
]


def figures_in(draft_path: Path) -> list[Path]:
    """Every TikZ figure file `draft_path` references, as real paths.

    Reuses `render_output/_figures.py`'s marker parsing and sibling-only
    resolution rather than a second parser. A dangling reference is
    dropped: `render_output` already warns about it.
    """
    text = draft_path.read_text(encoding="utf-8")
    resolved = (_resolve_sibling(draft_path.parent, ref) for ref in _figure_refs(text))
    return [path for path in resolved if path is not None]


def check_draft(draft_path: Path) -> list[FigureResult]:
    """Every figure in `draft_path`, checked as far as this host allows.

    The toolchain is probed once. Both `lualatex` and `tikz.sty` are
    required: `_require_tikz()` says nothing without `kpsewhich`, so on a
    host with no TeX at all (CI's Windows leg) it alone would crash later.
    A figure that does not compile is a finding on that figure only.
    """
    figures = figures_in(draft_path)
    if not figures:
        return []

    skipped = ""
    try:
        _require("lualatex")
        _require_tikz()  # pragma: no cover-windows
    except MissingBinary as exc:
        skipped = str(exc)

    return [check_figure(path, skipped) for path in figures]


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, declared once for the entry point."""
    if parser is None:
        parser = ClickParser(
            description="Report what a draft's TikZ figures' own geometry says.",
        )
    parser.add_argument("draft", help="Path to the draft whose figures to check")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the findings as JSON instead of as text. "
        "--write files it beside the report either way.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Also write the report to content/review/, mirroring the "
        "draft's path. Off by default: printing is the usual use.",
    )
    _emit.add_formats(parser)
    return parser


def main(argv: list[str]) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """**Exits 0 whatever it finds**: `citation_gate.py` is the only gate.
    `1` is for a draft the layer will not read (missing, or outside
    `content/`).
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    results = check_draft(draft_path)
    return _emit.emit(
        draft_path,
        "figure",
        args,
        text=lambda: format_report(draft_path, results),
        command=lambda: _command(draft_path, args.json, args.write),
        payload=lambda command: payload(draft_path, results, command),
        markdown=lambda command: render_markdown(draft_path, results, command),
    )


def _command(draft_path: Path, as_json: bool, write: bool) -> str:
    """The invocation recorded in the Markdown header and JSON envelope."""
    parts = ["python", "-m", "chitragupta.review", "figure", str(draft_path)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)
