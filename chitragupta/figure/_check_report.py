"""`figure check`'s text report and `--json` payload, serialised from what
`_check.py` found so the JSON is never a second computation.

One line per finding, `<rule-id> <target> <measurement>`, as an agent quotes it
in a `% cg-allow:` line; a target with a space is double-quoted (#1058).
Non-findings sit under their own headings and never change "No findings". The
emptiness proportion keeps `review figure`'s label: R3 keeps a continuous score
out of anything something could drive to zero.
"""

from chitragupta.figure._allow import Allow
from chitragupta.figure._check import FIGURE, CheckResult
from chitragupta.figure._rules import RULES, Finding
from chitragupta.page import Page
from chitragupta.review.figure_layout import EMPTINESS_LABEL


def format_text(result: CheckResult) -> str:
    lines = [str(result.path)]
    lines += [_row(f.rule, _quoted(f.target), f.measurement) for f in result.findings]
    lines += _section(
        "advisory (read; never resolved, allowed or capped)",
        [_row(f.rule, f.target, f.measurement) for f in result.advisory],
    )
    lines += _section("allowed", _allow_rows(result.allowed))
    lines += _section("stale allows", _allow_rows(result.stale))
    lines += _section("unchecked allows", _allow_rows(result.unchecked))
    lines += _section(
        "malformed allows",
        [f"  line {bad.line}: {bad.text}  ({bad.problem})" for bad in result.malformed],
    )
    lines += _section("not measured", [f"  {rule}: {why}" for rule, why in result.not_measured])
    lines += _section("diagnostics (not findings)", _diagnostics(result))
    if not result.findings:
        lines.append("No findings. This is not a verdict on the figure.")
    found = len(result.findings)
    lines.append(
        f"figure check: {found} finding{'' if found == 1 else 's'}, {len(result.allowed)} allowed, "
        f"{len(result.stale)} stale, {len(result.unchecked)} unchecked, "
        f"{len(result.malformed)} malformed"
    )
    return "\n".join(lines)


def _row(rule: str, target: str, text: str) -> str:
    # 21 is the longest rule id, `loads-library-by-hand`.
    return f"  {rule:<21} {target:<10} {text}"


def _allow_rows(pairs: list[tuple[Allow, str]]) -> list[str]:
    """One row per allow: what it set aside, or why it is stale or
    unchecked, then its own reason."""
    return [
        _row(
            allow.rule,
            _quoted(allow.target) or FIGURE,
            f"{said} -- {allow.reason} (line {allow.line})",
        )
        for allow, said in pairs
    ]


def _quoted(target: str) -> str:
    """`target` double-quoted when it has a space, unless its rule already
    quoted it (w4's label text)."""
    return f'"{target}"' if " " in target and not target.startswith('"') else target


def _section(heading: str, rows: list[str]) -> list[str]:
    return [heading, *rows] if rows else []


def _diagnostics(result: CheckResult) -> list[str]:
    figure = result.figure
    rows = []
    if figure.edges:
        drawn = ", ".join(f"{one} -> {other}" for one, other in figure.edges)
        rows.append(f"  edges (confirm against the prose): {drawn}")
    if figure.unmeasured:
        rows.append(f"  declared but not measured: {', '.join(figure.unmeasured)}")
    if result.loose_lines:
        rows.append(f"  lines not between two nodes, not checked by c1 to c7: {result.loose_lines}")
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
        "layout": result.layout or None,
        "findings": [_finding(f) for f in result.findings],
        "advisory": [_finding(f) for f in result.advisory],
        "allowed": [
            {**_allow(allow), "measurement": measured} for allow, measured in result.allowed
        ],
        "stale": [{**_allow(allow), "why": why} for allow, why in result.stale],
        "unchecked": [{**_allow(allow), "why": why} for allow, why in result.unchecked],
        "malformed": [
            {"line": bad.line, "text": bad.text, "problem": bad.problem} for bad in result.malformed
        ],
        "not_measured": [{"rule": rule, "why": why} for rule, why in result.not_measured],
        "diagnostics": {
            "edges": [list(edge) for edge in figure.edges],
            "empty_fraction": figure.empty_fraction,
            "empty_fraction_note": EMPTINESS_LABEL,
            "names_unmeasured": figure.unmeasured,
            "lines_not_between_nodes": result.loose_lines,
        },
    }


def _finding(finding: Finding) -> dict:
    return {
        "rule": finding.rule,
        "class": RULES[finding.rule].cls,
        "scope": RULES[finding.rule].scope,
        "target": finding.target,
        "measurement": finding.measurement,
    }


def _allow(allow: Allow) -> dict:
    return {"rule": allow.rule, "target": allow.target, "reason": allow.reason, "line": allow.line}


def page_entry(on: Page, why: str) -> dict:
    """The page a figure was checked against, and why that page (#1140)."""
    return {
        "name": on.name,
        "text_width_pt": on.text_width_pt,
        "text_height_pt": on.text_height_pt,
        "why": why,
    }


def page_row(entry: dict) -> str:
    size = f"{entry['text_width_pt']:.1f}pt x {entry['text_height_pt']:.1f}pt"
    return f"page     {entry['name']} ({size}), {entry['why']}"
