"""Dropping a chapter number that an authored heading states itself.

A unit whose top heading reads `# Chapter 1: Why Anyone Pays` is numbered
twice in an assembled book (#804). Neither half is a defect: `--fragment`
converts the authored heading faithfully, which is what it documents, and
the `book` class numbers chapters, which is what the skeleton's
`\\setcounter{secnumdepth}{2}` asks for. The chapter opens `Chapter 1` /
`Chapter 1: Why Anyone Pays` and the table of contents reads `1 Chapter
1: Why Anyone Pays` to match.

**Why the prefix is dropped here rather than in the authored draft.** The
two artefacts want opposite things from one line. A unit rendered on its
own has nothing supplying a chapter number, so that heading is the whole
of the chapter's identity in its standalone pdf; the same unit inside a
book has the class supplying one. Editing the draft to serve the book
would also take every unit from `accepted` to `stale` -- a unit's
`output_digest` hashes the authored `.md` -- which is a real cost for a
typographic fix, and `.claude/skills/book-assembler/SKILL.md` is explicit
that renumbering the author's headings is `draft-reviser`'s call rather
than the assembly's. Which numbering a book shows, on the other hand, is
a composition decision and belongs to the book.

**Both spellings, in one place.** A `.tex` draft reaches
`render(fragment=True)` exactly as a Markdown one does, and pandoc passes
a `\\chapter{}` through its latex reader unchanged -- so a Markdown-only
rewrite would leave the duplication standing on the one kind of draft
`chitragupta.ChapterSelfNumbered` reports, which is a finding whose named
repair does not fire. The two patterns share one separator alphabet with
that check, for the same reason.

**Conservative by construction.** The pattern fires only on a heading
that *already states a chapter number*, which is exactly the duplicating
case: a separator is required, so `Chapters and Verses` is untouched, and
so is a spelled-out `Chapter One`. Only a level-1 heading is read.
A self-numbered *section* (`## 1.0 Before you start`) is the older,
different clash, whose remedy is `\\setcounter{secnumdepth}{-2}` in the
book's authored preamble -- a document-level decision this must not
pre-empt by rewriting a `##` heading behind the author's back.
"""

import re

from chitragupta import citation_gate

# `Chapter 1:`, `Chapter 1 --`, `Chapter 1.`, and the two dashes a
# typographic draft uses in place of `--`. Unanchored, because the two
# call sites below anchor it differently (after a `# ` marker, after a
# `\chapter{`) and `chitragupta/style_headings.py` anchors it with
# `.match()` against a title it has already extracted -- one pattern,
# three anchorings, so a heading this drops is a heading that check
# reports and vice versa.
SELF_NUMBERED_TITLE = re.compile(r"Chapter\s+\d+\s*(?::|\.|--|[–—])\s*")

# A level-1 Markdown heading only: `--top-level-division=chapter` makes a
# `#` the book's chapter and leaves every deeper heading a section. The
# marker is captured so the substitution puts it back unchanged --
# `[ \t]` after the single `#` is also what keeps `##` out of the match.
_MARKDOWN_HEADING = re.compile(rf"(?m)^(#[ \t]+){SELF_NUMBERED_TITLE.pattern}")

# The LaTeX spelling, including the optional short title a hand-written
# `.tex` unit may carry (`\chapter[Pays]{Chapter 1: ...}`) and the
# starred form. Written once and shared with
# `chitragupta/style_headings.py`, which reads the same command to report
# what this drops -- two spellings of one heading is how the two would
# drift into disagreeing about which headings they are about.
CHAPTER_COMMAND = r"\\chapter\*?(?:\[[^\]]*\])?\{"

# Only the braced title is rewritten: a short title is the contents-line
# text and is the author's to keep as it reads.
_LATEX_CHAPTER = re.compile(rf"({CHAPTER_COMMAND}){SELF_NUMBERED_TITLE.pattern}")


def unnumbered(text: str, latex: bool = False) -> str:
    """`text` with a chapter number a heading states for itself dropped.

    Matched against a code-blanked copy rather than the text itself, the
    way every other scan in this project reads a draft: a fenced block or
    a `verbatim` environment holding a line that *looks* like a heading
    (`# Chapter 1: setup` in a shell sample, a `\\chapter{}` in a book
    about writing books) is a code sample being shown to the reader, and
    rewriting one would corrupt the sample silently. `_blank_code`
    preserves every offset character for character, which is what lets
    the spans it finds be cut out of the original.

    `latex` picks which regions those are, and is not cosmetic --
    `citation_gate._blank_code` documents why: in LaTeX a backtick is an
    open-quote character rather than code markup, so applying the
    Markdown rules to a `.tex` draft blanks the span between two quoted
    phrases and hides whatever is inside it.
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
