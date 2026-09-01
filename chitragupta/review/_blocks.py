"""What a *block* of a draft is: the unit smaller than a paragraph that
still carries one claim.

A blank-line paragraph is the wrong grain for two questions this layer
asks. A table or a list is one paragraph containing no sentence boundary
at all, so reading it whole quotes the entire table back as a single
claim; and a heading glued to the prose beneath it scores as though the
title were part of the sentence. So a paragraph is subdivided: a table
**row**, a list **item**, a **heading**, and otherwise the paragraph
itself. Both markups are recognised, since every genre skill exports
`.tex` and `.pdf` beside the `.md`.

Split out of `chitragupta/review/citation_provenance.py`, which wrote it
and was its only caller until `chitragupta/review/uncited_prose.py`
needed the same walk. Two alternatives were measured and rejected, and
they are worth recording so neither is re-proposed:

- **Importing it from `citation_provenance`** drags `ledger` and
  `passages` in behind it. `uncited_prose` reads only the draft -- no
  corpus, no ledger, no sync -- and that is a property worth keeping.
- **Moving it into `_units.py`** would take that module from 199 code
  lines to roughly 265, over docs/CODE-STANDARDS.md's C2 cap of 250, so
  it would need its own split first.

`verbatim_check._paragraphs` is a third copy of the paragraph walk and
deliberately stays one: 1880 code lines and frozen in the size register,
so migrating it is churn out of proportion.

Stdlib-only (`re`, plus `_units.blocks` for the paragraph walk itself).
"""

import re

from chitragupta.review import _units

# Markdown block openers. A table row and a heading are each complete in
# one line, so they are blocks by themselves; a list item opens one that
# runs until the next opener or the end of the paragraph, so a
# hard-wrapped bullet stays whole.
TABLE_ROW = re.compile(r"^\s*\|")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
HEADING = re.compile(r"^\s*#{1,6}\s+")
_OPENS_BLOCK = re.compile(
    r"^\s*(?:"
    r"\||[-*+]\s|\d+[.)]\s|#{1,6}\s"  # markdown
    r"|\\item\b|\\(?:begin|end)\{"  # LaTeX environments
    r"|\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{"  # LaTeX headings
    r")"
)
# A row and a heading are complete in one line: whatever follows starts
# its own block, so prose under a heading is not glued to the heading.
_STANDS_ALONE = re.compile(r"^\s*(?:\||#{1,6}\s)")
# A cell of the |---|:--:|---| separator row: alignment, not content.
_SEPARATOR_CELL = re.compile(r":?-{2,}:?")
# The same row, whole. `_cells_prose` already flattens it to nothing, so
# this exists for the one caller that has to recognise the row *above* it
# as a header row rather than a claim.
SEPARATOR_ROW = re.compile(r"^\s*\|[\s:|-]*\|\s*$")
# Split a row on its unescaped pipes only -- `\|` is markdown's way of
# putting a literal pipe inside a cell, and splitting there would cut a
# cell in half.
_ROW_SPLIT = re.compile(r"(?<!\\)\|")

# The same two shapes in LaTeX. Two differences from Markdown: a tabular
# row ends at `\\` rather than at a newline, so one row can span several
# hard-wrapped lines; and the environment and rule commands are structure
# that would otherwise be read as though `tabular` and `toprule` were
# words of the draft.
_TEX_ITEM = re.compile(r"^\s*\\item\b\s*")
_TEX_ROW_END = re.compile(r"\\\\\s*$")
TEX_HEADING = re.compile(r"^\s*\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{")
# The same command with its braced title, so `\section{Standards}` reads
# as "Standards" rather than as its own markup -- the counterpart of
# dropping a markdown heading's leading `#`.
_TEX_HEADING_TITLE = re.compile(r"\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{([^}]*)\}")
_TEX_STRUCTURE = re.compile(
    r"\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\]|\{[^}]*\})*"
    r"|\\(?:top|mid|bottom)rule|\\hline|\\cline\{[^}]*\}"
)
_TEX_CELL_SPLIT = re.compile(r"(?<!\\)&")

# A blockquote's marker, stripped from *every* line rather than only the
# first. Unlike a list item, whose hard-wrapped continuation lines carry
# no marker, a blockquote repeats its `>` on each line -- so the
# count=1 stripping below leaves the rest embedded mid-sentence, and a
# four-line quote is read back as "Method adapted from > hadufer/...".
_QUOTE_MARKER = re.compile(r"^\s*>\s?")


def paragraph_spans(lines: list[str]) -> list[tuple[int, int, str]]:
    """(first line, last line, joined text) per blank-line-separated block.

    The joined view of `_units.blocks`, which does the same walk but
    returns raw lines -- `synthesis` has to find a declaration marker
    among them before they are joined.
    """
    return [
        (start, start + len(block) - 1, " ".join(line.strip() for line in block))
        for start, block in _units.blocks(lines)
    ]


def _cells_prose(cells: list[str]) -> str:
    """Table cells as something quotable: joined with " -- ".

    Cells are phrases, not sentences, and a row's own delimiters would
    otherwise reach a report inside a blockquote -- where pandoc renders
    every `|` as `\\textbar{}`, so a cited table arrived as a wall of
    escapes.
    """
    stripped = (cell.strip() for cell in cells)
    return " -- ".join(c for c in stripped if c and not _SEPARATOR_CELL.fullmatch(c))


