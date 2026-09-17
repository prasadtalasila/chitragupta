"""The one `python -m chitragupta.draft style` finding about a heading.

Beside `chitragupta/style_acronym_drift.py`, `style_tables.py`,
`style_figures.py`, `style_equations.py` and `style_typeset.py`, the
sixth finding in that command computed in plain Python rather than by
Vale. One check: a `\\chapter{}` that states its own chapter number, so
the document it is `\\input` into numbers it a second time
(docs/WRITING-STANDARDS.md §15).

**Why Vale cannot do it.** Vale matches patterns inside prose, and a
`\\chapter{}` in a `.tex` fragment is markup rather than prose -- the
same region its Markdown scoping hides and the same reason the table,
figure and typesetting checks are not Vale rules either.

**Why a Markdown draft is deliberately silent, and it is not an
omission.** `chitragupta/render_output/_chapter_number.py` drops the
prefix from the copy the writer sees when a unit is rendered
`--fragment`, so a Markdown unit assembled into a book is numbered once
and its authored heading still titles its own standalone pdf. There is
nothing left there for an author to repair, and reporting one anyway
would be worse than silence: a `draft style` finding reaches the review
agenda in the `prose` class, which is *unattended* for the whole class
(`chitragupta/review/agenda/_items_findings.py`), so the finding would
authorise `agenda-reviser` to edit a heading that is doing its job.

**What is left is exactly what that repair cannot reach.** A unit already
drafted as `.tex` needs no conversion to be assembled, so
`.claude/skills/book-assembler/SKILL.md` `\\input`s it as written and no
render runs over it at all. There the duplication is real, nothing
downstream can drop it, and the repair is the author's: delete the
prefix the enclosing document supplies. That is the same asymmetry
`style_typeset.findings` documents from the other side -- there the
`.tex` fragment is the *more* important surface because this pipeline
cannot reach the preamble that would fix it, and here it is the only
surface for the same shape of reason.
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

# The chapter command itself is `_chapter_number`'s, imported rather than
# spelled again: that module drops what this reports, and two spellings
# of one heading is how the two would drift into disagreeing about which
# headings they are about. The braced title is this module's own capture,
# and `SELF_NUMBERED_TITLE` -- also shared -- decides whether it states a
# number, so a heading reported here is one that repair would have
# dropped had the unit been converted.
_CHAPTER_RE = re.compile(rf"{CHAPTER_COMMAND}([^}}]*)\}}")


def findings(draft: Path) -> "list[dict]":
    """Every self-numbered chapter heading in `draft`, ordered by line."""
    if draft.suffix.lower() in _paths._MARKDOWN_SUFFIXES:
        return []
    text = draft.read_text(encoding="utf-8")
    # Scanned on a code-blanked copy, the same discipline `style_typeset`
    # and the citation gate read a draft with, and for the reason the
    # render-time repair blanks too: a `\chapter{}` inside a `verbatim`
    # is a sample being shown to the reader, not this document's own
    # heading. `latex=True` because this only ever reads a `.tex` draft,
    # where a backtick is an open quote rather than code markup.
    # `_blank_code` preserves every offset, so the title is read back out
    # of the original text at the span found in the blanked one.
    scannable = citation_gate._blank_code(text, latex=True)
    found = []
    for match in _CHAPTER_RE.finditer(scannable):
        title = text[match.start(1) : match.end(1)]
        if not SELF_NUMBERED_TITLE.match(title):
            continue
        # A `.tex` unit's own line wrapping falls inside the braces, and a
        # real one measured here ran to three lines. `style_report.py`
        # prints a finding as one column of a fixed-width line, so a raw
        # title breaks the report's shape and the agenda summary built
        # from the same string; collapsed and clipped the way
        # `style_typeset`'s own match is.
        quoted = " ".join(title.split())[:60]
        found.append(
            style_elements.finding(
                RULES,
                "chapter-self-numbered",
                quoted,
                line_of(text, match.start()),
                f"`{quoted}` states its own chapter number. The document this "
                "fragment is `\\input` into numbers the chapter itself, so it "
                "is printed twice -- at the chapter opening and in the table "
                "of contents. Drop the prefix and leave the number to the "
                "enclosing document (WRITING-STANDARDS.md §15).",
            )
        )
    return found
