"""What pandoc's Markdown reader does not read as prose, found by block structure.

Standard library only, like `citation_gate`. See the comment below for
where this must not err.
"""

# The gate must extract exactly the citations pandoc resolves (#944); a
# line-pairing pass disagreed with pandoc on fences in comments (#945),
# code under list items (#946), comments, link targets and reference
# definitions. This is one pass over pandoc's block structure, containers
# parsed recursively; each rule was checked against `pandoc -t json`, and
# tests/test_citation_gate_pandoc.py keeps that comparison running.
#
# **Where it must not err.** Blanking prose pandoc reads makes a citation
# vanish from the gate, so a construct is blanked only when complete, and
# an unplaceable container is read as a larger indent. Known safe-side
# gaps: `$math$` and raw inline HTML other than comments.
#
# Linear (#824): closers come from an index or memoised search, and
# containers deeper than `_MAX_DEPTH` are read as prose.

import re

from chitragupta._markdown_inline import InlineScanner
from chitragupta._markdown_lines import (
    FenceClosers,
    Finder,
    Line,
    TableBorders,
    dedent,
    document_lines,
    drop,
    indent,
    is_blank,
    unquote,
)
from chitragupta._markdown_marks import ContainerText, Found

# A thousand `>` would otherwise recurse past Python's limit.
_MAX_DEPTH = 32

# A fence opener: three or more of one character, then at most one
# attribute block or word; more makes it an inline code span to pandoc.
_FENCE_RE = re.compile(r"(`{3,}|~{3,})[ \t]*(?:\{[^}\n]*\}|\S+)?[ \t]*\r?$")
# Raw LaTeX: a `\\citep{}` inside is live in a LaTeX render, so not blanked.
_RAW_TEX_RE = re.compile(r"\{=(?:latex|tex)\}")
# Every pandoc list/definition/example marker. A false match costs only a
# larger indent; a miss would read indented paragraphs as code.
_ITEM_RE = re.compile(
    r"(?:[-*+]|\d{1,9}[.)]|#[.)]|\(\d{1,9}\)|[A-Za-z][.)]|\([A-Za-z]\)"
    r"|[ivxlcdmIVXLCDM]+[.)]|\([ivxlcdmIVXLCDM]+\)|\(@[\w-]*\)|@[\w-]*[.)]|[:~])(?=[ \t]|$)"
)
# Example markers. A label they define makes `@label` outside a bracketed
# citation an example reference, not a citation (#1021).
_EXAMPLE_RE = re.compile(r"\(@([\w-]+)\)|@([\w-]+)[.)]")
# A setext underline or table delimiter row, which pandoc reads before a
# list item. Deliberately broad: a missed label only over-reports.
_UNDERLINE_RE = re.compile(r"[ \t|:+]*[-=][-=|:+ \t]*\r?$")
_DEFINITION_RE = re.compile(r"[:~](?=[ \t])")
_FOOTNOTE_RE = re.compile(r"\[\^[^\]\s]+\]:")
_ATX_RE = re.compile(r"#{1,6}(?=[ \t]|$)")
# A rule, which pandoc tries before a list marker: `-   ---` is a rule.
_RULE_RE = re.compile(r"([-*_])(?:[ \t]*\1){2,}[ \t]*\r?$")
# Not prose, unless the label is a citation (`[@k]: x` cites `k`).
_REFERENCE_RE = re.compile(
    r"\[(?![\^@]|-@)[^\]\n]+\]:[ \t]*(?:<[^>\n]*>|\S+)"
    r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^)\n]*\)))?[ \t]*\r?$"
)
# The opening tag must be whole on its line: `<pre` alone is prose.
_RAW_BLOCK_RE = re.compile(r"<(pre|script|style|textarea)(?:[ \t][^>\n]*)?>", re.IGNORECASE)


