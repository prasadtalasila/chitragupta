"""The draft-substitution pipeline: math mapping validation, figure/table
warnings, and the one chain that resolves every marker before a writer
sees the text.

Split from `chitragupta/render_output/__init__.py` (#441). Re-exported
from there like every other `_X.py` sibling in this package -- see that
module's own docstring on why the package's attribute surface has to
stay identical to the single module it replaced.
"""

import sys
from pathlib import Path

from chitragupta.render_output import _equation_captions, _math, _tables
from chitragupta.render_output._figure_captions import figures as _declared_figures
from chitragupta.render_output._figure_captions import substitute_captions, substitute_refs
from chitragupta.render_output._figures import _figure_warnings, _with_figures_for


def _checked_math_mapping(draft_text: str, input_path: Path) -> "dict[str, str]":
    """`input_path`'s ASCII-to-LaTeX mapping, having reported what is wrong.

    Called past `render`'s Markdown-to-Markdown early return, so it runs
    for exactly the formats that reach pandoc -- the one predicate §12's
    mapping turns on. A Markdown-to-Markdown render leaves the draft's
    ASCII alone, which is the whole point of holding the LaTeX elsewhere.

    Above `_require("pandoc")` in the caller, deliberately: a mapping
    problem is worth reporting on a host with no pandoc installed, and
    keeping it out of that untestable tail is what lets it be covered.

    `check` raises rather than warning, for the two conditions that are
    certain rather than heuristic -- see `_math.check`. The gaps below it
    print and carry on, the way a figure problem does.
    """
    mapping = _math.load_mapping(input_path)
    path = _math.mapping_path(input_path)
    _math.check(draft_text, input_path, mapping)
    for warning in _math.warnings(draft_text, mapping, path is not None and path.is_file()):
        print(f"[math] {warning}", file=sys.stderr)
    return mapping


# One list rather than a loop per kind in `render()`, and the tag is what
# keeps `[figure]` and `[table]` apart in the one stderr stream a genre
# skill reads.
#
# Both kinds are collected *above* `render`'s Markdown-to-Markdown early
# return, because that path is where a table's number is written here
# rather than deferred to LaTeX -- so it is the path where an
# unresolvable marker costs the most, and the one that would otherwise
# report nothing at all.
def _draft_warnings(draft_text: str, input_path: Path) -> "list[tuple[str, str]]":
    """Every figure, table and equation problem in the draft, tagged with
    its source."""
    return (
        [("figure", w) for w in _figure_warnings(draft_text, input_path)]
        + [("table", w) for w in _tables.warnings(draft_text)]
        + [("equation", w) for w in _equation_captions.warnings(draft_text)]
    )


# Figure captions and references, then figure content, then tables, then
# mathematics -- one chain with one definition, reached by both of
# `render`'s paths.
#
# The figure list is computed exactly once, off `draft_text` before either
# substitution has touched it, and handed to both. Recomputing it off text
# a prior pass already rewrote is wrong twice over: after `substitute_refs`
# has run, a `figureref` sentence right after an uncaptioned marker no
# longer starts with `<!--`, so `substitute_captions`'s own pair regex
# would misread that sentence as the marker's caption and swallow it, and
# a marker `substitute_captions` has already wrapped in `\caption{...}` or
# `**Figure N:**` would spuriously match the pair regex *again*. Captions
# therefore run first, off the one precomputed list, and refs run second
# on the result -- a `figureref` marker is a self-contained inline token,
# so wrapping earlier text in a caption around it changes nothing about
# resolving it. Both have to run before `_with_figures_for` replaces the
# marker with actual content, too: after that, the `[marker, caption]`
# adjacency captions looks for no longer exists. A figure substitution can
# also introduce a fenced ASCII block, and `_math`'s own display rule
# reads fences, so mathematics goes last.
#
# The Markdown path passes an empty mapping, which substitutes nothing --
# §12 deliberately leaves a Markdown render's ASCII alone, and
# `tests/test_render_output_math.py` pins that. Tables are the opposite
# case and pass through here on that path too: their numbers exist
# nowhere else, since that path never reaches pandoc.
#
# Equation numbering runs last, and needs no precomputed list of its own
# unlike the figure one above: `_equation_captions.py` is the only pass
# that reads whatever `_math.substitute` left behind rather than content
# beside it, so nothing earlier in this chain moves an equation marker
# relative to another one, and counting document order in the result
# agrees with counting it in `draft_text`. See that module's own
# docstring for why its numbering, unlike its content, is not gated on
# `math_mapping` being non-empty -- it runs on every format, `md` included.
def _substituted(
    draft_text: str, input_path: Path, output_format: str, math_mapping: "dict[str, str]"
) -> str:
    """The text a writer actually sees, with every marker resolved."""
    declared = _declared_figures(draft_text)
    with_captions = substitute_captions(draft_text, output_format, declared)
    with_refs = substitute_refs(with_captions, output_format, declared)
    with_figures = _with_figures_for(with_refs, input_path, output_format)
    mathed = _math.substitute(_tables.substitute(with_figures, output_format), math_mapping)
    return _equation_captions.substitute(mathed, output_format)
