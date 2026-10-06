"""Where a draft's References section starts and ends.

Split from `chitragupta/references.py`, which builds that section, because
three callers need only to find it: `render_output` strips it before
handing a draft to pandoc, `verbatim_check` masks it before scanning, and
`references` itself splices a rebuilt one in. None of them needs the
ledger to ask where a heading is. `references.py` imports these, and
nothing here imports back -- the same one-way shape as `references_ieee`
and `references_renumber`.
"""

import re

from chitragupta import citation_gate


# Matches the References heading `references.py` writes, bare ("## References")
# or numbered to match a draft's own heading convention ("## 6. References"),
# at any heading level -- used both to detect an existing section (for
# render_output.py, which strips it before handing the draft to pandoc)
# and to find where to splice in a replacement.
#
# The section number is multi-level (`\d+(?:\.\d+)*`), not a single digit
# group: a book numbers its headings per chapter, so every chapter of a
# book-length draft ends in "## 1.14 References", which an earlier
# `(?:\d+[.)]\s*)?` did not match. The consequence was silent and
# expensive -- `section_start` returned None, so the whole bibliography
# stayed in the draft for every caller that acts on it. For
# `verbatim_check.scan` that meant scanning the reference list against
# the corpus, where two documents citing the same paper share its title
# and venue verbatim: on this project's own 15-chapter book that was
# 97.7% of all findings and 100% of the long-run bucket, none of them
# reuse. The trailing separator stays optional because "1.14 References"
# carries none, while "6. References" and "6) References" still do.
#
# The title itself is shared: `review/_claims.py` and `style_typeset.py`
# compose `REFERENCE_TITLE` into their own patterns rather than each
# restating which words open a bibliography, which is how `## Bibliography`
# came to be the reference list for two readers and prose for the third
# (#951). It is a string, not a compiled pattern, because the three match
# different things -- a heading line here, a title with its markup already
# stripped there, a heading-to-next-heading region in the typeset check --
# the same reason `_pandoc_cites.PANDOC_KEY` is one. Anchored at both ends
# by every caller: `## References and notes` is not the bibliography, and
# this module's callers act on the answer destructively. `[ \t]`, not
# `\s`, so a caller compiling it under DOTALL cannot let a title run
# onto the next line. A letter or Roman-numeral number needs its `.` or
# `)`, so "See. References" is not read as section "See".
REFERENCE_TITLE = (
    r"(?:(?:\d+(?:\.\d+)*[.)]?|(?:[A-Z]|[IVXLC]+)[.)])[ \t]*)?"
    r"(?:References|Bibliography|Works[ \t]+cited)"
)
_HEADING_RE = re.compile(rf"^#{{1,6}}[ \t]*{REFERENCE_TITLE}[ \t]*$", re.IGNORECASE)


# Any Markdown ATX heading, for section_end below -- deliberately not
# level-restricted: a heading nested under References (e.g. an
# "### Acknowledgments" some genre skill emits right after the
# bibliography) still marks where the References section stops, the same
# "next heading, any level" extent dossier.sections() uses for its own
# outline.
_ANY_HEADING_RE = re.compile(r"^#{1,6}\s")


def has_section(text: str) -> bool:
    return section_start(text.splitlines(keepends=True)) is not None


def section_start(lines: list[str]) -> int | None:
    """Index of the bibliography heading in `lines` (References,
    Bibliography or Works cited, per `REFERENCE_TITLE`), or None.

    A heading inside a fenced code block doesn't count. Both callers act
    on the answer destructively -- `apply` replaces everything from here
    down, and render_output strips it from what pandoc sees -- so a
    tutorial that *shows* a `## References` line in an example would
    otherwise have the rest of its lesson silently truncated.
    citation_gate's own code-blanking is what the gate uses to avoid the
    same class of false positive, and it preserves line structure, so
    indices still line up with `lines`.
    """
    blanked = citation_gate._blank_code("".join(lines)).splitlines()
    for i, line in enumerate(blanked):
        if _HEADING_RE.match(line.strip()):
            return i
    return None


def section_end(lines: list[str], start: int) -> int:
    """Index of the next heading line after `lines[start]` (of any
    level), or `len(lines)` if none follows -- i.e. `lines[start:end]` is
    the whole section `lines[start]` heads, heading included.

    General-purpose despite living beside the References-specific helpers
    above -- every caller passes `section_start`'s return, but nothing
    here requires that heading to be References specifically. The same
    "next heading, any level" extent `chitragupta/dossier/_sections.py`'s
    `sections()` computes for its own outline, kept as a separate,
    smaller implementation here rather than importing the dossier
    (drafting-review) layer from this corpus-adjacent module.

    Every caller used to treat "the References heading" as "to end of
    file" -- `apply`/`numbered_markdown` deleted whatever came after it,
    `render_output` stripped it from what pandoc sees, and the verbatim
    scanner masked it from detection. All three silently lost or hid an
    appendix or acknowledgments section introduced by its own heading
    after References, which is not part of it (M-8/m-33/m-34). Fence-aware
    the same way section_start is, and for the same reason: a `#` shown
    inside a code example must not end the section early.
    """
    blanked = citation_gate._blank_code("".join(lines)).splitlines()
    for i in range(start + 1, len(blanked)):
        if _ANY_HEADING_RE.match(blanked[i].strip()):
            return i
    return len(lines)
