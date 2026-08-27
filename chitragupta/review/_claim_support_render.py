"""How a claim-support report reads: the Markdown document and the
plain-text stdout form.

Split from `claim_support.py` the same way `_uncited_render.py` is split
from `uncited_prose.py` -- nothing here imports it back, keeping the
dependency one-way.

One paragraph here is load-bearing and must not be trimmed: the caveat
that a low score is not a fact-check and a high score is not proof,
because retrieval already selected these passages by similarity.
Dropping it is exactly the failure mode docs/REVIEW.md's "Three limits"
section warns against -- a score read as a verdict.

A finding whose citekey could not be scored (`finding["note"]` is set)
is never printed with a percentage here, in either form. `findings()`
(Task 2) still gives every unscoreable citekey a `Finding` with
`score=0.0` so it sorts and lists like any other citation, but a
"(0%)" beside `[@missing_2024]` would read as "checked and scored
zero" -- exactly the "checked and found wanting" standing
`claim_support.py`'s own module docstring says an unscoreable citekey
must not carry. Telling the two apart at render time is this module's
job; the upstream report has no generic way to do it.
"""

from chitragupta import review

_HOW_TO_READ = [
    "## How to read this",
    "",
    "Each entry pairs a citing sentence with the passage of its cited",
    "source an entailment model scored as the best match, ranked",
    "**worst first**. There are no bands here, unlike `provenance` --",
    "retrieval already selected these passages by similarity, so the",
    "model is discriminating inside a set chosen for being similar,",
    "and a threshold would claim a precision this corpus does not",
    "support (see docs/PLAGIARISM-DESIGN.md's tier 3 for the same",
    "argument made about wording overlap instead of entailment).",
    "",
    "**A low score is not a fact-check, and a high score is not proof.**",
    "A correct paraphrase can score low if it drifts from the source's",
    "own wording style; a claim that happens to echo its source's",
    "vocabulary can score high while misrepresenting it. The score is",
    "where to spend attention, not a verdict.",
    "",
    "A citekey whose source has no passage with readable text (a",
    "page-level scan, or nothing parsed at all) cannot be scored and",
    'is noted rather than given a score of zero standing for "checked',
    'and found wanting".',
    "",
]


def _scored(found: list[dict]) -> list[dict]:
    """The findings an entailment model actually scored -- every other
    citation `findings()` lists is still one line in Findings below,
    just not counted as "scored" here or given a percentage."""
    return [f for f in found if f["note"] is None]


def _summary(report, found: list[dict]) -> list[str]:
    scored = _scored(found)
    lines = [
        "## Summary",
        "",
        f"**{len(scored)}** citation{'s' if len(scored) != 1 else ''} scored, "
        f"**{len(report.unscoreable)}** citekey{'s' if len(report.unscoreable) != 1 else ''} "
        "could not be scored.",
        "",
    ]
    if report.unscoreable:
        lines += ["### Not scored", ""]
        for citekey, reason in sorted(report.unscoreable.items()):
            lines.append(f"- `{citekey}`: {reason}")
        lines.append("")
    return lines


def _status(finding: dict) -> str:
    """What to print in place of a percentage -- a real score for a
    scored finding, or the reason for one that could not be, never a
    "0%" standing in for "checked and found wanting"."""
    if finding["note"]:
        return f"not scored -- {finding['note']}"
    return f"{finding['score']:.0%}"


def _finding_lines(finding: dict) -> list[str]:
    return [
        f"- **line {finding['line']}** `[@{finding['citekey']}]` "
        f"({_status(finding)}) (`{finding['id']}`)",
        f"  > {finding['claim']}" if finding["claim"] else "  > (no claim text)",
    ]


def render_markdown(report, command: str, found: list[dict]) -> str:
    lines = review.header(report.draft, "support", command)
    lines += _HOW_TO_READ
    lines += _summary(report, found)
    lines += ["## Findings", ""]
    if not found:
        lines += ["No citations found in this draft.", ""]
    for finding in found:
        lines += _finding_lines(finding)
    return "\n".join(lines)


def _format_finding(finding: dict) -> str:
    if finding["note"]:
        return f"  n/a  line {finding['line']} [@{finding['citekey']}]: {finding['note']}"
    return (
        f"  {finding['score']:.0%} line {finding['line']} "
        f"[@{finding['citekey']}]: {finding['claim']}"
    )


def format_report(report, found: list[dict]) -> str:
    """No sections here, unlike `render_markdown` -- a flat list, one line
    per citation. So this does not also walk `report.unscoreable` the way
    `_summary` does: `build_report` (Task 2) never sets
    `unscoreable[citekey]` without appending a `Finding` carrying the same
    reason in the same pass, so every unscoreable citekey is already one
    of `_format_finding`'s `n/a` lines above -- a second pass over
    `report.unscoreable` here would repeat the same reason on an adjacent
    line rather than add anything a flat, section-less report can use."""
    scored = _scored(found)
    lines = [
        f"Claim support in {report.draft}",
        f"{len(scored)} citations scored, {len(report.unscoreable)} not scored",
    ]
    for finding in found:
        lines.append(_format_finding(finding))
    return "\n".join(lines)
