"""How the verbatim digest aid prints and serialises what it found (#991).

The report leads with the unsupported fraction, beside the copied,
own-words and not-checkable shares that account for the whole digest
(#1172). Item lines use `agenda`'s format, with ids hashing the sentence,
never its line, so they survive revision. Every item is `[surfaced]`: a
source's support is a judgement no re-run settles. The payload is what the
next `--baseline` reads; no timestamp (see `review/__init__.py`).
"""

from dataclasses import asdict
from pathlib import Path

from chitragupta import dossier, review
from chitragupta.review._digest_match import CLASSES, Checked, Finding
from chitragupta.review.agenda._identity import item_id, section_anchor

AID = "digest"

# Item lines are for scanning; the payload's `detail.text` is whole.
_EXCERPT = 90


def _excerpt(text: str) -> str:
    return text if len(text) <= _EXCERPT else text[: _EXCERPT - 3].rstrip() + "..."


_DANGLING = {
    "cross-reference": "names {match}, which the digest does not contain",
    "reference-marker": "keeps the source's reference marker {match}",
    "opener": 'opens on "{match}" with nothing before it from the same source',
}


def _summary(finding: Finding) -> str:
    quoted = f'"{_excerpt(finding.text)}"'
    if finding.cls == "repeated-text":
        return f"{quoted} -- already copied at line {finding.detail['first_line']}"
    if finding.cls == "dangling-reference":
        return f"{quoted} -- " + _DANGLING[finding.detail["kind"]].format(**finding.detail)
    if finding.cls == "copy-mismatch":
        missing = ", ".join(finding.detail["missing"]) or "(none)"
        return f"{quoted} -- nearly on p. {finding.detail['page']}; missing: {missing}"
    if finding.cls == "unsupported-text" and not finding.citekeys:
        return f"{quoted} -- no citation covers it"
    if finding.cls == "unsupported-text":
        return f"{quoted} -- lexical support {finding.detail['support_score']} in the cited source"
    return f"{quoted} -- not verified as copied"


def items(checked: Checked, draft_text: str) -> list[dict]:
    """One worklist row per finding, worst class first, then by line."""
    sections = dossier.sections(draft_text)
    rows = []
    for finding in checked.findings:
        section = section_anchor(sections, finding.line)
        citekey = finding.citekeys[0] if finding.citekeys else None
        rows.append(
            {
                "id": item_id(AID, finding.cls, section, citekey, finding.text),
                "class": finding.cls,
                "disposition": "surfaced",
                "section": section,
                "citekeys": list(finding.citekeys),
                "line": finding.line,
                "summary": _summary(finding),
                "detail": {"text": finding.text, **finding.detail},
            }
        )
    rows.sort(key=lambda row: (CLASSES.index(row["class"]), row["line"], row["id"]))
    return rows


def _counts(rows: list[dict]) -> dict[str, int]:
    return {cls: sum(1 for row in rows if row["class"] == cls) for cls in CLASSES}


def payload(draft: Path, command: str, checked: Checked, rows: list[dict]) -> dict:
    data = review.envelope(draft, AID, command)
    data.update(
        {
            "unsupported_fraction": checked.unsupported_fraction,
            "copied_fraction": checked.copied_fraction,
            "own_fraction": checked.own_fraction,
            "unverifiable_fraction": checked.unverifiable_fraction,
            "words_total": checked.words_total,
            "words_flagged": checked.words_flagged,
            "words_copied": checked.words_copied,
            "words_own": checked.words_own,
            "words_unverifiable": checked.words_unverifiable,
            "counts": _counts(rows),
            "items": rows,
            "spans": [
                {
                    "line": span.line,
                    "citekeys": list(span.citekeys),
                    "text": span.text,
                    "tier": span.tier,
                    "pages": list(span.pages),
                    "cited": list(span.cited) if span.cited else None,
                    "note": span.note,
                }
                for span in checked.spans
            ],
            "unverifiable": [asdict(run) for run in checked.unverifiable],
        }
    )
    return data


def _summary_lines(checked: Checked, rows: list[dict]) -> list[str]:
    total = checked.words_total
    lines = [
        "## Summary",
        "",
        f"- Unsupported fraction: {checked.unsupported_fraction} "
        f"({checked.words_flagged} of {total} words)",
        f"- Copied fraction: {checked.copied_fraction} ({checked.words_copied} of {total} words)",
        f"- Own words, supported or declared: {checked.own_fraction} "
        f"({checked.words_own} of {total} words)",
        f"- Not checkable: {checked.unverifiable_fraction} "
        f"({checked.words_unverifiable} of {total} words, {len(checked.unverifiable)} runs)",
        f"- Copied spans: {len(checked.spans)}",
    ]
    lines += [f"- {cls}: {count}" for cls, count in _counts(rows).items()]
    if total == 0:
        # Fractions are 0.0 by construction: say so before it reads as success.
        lines.append(
            "- No prose found: nothing to check (a digest is Markdown prose with "
            "`[@citekey]` brackets closing each copied run)."
        )
    return lines + [""]


def _findings_lines(rows: list[dict]) -> list[str]:
    lines = ["## Findings", ""]
    if not rows:
        return lines + ["No findings.", ""]
    for cls in CLASSES:
        rows_of = [row for row in rows if row["class"] == cls]
        if not rows_of:
            continue
        lines += [f"### {cls}", ""]
        for row in rows_of:
            where = f" ({row['section']})" if row["section"] else ""
            lines.append(f"- `{row['id']}` [surfaced]{where}: {row['summary']}")
        lines.append("")
    return lines


def _spans_lines(checked: Checked) -> list[str]:
    lines = ["## Copied spans", ""]
    for span in checked.spans:
        pages = ", ".join(str(page) for page in span.pages) or "?"
        keys = ", ".join(f"`{key}`" for key in span.citekeys)
        note = f" -- {span.note}" if span.note else ""
        lines.append(
            f'- line {span.line}, {keys}, p. {pages}, {span.tier}{note}: "{_excerpt(span.text)}"'
        )
    if not checked.spans:
        lines.append("None.")
    lines.append("")
    if checked.unverifiable:
        lines += ["## Not checkable", ""]
        lines += [
            f"- line {run.line}: {run.reason} ({run.words} words)" for run in checked.unverifiable
        ]
        lines.append("")
    return lines


def render_markdown(draft: Path, command: str, checked: Checked, rows: list[dict]) -> str:
    lines = review.header(draft, AID, command)
    lines += [
        "Every item is **[surfaced]**: whether a source backs a sentence, and",
        "which passage should replace it, are judgement calls. The unsupported",
        "fraction and the per-class counts are what a repair pass drives down.",
        "`dangling-reference` and `repeated-text` count in no fraction: the",
        "run is still the source's words, it just points at something the",
        "digest lacks, or says again what the digest already says.",
        "",
    ]
    lines += _summary_lines(checked, rows)
    lines += _findings_lines(rows)
    lines += _spans_lines(checked)
    return "\n".join(lines).rstrip() + "\n"
