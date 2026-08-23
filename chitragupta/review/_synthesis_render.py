"""How a multi-source synthesis report reads: the Markdown document and
the plain-text stdout form.

Split from `chitragupta/review/synthesis.py`, which owns what the numbers
*are* and passes its `findings()` list in. The two are genuinely
separate questions -- one is arithmetic over units, the other is the
prose that stops the arithmetic being misread -- and keeping them apart
is also what holds both under docs/CODE-STANDARDS.md's C2.

Nothing here imports `synthesis`, deliberately: `synthesis` imports this
module, and taking `found` as an argument rather than recomputing it is
what keeps that a one-way dependency instead of a cycle papered over
with a deferred import.

The prose here does real work rather than decorating the counts. Two
sentences in particular are load-bearing and should not be trimmed as
boilerplate:

- **which unit was measured, and why that one.** Without it a tutorial's
  report -- measured at the whole document -- reads as a draft with no
  multi-source paragraphs, which is true, meaningless, and looks like a
  failure.
- **that a thin corpus legitimately produces single-source units.** The
  report counts; it does not judge, and R3 keeps the proportion out of
  any unattended loop.
"""

from chitragupta import review


def _how_to_read(report) -> list[str]:
    """The paragraph that stops the numbers below being misread."""
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
    """The report as a Markdown document, for `--write`.

    `found` is passed in rather than recomputed here. That is what keeps
    this module from importing `synthesis` -- which imports this one --
    and it also means `findings()` runs once per invocation instead of
    once per output format.
    """
    lines = review.header(report.draft, "synthesis", command)
    lines += _how_to_read(report)
    lines += _summary(report)
    lines += _finding_lines(report, found)
    return "\n".join(lines)


def format_report(report, found: list[dict]) -> str:
    """The same report as plain text, for stdout.

    Kept beside the Markdown for the reason `citation_coverage` keeps
    both: stdout is read in a terminal mid-review and wants no syntax,
    while a file kept for months sits beside the draft's other review
    reports and should look like them.
    """
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
