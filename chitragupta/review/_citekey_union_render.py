"""How a citekey-union report reads: the Markdown document and the
plain-text stdout form.

Split from `chitragupta/review/citekey_union.py`, which owns
`UnionResult` and how it is computed, and passes one in. Nothing here
imports it back -- the same one-way shape
`chitragupta/review/_citation_coverage_render.py` and `_uncited_render.py`
use, and for the same reason: taking the result as an argument rather
than recomputing it keeps the dependency one-way instead of a cycle
papered over with a deferred import.
"""

from chitragupta import review

# Said in both forms of the report, because the withheld direction is the
# thing most likely to be misread: an empty "appeared" section and an
# undeterminable one look alike to a skimming reader, and only one of
# them is a clean bill.
_WITHHELD = (
    "not determinable -- a citekey the assembly carries could have come from a unit "
    "below, so this run does not guess"
)


def _unchecked_lines(result, bullet: str) -> list[str]:
    """The unassessed units, listed with the state that disqualified each.

    Always emitted when there are any, in both forms: a report that
    silently narrowed what it compared reads as a clean bill of health
    for units it never looked at.
    """
    return [f"{bullet}{entry.unit} -- {entry.state}" for entry in result.unchecked]


def format_report(result) -> str:
    lines = [
        f"Citekey union for {result.assembled}",
        f"Units compared: {len(result.checked)} ({len(result.unchecked)} not checked)"
        if result.unchecked
        else f"Units compared: {len(result.checked)}",
        f"Citekeys in the assembly: {len(result.cited)}",
    ]

    dropped = result.dropped
    if dropped:
        lines.append("Lost in assembly (a unit stands on it, the assembly does not cite it):")
        for key, units in dropped.items():
            lines.append(f"  - {key}: cited by {', '.join(units)}")
    else:
        lines.append("Lost in assembly: none.")

    appeared = result.appeared
    if appeared is None:
        lines.append(f"Cited by no unit: {_WITHHELD}.")
    elif appeared:
        lines.append("Cited by no unit:")
        lines += [f"  - {key}" for key in sorted(appeared)]
    else:
        lines.append("Cited by no unit: none.")

    if result.unchecked:
        lines.append("Not checked:")
        lines += _unchecked_lines(result, "  - ")
    return "\n".join(lines)


def _dropped_section(result) -> list[str]:
    lines = ["## Lost in assembly", ""]
    dropped = result.dropped
    if not dropped:
        return lines + ["Every citekey an accepted unit stands on is cited in the assembly.", ""]
    lines += [
        "Each of these is recorded in a unit's own acceptance record and is not",
        "cited in the assembled document. Set arithmetic, not a judgement: the",
        "citekey went in and did not come out.",
        "",
    ]
    for key, units in dropped.items():
        lines.append(f"- `{key}` -- stood on by {', '.join(f'`{u}`' for u in units)}")
    return lines + [""]


def _appeared_section(result) -> list[str]:
    lines = ["## Cited by no unit", ""]
    appeared = result.appeared
    if appeared is None:
        return lines + [
            "**Not determinable.** One or more units below were not compared, so a",
            "citekey the assembly carries may simply be one of theirs. Accept the",
            "outstanding units and run this again for an answer.",
            "",
        ]
    if not appeared:
        return lines + ["Every citekey in the assembly is one a unit recorded.", ""]
    lines += [
        "The citation gate already proves each of these is a real citekey. What",
        "this adds is that no unit records standing on it -- so it entered at",
        "assembly rather than in a unit that was accepted.",
        "",
    ]
    lines += [f"- `{key}`" for key in sorted(appeared)]
    return lines + [""]


def render_markdown(result, command: str) -> str:
    """The same report as `format_report`, as a Markdown document.

    Kept beside the plain-text version rather than replacing it: stdout
    is read in a terminal mid-review and wants no syntax, while a file
    kept for months is read next to the draft's other review reports and
    should look like them.
    """
    lines = review.header(result.assembled, "union", command)
    lines += [
        "## How to read this",
        "",
        "Every unit of this book recorded, when it was accepted, the citekeys its",
        "prose stands on. Assembly composes those units into one document and",
        "should carry every one of them across. This report is that subtraction,",
        "in both directions.",
        "",
        f"- Units compared: **{len(result.checked)}**",
        f"- Units not checked: **{len(result.unchecked)}**",
        f"- Citekeys in the assembly: **{len(result.cited)}**",
        "",
    ]
    lines += _dropped_section(result)
    lines += _appeared_section(result)
    lines += ["## Not checked", ""]
    if not result.unchecked:
        return "\n".join(lines + ["Every unit the outline declares was compared.", ""])
    lines += [
        "A unit is compared only when its acceptance record still describes its",
        "prose. These do not, so their recorded citekeys would answer for text",
        "that no longer exists -- they are named rather than skipped.",
        "",
    ]
    lines += _unchecked_lines(result, "- ")
    return "\n".join(lines + [""])
