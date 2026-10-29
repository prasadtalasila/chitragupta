"""`figure check`'s two outputs: the text report and the `--json`
payload. Nothing here checks anything; `_check.py` does, and this
serialises what it found, so the JSON is never a second computation.

The text is one line per finding, `<rule-id> <target> <measurement>`,
because that is what a drafting agent quotes back in a `% cg-allow:`
line or to its caller. Everything that is not a finding -- an allow,
a rule that could not run, the edge list, the emptiness proportion --
sits under its own heading, so nothing is read as a finding that is
not one. The emptiness proportion keeps `review figure`'s label for the
reason that module gives: R3 keeps a continuous score out of anything
something could drive to zero.
"""

from chitragupta.figure._check import FIGURE, CheckResult
from chitragupta.figure._rules import RULES
from chitragupta.review.figure_layout import EMPTINESS_LABEL, FigureResult


def format_text(result: CheckResult) -> str:
    lines = [str(result.path)]
    lines += [_row(f.rule, f.target, f.measurement) for f in result.findings]
    lines += _section(
        "allowed",
        [
            _row(allow.rule, allow.target or FIGURE, f"{measured or 'did not fire'} {_why(allow)}")
            for allow, measured in result.allowed
        ],
    )
    lines += _section(
        "not honoured until #1058",
        [_row(allow.rule, allow.target, _why(allow)) for allow in result.deferred],
    )
    lines += _section(
        "malformed allows",
        [f"  line {bad.line}: {bad.text}  ({bad.problem})" for bad in result.malformed],
    )
    lines += _section("not measured", [f"  {rule}: {why}" for rule, why in result.not_measured])
    lines += _section("diagnostics (not findings)", _diagnostics(result.figure))
    if not result.findings:
        lines.append("No findings. This is not a verdict on the figure.")
    found = len(result.findings)
    lines.append(
        f"figure check: {found} finding{'' if found == 1 else 's'}, {len(result.allowed)} allowed, "
        f"{len(result.deferred)} deferred, {len(result.malformed)} malformed"
    )
    return "\n".join(lines)


def _row(rule: str, target: str, text: str) -> str:
    # 21 is the longest rule id, `loads-library-by-hand`.
    return f"  {rule:<21} {target:<10} {text}"


def _why(allow) -> str:
    return f"-- {allow.reason} (line {allow.line})"


def _section(heading: str, rows: list[str]) -> list[str]:
    """`rows` under `heading`, or nothing: an empty section says nothing."""
    return [heading, *rows] if rows else []


def _diagnostics(figure: FigureResult) -> list[str]:
    rows = []
    if figure.edges:
        drawn = ", ".join(f"{one} -> {other}" for one, other in figure.edges)
        rows.append(f"  edges (confirm against the prose): {drawn}")
    if figure.unmeasured:
        rows.append(f"  declared but not measured: {', '.join(figure.unmeasured)}")
    if figure.empty_fraction is not None:
        rows.append(
            f"  {figure.empty_fraction * 100:.0f}% of the figure's box is empty ({EMPTINESS_LABEL})"
        )
    return rows


def payload(result: CheckResult) -> dict:
    figure = result.figure
    return {
        "figure": str(result.path),
        "width_pt": result.width_pt,
        "findings": [
            {
                "rule": f.rule,
                "class": RULES[f.rule].cls,
                "scope": RULES[f.rule].scope,
                "target": f.target,
                "measurement": f.measurement,
            }
            for f in result.findings
        ],
        "allowed": [
            {**_allow(allow), "measurement": measured} for allow, measured in result.allowed
        ],
        "deferred": [_allow(allow) for allow in result.deferred],
        "malformed": [
            {"line": bad.line, "text": bad.text, "problem": bad.problem} for bad in result.malformed
        ],
        "not_measured": [{"rule": rule, "why": why} for rule, why in result.not_measured],
        "diagnostics": {
            "edges": [list(edge) for edge in figure.edges],
            "empty_fraction": figure.empty_fraction,
            "empty_fraction_note": EMPTINESS_LABEL,
            "names_unmeasured": figure.unmeasured,
        },
    }


def _allow(allow) -> dict:
    return {"rule": allow.rule, "target": allow.target, "reason": allow.reason, "line": allow.line}
