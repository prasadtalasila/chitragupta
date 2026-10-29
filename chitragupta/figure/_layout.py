"""Which layout a figure is drawn in, and what a typical figure of that
layout measures (#1057).

The layout is the figure's own claim, `% cg-layout: <name>` on a line of
its own, for the reason `% cg-allow:` lives in the figure file: the file
is what travels. It is never inferred from the drawing. A guess would
put a figure beside the wrong reference and read as an answer.

The reference is the `## Reference ranges` table of that layout's file
under the figure-drawer skill's references (#1049), measured from the
layout's scaffold and exemplars. `tests/test_tikz_scaffolds.py`
re-measures every row through this parser, so the numbers `figure check`
prints beside a figure move only when a scaffold or exemplar does.
FIGURE-ROADMAP VI.3: a range describes what the exemplars do, and is
never a cap.
"""

import re
from pathlib import Path
from typing import NamedTuple

from chitragupta import config

# `.claude/` ships in the wheel (pyproject's `include`), so this resolves
# in a checkout and in an install alike.
LAYOUT_DIR: Path = config.shipped(".claude", "skills", "figure-drawer", "references", "layouts")

_LAYOUT_RE = re.compile(r"^[ \t]*%+[ \t]*cg-layout:[ \t]*(?P<name>\S*)", re.MULTILINE)

# A row of a layout file's range table: the source it was measured from,
# then nodes, edges, width, height and slack.
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
    """The first `% cg-layout:` line's name, or `""` where there is none."""
    match = _LAYOUT_RE.search(source)
    return match["name"] if match else ""


def layout_names() -> list[str]:
    """Every layout that has a reference file."""
    return sorted(path.stem for path in LAYOUT_DIR.glob("*.md"))


def range_rows(text: str) -> list[RangeRow]:
    """Every measured row of one layout file's reference-range table."""
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

    Matched against the files present rather than joined into a path, so
    a name from a figure file cannot reach outside the directory."""
    if layout not in layout_names():
        return None
    return range_rows((LAYOUT_DIR / f"{layout}.md").read_text(encoding="utf-8"))


def span(rows: list[RangeRow], column: str) -> tuple[float, float]:
    """The lowest and highest value of `column` across `rows`."""
    values = [getattr(row, column) for row in rows]
    return min(values), max(values)