class _Container(ContainerText):
    """One container's blocks, scanned for what to mark."""

    def __init__(self, lines: list[Line], depth: int, in_item: bool, found: Found) -> None:
        super().__init__(lines, found)
        self.depth = depth
        self.in_item = in_item
        self._closers = FenceClosers(lines)
        self._tables = TableBorders(lines)
        self._inline = InlineScanner(self)
        self._raw_closers: dict = {}

    def fence_at(self, row: int) -> "int | None":
        """The closing row of a complete fence opened at `row`, or None."""
        line = self.lines[row]
        columns, chars = indent(line)
        match = _FENCE_RE.match(line.text, chars) if columns < 4 else None
        if not match:
            return None
        return self._closers.after(row, match.group(1)[0], len(match.group(1)))

    def interrupts(self, row: int) -> bool:
        """Does `row` end the paragraph above it?"""
        # Short, since pandoc wants a blank line before most blocks. A
        # definition or footnote marker interrupts because a miss would
        # cost a citation; a tilde fence does not.
        line = self.lines[row]
        columns, chars = indent(line)
        if columns >= 4:
            return False
        rest = line.text[chars:]
        if rest.startswith("```") and self.fence_at(row) is not None:
            return True
        if self.in_item and _ITEM_RE.match(rest):
            return True
        return bool(_DEFINITION_RE.match(rest) or _FOOTNOTE_RE.match(rest))

    def paragraph_end(self, row: int) -> int:
        """The row after the paragraph that `row` is part of."""
        row += 1
        while row < len(self.lines) and not is_blank(self.lines[row]) and not self.interrupts(row):
            row += 1
        return row

    def scan(self) -> None:
        row = 0
        while row < len(self.lines):
            row = self._block(row)

    def _block(self, row: int) -> int:
        """Handle the block starting at `row`; return the row after it."""
        line = self.lines[row]
        if is_blank(line):
            return row + 1
        columns, chars = indent(line)
        if columns >= 4:
            # Indented code; paragraphs are consumed whole, so a block start.
            end = row
            while end < len(self.lines) and (
                is_blank(self.lines[end]) or indent(self.lines[end])[0] >= 4
            ):
                end += 1
            self.mark_rows(row, end - 1, code=True)
            return end
        rest = line.text[chars:]
        handled = self._yaml(row, rest) or self._fence(row) or self._container(row, chars, rest)
        if handled is not None:
            return handled
        handled = self._raw_block(row, rest) or self._reference(row, rest)
        if handled is not None:
            return handled
        end = row + 1 if _ATX_RE.match(rest) else self.paragraph_end(row)
        return self._inline.scan(row, end)

    def _yaml(self, row: int, rest: str) -> "int | None":
        """A metadata block is skipped, not blanked: pandoc reads its
        values as Markdown, so a `nocite` list there is citations."""
        if self.depth or rest.rstrip() != "---" or rest != self.lines[row].text:
            return None
        if row and not is_blank(self.lines[row - 1]):
            return None
        if row + 1 == len(self.lines) or is_blank(self.lines[row + 1]):
            return None
        for end in range(row + 1, len(self.lines)):
            if self.lines[end].text.rstrip() in ("---", "..."):
                return end + 1
        return None

    def _fence(self, row: int) -> "int | None":
        """Code only with its closer: blanking an unclosed fence hid every
        later citation (#945)."""
        end = self.fence_at(row)
        if end is None:
            return None
        if _RAW_TEX_RE.search(self.lines[row].text):
            self.mark_raw_tex(self.offsets[row], self.line_end(end), block=True)
        else:
            self.mark_rows(row, end, code=True)
        return end + 1

    def _container(self, row: int, chars: int, rest: str) -> "int | None":
        if _RULE_RE.match(rest):
            return self._tables.after(row) or row + 1
        if self.depth >= _MAX_DEPTH:
            return None
        if rest.startswith(">"):
            return self._quote(row)
        match = _FOOTNOTE_RE.match(rest)
        if match:
            return self._item(row, chars + match.end(), footnote=True)
        match = _ITEM_RE.match(rest)
        if match:
            example = _EXAMPLE_RE.fullmatch(match.group())
            underlined = row + 1 < len(self.lines) and _UNDERLINE_RE.match(self.lines[row + 1].text)
            if example and not underlined:
                self.found.labels.add(example.group(1) or example.group(2))
            return self._item(row, chars + match.end(), footnote=False)
        return None

    def _quote(self, row: int) -> int:
        """A blockquote: `>`-prefixed lines, plus the lazy lines pandoc
        lets follow a non-blank one, parsed again as their own blocks."""
        inner = [unquote(self.lines[row])]
        end = row + 1
        while end < len(self.lines):
            line = self.lines[end]
            columns, chars = indent(line)
            if columns < 4 and line.text[chars:].startswith(">"):
                inner.append(unquote(line))
            elif not is_blank(line) and not is_blank(self.lines[end - 1]):
                inner.append(line)
            else:
                break
            end += 1
        _Container(inner, self.depth + 1, self.in_item, self.found).scan()
        return end

    def _item(self, row: int, marker_end: int, footnote: bool) -> int:
        """A list item, definition or footnote, with its content column:
        the first non-space after the marker, or one past it when 5+
        spaces open indented code; a footnote's is four. Indented and lazy
        continuation lines belong to the item."""
        line = self.lines[row]
        after = drop(line, marker_end)
        gap, gap_chars = indent(after)
        marker = after.col - line.col
        if footnote:
            column, first = 4, drop(after, gap_chars)
        elif 0 < gap <= 4 and not is_blank(after):
            column, first = marker + gap, drop(after, gap_chars)
        else:
            column, first = marker + 1, dedent(after, 1)
        inner = [first]
        last = row
        for end in range(row + 1, len(self.lines)):
            nxt = self.lines[end]
            if is_blank(nxt):
                continue
            columns, chars = indent(nxt)
            if columns >= column:
                inner.extend(dedent(self.lines[k], column) for k in range(last + 1, end + 1))
            elif end == last + 1 and not _ITEM_RE.match(nxt.text, chars):
                inner.append(nxt)
            else:
                break
            last = end
        _Container(inner, self.depth + 1, True, self.found).scan()
        return last + 1

    def _raw_block(self, row: int, rest: str) -> "int | None":
        """`<pre>`, `<script>`, `<style>`, `<textarea>`: raw to their
        closing tag, as pandoc keeps them. Unclosed, they are prose."""
        match = _RAW_BLOCK_RE.match(rest)
        if not match:
            return None
        tag = match.group(1).lower()
        finder = self._raw_closers.setdefault(
            tag, Finder(self.text, re.compile(rf"</{tag}\s*>", re.IGNORECASE))
        )
        found = finder.find(self.offsets[row])
        if found is None:
            return None
        self.mark(self.offsets[row], found.end(), code=False)
        return self.row_of(found.end() - 1) + 1

    def _reference(self, row: int, rest: str) -> "int | None":
        if not _REFERENCE_RE.match(rest):
            return None
        self.mark_rows(row, row, code=False)
        return row + 1


