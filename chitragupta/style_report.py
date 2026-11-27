"""What a prose-conformance report looks like: the lines, not the findings.

Every header line names what was checked and on whose authority, because
a report that omits findings nobody enabled looks like a clean draft.
"""

from pathlib import Path

from chitragupta.style_rules import DIALECT_RULES


def _dialect_lines(payload: dict) -> list[str]:
    """The header's dialect lines, and how to record a dialect if none was."""
    language, source = payload["language"], payload["language_source"]
    if language and language in DIALECT_RULES:
        return [f"  dialect: {language} (from {source})"]
    if language:
        return [
            f"  dialect: {language} (from {source}) -- no rules for that tag "
            "in this style, so nothing was checked"
        ]
    lines = [
        "  dialect: not checked -- no `language:` in scope.md and no "
        "[style].language in config.toml (WRITING-STANDARDS.md section 8)"
    ]
    proposal = payload.get("proposed_language")
    if proposal:
        measured = sorted(proposal["findings_by_language"].items())
        counts = ", ".join(f"{tag}: {n}" for tag, n in measured)
        lines.append(f"  it reads as {proposal['language']} ({counts}). To record that:")
        lines.append(
            f"    python -m chitragupta.draft dossier set-language "
            f"{proposal['language']} {payload['draft']}"
        )
    return lines


def report(draft: Path, payload: dict) -> list[str]:
    """The human-readable lines, including what was *not* checked."""
    findings = payload["findings"]
    lines = [f"{draft}"] + _dialect_lines(payload)
    if payload.get("vale_error"):
        # An unexplained short report reads as a clean draft, so say why
        # findings are missing and name what still ran.
        lines.append(
            "  prose rules: not checked -- vale is not installed. The "
            "glossary and table findings below still ran."
        )
    if not findings:
        lines.append("  no findings.")
        return lines
    for finding in findings:
        times = "" if finding["count"] == 1 else f" (x{finding['count']})"
        lines.append(
            f"  {finding['line']:>5}  {finding['severity']:<10} {finding['message']}{times}"
        )
    lines.append(
        f"  {len(findings)} finding(s). A review aid, not a gate: nothing here blocks the draft."
    )
    return lines
