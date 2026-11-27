"""Dropping a chapter number that an authored heading states itself (#804).

`# Chapter 1: Why Anyone Pays` is numbered twice in a book, since the `book`
class numbers chapters too. Dropped here, not in the draft: a standalone render
needs the heading's number, and editing the draft would turn every unit from
`accepted` to `stale`; renumbering is `draft-reviser`'s call, not assembly's.

Both Markdown and `\\chapter{}` spellings, sharing the separator alphabet of
`chitragupta.ChapterSelfNumbered`, so the finding's repair always fires. A
separator is required (`Chapters and Verses`, `Chapter One` are untouched), and
only level-1 headings are read: a self-numbered `##` section is the book
preamble's `\\setcounter{secnumdepth}{-2}` decision, not this one.
"""

import re

from chitragupta import citation_gate

# `Chapter 1:`, `Chapter 1 --`, `Chapter 1.`, typographic dashes, and `Appendix A:`
# (#1137). Unanchored: shared with `chitragupta/style_headings.py`, so a heading
# this drops is one that check reports and vice versa.
SELF_NUMBERED_TITLE = re.compile(r"(?:Chapter\s+\d+|Appendix\s+[A-Z])\s*(?::|\.|--|[–—])\s*")

# A level-1 heading only (`--top-level-division=chapter`); `[ \t]` after the
# single `#` keeps `##` out, and the captured marker is put back unchanged.
_MARKDOWN_HEADING = re.compile(rf"(?m)^(#[ \t]+){SELF_NUMBERED_TITLE.pattern}")

# The LaTeX spelling, with optional short title and starred form; shared with
# `chitragupta/style_headings.py` so the two cannot drift.
CHAPTER_COMMAND = r"\\chapter\*?(?:\[[^\]]*\])?\{"

# Only the braced title is rewritten: the short title is the author's contents line.
_LATEX_CHAPTER = re.compile(rf"({CHAPTER_COMMAND}){SELF_NUMBERED_TITLE.pattern}")


def unnumbered(text: str, latex: bool = False) -> str:
    """`text` with a chapter number a heading states for itself dropped.

    Matched on a code-blanked copy (offsets preserved), so a heading-like line
    in a code sample is never rewritten. `latex` matters: in LaTeX a backtick
    is an open quote, so Markdown blanking would hide text (see
    `citation_gate._blank_code`).
    """
    scannable = citation_gate._blank_code(text, latex=latex)
    cuts = sorted(
        (found.end(1), found.end())
        for pattern in (_MARKDOWN_HEADING, _LATEX_CHAPTER)
        for found in pattern.finditer(scannable)
    )
    kept, last = [], 0
    for start, end in cuts:
        kept.append(text[last:start])
        last = end
    kept.append(text[last:])
    return "".join(kept)