def _scan(text: str) -> Found:
    found = Found()
    _Container(document_lines(text), 0, False, found).scan()
    return found


def non_prose_spans(text: str, *, code_only: bool = False) -> list[tuple[int, int]]:
    """Every (start, end) offset range of `text` pandoc does not read as
    prose: code, comments, link targets, reference definitions and raw
    HTML blocks -- or, with `code_only`, just the fenced, indented and
    inline code. Ranges never include a newline."""
    return [(start, end) for start, end, code in _scan(text).spans if code or not code_only]


def prose(text: str) -> tuple[str, set[str]]:
    """`blank(text)` and the example-list labels `text` defines, from one
    scan. Only a list-item marker defines a label; elsewhere `(@label)` is
    a citation, and reading it as a definition would hide `@label` (#1021)."""
    found = _scan(text)
    return _blanked(text, [(start, end) for start, end, _ in found.spans]), found.labels


def raw_tex_spans(text: str) -> list[tuple[int, int, bool]]:
    """Every (start, end, block) offset range of `text` that pandoc reads
    as raw LaTeX, in document order: a complete ```` ```{=latex} ```` or
    `{=tex}` fence, opener through closer (`block`), or an inline
    `` `...`{=latex} `` span, attribute included. Never one inside code."""
    return sorted(_scan(text).raw_tex)


def _blanked(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def blank(text: str, *, code_only: bool = False) -> str:
    """`text` with every `non_prose_spans` range replaced by spaces, so
    every offset and every line number is unchanged."""
    return _blanked(text, non_prose_spans(text, code_only=code_only))
