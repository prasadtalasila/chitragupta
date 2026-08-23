"""TikZ layout check: what a figure's own geometry says about it.

One of the six aids in the **review layer**, with
chitragupta/review/citation_provenance.py, chitragupta/review/citation_coverage.py,
chitragupta/review/verbatim_check.py, chitragupta/review/synthesis.py and
chitragupta/review/uncited_prose.py -- read over a finished draft, by a person
or by a driver, never a gate, and never holding the write lock. It reports
and exits 0 whatever it finds.

docs/TIKZ-STYLE.md is the standard a figure is written against; this is
the mechanical half of it (#314, docs/FEATURE-ROADMAP.md's D2, planned in
plans/d2-tikz-layout-check.md). Only some of that checklist is decidable
from geometry, and the split matters:

| Check | Kind | Needs pdflatex |
|---|---|---|
| Node text overload (>15 words) | binary | no |
| Edge list | binary, reported for confirmation | no |
| Node overlap | binary | yes |
| Content protrusion | binary | yes |
| Corner emptiness | **continuous, human-read only** | yes |

**Corner emptiness is reported and consumed by nothing**, per
docs/AUTO-IMPROVEMENT.md's R3: no continuous score may be the thing an
unattended loop optimises. The report labels it as such rather than
leaving a reader to infer it -- an unlabelled mixture of binary findings
and a proportion is how a score ends up being driven to zero by
something that should not be driving it.

**Arrow crossings ("chaotic routing") are deliberately not checked.** Not
cheaply reachable from node geometry, and a bad approximation of it would
be worse than its absence, so docs/TIKZ-STYLE.md keeps it a human
judgement.

**The edge list is the point.** Every published PaperBanana diagram
failure is a wrong or missing edge -- semantics, not layout -- and every
one is invisible to a check over pixels. In TikZ an edge is
`\\draw (a) -- (b);`, so it is recoverable from source and reported
plainly for the author to confirm against the prose the figure
illustrates. It is the cheapest possible faithfulness check, needs no
model, and exists only because this pipeline generates source rather than
images.

Usage:
    python -m chitragupta.review figure <draft.md>
    python -m chitragupta.review figure <draft.md> --json
    python -m chitragupta.review figure <draft.md> --write
"""

import argparse
import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import config, review
from chitragupta.render_output._errors import MissingBinary, _require
from chitragupta.render_output._figures import (
    _figure_refs,
    _require_tikz,
    _resolve_sibling,
)
from chitragupta.review.figure_layout._geometry import (
    BBOX_NAME,
    Box,
    emptiness,
    overlaps,
    protrudes,
)
from chitragupta.review.figure_layout._result import FigureResult
from chitragupta.review.figure_layout._report import (
    EMPTINESS_LABEL,
    format_report,
    payload,
    render_markdown,
)
from chitragupta.review.figure_layout._probe import (
    FigureCompileError,
    node_boxes,
    node_names,
    parse_boxes,
    scaffold,
)
from chitragupta.review.figure_layout._source import (
    MAX_NODE_WORDS,
    edge_list,
    overlong_nodes,
)

# Re-exported so the aid is one import for a caller and one name in
# `review.AIDS`, while the three modules behind it stay split by what
# they need: `_source` compiles nothing, `_geometry` is arithmetic, and
# only `_probe` shells out to pdflatex.
__all__ = [
    "BBOX_NAME",
    "Box",
    "EMPTINESS_LABEL",
    "FigureCompileError",
    "FigureResult",
    "MAX_NODE_WORDS",
    "MissingBinary",
    "check_draft",
    "edge_list",
    "emptiness",
    "figures_in",
    "format_report",
    "node_boxes",
    "node_names",
    "overlaps",
    "overlong_nodes",
    "parse_boxes",
    "payload",
    "protrudes",
    "render_markdown",
    "scaffold",
]


