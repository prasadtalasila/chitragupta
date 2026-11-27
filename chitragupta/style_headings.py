"""The one `python -m chitragupta.draft style` finding about a heading.

A `\\chapter{}` that states its own number, so the document it is
`\\input` into numbers it twice (docs/WRITING-STANDARDS.md §15). Plain
Python, since a `\\chapter{}` is markup Vale does not see.

A Markdown draft is deliberately silent: `render_output/_chapter_number.py`
drops the prefix on a `--fragment` render, and a `prose` finding is
unattended on the agenda, so reporting it would authorise
`agenda-reviser` to edit a heading doing its job. A `.tex` unit is
`\\input` as written by book-assembler, so there only the author can fix it.
"""

import re
from pathlib import Path

from chitragupta import citation_gate, style_elements
from chitragupta.render_output import _paths
from chitragupta.render_output._chapter_number import CHAPTER_COMMAND, SELF_NUMBERED_TITLE
from chitragupta.render_output._tables import line_of

RULES = {
    "chapter-self-numbered": "chitragupta.ChapterSelfNumbered",
}

# The chapter command and `SELF_NUMBERED_TITLE` are `_chapter_number`'s,
# imported so this check and the repair cannot drift apart.
_CHAPTER_RE = re.compile(rf"{CHAPTER_COMMAND}([^}}]*)\}}")


def findings(draft: Path) -> "list[dict]":
    """Every self-numbered chapter heading in `draft`, ordered by line."""
    if draft.suffix.lower() in _paths._MARKDOWN_SUFFIXES:
        return []
    text = draft.read_text(encoding="utf-8")
    # Scanned code-blanked (`latex=True`): a `\chapter{}` in `verbatim`
    # is a sample. Offsets are preserved, so the title is read back
    # from the original text.
    scannable = citation_gate._blank_code(text, latex=True)
    found = []
    for match in _CHAPTER_RE.finditer(scannable):
        title = text[match.start(1) : match.end(1)]
        if not SELF_NUMBERED_TITLE.match(title):
            continue
        # A title can wrap over lines, which would break the report's
        # one-line shape; collapsed and clipped as `style_typeset` does.
        quoted = " ".join(title.split())[:60]
        found.append(
            style_elements.finding(
                RULES,
                "chapter-self-numbered",
                quoted,
                line_of(text, match.start()),
                f"`{quoted}` states its own chapter number or appendix letter. The "
                "document this fragment is `\\input` into numbers the chapter itself, so it "
                "is printed twice -- at the chapter opening and in the table "
                "of contents. Drop the prefix and leave the number to the "
                "enclosing document (WRITING-STANDARDS.md §15).",
            )
        )
    return found
