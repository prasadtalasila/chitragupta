"""Where a draft's References section starts and ends.

For the callers that only need to find it (`render_output`,
`verbatim_check`, `references`), without the ledger; nothing here imports
back.
"""

import re

from chitragupta import citation_gate


# The References heading, bare or numbered, at any heading level.
#
# The number is multi-level: a book's "## 1.14 References" once missed, so
# `verbatim_check.scan` scanned the bibliography and 97.7% of findings on
# a 15-chapter book were shared titles, none reuse. The trailing separator
# stays optional for that form.
#
# `REFERENCE_TITLE` is shared with `review/_claims.py` and
# `style_typeset.py` so all three agree on which words open a
# bibliography (#951); a string, since each matches a different shape.
# Anchored at both ends by every caller, as their actions are destructive.
# `[ \t]`, not `\s`, so DOTALL cannot run a title onto the next line. A
# letter or Roman-numeral number needs its `.` or `)`.
REFERENCE_TITLE = (
    r"(?:(?:\d+(?:\.\d+)*[.)]?|(?:[A-Z]|[IVXLC]+)[.)])[ \t]*)?"
    r"(?:References|Bibliography|Works[ \t]+cited)"
)
_HEADING_RE = re.compile(rf"^#{{1,6}}[ \t]*{REFERENCE_TITLE}[ \t]*$", re.IGNORECASE)


# Any ATX heading, any level: a heading nested under References still ends
# it, as in dossier.sections().
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s")


def has_section(text: str) -> bool:
    return section_start(text.splitlines(keepends=True)) is not None


def section_start(lines: list[str]) -> int | None:
    """Index of the bibliography heading in `lines` (References,
    Bibliography or Works cited, per `REFERENCE_TITLE`), or None.

    A heading in a fenced code block doesn't count: callers replace or
    strip from here down, which would truncate a tutorial that shows one.
    """
    blanked = citation_gate._blank_code("".join(lines)).splitlines()
    for i, line in enumerate(blanked):
        if _HEADING_RE.match(line.strip()):
            return i
    return None


def section_end(lines: list[str], start: int) -> int:
    """Index of the next heading line after `lines[start]` (of any
    level), or `len(lines)` if none follows, so `lines[start:end]` is the
    whole section, heading included.

    Not "to end of file": that lost appendices after References
    (M-8/m-33/m-34). Fence-aware like `section_start`. A small copy of
    `dossier/_sections.py`'s extent, as this layer may not import the dossier.
    """
    blanked = citation_gate._blank_code("".join(lines)).splitlines()
    for i in range(start + 1, len(blanked)):
        if _ANY_HEADING_RE.match(blanked[i].strip()):
            return i
    return len(lines)
