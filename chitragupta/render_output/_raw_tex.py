"""A Markdown render's raw LaTeX, dropped the way pandoc's other writers drop it (#1144).

`--format md` never reaches pandoc, so `{=latex}`/`{=tex}` blocks and spans
reached the `.md` verbatim. The draft keeps them (they are PDF layout tweaks).
Locations come from `_markdown_inert.raw_tex_spans`, the citation gate's scan,
so fence rules follow pandoc. `{=html}` is left alone: Markdown viewers render it.
"""

from chitragupta._markdown_inert import raw_tex_spans

# Indentation and blockquote markers may precede a block's opener and the whole
# line still goes. A list marker may not -- cutting that line would cut the item.
_LINE_PREFIX = " \t>"
# After a dropped inline span, these take the space before it with it:
# "wide `\\hfill`{=latex}, then" reads "wide, then", not "wide , then".
_CLOSING = " \t\r\n.,;:!?)]}"


def _is_blank(line: str) -> bool:
    """Blank, or a blockquote's empty `>` line."""
    return not line.strip(" \t\r\n>")


def _line_end(text: str, pos: int) -> int:
    newline = text.find("\n", pos)
    return len(text) if newline == -1 else newline + 1


def _line_cut(text: str, start: int, end: int, taken: int) -> "tuple[int, int]":
    """The whole lines holding [start, end), plus one adjacent blank line where
    removing them would leave two blanks in a row (unless `taken` already took it)."""
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
    """An inline span, and the one space its removal would leave doubled or stranded."""
    if start and text[start - 1] in " \t" and (end == len(text) or text[end] in _CLOSING):
        return start - 1, end
    if (start == 0 or text[start - 1] == "\n") and text[end : end + 1] in (" ", "\t"):
        return start, end + 1
    return start, end


def dropped(text: str) -> str:
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
