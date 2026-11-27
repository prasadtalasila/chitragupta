"""How a multi-source synthesis report reads: the Markdown document,
the plain-text stdout form, and the same findings as a JSON payload.

Takes `findings()` as an argument, so `synthesis` imports this one-way.
Two sentences of the report are load-bearing, not boilerplate: which unit
was measured and why (a tutorial measured whole otherwise reads as a
failure), and that a thin corpus legitimately yields single-source units
(the report counts; R3 keeps it out of any unattended loop).
"""

from chitragupta import review


def _how_to_read(report) -> list[str]:
    recorded = {
        "scope.md": f"recorded as `{report.genre}` in this draft's dossier",
        "--unit": "given on the command line",
        "nothing": "a fallback -- no genre is recorded for this draft",
    }[report.source]
    return [
        "## How to read this",
        "",
        f"Measured at the **{report.kind}**, {recorded}.",
        "",
        "Prose required to fuse two or more sources cannot be a transcription",
        "of any one of them. That is what a multi-source unit buys, and it is",
        "why the unit differs by genre -- see docs/WRITING-STANDARDS.md, §11.",
        "",
        "A **thin corpus legitimately produces single-source units.** This",
        "report counts them; it does not judge them. A driver may read it",
        "back, no draft is blocked by it, and there is no target",
        "proportion here to drive down.",
        "",
    ]


def _summary(report) -> list[str]:
    lines = ["## Summary", ""]
    if report.single_source_pct is None:
        return lines + [
            f"This draft cites nothing: {len(report.units)} "
            f"{report.kind}s, none of them citing a source.",
            "",
        ]
    return lines + [
        f"- {len(report.units)} {report.kind}s, of which {report.uncited} cite nothing",
        f"- {report.multi_source} cite two or more sources",
        f"- {report.single_source} rest on a single source "
        f"({report.declared} declared, {report.undeclared} not)",
        f"- **{report.single_source_pct:.0f}%** of the {report.kind}s that cite at "
        "all rest on one source",
        "",
    ]


def _finding_lines(report, found: list[dict]) -> list[str]:
    lines = ["## Units", ""]
    if not found:
        return lines + ["Every unit that cites at all cites more than one source.", ""]
    for entry in found:
        keys = ", ".join(f"`{key}`" for key in entry["citekeys"])
        if entry["kind"] == "single_key_run":
            lines.append(
                f"- line {entry['line']}: {entry['longest_run']} consecutive "
                f"paragraphs on one source, in a {report.kind} citing {keys}"
            )
        else:
            lines.append(f"- line {entry['line']}: {keys}")
        if entry["declared"]:
            lines.append(f"  - declared: {entry['declared']}")
    return lines + [""]


def render_markdown(report, command: str, found: list[dict]) -> str:
    """The report as a Markdown document, for `--write`; `found` is passed
    in so `findings()` runs once per invocation.
    """
    lines = review.header(report.draft, "synthesis", command)
    lines += _how_to_read(report)
    lines += _summary(report)
    lines += _finding_lines(report, found)
    return "\n".join(lines)


def format_report(report, found: list[dict]) -> str:
    """The same report as plain text, for stdout, which wants no syntax."""
    lines = [
        f"Multi-source synthesis for {report.draft}",
        f"Unit: {report.kind} (from {report.source})",
    ]
    if report.single_source_pct is None:
        lines.append(f"This draft cites nothing: {len(report.units)} {report.kind}s.")
        return "\n".join(lines)
    lines.append(
        f"{report.single_source}/{len(report.citing)} citing {report.kind}s rest on "
        f"one source ({report.single_source_pct:.0f}%); "
        f"{report.declared} of those are declared."
    )
    for entry in found:
        keys = ", ".join(entry["citekeys"])
        note = " [declared]" if entry["declared"] else ""
        lines.append(f"  - line {entry['line']}: {entry['kind']} -- {keys}{note}")
    return "\n".join(lines)


def synthesis_payload(report, command: str, found: list[dict]) -> dict:
    """The same findings the report prints, as data."""
    payload = review.envelope(report.draft, "synthesis", command)
    payload.update(
        {
            "genre": report.genre,
            "unit": report.kind,
            "unit_source": report.source,
            "units_total": len(report.units),
            "uncited": report.uncited,
            "single_source": report.single_source,
            "multi_source": report.multi_source,
            "declared": report.declared,
            "undeclared": report.undeclared,
            "single_source_pct": report.single_source_pct,
            "findings": found,
        }
    )
    return payload
