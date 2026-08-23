"""How an uncited-prose report reads: the Markdown document and the
plain-text stdout form.

Split from `chitragupta/review/uncited_prose.py`, which owns which
sentences are findings and passes its `findings()` list in. Nothing here
imports it back, deliberately -- that is what keeps the dependency
one-way instead of a cycle papered over with a deferred import, which is
the mistake `_synthesis_render.py` records having made first.

Three sentences here are load-bearing and should not be trimmed as
boilerplate:

- **which genre it was read under, and what that genre means.** A
  tutorial's report raises no findings by design, and without the
  sentence saying so it reads as a draft that passed a check. None was
  applied.
- **that an uncited sentence is not a defect.** Scope statements, worked
  examples and the draft's own transitions legitimately cite nothing.
  The report surfaces; a human decides.
- **that the fix is evidence, not wording.** Rewording an uncited
  sentence makes it look supported without making it supported, which is
  the failure this project exists to prevent, so nothing repairs these
  findings unattended.
"""

from chitragupta import review

_STANDING = {
    "exceptional": (
        "In this genre a claim is expected to rest on a source, so every "
        "sentence below carries no citation **and no explanation for why "
        "not**."
    ),
    "ordinary": (
        "In this genre most prose is original by design -- worked examples, "
        "exercises, a lesson the reader follows -- so uncited prose raises "
        "**no findings**. The counts below are still reported, because a "
        "background section resting on nothing is worth an eye. Nothing here "
        "has passed a check; none was applied."
    ),
}


def _under(report) -> str:
    """One clause naming the genre and where it came from."""
    return {
        "scope.md": f"recorded as `{report.genre}` in this draft's dossier",
        "--genre": f"`{report.genre}`, given on the command line",
        "nothing": "**not recorded** for this draft, so the strict reading applies",
    }[report.genre_source]


def _how_to_read(report) -> list[str]:
    """The paragraph that stops the counts below being misread."""
    return [
        "## How to read this",
        "",
        f"Read under a genre {_under(report)}, where uncited prose is **{report.standing}**.",
        "",
        f"{_STANDING[report.standing]}",
        "",
        "An uncited sentence is **not** a defect. A scope statement, a worked",
        "example and the draft's own transitions all legitimately rest on",
        "nothing. What this report does is stop them being silently mixed in",
        "with cited prose.",
        "",
        "**The fix for an uncited claim is evidence, not wording.** Rewording",
        "one would make it look supported without making it supported, so",
        "nothing in this pipeline repairs these findings for you.",
        "",
        "A finding whose block cites nothing rests on nothing at all; one",
        "whose block cites something sits beside evidence that may or may not",
        "cover it. The first kind is listed first.",
        "",
    ]


def _summary(report) -> list[str]:
    return [
        "## Summary",
        "",
        f"**{len(report.uncited)}** of {len(report.sentences)} claim-bearing "
        f"sentences carry no citation, **{len(report.bare)}** of them in a "
        "block that cites nothing.",
        "",
    ]


def _finding_lines(finding: dict) -> list[str]:
    where = (
        "block cites nothing" if not finding["block_cites"] else "block cites a source elsewhere"
    )
    return [
        f"- **line {finding['line']}** (`{finding['id']}`, {where})",
        f"  > {finding['sentence']}",
    ]


def _findings_section(report, found: list[dict]) -> list[str]:
    if report.standing == "ordinary":
        return [
            "## Findings",
            "",
            "None raised -- see above. This genre's prose is original by design.",
            "",
        ]
    if not found:
        return [
            "## Findings",
            "",
            "None. Every claim-bearing sentence in this draft carries a citation.",
            "",
        ]
    lines = ["## Findings", ""]
    for finding in found:
        lines += _finding_lines(finding)
    return lines + [""]


def render_markdown(report, command: str, found: list[dict]) -> str:
    """The report as a Markdown document, for `content/review/`.

    Kept beside the plain-text version rather than replacing it: stdout
    is read in a terminal mid-review and wants no syntax, while a file
    kept for months is read next to the draft's other review reports and
    should look like them.
    """
    lines = review.header(report.draft, "uncited", command)
    lines += _how_to_read(report)
    lines += _summary(report)
    lines += _findings_section(report, found)
    return "\n".join(lines)


def format_report(report, found: list[dict]) -> str:
    """The same report, as plain text for stdout."""
    lines = [
        f"Uncited prose in {report.draft}",
        f"Genre: {report.genre or 'not recorded'} "
        f"({report.genre_source}) -- uncited prose is {report.standing}",
        f"{len(report.uncited)}/{len(report.sentences)} claim-bearing sentences "
        f"carry no citation, {len(report.bare)} in a block citing nothing",
    ]
    if report.standing == "ordinary":
        lines.append("No findings raised: this genre's prose is original by design.")
        return "\n".join(lines)
    for finding in found:
        mark = " " if finding["block_cites"] else "*"
        lines.append(f"  {mark} line {finding['line']}: {finding['sentence']}")
    return "\n".join(lines)
