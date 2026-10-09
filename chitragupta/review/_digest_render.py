"""How the verbatim digest aid prints and serialises what it found (#991).

The report is the digest's own worklist. It leads with the unsupported
fraction, the number a repair pass drives down, with the copied fraction
and the not-checkable share beside it so the three account for the
whole digest. Item lines use `agenda`'s format -- a stable 12-character
id, `[surfaced]`, the section anchor, a one-line summary -- so a person
who has read an agenda reads this without learning a second shape, and
so the ids survive a revision the way agenda's do: `_identity.item_id`
hashes the sentence, never its line. Every item is `[surfaced]`:
whether a source backs a sentence and which passage should replace it
are judgement calls, and nothing a re-run can settle.

The payload is the findings as data, in `review.envelope`'s frame, and
it is what the next run's `--baseline` reads. No timestamp, for the
reason `review/__init__.py` gives.
"""

from dataclasses import asdict
from pathlib import Path

from chitragupta import dossier, review
from chitragupta.review._digest_match import CLASSES, Checked, Finding
from chitragupta.review.agenda._identity import item_id, section_anchor

AID = "digest"

# How much of a sentence an item line shows. The payload carries the
# whole sentence in `detail.text`; the line is for scanning.
_EXCERPT = 90


def _excerpt(text: str) -> str:
    return text if len(text) <= _EXCERPT else text[: _EXCERPT - 3].rstrip() + "..."


def _summary(finding: Finding) -> str:
    quoted = f'"{_excerpt(finding.text)}"'
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
            "unverifiable_fraction": checked.unverifiable_fraction,
            "words_total": checked.words_total,
            "words_flagged": checked.words_flagged,
            "words_copied": checked.words_copied,
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
        f"- Not checkable: {checked.unverifiable_fraction} "
        f"({checked.words_unverifiable} of {total} words, {len(checked.unverifiable)} runs)",
        f"- Copied spans: {len(checked.spans)}",
    ]
    lines += [f"- {cls}: {count}" for cls, count in _counts(rows).items()]
    if total == 0:
        # The fractions are 0.0 by construction, not by merit: say so
        # where a reader skimming the first line would read success.
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
        "",
    ]
    lines += _summary_lines(checked, rows)
    lines += _findings_lines(rows)
    lines += _spans_lines(checked)
    return "\n".join(lines).rstrip() + "\n"