def _row_prose(row: str) -> str:
    """A markdown table row, flattened."""
    return _cells_prose(_ROW_SPLIT.split(row.strip().strip("|")))


def _tex_row_prose(text: str) -> str:
    """A LaTeX row or environment fragment, flattened.

    Structure first, then cells: dropping `\\begin{tabular}{lll}` before
    splitting keeps its `{lll}` column spec out of the first cell.
    """
    without_structure = _TEX_ROW_END.sub("", _TEX_STRUCTURE.sub(" ", text)).strip()
    # `\begin{itemize} \item ...` on one line reaches here rather than the
    # marker branch, and "item" is not a word of the draft.
    without_marker = _TEX_ITEM.sub("", without_structure, count=1)
    return _cells_prose(_TEX_CELL_SPLIT.split(without_marker))


def spans(lines: list[str]) -> list[tuple[int, int, str]]:
    """(first line, last line, text) per *block*, subdividing paragraphs.

    A paragraph of prose comes back as one span, exactly as a paragraph
    walk would give it. A paragraph that is a table or a list comes back
    as one span per row or item, because those carry no sentence boundary
    to find and so would otherwise be read whole.
    """
    found = []
    for start, end, _ in paragraph_spans(lines):
        block: list[str] = []
        block_start = start
        for index in range(start, end + 1):
            line = lines[index - 1]
            if block and _OPENS_BLOCK.match(line):
                found.append((block_start, index - 1, text_of(block)))
                block, block_start = [], index
            block.append(line)
            # A markdown row or heading ends with its line; a LaTeX row
            # ends at `\\`, wherever in the block that falls; a sectioning
            # command is a heading either way.
            if _STANDS_ALONE.match(line) or _TEX_ROW_END.search(line) or TEX_HEADING.match(line):
                found.append((block_start, index, text_of(block)))
                block, block_start = [], index + 1
        if block:
            found.append((block_start, end, text_of(block)))
    return found


def text_of(block: list[str]) -> str:
    """The block's text as prose: a row flattened, a marker dropped."""
    if TABLE_ROW.match(block[0]):
        return _row_prose(block[0])
    joined = " ".join(_QUOTE_MARKER.sub("", line).strip() for line in block)
    if TEX_HEADING.match(block[0]):
        return _TEX_HEADING_TITLE.sub(r"\1", joined)
    if _TEX_STRUCTURE.search(joined) or _TEX_ROW_END.search(joined):
        return _tex_row_prose(joined)
    for marker in (LIST_ITEM, _TEX_ITEM, HEADING):
        if marker.match(block[0]):
            return marker.sub("", joined, count=1)
    return joined


def _is_plain_paragraph(block: list[str]) -> bool:
    """Whether `text_of(block)` takes its default `" ".join` branch
    untouched by a further substitution -- the only branch whose offsets
    `line_of_offset` maps precisely, decided by the same checks
    `text_of` itself makes, in the same order.
    """
    first = block[0]
    if TABLE_ROW.match(first) or TEX_HEADING.match(first):
        return False
    joined = " ".join(_QUOTE_MARKER.sub("", line).strip() for line in block)
    if _TEX_STRUCTURE.search(joined) or _TEX_ROW_END.search(joined):
        return False
    return not any(marker.match(first) for marker in (LIST_ITEM, _TEX_ITEM, HEADING))


def line_of_offset(block_start: int, block: list[str], offset: int) -> int:
    """Which physical line (absolute, matching `spans`'s own numbering)
    `offset` -- a character offset into `text_of(block)` -- falls on.

    Exact for the plain multi-line paragraph `text_of`'s default branch
    builds: `" ".join` of each line's quote-marker-stripped, stripped
    text, one line's worth of it a sentence-finding caller needs to
    locate precisely (#496).

    Every other branch -- a table row, a TeX structure, a list or
    heading marker -- falls back to `block_start` instead of computing a
    precise offset. A table row and a heading are one physical line in
    every case a caller of `spans` actually reaches them for (a header
    row's own line is never a body row's, and a heading block never
    reaches a caller that asks this at all), so the fallback there is
    exact too. **A list or TeX item is not always one line** -- a
    hard-wrapped bullet stays one block across several physical lines
    (`spans`'s own docstring) -- and `text_of` strips that block's marker
    from the *front* of the already-joined text, shifting every
    subsequent line's offset by the marker's length. Reproducing that
    shift here to stay exact was rejected: it would restate `text_of`'s
    marker-stripping in a second place for a case this project has not
    measured, against the same "measured, not guessed" bar the module
    docstring sets. `block_start` is what every sentence in such a block
    reported before this offset mapping existed, so this is a documented
    coarsening, not a regression.
    """
    if len(block) == 1 or not _is_plain_paragraph(block):
        return block_start
    cursor = 0
    ends = []
    for raw in block:
        cursor += len(_QUOTE_MARKER.sub("", raw).strip())
        ends.append(cursor)
        cursor += 1  # the joining space
    # `offset` is always within `text_of(block)`'s own length here --
    # `sentences.spans`' tightened offsets never exceed the text they
    # were cut from -- so this always finds a line and never falls
    # through.
    return block_start + next(index for index, end in enumerate(ends) if offset <= end)
