"""A Markdown render's raw LaTeX, dropped the way pandoc's other writers drop it (#1144).

`--format md` on a Markdown draft never reaches pandoc (see `render`), so
nothing removed a ```` ```{=latex} ```` / `{=tex}` block or a
`` `...`{=latex} `` span, and every one reached the rendered `.md`
verbatim, where a Markdown viewer shows it as a box of LaTeX. Pandoc's
`docx` and `html` writers drop exactly these, and its LaTeX writer
applies them; this is the first half of that for the one writer that is
not pandoc. A draft legitimately carries them -- an `\\arraystretch` pair
around a table is a PDF layout tweak -- so the draft keeps them.

Where they are comes from `_markdown_inert.raw_tex_spans`, the same
block-structure scan the citation gate reads, so a raw fence shown inside
a longer code fence stays an example, and fence lengths, tildes and an
unclosed fence follow pandoc there rather than a second, simpler reading
here.

**Only `latex` and `tex`.** A `{=html}` block or span is left as it is:
raw HTML is Markdown's own passthrough, and every Markdown viewer this
output is for renders it rather than showing it as code. Any other
format's raw block is pandoc-only and rare enough to leave verbatim
rather than guess at.

Standard library only, like the rest of this path.
"""

from chitragupta._markdown_inert import raw_tex_spans

# What may sit before a block's opener on its line and still let the
# whole line go: indentation and blockquote markers. A list marker may
# not -- cutting that line would cut the item -- so such a block stays.
_LINE_PREFIX = " \t>"
# After a dropped inline span, these take the space before it with it:
# "wide `\\hfill`{=latex}, then" reads "wide, then", not "wide , then".
_CLOSING = " \t\r\n.,;:!?)]}"


def _is_blank(line: str) -> bool:
    """Blank, or a blockquote's empty `>` line."""
    return not line.strip(" \t\r\n>")


def _line_end(text: str, pos: int) -> int:
    """Where the line holding `pos` ends, its newline included."""
    newline = text.find("\n", pos)
    return len(text) if newline == -1 else newline + 1


def _line_cut(text: str, start: int, end: int, taken: int) -> "tuple[int, int]":
    """The whole lines holding [start, end), and one blank line beside them
    where removing them would otherwise leave two blank lines in a row.

    The blank after them goes when the line before is blank too, or they
    open the document; at the very end, the blank before them goes
    instead, unless an earlier cut (`taken`) already took it."""
    first = text.rfind("\n", 0, start) + 1
    last = _line_end(text, end)
    before = text.rfind("\n", 0, max(first - 1, 0)) + 1
    blank_before = first == 0 or _is_blank(text[before:first])
    if blank_before and last < len(text) and _is_blank(text[last : _line_end(text, last)]):
        return first, _line_end(text, last)
    if blank_before and first and last == len(text) and before >= taken:
        return before, last
    return first, last


def _span_cut(text: str, start: int, end: int) -> "tuple[int, int]":
    """An inline span, and the one space its removal would leave doubled
    or stranded: before it when punctuation or a line end follows, after
    it when it opens the line."""
    if start and text[start - 1] in " \t" and (end == len(text) or text[end] in _CLOSING):
        return start - 1, end
    if (start == 0 or text[start - 1] == "\n") and text[end : end + 1] in (" ", "\t"):
        return start, end + 1
    return start, end


def dropped(text: str) -> str:
    """`text` without its raw LaTeX blocks and inline spans."""
    kept = []
    taken = 0
    for start, end, block in raw_tex_spans(text):
        first = text.rfind("\n", 0, start) + 1
        newline = text.find("\n", end)
        rest = text[end:] if newline == -1 else text[end:newline]
        if block and text[first:start].strip(_LINE_PREFIX):
            continue
        if text[first:start].strip(_LINE_PREFIX) or rest.strip():
            cut = _span_cut(text, start, end)
        else:
            cut = _line_cut(text, start, end, taken)
        # A span cut may reach back for a space an earlier cut took.
        kept.append(text[taken : max(cut[0], taken)])
        taken = cut[1]
    kept.append(text[taken:])
    return "".join(kept)
