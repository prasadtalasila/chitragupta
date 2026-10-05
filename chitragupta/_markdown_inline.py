"""Inline non-prose inside one paragraph, for `chitragupta/_markdown_inert.py`.

Code spans, HTML comments, autolinks and link targets, scanned left to
right so whichever opens first wins: a comment inside a code span stays
code, and a backtick inside a comment stays comment. Split out of
`_markdown_inert` for size; nothing else uses it. Standard library only.
"""

import bisect
import re

from chitragupta._markdown_lines import Finder, matching_environments, matching_parens

_AUTOLINK_RE = re.compile(r"<[A-Za-z][A-Za-z0-9+.\-]{1,31}:[^\s<>]*>")
_BACKTICKS_RE = re.compile(r"`+")
_EMPTY_COMMENT_RE = re.compile(r"-?>")
# `\\citet{k}`{=latex} is raw LaTeX, live in a LaTeX render, not code.
_RAW_TEX_RE = re.compile(r"\{=(?:latex|tex)\}")


def _backtick_runs(text: str) -> tuple[list, list]:
    """Every backtick run, and for each the next run of its length."""
    runs = [(m.start(), m.end() - m.start()) for m in _BACKTICKS_RE.finditer(text)]
    following: list = [None] * len(runs)
    seen: dict = {}
    for k in range(len(runs) - 1, -1, -1):
        following[k] = seen.get(runs[k][1])
        seen[runs[k][1]] = k
    return runs, following


class InlineScanner:
    """One container's inline indexes, and the paragraph scan over them.

    `container` supplies the joined text and the line geometry, marks
    what is blanked, and says where a paragraph ends."""

    def __init__(self, container) -> None:
        self._box = container
        self._runs, self._next_run = _backtick_runs(container.text)
        self._comments = Finder(container.text, re.compile("-->"))
        self._parens: "dict[int, int] | None" = None
        self._environments: "dict[int, int] | None" = None

    def scan(self, row: int, end_row: int) -> int:
        """Blank inline non-prose in the paragraph `row`..`end_row`, and
        return the row after it -- later than `end_row` when a comment
        ran on past it."""
        box = self._box
        text = box.text
        pos = box.offsets[row]
        end = box.line_end(end_row - 1)
        brackets: list[int] = []
        while pos < end:
            char = text[pos]
            if text.startswith("\\begin{", pos):
                pos, end = self._environment(pos, end)
            elif char == "\\":
                pos += 2
            elif char == "`":
                pos = self._code_span(pos, end)
            elif text.startswith("<!--", pos):
                pos, end = self._comment(pos, end)
            elif char == "<":
                pos = self._autolink(pos)
            elif char in "[]":
                pos = self._bracket(pos, brackets)
            else:
                pos += 1
        return box.row_of(end) + 1 if end < len(text) else len(box.lines)

    def _code_span(self, pos: int, end: int) -> int:
        """Blank the code span the backtick run at `pos` opens, if it
        closes inside the paragraph; return where scanning resumes."""
        run = bisect.bisect_right(self._runs, (pos, len(self._box.text))) - 1
        start, length = self._runs[run]
        if start < pos:
            # Landing inside a run (an escaped backtick began it) leaves
            # the rest of the run literal.
            return start + length
        closing = self._next_run[run]
        if closing is None or self._runs[closing][0] >= end:
            return start + length
        stop = self._runs[closing][0] + length
        if not _RAW_TEX_RE.match(self._box.text, stop):
            self._box.mark(start, stop, code=True)
        return stop

    def _comment(self, pos: int, end: int) -> tuple[int, int]:
        """Blank the comment opening at `pos`, which runs to its `-->`
        even past a blank line, as pandoc's does: the paragraph then
        carries on from the line that closed it. Unclosed, it is prose,
        and `<!-->` / `<!--->` close themselves."""
        box = self._box
        empty = _EMPTY_COMMENT_RE.match(box.text, pos + 4)
        if empty:
            box.mark(pos, empty.end(), code=False)
            return empty.end(), end
        found = self._comments.find(pos + 4)
        if found is None:
            return pos + 4, end
        box.mark(pos, found.end(), code=False)
        if found.end() > end:
            end = box.line_end(box.paragraph_end(box.row_of(found.end() - 1)) - 1)
        return found.end(), end

    def _environment(self, pos: int, end: int) -> tuple[int, int]:
        """Step over a raw TeX environment, unblanked: pandoc passes it to
        LaTeX whole, blank lines and indented lines included, so a
        `\\citet{}` inside it is live -- and reading its indented lines
        as code would hide that from the gate. Unmatched, it is prose."""
        if self._environments is None:
            self._environments = matching_environments(self._box.text)
        stop = self._environments.get(pos)
        if stop is None:
            return pos + 2, end
        if stop > end:
            box = self._box
            end = box.line_end(box.paragraph_end(box.row_of(stop - 1)) - 1)
        return stop, end

    def _autolink(self, pos: int) -> int:
        """Blank the target of an autolink `<scheme:...>` at `pos`."""
        link = _AUTOLINK_RE.match(self._box.text, pos)
        if link is None:
            return pos + 1
        self._box.mark(pos + 1, link.end() - 1, code=False)
        return link.end()

    def _bracket(self, pos: int, brackets: list[int]) -> int:
        """Track `[`; at the `]` closing one, blank a link target after it.

        A `]` closing `[^...` is a footnote reference, never link text:
        `[^1](@b)` is a reference followed by a live citation."""
        if self._box.text[pos] == "[":
            brackets.append(pos)
            return pos + 1
        if not brackets or self._box.text.startswith("[^", brackets.pop()):
            return pos + 1
        return self._destination(pos + 1)

    def _destination(self, pos: int) -> int:
        """Blank a link target `(...)` straight after a `]` that closed a
        `[`: balanced parentheses, on one line. Pandoc's own target
        grammar is looser (`[t](a b)` is a link), and anything this
        declines stays prose."""
        if not self._box.text.startswith("(", pos):
            return pos
        if self._parens is None:
            self._parens = matching_parens(self._box.text)
        close = self._parens.get(pos)
        if close is None:
            return pos
        self._box.mark(pos, close + 1, code=False)
        return close + 1
