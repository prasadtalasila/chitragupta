"""What a *block* of a draft is: the unit smaller than a paragraph that
still carries one claim.

A blank-line paragraph is the wrong grain: a table or list has no sentence
boundary and would be quoted whole, and a heading glued to prose would
score as part of the sentence. So a paragraph splits into table rows, list
items and headings, in both Markdown and LaTeX.

Rejected homes, so neither is re-proposed: importing from
`citation_provenance` drags `ledger` in, and `uncited_prose` reads no
corpus; `_units.py` would exceed CODE-STANDARDS C2's 250-line cap.
`verbatim_check._paragraphs` stays a separate copy, frozen in the size
register.
"""

import re

from chitragupta.review import _units

# A table row and a heading are complete in one line; a list item runs to
# the next opener, so a hard-wrapped bullet stays whole.
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
# Whatever follows a row or heading starts its own block.
_STANDS_ALONE = re.compile(r"^\s*(?:\||#{1,6}\s)")
# A cell of the |---|:--:|---| separator row: alignment, not content.
_SEPARATOR_CELL = re.compile(r":?-{2,}:?")
# The whole separator row, so a caller can recognise the row above it as a
# header rather than a claim.
SEPARATOR_ROW = re.compile(r"^\s*\|[\s:|-]*\|\s*$")
# Unescaped pipes only: `\|` is a literal pipe inside a cell.
_ROW_SPLIT = re.compile(r"(?<!\\)\|")

# LaTeX: a tabular row ends at `\\`, so may span lines, and environment and
# rule commands are structure, not words of the draft.
_TEX_ITEM = re.compile(r"^\s*\\item\b\s*")
_TEX_ROW_END = re.compile(r"\\\\\s*$")
TEX_HEADING = re.compile(r"^\s*\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{")
# The braced title, so `\section{Standards}` reads as "Standards".
_TEX_HEADING_TITLE = re.compile(r"\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{([^}]*)\}")
_TEX_STRUCTURE = re.compile(
    r"\\(?:begin|end)\{[^}]*\}(?:\[[^\]]*\]|\{[^}]*\})*"
    r"|\\(?:top|mid|bottom)rule|\\hline|\\cline\{[^}]*\}"
)
_TEX_CELL_SPLIT = re.compile(r"(?<!\\)&")

# Stripped from every line: a blockquote repeats `>` on each, unlike a list
# item, so count=1 stripping would leave "> " mid-sentence.
_QUOTE_MARKER = re.compile(r"^\s*>\s?")


def paragraph_spans(lines: list[str]) -> list[tuple[int, int, str]]:
    """(first line, last line, joined text) per blank-line-separated block;
    the joined view of `_units.blocks`.
    """
    return [
        (start, start + len(block) - 1, " ".join(line.strip() for line in block))
        for start, block in _units.blocks(lines)
    ]


def _cells_prose(cells: list[str]) -> str:
    """Table cells joined with " -- ": raw `|` in a report's blockquote
    renders as a wall of `\\textbar{}` escapes.
    """
    stripped = (cell.strip() for cell in cells)
    return " -- ".join(c for c in stripped if c and not _SEPARATOR_CELL.fullmatch(c))


def _row_prose(row: str) -> str:
    return _cells_prose(_ROW_SPLIT.split(row.strip().strip("|")))


def _tex_row_prose(text: str) -> str:
    """A LaTeX row or environment fragment, flattened. Structure goes first,
    so `\\begin{tabular}{lll}`'s column spec stays out of the first cell.
    """
    without_structure = _TEX_ROW_END.sub("", _TEX_STRUCTURE.sub(" ", text)).strip()
    # One-line `\begin{itemize} \item ...` reaches here, not the marker branch.
    without_marker = _TEX_ITEM.sub("", without_structure, count=1)
    return _cells_prose(_TEX_CELL_SPLIT.split(without_marker))


def spans(lines: list[str]) -> list[tuple[int, int, str]]:
    """(first line, last line, text) per *block*: a prose paragraph is one
    span, a table or list one span per row or item.
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
            # A markdown row or heading ends with its line, a LaTeX row at `\\`.
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
    """Whether `text_of(block)` takes its plain `" ".join` branch, the only
    one `line_of_offset` maps precisely; same checks, same order.
    """
    first = block[0]
    if TABLE_ROW.match(first) or TEX_HEADING.match(first):
        return False
    joined = " ".join(_QUOTE_MARKER.sub("", line).strip() for line in block)
    if _TEX_STRUCTURE.search(joined) or _TEX_ROW_END.search(joined):
        return False
    return not any(marker.match(first) for marker in (LIST_ITEM, _TEX_ITEM, HEADING))


def line_of_offset(block_start: int, block: list[str], offset: int) -> int:
    """Which physical line (absolute, as `spans` numbers) `offset` into
    `text_of(block)` falls on; exact for a plain paragraph (#496).

    Other branches fall back to `block_start`. That is exact for a table row
    or heading, but a hard-wrapped list item is coarsened: reproducing
    `text_of`'s marker-stripping shift here was rejected as a second copy
    of it for an unmeasured case.
    """
    if len(block) == 1 or not _is_plain_paragraph(block):
        return block_start
    cursor = 0
    ends = []
    for raw in block:
        cursor += len(_QUOTE_MARKER.sub("", raw).strip())
        ends.append(cursor)
        cursor += 1  # the joining space
    # `offset` never exceeds the text, so this always finds a line.
    return block_start + next(index for index, end in enumerate(ends) if offset <= end)
