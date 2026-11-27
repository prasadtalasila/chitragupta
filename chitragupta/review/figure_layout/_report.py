"""Turning checked figures into text, Markdown and a JSON payload.

Nothing here checks anything. The emptiness proportion is labelled
advisory everywhere and kept out of `findings` (R3): a number in a
findings array is one something will try to drive to zero.
"""

from pathlib import Path

from chitragupta import review
from chitragupta.review.figure_layout._result import FigureResult
from chitragupta.review.figure_layout._source import MAX_NODE_WORDS

# Said the same way in all three formats.
EMPTINESS_LABEL = "advisory, human-read only -- nothing consumes this"

# #405: "nothing here to check" used to print the same as "fine".
UNMEASURABLE = (
    "names no node, so nothing was measured -- the overlap, protrusion "
    "and emptiness checks did not run"
)


def _figure_lines(result: FigureResult) -> list[str]:
    lines = []
    if result.failed:
        lines.append(f"  - does not compile: {result.failed}")
    for name, count in result.overlong:
        lines.append(f"  - node `{name}` has {count} words (over {MAX_NODE_WORDS})")
    # Comprehensions only to stay inside C1's statement limit.
    lines += [
        f"  - an arrowhead lands mid-line at `({point})`, where another path "
        f"continues -- put the `->` on the last piece only"
        for point in result.stranded
    ]
    lines += [
        f"  - loads its TikZ library by hand (`{internal}`) -- the renderer loads "
        f"the union in the preamble, so delete this and keep only the plain "
        f"`\\usetikzlibrary` line"
        for internal in result.by_hand
    ]
    for one, other in result.overlapping:
        lines.append(f"  - nodes `{one}` and `{other}` overlap")
    if result.protruding:
        lines.append("  - content protrudes past the main block, wasting vertical space")
    if result.nothing_measurable:
        lines.append(f"  - {UNMEASURABLE}")
    if result.unmeasured:
        # A diagnostic, not a finding: it makes a protrusion untrustworthy.
        # Named, not counted: a ratio is something to drive (R3).
        named = ", ".join(f"`{name}`" for name in result.unmeasured)
        lines.append(
            f"  - declared but not measured: {named} "
            f"(the geometry checks ran over less than the figure)"
        )
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
    """The plain-text report; `render_markdown` is the filed version."""
    if not results:
        return f"No figures found in {draft_path} -- nothing to check."
    lines = [f"TikZ layout check for {draft_path}", ""]
    for result in results:
        # A figure with nothing to say gets no empty heading.
        said = _figure_lines(result)
        if said:
            lines += [f"{result.path}:", *said]
    if not any(result.has_findings for result in results):
        lines += ["", "No layout findings. This is not a verdict on the figure."]
    return "\n".join(lines)


def render_markdown(draft_path: Path, results: list[FigureResult], command: str) -> str:
    """The same findings as a Markdown document, filed and read later."""
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
        said = [f"- {line.strip().removeprefix('- ')}" for line in _figure_lines(result)]
        # Every figure keeps its heading here: a filed record must show
        # what was checked.
        lines += said or ["Nothing to report for this figure."]
        lines.append("")
    return "\n".join(lines)


def _findings(results: list[FigureResult]) -> list[dict]:
    """One object per binary finding.

    `empty_fraction` and the unmeasured names ride per-figure instead
    (R3: a score among findings is a target). `nothing-measurable` is
    binary with one fix, so it is a finding.
    """
    findings = []
    for result in results:
        figure = str(result.path)
        if result.failed:
            findings.append({"figure": figure, "kind": "does-not-compile", "detail": result.failed})
        findings += [
            {"figure": figure, "kind": "node-text-overload", "node": name, "words": count}
            for name, count in result.overlong
        ]
        findings += [
            {"figure": figure, "kind": "node-overlap", "nodes": [one, other]}
            for one, other in result.overlapping
        ]
        findings += [
            {"figure": figure, "kind": "stranded-arrowhead", "at": point}
            for point in result.stranded
        ]
        findings += [
            {"figure": figure, "kind": "loads-library-by-hand", "internal": internal}
            for internal in result.by_hand
        ]
        if result.protruding:
            findings.append({"figure": figure, "kind": "content-protrusion"})
        if result.nothing_measurable:
            findings.append({"figure": figure, "kind": "nothing-measurable"})
    return findings


def payload(draft_path: Path, results: list[FigureResult], command: str) -> dict:
    """The findings as data: a serialisation, never a second computation."""
    body = review.envelope(draft_path, "figure", command)
    body.update(
        {
            "findings": _findings(results),
            "figures": [
                {
                    "path": str(result.path),
                    "edges": [list(edge) for edge in result.edges],
                    "empty_fraction": result.empty_fraction,
                    "empty_fraction_note": EMPTINESS_LABEL,
                    # True because a compile happened, not because anything
                    # was checked (#405); a shipped key, so the two fields
                    # beside it carry the fix.
                    "geometry_checked": result.boxes is not None,
                    "names_declared": result.declared,
                    "names_unmeasured": result.unmeasured,
                }
                for result in results
            ],
        }
    )
    return body
