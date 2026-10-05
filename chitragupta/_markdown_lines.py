"""The line model `chitragupta/_markdown_inert.py` parses block structure with.

A container's lines keep where they sit in the document, so a blockquote
or list item can be stripped of its prefix and parsed again without any
offset moving. Split out of `_markdown_inert` for size; nothing else
uses it. Standard library only, like `citation_gate`.
"""

import bisect
import re
from dataclasses import dataclass

TAB_STOP = 4
# The line that closes a fence: three or more of one character, alone.
_CLOSER_RE = re.compile(r"(`{3,}|~{3,})[ \t]*\r?$")
# A dashed table border, `-----` or `---  ------`, which is also a rule.
_BORDER_RE = re.compile(r" {0,3}-+(?:[ \t]+-+)*[ \t]*\r?$")


@dataclass(frozen=True)
class Line:
    """One line of a container: where its text starts in the document,
    the column it starts at (for tab stops), and the text itself."""

    start: int
    col: int
    text: str


def document_lines(text: str) -> list[Line]:
    """`text`'s lines, each knowing its offset, with no prefix stripped."""
    lines = []
    pos = 0
    for raw in text.split("\n"):
        lines.append(Line(pos, 0, raw))
        pos += len(raw) + 1
    return lines


def indent(line: Line) -> tuple[int, int]:
    """(columns, characters) of `line`'s leading whitespace."""
    col = line.col
    count = 0
    for char in line.text:
        if char == " ":
            col += 1
        elif char == "\t":
            col += TAB_STOP - col % TAB_STOP
        else:
            break
        count += 1
    return col - line.col, count


def drop(line: Line, chars: int) -> Line:
    """`line` less its first `chars` characters, columns kept honest."""
    col = line.col
    for char in line.text[:chars]:
        col += TAB_STOP - col % TAB_STOP if char == "\t" else 1
    return Line(line.start + chars, col, line.text[chars:])


def dedent(line: Line, columns: int) -> Line:
    """`line` less `columns` columns of leading whitespace.

    A tab straddling the cut is consumed whole, which leaves the rest
    less indented than pandoc sees it: never enough to make a paragraph
    read as code, only the reverse."""
    col = line.col
    count = 0
    for char in line.text:
        if col - line.col >= columns or char not in " \t":
            break
        col += TAB_STOP - col % TAB_STOP if char == "\t" else 1
        count += 1
    return Line(line.start + count, col, line.text[count:])


def is_blank(line: Line) -> bool:
    return not line.text.strip()


def unquote(line: Line) -> Line:
    """`line` less its `>` marker and the one space that may follow it."""
    _, chars = indent(line)
    inner = drop(line, chars + 1)
    return drop(inner, 1) if inner.text[:1] in (" ", "\t") else inner


class Finder:
    """`pattern.search(text, pos)` with its answer remembered, so a run
    of openers with no closer costs one scan rather than one each."""

    def __init__(self, text: str, pattern: "re.Pattern") -> None:
        self._text = text
        self._pattern = pattern
        self._asked = -1
        self._found: "re.Match | None" = None

    def find(self, pos: int) -> "re.Match | None":
        if self._asked != -1 and pos >= self._asked:
            if self._found is None or self._found.start() >= pos:
                return self._found
        self._asked = pos
        self._found = self._pattern.search(self._text, pos)
        return self._found


def matching_parens(text: str) -> "dict[int, int]":
    """Each `(`'s matching `)` on its own line, backslash escapes
    honoured: one pass, so a line of unclosed `[a](` stays linear."""
    found: dict[int, int] = {}
    stack: list[int] = []
    for match in re.finditer(r"\\.|[()\n]", text):
        char = match.group()
        if char == "(":
            stack.append(match.start())
        elif char == ")":
            if stack:
                found[stack.pop()] = match.start()
        elif char == "\n":
            stack.clear()
    return found


def matching_environments(text: str) -> "dict[int, int]":
    """Each `\\begin{env}`'s offset mapped to the end of its matching
    `\\end{env}`, nesting honoured: one pass over every begin and end."""
    found: dict[int, int] = {}
    stack: list[tuple[str, int]] = []
    for match in re.finditer(r"\\(begin|end)\{([A-Za-z*]+)\}", text):
        kind, name = match.groups()
        if kind == "begin":
            stack.append((name, match.start()))
            continue
        for depth in range(len(stack) - 1, -1, -1):
            if stack[depth][0] == name:
                found[stack[depth][1]] = match.end()
                del stack[depth:]
                break
    return found


class FenceClosers:
    """Every line that could close a fence, indexed so an opener finds
    its closer by lookup: per character, the closers' rows and lengths
    and the longest closer at or after each, for an O(1) "none"."""

    def __init__(self, lines: list[Line]) -> None:
        found: dict = {"`": ([], []), "~": ([], [])}
        for row, line in enumerate(lines):
            columns, chars = indent(line)
            match = _CLOSER_RE.match(line.text, chars) if columns < 4 else None
            if match:
                rows, lengths = found[match.group(1)[0]]
                rows.append(row)
                lengths.append(len(match.group(1)))
        self._index = {}
        for char, (rows, lengths) in found.items():
            longest = lengths[:]
            for k in range(len(longest) - 2, -1, -1):
                longest[k] = max(longest[k], longest[k + 1])
            self._index[char] = (rows, lengths, longest)

    def after(self, row: int, char: str, length: int) -> "int | None":
        """The row closing a fence of `length` `char`s opened at `row`.

        The closers skipped on the way are inside the fence, which the
        caller then consumes, so the walk is paid for once."""
        rows, lengths, longest = self._index[char]
        k = bisect.bisect_right(rows, row)
        if k == len(rows) or longest[k] < length:
            return None
        while lengths[k] < length:
            k += 1
        return rows[k]


class TableBorders:
    """Where a table ruled by dashed lines ends, so its rows stay prose.

    Pandoc reads a dashed line followed straight away by a row as the top
    of a multiline or headerless table, closed by a dashed line before a
    blank one; its rows are cells, and a row indented four spaces after a
    blank line is not indented code there. A dashed line with a blank
    line after it is a rule. Closing borders are indexed once."""

    def __init__(self, lines: list[Line]) -> None:
        self._lines = lines
        self._closing: "list[int] | None" = None

    def _is_border(self, row: int) -> bool:
        text = self._lines[row].text
        return bool(_BORDER_RE.match(text)) and text.count("-") >= 3

    def after(self, row: int) -> "int | None":
        """The row after the table whose top border is `row`, or None."""
        lines = self._lines
        if not self._is_border(row) or row + 1 == len(lines) or is_blank(lines[row + 1]):
            return None
        if self._closing is None:
            self._closing = [
                k
                for k in range(len(lines))
                if self._is_border(k) and (k + 1 == len(lines) or is_blank(lines[k + 1]))
            ]
        index = bisect.bisect_left(self._closing, row + 2)
        return self._closing[index] + 1 if index < len(self._closing) else None
