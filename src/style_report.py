"""What a prose-conformance report looks like: the lines, not the findings.

Split from `src/style_check.py` for the reason `src/review/__init__.py` is
split from the three aids it serves -- what a report *says* is a separate
concern from what produced it, and keeping them together pushed one module
past the 250-line limit docs/CODE-STANDARDS.md sets.

The header is the part worth care. A report that omits dialect findings
because nobody recorded a dialect looks exactly like a report on a draft
that had none, and the second is the reading a reader will take. So every
line here names *what was checked and on whose authority* before it names
a single finding.
"""

from pathlib import Path

from src.style_rules import DIALECT_RULES


def _dialect_lines(payload: dict) -> list[str]:
    """The header's dialect lines: what was checked, from where, and -- if
    nothing was -- what the draft looks like and how to record it."""
    language, source = payload["language"], payload["language_source"]
    if language and language in DIALECT_RULES:
        return [f"  dialect: {language} (from {source})"]
    if language:
        return [f"  dialect: {language} (from {source}) -- no rules for that tag "
                "in this style, so nothing was checked"]
    lines = ["  dialect: not checked -- no `language:` in scope.md and no "
             "[style].language in config.toml (WRITING-STANDARDS.md section 8)"]
    proposal = payload.get("proposed_language")
    if proposal:
        measured = sorted(proposal["findings_by_language"].items())
        counts = ", ".join(f"{tag}: {n}" for tag, n in measured)
        lines.append(f"  it reads as {proposal['language']} ({counts}). To record that:")
        lines.append(f"    python -m src.draft dossier set-language "
                     f"{proposal['language']} {payload['draft']}")
    return lines


def report(draft: Path, payload: dict) -> list[str]:
    """The human-readable lines, including what was *not* checked.

    Naming the skipped rules is the point of the header. A report that
    silently omits dialect findings because `language:` is unset looks
    exactly like a draft with none, and the second is the reading a reader
    will take.
    """
    findings = payload["findings"]
    lines = [f"{draft}"] + _dialect_lines(payload)
    if not findings:
        lines.append("  no findings.")
        return lines
    for finding in findings:
        times = "" if finding["count"] == 1 else f" (x{finding['count']})"
        lines.append(f"  {finding['line']:>5}  {finding['severity']:<10} "
                     f"{finding['message']}{times}")
    lines.append(f"  {len(findings)} finding(s). A review aid, not a gate: "
                 "nothing here blocks the draft.")
    return lines
