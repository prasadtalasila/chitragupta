"""Which layout a figure is drawn in, and what a typical figure of that
layout measures (#1057).

The layout is the figure's own `% cg-layout: <name>` line, never inferred: a
guess would compare against the wrong reference. Ranges come from the
figure-drawer skill's layout files (#1049), re-measured by
`tests/test_tikz_scaffolds.py`. A range describes the exemplars and is never
a cap (FIGURE-ROADMAP VI.3).
"""

import re
from pathlib import Path
from typing import NamedTuple

from chitragupta import config

# `.claude/` ships in the wheel (pyproject's `include`), so this resolves
# in a checkout and in an install alike.
LAYOUT_DIR: Path = config.shipped(".claude", "skills", "figure-drawer", "references", "layouts")

_LAYOUT_RE = re.compile(r"^[ \t]*%+[ \t]*cg-layout:[ \t]*(?P<name>\S*)", re.MULTILINE)

# A range-table row: source, then nodes, edges, width, height and slack.
_RANGE_ROW_RE = re.compile(
    r"^\| `(?P<source>assets/tikz/[\w/-]+\.tex)` \| (?P<nodes>\d+) \| (?P<edges>\d+) \| "
    r"(?P<width>[\d.]+) \| (?P<height>[\d.]+) \| (?P<slack>[\d.]+) \|$",
    re.MULTILINE,
)


class RangeRow(NamedTuple):
    source: str
    nodes: int
    edges: int
    width: float
    height: float
    slack: float


def declared_layout(source: str) -> str:
    match = _LAYOUT_RE.search(source)
    return match["name"] if match else ""


def layout_names() -> list[str]:
    return sorted(path.stem for path in LAYOUT_DIR.glob("*.md"))


def range_rows(text: str) -> list[RangeRow]:
    return [
        RangeRow(
            m["source"],
            int(m["nodes"]),
            int(m["edges"]),
            float(m["width"]),
            float(m["height"]),
            float(m["slack"]),
        )
        for m in _RANGE_ROW_RE.finditer(text)
    ]


def reference(layout: str) -> list[RangeRow] | None:
    """`layout`'s rows, or `None` where it has no reference file.

    Matched against present files, not joined into a path, so a figure's name
    cannot reach outside the directory."""
    if layout not in layout_names():
        return None
    return range_rows((LAYOUT_DIR / f"{layout}.md").read_text(encoding="utf-8"))


def span(rows: list[RangeRow], column: str) -> tuple[float, float]:
    values = [getattr(row, column) for row in rows]
    return min(values), max(values)
