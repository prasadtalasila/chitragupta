"""Keeping a Markdown pipe table whole when a retrieval window lands
inside one.

Split out of `chitragupta/retrieval.py` rather than added to it (#652):
that module was at 249 of docs/CODE-STANDARDS.md's 250 code lines when
this was written, and `_windows` is a registered C1 offender at 28
statements, so neither had room. `retrieval.py` gains no code line at
all -- this module joins its existing `from chitragupta import ...` line,
and `_windows`' final `return` calls `render_windows` in place of the
list comprehension it used to build.

**The problem, measured.** Docling serialises tables as pipe tables and
274 of 497 parsed texts in this corpus contain one, so BM25 has always
indexed their cell text. But one real row here measures ~450 characters
against a 500-character default window, so a hit inside a table returned
a fragment cut through the middle of a single row -- without the header
row naming the columns, which is most of what made the table worth
retrieving.

**Two halves, and the second is easy to miss.** Widening the window is
not enough on its own: `retrieval._clean_window` normalises whitespace
with `" ".join(text.split())`, which collapses every row of a table onto
one line. A table with no row breaks is not a table, so the block is
rendered line by line instead, each line cleaned individually. Everything
that is *not* a table still goes through the caller's own cleaner
unchanged, byte for byte -- most callers never touch a table and none of
them should be able to tell this module exists.

The cleaner is passed in rather than imported back, so `retrieval.py`
keeps owning what a window's text is allowed to contain (its citation
marker stripping in particular) and there is no import cycle.
"""

# Two lines, because a single piped line is prose -- a shell pipeline, a
# maths alternation, a table of one row that carries no header anyway --
# and preserving newlines around it would be noise. A real Markdown table
# is at minimum a header row and its separator.
_MIN_BLOCK_LINES = 2

# Ceiling on one rendered block, so a pathological table cannot swallow a
# result. Eight times the 500-character default window: comfortably more
# than any table in this corpus (the widest is ~2.7k characters), while
# still bounding the 200-row case the issue named. On exceeding it, whole
# rows are dropped from the end rather than the block being cut mid-row,
# which would put a caller back where it started -- and the header row is
# first, so it is the last thing to go.
_TABLE_BLOCK_MAX_CHARS = 4000


def _pipe_blocks(text: str) -> list:
    """Character bounds of every run of `_MIN_BLOCK_LINES` or more
    consecutive lines beginning with `|`.

    Offsets are tracked while walking `split("\\n")` rather than found
    again with `str.find`, because a table's separator row (`|---|---|`)
    repeats verbatim across documents and searching for a line's text
    would match the wrong one.
    """
    blocks: list = []
    start = None
    end = 0
    length = 0
    position = 0
    for line in text.split("\n"):
        if line.startswith("|"):
            if start is None:
                start = position
            end = position + len(line)
            length += 1
        else:
            if length >= _MIN_BLOCK_LINES:
                blocks.append((start, end))
            start, length = None, 0
        position += len(line) + 1
    if length >= _MIN_BLOCK_LINES:
        blocks.append((start, end))
    return blocks


def _block_around(begin: int, end: int, blocks: list) -> "tuple | None":
    """The first block the span `[begin, end)` touches, or `None`.

    Any overlap counts, however small: a window that catches the last
    cell of a table is exactly the case this exists for.
    """
    for block_begin, block_end in blocks:
        if begin < block_end and end > block_begin:
            return (block_begin, block_end)
    return None


def _render_block(block: str, clean) -> str:
    """One pipe-table block, cleaned line by line and capped.

    No empty-line guard, deliberately: a block runs from the start of its
    first `|` line to the end of its last, and a line that does not begin
    with `|` is what ended the block -- so every line here begins with one
    and none can clean away to nothing.
    """
    rendered: list = []
    total = 0
    for line in block.split("\n"):
        cleaned = clean(line)
        if total + len(cleaned) + 1 > _TABLE_BLOCK_MAX_CHARS:
            break
        rendered.append(cleaned)
        total += len(cleaned) + 1
    return "\n".join(rendered)


def render_windows(text: str, chosen: list, clean) -> list:
    """`chosen` spans of `text` rendered in document order, with any that
    fall inside a pipe table widened to the whole table.

    De-duplicated after widening, which is the one ordering subtlety
    here: the caller de-overlaps its spans *before* this runs, so two
    windows that each caught a different corner of the same table are not
    overlapping when it chooses them and become the identical block once
    widened. Returning both would repeat one table twice and spend a
    caller's result budget doing it.

    That can leave fewer windows than the caller asked for. This is
    correct -- one table replacing two fragments of itself is the point --
    and it is why nothing here tries to backfill the count.
    """
    blocks = _pipe_blocks(text) if "|" in text else []
    spans: list = []
    for begin, end in sorted(chosen):
        span = _block_around(begin, end, blocks) or (begin, end)
        if span not in spans:
            spans.append(span)
    return [
        _render_block(text[begin:end], clean) if (begin, end) in blocks else clean(text[begin:end])
        for begin, end in spans
    ]
