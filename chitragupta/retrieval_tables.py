"""Keeping a Markdown pipe table whole when a retrieval window lands
inside one (#652).

274 of 497 parsed texts carry a Docling pipe table, and one row can be
~450 characters against a 500-character window, so a hit returned a
fragment of one row without the header. Widening is half the fix:
`retrieval._clean_window` collapses whitespace, which would flatten the
table, so a block is cleaned line by line. Everything else goes through
the caller's cleaner unchanged, which is passed in to avoid a cycle.

`style_tables.py` and the dossier's `retrieval.md` readers also look at
`|` lines, but ask different questions of different artefacts; sharing
code would couple three layers.
"""

# Two lines: a single piped line is prose, and a real table has at least a
# header row and its separator.
_MIN_BLOCK_LINES = 2

# Ceiling on one block: eight default windows, above the corpus's widest
# table (~2.7k characters). Whole rows drop from the end, never mid-row,
# so the header goes last.
_TABLE_BLOCK_MAX_CHARS = 4000


def _pipe_blocks(text: str) -> list:
    """Character bounds of every run of `_MIN_BLOCK_LINES` or more
    consecutive lines beginning with `|`.

    Offsets are tracked while walking `split("\\n")`, not found with
    `str.find`: a separator row repeats verbatim and would match wrongly.
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
    """The first block the span `[begin, end)` touches, or `None`; any
    overlap counts."""
    for block_begin, block_end in blocks:
        if begin < block_end and end > block_begin:
            return (block_begin, block_end)
    return None


def _render_block(block: str, clean) -> str:
    """One pipe-table block, cleaned line by line and capped. Every line
    begins with `|`, so none can clean away to nothing."""
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

    De-duplicated after widening, since two windows on one table become
    the same block. That can return fewer windows than asked for, which
    is correct, so nothing backfills.
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
