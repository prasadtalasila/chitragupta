"""How a claim-support report reads: the Markdown document, the
plain-text stdout form, and the same findings as a JSON payload.

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

import hashlib

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


def finding_id(citekey: str, claim: str) -> str:
    """A finding's identity, stable across runs (R2) -- keyed on the
    same (citekey, claim) pair _citation_provenance_render.finding_id uses,
    because this is the same underlying question asked by a different
    scorer. Defined locally rather than imported: every aid in this
    layer owns its own finding_id, even when the formula matches."""
    digest = hashlib.sha256(f"{citekey}\x00{claim}".encode())
    return digest.hexdigest()[:12]


def findings(report) -> list[dict]:
    """One object per citation, worst-scoring first -- already the
    Report's own sort order, so this only shapes the dicts."""
    return [
        {
            "id": finding_id(f.citekey, f.claim),
            "line": f.line,
            "citekey": f.citekey,
            "claim": f.claim,
            "score": f.score,
            "note": f.note,
        }
        for f in report.findings
    ]


def support_payload(report, command: str) -> dict:
    """The same findings the report prints, as data -- an additional
    serialisation, never a second computation.

    `"scored"` counts findings the entailer actually scored (`note is
    None`), not `len(report.findings) - len(report.unscoreable)`. The
    two differ when a single unscoreable citekey is cited more than
    once: `report.unscoreable` is keyed by citekey, so it gains one
    entry no matter how many findings that citekey produces, while
    `build_report` still gives every one of those findings its own
    `note`. Counting the naive way would let "scored" overcount by the
    number of repeat citations of an already-unscoreable citekey --
    inconsistent with `_claim_support_render._scored`, which every
    rendered report already uses for the same number. Matching that
    keeps the JSON and the text report agreeing on what "scored"
    means.

    Deliberately different units, not a second inconsistency:
    `"scored"` counts findings (one per citation), `"unscoreable"`
    counts citekeys (one per source), the same split
    `_claim_support_render._summary` already prints -- a repeated
    citation of one bad citekey is one line under "Not scored" but two
    lines under Findings, in the JSON exactly as in the rendered
    report."""
    payload = review.envelope(report.draft, "support", command)
    payload.update(
        {
            "scored": len([f for f in report.findings if f.note is None]),
            "unscoreable": dict(sorted(report.unscoreable.items())),
            "findings": findings(report),
        }
    )
    return payload
