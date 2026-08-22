"""TikZ layout check: what a figure's own geometry says about it.

The fourth aid in the **review layer**, with
chitragupta/review/citation_provenance.py, chitragupta/review/citation_coverage.py and
chitragupta/review/verbatim_check.py -- run by hand on a finished draft, never
automatically, never a gate, and never holding the write lock. It reports
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

from pathlib import Path

from chitragupta.render_output._figures import _figure_refs, _resolve_sibling
from chitragupta.review.figure_layout._geometry import (
    BBOX_NAME, Box, emptiness, overlaps, protrudes,
)
from chitragupta.review.figure_layout._probe import (
    FigureCompileError, node_boxes, node_names, parse_boxes, scaffold,
)
from chitragupta.review.figure_layout._source import (
    MAX_NODE_WORDS, edge_list, overlong_nodes,
)

# Re-exported so the aid is one import for a caller and one name in
# `review.AIDS`, while the three modules behind it stay split by what
# they need: `_source` compiles nothing, `_geometry` is arithmetic, and
# only `_probe` shells out to pdflatex.
__all__ = [
    "BBOX_NAME", "Box", "FigureCompileError", "MAX_NODE_WORDS",
    "edge_list", "emptiness", "figures_in", "node_boxes", "node_names",
    "overlaps", "overlong_nodes", "parse_boxes", "protrudes", "scaffold",
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

