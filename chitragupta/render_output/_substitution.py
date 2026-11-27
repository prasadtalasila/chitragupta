"""The draft-substitution pipeline: math mapping validation, figure/table
warnings, and the one chain that resolves every marker before a writer
sees the text (#441; re-exported from the package root).
"""

import sys
from pathlib import Path

from chitragupta import config
from chitragupta.render_output import (
    _chapter_number,
    _equation_captions,
    _figure_style,
    _math,
    _math_findings,
    _math_symbols,
    _paths,
    _raw_tex,
    _tables,
    _tex_preview,
)
from chitragupta.render_output._citeproc import drop_manual_refs
from chitragupta.render_output._figure_captions import figures as _declared_figures
from chitragupta.render_output._figure_captions import substitute_captions, substitute_refs
from chitragupta.render_output._figures import _figure_warnings, _with_figures_for


def _checked_math_mapping(
    draft_text: str, input_path: Path, mapping_path: "str | Path | None" = None
) -> "dict[str, str]":
    """`input_path`'s ASCII-to-LaTeX mapping, having reported what is wrong.

    Runs only for formats that reach pandoc (a Markdown render keeps its
    ASCII), but above `_require("pandoc")` so it is testable without pandoc.
    `check` raises for the two certain conditions (`_math.check`); the gaps
    only print. A file that can have no `math.md` (outside `content/drafts/`)
    prints no gaps (#1115), but `check` still runs.

    `mapping_path` names the mapping for a draft copy rendered elsewhere
    (`draft diff`'s sides, #1194), confined to `content/`; such a copy prints
    no gaps and reads no glossary.
    """
    if mapping_path is not None:
        mapping_path = config.require_inside_content(Path(mapping_path), "math mapping")
    text = _math.mapping_text(input_path, mapping_path)
    rows = _math.mapping_rows(text)
    mapping = dict(rows)
    path = _math.mapping_path(input_path)
    _math.check(draft_text, input_path, mapping, mapping_path)
    if path is None:
        return mapping
    not_math = _math.not_math(text)
    glossary = _math_symbols.glossary_spans(input_path)
    found = _math_findings.duplicates(rows, not_math) + _math_findings.findings(
        draft_text, mapping, path.is_file(), not_math, glossary
    )
    for finding in found + _math_symbols.findings(rows, text):
        print(f"[math] {finding.message}", file=sys.stderr)
    return mapping


# The tag keeps `[figure]`/`[table]` apart in the one stderr stream a skill
# reads. Collected above `render`'s md early return, where a table's number is
# written here and an unresolvable marker would otherwise go unreported.
def _draft_warnings(draft_text: str, input_path: Path) -> "list[tuple[str, str]]":
    """Every figure, table and equation problem in the draft, tagged with
    its source."""
    return (
        [("figure", w) for w in _figure_warnings(draft_text, input_path)]
        + [("figure", w) for w in _figure_style.warnings(draft_text, input_path)]
        + [("table", w) for w in _tables.warnings(draft_text)]
        + [("equation", w) for w in _equation_captions.warnings(draft_text)]
    )


# Figure captions, refs, figure content, tables, mathematics, equation numbers:
# one chain for both of `render`'s paths.
#
# The figure list is computed once off the pristine `draft_text`: after
# `substitute_refs` or `substitute_captions` has run, the caption pair regex
# would swallow a following sentence or rematch a wrapped caption. Captions
# and refs must also run before `_with_figures_for` replaces the marker.
# Mathematics goes after figures because a figure can introduce an ASCII
# fence that `_math` reads.
#
# The md path passes an empty mapping, so no math is substituted
# (`tests/test_render_output_math.py` pins this), but tables and equation
# numbers still run there, since nothing else numbers them.
def _substituted(
    draft_text: str,
    input_path: Path,
    output_format: str,
    math_mapping: "dict[str, str]",
    fragment: bool = False,
    defer_citations: bool = False,
) -> str:
    """The text a writer actually sees, with every marker resolved.

    `fragment` also drops the References section (the including document
    resolves citations once, `_citeproc.drop_manual_refs`) and a self-stated
    chapter number (`_chapter_number`). Done here so only one place rewrites
    what the writer sees. `defer_citations` drops the References only: it is a
    standalone article with one `\\bibliography`, not a chapter.
    """
    if defer_citations:
        draft_text = drop_manual_refs(draft_text)
    if fragment:
        # `latex` off the `.tex` suffix, not `output_format`: it selects the
        # draft's code regions, and a `.tex` draft's backticks are quotes.
        draft_text = _chapter_number.unnumbered(
            drop_manual_refs(draft_text),
            input_path.suffix.lower() not in _paths._MARKDOWN_SUFFIXES,
        )
    # A `.tex` draft's preview only: its absolute column widths and a
    # figure's own `\centering`, which pandoc's reader would lose or
    # misread (#1120, #1164); `_tex_preview` has why.
    draft_text = _tex_preview.rewrite(draft_text, input_path, output_format, fragment)
    declared = _declared_figures(draft_text)
    with_captions = substitute_captions(draft_text, output_format, declared)
    with_refs = substitute_refs(with_captions, output_format, declared)
    with_figures = _with_figures_for(with_refs, input_path, output_format)
    mathed = _math.substitute(_tables.substitute(with_figures, output_format), math_mapping)
    numbered = _equation_captions.substitute(mathed, output_format)
    # The md path has no pandoc to drop raw LaTeX (#1144). Last in the chain,
    # so it catches a raw span from any pass above too.
    if output_format == "md" and input_path.suffix.lower() in _paths._MARKDOWN_SUFFIXES:
        return _raw_tex.dropped(numbered)
    return numbered