def figures_in(draft_path: Path) -> list[Path]:
    """Every TikZ figure file `draft_path` references, as real paths.

    Deliberately not a second parser. `render_output/_figures.py` already
    owns both spellings a draft uses -- a Markdown draft's
    `<!-- figure: ... -->` marker and a `.tex` fragment's real
    `\\input{...}` -- and `_resolve_sibling()` owns the rule that a
    draft's own text is never a reason to read outside its own directory.
    Reusing them means a marker convention changes in one place, not two.

    A reference that does not resolve to a readable file is dropped
    rather than reported here: `render_output`'s own `_figure_warnings()`
    already tells the user about a dangling marker, and there is no
    geometry to check for a figure that is not there.
    """
    text = draft_path.read_text(encoding="utf-8")
    resolved = (_resolve_sibling(draft_path.parent, ref) for ref in _figure_refs(text))
    return [path for path in resolved if path is not None]


def check_draft(draft_path: Path) -> list[FigureResult]:
    """Every figure in `draft_path`, checked as far as this host allows.

    The toolchain is probed once, not once per figure: what this host has
    installed is one fact, and re-probing it per figure would report the
    same absence n times. Where it is missing the static checks still run
    -- that is what the source/geometry split in this package is for.

    **Both halves of the toolchain are probed, and needing both is not
    obvious.** `_require_tikz()` answers "is `tikz.sty` installed?" and
    deliberately says *nothing* on a host with no `kpsewhich`, leaving
    `pdflatex` to report a missing package itself -- correct for the
    renderer, which calls `_require("pdflatex")` separately right beside
    it. An aid that called only `_require_tikz()` would sail past a host
    with no TeX at all and then crash on `FileNotFoundError` from the
    `subprocess` call. CI's Windows leg installs no `os-deps` and is
    exactly that host; it caught this.

    A figure whose own TikZ does not compile becomes a finding on that
    figure and nothing more; the remaining figures are still checked.
    """
    figures = figures_in(draft_path)
    if not figures:
        return []

    skipped = ""
    try:
        _require("pdflatex")
        _require_tikz()  # pragma: no cover-windows
    except MissingBinary as exc:
        skipped = str(exc)

    results = []
    for path in figures:
        source = path.read_text(encoding="utf-8")
        result = FigureResult(
            path=path,
            overlong=overlong_nodes(source),
            edges=edge_list(source),
            skipped=skipped,
        )
        # Unreachable on a host with no TeX, where `skipped` is always
        # set above -- CI's Windows leg, which installs no `os-deps`.
        if not skipped:  # pragma: no cover-windows
            try:
                result.boxes = node_boxes(path)
            except FigureCompileError as exc:
                result.failed = str(exc)
        results.append(result)
    return results


# Said the same way in the text report, the Markdown and the JSON, so a
# reader of any of the three learns the same thing about the number.


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, declared here so the entry point never restates
    them -- `citation_coverage.build_parser`'s own contract."""
    if parser is None:
        parser = argparse.ArgumentParser(
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
    parser.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown "
        "report (default: md,tex,pdf). The .md is always "
        "written -- it is the report; tex/pdf are renders "
        "of it, and need pandoc/pdflatex on PATH.",
    )
    return parser


def main(argv: list[str]) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """**Exits 0 whatever it finds.** An aid that can fail a build is a
    gate, and `citation_gate.py` is the only one this project has.

    `1` is reserved for a draft the layer will not read at all -- missing,
    or outside `content/` -- which is the same contract the other three
    aids apply.
    """
    try:
        draft_path = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1

    results = check_draft(draft_path)
    command = _command(draft_path, args.json, args.write)

    if args.json:
        print(json.dumps(payload(draft_path, results, command), indent=2))
    else:
        print(format_report(draft_path, results))

    if args.write:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        body = render_markdown(draft_path, results, command)
        written = review.write(draft_path, "figure", body, formats)
        written["json"] = review.write_json(
            draft_path, "figure", payload(draft_path, results, command)
        )
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0


def _command(draft_path: Path, as_json: bool, write: bool) -> str:
    """The invocation recorded in the Markdown header and JSON envelope."""
    parts = ["python", "-m", "chitragupta.review", "figure", str(draft_path)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)
