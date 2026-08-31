"""How a citekey-union report reads: the Markdown document and the
plain-text stdout form.

Split from `chitragupta/review/citekey_union.py`, which reads the book off
disk, and `_citekey_union_result.py`, which owns the arithmetic and is
passed in. Nothing here imports either back -- the same one-way shape
`chitragupta/review/_citation_coverage_render.py` and `_uncited_render.py`
use, and for the same reason: taking the result as an argument rather
than recomputing it keeps the dependency one-way instead of a cycle
papered over with a deferred import.

**Every form says what it could not look at.** A book whose units are all
unaccepted compares nothing, and a report that printed "none lost" for it
would be a clean bill of health for work it never opened -- which is the
one way an advisory aid does real damage.
"""

from chitragupta import review

_WITHHELD = "not determinable -- an unchecked unit below may record it, so this run does not guess"


def _unchecked_lines(result, bullet: str) -> list[str]:
    """The unassessed units, each with the state that disqualified it and
    whether the assembly included it anyway -- both facts, because a unit
    can be omitted *and* unbelievable and the two want different fixes."""
    return [
        f"{bullet}{entry.unit} -- {entry.state}"
        + ("" if entry.included else "; also not included in the assembly")
        for entry in result.unchecked
    ]


def _coverage_lines(result, bullet: str) -> list[str]:
    """What the run read besides the units, and what it could not find."""
    lines = []
    if result.outside_units:
        lines.append(f"{bullet}read outside the units: {', '.join(result.outside_units)}")
    if result.unresolved:
        lines.append(f"{bullet}named but not read: {', '.join(result.unresolved)}")
    return lines


def format_report(result) -> str:
    included = [entry.unit for entry in result.checked if entry.included]
    lines = [
        f"Citekey union for {result.assembled}",
        f"Accepted units included: {len(included)} of {len(result.checked)}"
        + (f" ({len(result.unchecked)} not checked)" if result.unchecked else ""),
        f"Citekeys stated outside any unit: {len(result.own)}",
    ]
    lines += _coverage_lines(result, "  - ")

    dropped = result.dropped
    if dropped:
        lines.append("Lost in assembly (a unit stands on it, the book carries it nowhere):")
        for key, units in dropped.items():
            lines.append(f"  - {key}: stood on by {', '.join(units)}")
    else:
        lines.append("Lost in assembly: none.")

    appeared = result.appeared
    if appeared is None:
        lines.append(f"Cited outside any unit: {_WITHHELD}.")
    elif appeared:
        lines.append("Cited outside any unit:")
        lines += [f"  - {key}" for key in sorted(appeared)]
    else:
        lines.append("Cited outside any unit: none.")

    if result.unchecked:
        lines.append("Not checked:")
        lines += _unchecked_lines(result, "  - ")
    return "\n".join(lines)


def _dropped_section(result) -> list[str]:
    lines = ["## Lost in assembly", ""]
    dropped = result.dropped
    if not dropped:
        return lines + [
            "Every citekey an accepted, included unit stands on is carried by the book.",
            "",
        ]
    lines += [
        "A book is composed by reference: including a unit includes all of its",
        "prose, so a source goes missing here by the assembly omitting the unit",
        "that stood on it. Each citekey below belongs to an omitted unit and is",
        "carried nowhere else in the book.",
        "",
    ]
    for key, units in dropped.items():
        lines.append(f"- `{key}` -- stood on by {', '.join(f'`{u}`' for u in units)}")
    return lines + [""]


def _appeared_section(result) -> list[str]:
    lines = ["## Cited outside any unit", ""]
    appeared = result.appeared
    if appeared is None:
        return lines + [
            "**Not determinable.** One or more units below were not compared, so a",
            "citekey this book states outside its units may be recorded by one of",
            "them after all. Accept the outstanding units and run this again.",
            "",
        ]
    if not appeared:
        return lines + [
            "The assembly's own text and every file it includes that no unit owns",
            "were read, and they state no citekey an accepted unit does not record.",
            "",
        ]
    lines += [
        "The citation gate already proves each of these is a real citekey. What",
        "this adds is that it entered through the assembly's own material rather",
        "than through a unit anybody accepted.",
        "",
    ]
    lines += [f"- `{key}`" for key in sorted(appeared)]
    return lines + [""]


def _coverage_section(result) -> list[str]:
    lines = ["## What was read", ""]
    included = [entry.unit for entry in result.checked if entry.included]
    lines += [
        f"- Accepted units included by the assembly: **{len(included)}** of "
        f"**{len(result.checked)}**",
        f"- Units not compared: **{len(result.unchecked)}**",
        f"- Citekeys stated outside any unit: **{len(result.own)}**",
        "",
    ]
    lines += _coverage_lines(result, "- ")
    return lines + ([""] if result.outside_units or result.unresolved else [])


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
        "prose stands on. The assembly composes those units by reference, so it",
        "should include every one of them -- and anything it states outside a unit",
        "is material no acceptance record covers. This report is that subtraction,",
        "in both directions.",
        "",
    ]
    lines += _coverage_section(result)
    lines += _dropped_section(result)
    lines += _appeared_section(result)
    lines += ["## Not checked", ""]
    if not result.unchecked:
        return "\n".join(lines + ["Every unit the outline declares was compared.", ""])
    lines += [
        "A unit is compared only when its acceptance record still describes its",
        "prose. These do not, so their recorded citekeys would answer for text",
        "that no longer exists -- they are named rather than skipped, and nothing",
        "above is a verdict on them.",
        "",
    ]
    lines += _unchecked_lines(result, "- ")
    return "\n".join(lines + [""])
