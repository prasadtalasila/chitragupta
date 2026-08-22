"""Turning checked figures into the three things a reader gets: text on
stdout, a Markdown document, and a JSON payload.

Split from `__init__.py` for size, and the seam is a real one: nothing
here checks anything. It receives `FigureResult`s and serialises them, so
the checks stay testable without going through a formatter and the
formatting stays testable without a compile.

**One rule runs through all three formats.** The emptiness proportion is
labelled advisory wherever it appears and is kept out of the `findings`
list entirely -- docs/AUTO-IMPROVEMENT.md's R3. A number sitting in a
findings array is a number something will eventually try to drive to
zero, and this one must not be.
"""

from pathlib import Path

from chitragupta import review
from chitragupta.review.figure_layout._result import FigureResult
from chitragupta.review.figure_layout._source import MAX_NODE_WORDS

# Said the same way in the text report, the Markdown and the JSON, so a
# reader of any of the three learns the same thing about the number.
EMPTINESS_LABEL = "advisory, human-read only -- nothing consumes this"

def _figure_lines(result: FigureResult) -> list[str]:
    """One figure's findings, as the report prints them."""
    lines = []
    if result.failed:
        lines.append(f"  - does not compile: {result.failed}")
    for name, count in result.overlong:
        lines.append(
            f"  - node `{name}` has {count} words (over {MAX_NODE_WORDS})"
        )
    for one, other in result.overlapping:
        lines.append(f"  - nodes `{one}` and `{other}` overlap")
    if result.protruding:
        lines.append("  - content protrudes past the main block, wasting vertical space")
    if result.edges:
        drawn = ", ".join(f"{one} -> {other}" for one, other in result.edges)
        lines.append(f"  - edges (confirm against the prose): {drawn}")
    if result.empty_fraction is not None:
        lines.append(
            f"  - {result.empty_fraction * 100:.0f}% of the figure's box is empty "
            f"({EMPTINESS_LABEL})"
        )
    if result.skipped:
        lines.append(f"  - geometry not checked: {result.skipped}")
    return lines


def format_report(draft_path: Path, results: list[FigureResult]) -> str:
    """The plain-text report, for a question asked and answered in one
    sitting. `render_markdown` is the same findings for a file kept."""
    if not results:
        return f"No figures found in {draft_path} -- nothing to check."
    lines = [f"TikZ layout check for {draft_path}", ""]
    for result in results:
        # A figure with nothing to say is left out rather than given an
        # empty heading. Over a chapter's worth of figures the bare
        # `path:` lines were most of the output and carried none of the
        # information.
        said = _figure_lines(result)
        if said:
            lines += [f"{result.path}:", *said]
    if not any(result.has_findings for result in results):
        lines += ["", "No layout findings. This is not a verdict on the figure."]
    return "\n".join(lines)


def render_markdown(draft_path: Path, results: list[FigureResult], command: str) -> str:
    """The same findings as a Markdown document, filed beside the draft's
    other review reports and read months later."""
    lines = review.header(draft_path, "figure", command)
    lines += [
        "## How to read this",
        "",
        "Geometry, not taste. Every binary finding below is a fact about where",
        "TeX actually put something -- but a figure with no findings is not",
        "thereby a good figure, and docs/TIKZ-STYLE.md's own checklist has",
        "several items nothing here can see. Arrow crossings in particular are",
        "deliberately not checked.",
        "",
        "**The edge list is the one to read closely.** Nothing here knows which",
        "edges *should* exist, so confirming them against the prose the figure",
        "illustrates is the check -- and it is the failure mode that a review",
        "of the rendered picture would most easily miss.",
        "",
    ]
    if not results:
        lines += [f"No figures found in `{draft_path}`.", ""]
        return "\n".join(lines)
    for result in results:
        lines += ["## " + str(result.path), ""]
        said = [f"- {line.strip().removeprefix('- ')}"
                for line in _figure_lines(result)]
        # Unlike the text report, every figure keeps its heading here: a
        # filed report is read as a record of what was checked, so a
        # figure silently absent from it is indistinguishable from one
        # that was never looked at.
        lines += said or ["Nothing to report for this figure."]
        lines.append("")
    return "\n".join(lines)


def _findings(results: list[FigureResult]) -> list[dict]:
    """One object per binary finding.

    `empty_fraction` is deliberately **not** here. It rides in the
    per-figure section of the payload instead, because R3's rule is that
    a continuous score is never the thing optimised -- and a score listed
    among the findings is a score something will eventually try to close.
    """
    findings = []
    for result in results:
        figure = str(result.path)
        if result.failed:
            findings.append({"figure": figure, "kind": "does-not-compile",
                             "detail": result.failed})
        findings += [{"figure": figure, "kind": "node-text-overload",
                      "node": name, "words": count}
                     for name, count in result.overlong]
        findings += [{"figure": figure, "kind": "node-overlap",
                      "nodes": [one, other]}
                     for one, other in result.overlapping]
        if result.protruding:
            findings.append({"figure": figure, "kind": "content-protrusion"})
    return findings


def payload(draft_path: Path, results: list[FigureResult], command: str) -> dict:
    """The findings as data -- an additional serialisation of what the
    report prints, never a second computation."""
    body = review.envelope(draft_path, "figure", command)
    body.update({
        "findings": _findings(results),
        "figures": [
            {
                "path": str(result.path),
                "edges": [list(edge) for edge in result.edges],
                "empty_fraction": result.empty_fraction,
                "empty_fraction_note": EMPTINESS_LABEL,
                "geometry_checked": result.boxes is not None,
            }
            for result in results
        ],
    })
    return body
