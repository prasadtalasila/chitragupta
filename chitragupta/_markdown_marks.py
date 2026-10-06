"""What `_markdown_inert`'s block scan records, and where it records it.

Split out of `_markdown_inert` (#1021) at the boundary the class already
had: its "marking" half, which turns a container's own offsets back
into the document's, and the record it writes into. The "blocks" half,
which decides what to mark, stays there. Standard library only, like
`citation_gate` itself.
"""

import bisect
from dataclasses import dataclass, field

from chitragupta._markdown_lines import Line


@dataclass
class Found:
    """What one scan of a document found, shared by every container in it.

    `spans` are (start, end, code) document offsets pandoc does not read
    as prose, `code` saying whether code-only callers blank them too.
    `labels` are the example-list labels the document defines.
    """

    spans: list = field(default_factory=list)
    labels: set = field(default_factory=set)


class ContainerText:
    """One container's lines, joined, and the marking done in its offsets."""

    def __init__(self, lines: list[Line], found: Found) -> None:
        self.lines = lines
        self.found = found
        self.text = "\n".join(line.text for line in lines)
        self.offsets = []
        pos = 0
        for line in lines:
            self.offsets.append(pos)
            pos += len(line.text) + 1

    def row_of(self, pos: int) -> int:
        return bisect.bisect_right(self.offsets, pos) - 1

    def line_end(self, row: int) -> int:
        return self.offsets[row] + len(self.lines[row].text)

    def mark(self, start: int, end: int, *, code: bool) -> None:
        """Blank container text [start, end), line by line; `code` says
        whether `_blank_code`'s code-only callers blank it too."""
        row = self.row_of(start)
        while start < end:
            stop = min(end, self.line_end(row))
            if stop > start:
                base = self.lines[row].start - self.offsets[row]
                self.found.spans.append((base + start, base + stop, code))
            row += 1
            if row == len(self.lines):
                break
            start = self.offsets[row]

    def mark_rows(self, first: int, last: int, *, code: bool) -> None:
        for row in range(first, last + 1):
            line = self.lines[row]
            self.found.spans.append((line.start, line.start + len(line.text), code))
