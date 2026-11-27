"""What TikZ drew, as `figure check`'s probe reports it (#1054).

`assets/latex/cg-figure-probe.tex` hooks `\\pgfusepath` and
`\\pgfmultipartnode`, logging every path and node in canvas pt. Read from
TeX, not source: a source parser cannot see `\\foreach`, `child`, `pic`
or `(a.north |- b.south)` without re-implementing TikZ.

Log lines (one `\\typeout` per item, under `max_print_line`):
`CGNODE <wd> <ht> <dp> <shape>/<name>` (unnamed nodes become `cgu-<n>`);
`CGPATH <index> <N|E> <start-tip> <end-tip> <action>` (`N` a node frame);
`CGSEG <index> <op> <x> <y>` (op M, L, C, Z, R/S);
`CGNB <w> <s> <e> <n> <tx> <ty> <b> <c> <name>` (box from four side
anchors, #1064; a quarter turn is measured, other turns set aside);
`CGLW` and `CGTIP` (line width, arrowhead hull, #1113); `CGPAINT`,
`CGTEXT`, `CGTEXTCOLOR` (`_paint.py`). **Names come last** because a
shape or node name may hold spaces (#1054's review crash).

A node is framed when a painted `N` path follows its `CGNODE`; its colours
are the last such path's (`cgsoft`'s shadow paths come first). A node
logged before an `E` path is that path's label; a `\\node` statement's
own empty `E` path consumes it, so it never tags the next line.
"""

import re
from dataclasses import dataclass, field, replace

from chitragupta.review.figure_layout._geometry import Box, Point, subpaths
from chitragupta.review.figure_layout._paint import Colours, Paint, TextRun, frame_paint


_LINE_RE = re.compile(
    r"^(CGNODE|CGPATH|CGSEG|CGNB|CGPAINT|CGTEXT|CGTEXTCOLOR|CGLW|CGTIP) (.*)$", re.MULTILINE
)


@dataclass(frozen=True)
class DrawnNode:
    name: str
    shape: str
    box: Box
    # The `text` anchor plus the text's size; `None` with no `text` anchor.
    text_box: Box | None
    # An unframed node containing others (an undrawn `fit`) hides nothing.
    framed: bool = True
    # Turned other than a quarter turn, so its boxes are not where it was set.
    rotated: bool = False
    # Frame colours (#1055), `None` where not filled or not drawn.
    fill: Paint | None = None
    stroke: Paint | None = None
    runs: tuple[TextRun, ...] = ()
    text_written: str = ""


@dataclass(frozen=True)
class DrawnLine:
    """One stroked subpath that is not part of a node; `labels` repeat on
    each subpath of a path, since the geometry decides which a tag is by.
    """

    index: int
    points: tuple[Point, ...]
    curved: bool
    start_tip: bool
    end_tip: bool
    labels: tuple[str, ...]
    # (#1055); `None` from a log without paint.
    stroke: Paint | None = None
    # (#1113); 0 and none from a log without them.
    width: float = 0.0
    heads: tuple[tuple[Point, ...], ...] = ()


@dataclass
class Drawn:
    nodes: dict[str, DrawnNode] = field(default_factory=dict)
    lines: list[DrawnLine] = field(default_factory=list)


@dataclass
class _Path:
    in_node: bool
    start_tip: bool
    end_tip: bool
    stroked: bool
    painted: bool
    labels: tuple[str, ...]
    segments: list[tuple[str, Point]] = field(default_factory=list)
    paint: tuple[Paint, Paint] | None = None
    action: str = ""
    width: float = 0.0
    heads: dict[int, list[Point]] = field(default_factory=dict)


def parse_drawn(log: str) -> Drawn | None:
    """The drawn figure from a probe log, or `None` where the hook did
    not run (no `CGNODE`, `CGPATH` or `CGNB` line at all)."""
    found = _LINE_RE.findall(log)
    if not found:
        return None
    reader = _Reader()
    for kind, rest in found:
        reader.take(kind, rest)
    drawn = Drawn(nodes=reader.nodes)
    for index, path in reader.paths.items():
        if path.stroked and not path.in_node:
            drawn.lines += _lines(index, path)
    return drawn


@dataclass
class _Reader:
    """The log's state as read in order: which nodes await the next path
    as its labels."""

    paths: dict[int, _Path] = field(default_factory=dict)
    texts: dict[str, tuple[str, float, float, float]] = field(default_factory=dict)
    nodes: dict[str, DrawnNode] = field(default_factory=dict)
    pending: list[str] = field(default_factory=list)
    framed: dict[str, _Path] = field(default_factory=dict)
    colours: Colours = field(default_factory=Colours)

    def take(self, kind: str, rest: str) -> None:
        if kind == "CGNODE":
            *dims, named = rest.split(None, 3)
            shape, name = named.split("/", 1)
            self.texts[name] = (shape, *(_pt(dim) for dim in dims))
            self.pending.append(name)
        elif kind == "CGPATH":
            fields = rest.split()
            path = _path(fields, tuple(self.pending), self.colours.paints.get(int(fields[0])))
            if not path.in_node:
                self.pending = []
            elif path.painted and self.pending:
                self.framed[self.pending[-1]] = path
            self.paths[int(fields[0])] = path
        elif kind == "CGSEG":
            index, op, x, y = rest.split()
            self.paths[int(index)].segments.append((op, (float(x), float(y))))
        elif kind in ("CGLW", "CGTIP"):
            self._ink(kind, rest.split())
        elif kind == "CGNB":
            *fields, name = rest.split(None, 8)
            node = _node(name, fields, self.texts, name in self.framed)
            self.nodes[name] = self._coloured(node)
        else:
            self.colours.take(kind, rest)

    def _ink(self, kind: str, fields: list[str]) -> None:
        """A path's line width, or one point of an arrowhead on it (#1113)."""
        path = self.paths[int(fields[0])]
        if kind == "CGLW":
            path.width = _pt(fields[1])
        else:
            path.heads.setdefault(int(fields[1]), []).append((float(fields[2]), float(fields[3])))

    def _coloured(self, node: DrawnNode) -> DrawnNode:
        """`node` with its frame's paint and its text's runs (#1055)."""
        frame = self.framed.get(node.name)
        stroke, fill = frame_paint(frame.paint, frame.action) if frame else (None, None)
        return replace(
            node,
            fill=fill,
            stroke=stroke,
            runs=tuple(self.colours.runs.get(node.name, ())),
            text_written=self.colours.written.get(node.name, ""),
        )


def _pt(dimension: str) -> float:
    return float(dimension.removesuffix("pt"))


def _path(fields: list[str], labels: tuple[str, ...], paint: tuple[Paint, Paint] | None) -> _Path:
    _, where, start, end, *action = fields
    words = " ".join(action)
    return _Path(
        in_node=where == "N",
        start_tip=start == "1",
        end_tip=end == "1",
        stroked="draw" in words or "stroke" in words,
        painted="draw" in words or "stroke" in words or "fill" in words,
        labels=labels if where == "E" else (),
        paint=paint,
        action=words,
    )


def _node(
    name: str, fields: list[str], texts: dict[str, tuple[str, float, float, float]], framed: bool
) -> DrawnNode:
    w, s, e, n, tx, ty, *turn = fields
    shape, wd, ht, dp = texts.get(name, ("", 0.0, 0.0, 0.0))
    b, c = (float(entry) for entry in turn)
    quarter = _quarter_turn(b, c)
    text_box = None
    if tx != "-":
        x, y = float(tx), float(ty)
        text_box = (x, y - dp, x + wd, y + ht)
        if quarter:
            # pgf maps (x, y) to (a x + c y, b x + d y); a quarter turn has
            # a = d = 0, so the text's corners land at (c y, b x).
            xs = (c * -dp, c * ht)
            ys = (b * 0.0, b * wd)
            text_box = (x + min(xs), y + min(ys), x + max(xs), y + max(ys))
    rotated = (abs(b) > 1e-4 or abs(c) > 1e-4) and not quarter
    box = (float(w), float(s), float(e), float(n))
    return DrawnNode(name, shape, box, text_box, framed, rotated)


def _quarter_turn(b: float, c: float) -> bool:
    """`rotate=90` or `rotate=-90`, unscaled: the turns whose box the
    probe's four side anchors give exactly (#1064)."""
    return abs(abs(b) - 1.0) < 1e-4 and abs(b + c) < 1e-4


def _lines(index: int, path: _Path) -> list[DrawnLine]:
    """A path's open and closed subpaths as lines; rectangles dropped.
    pgf sets a start tip on the first subpath and an end tip on the
    last, so the heads go to the subpaths that carry a tip."""
    pieces = subpaths(path.segments)
    heads = tuple(tuple(points) for points in path.heads.values())
    lines = []
    for number, (points, curved) in enumerate(pieces):
        start_tip = path.start_tip and number == 0
        end_tip = path.end_tip and number == len(pieces) - 1
        lines.append(
            DrawnLine(
                index=index,
                points=tuple(points),
                curved=curved,
                start_tip=start_tip,
                end_tip=end_tip,
                labels=path.labels,
                stroke=path.paint[0] if path.paint else None,
                width=path.width,
                heads=heads if start_tip or end_tip else (),
            )
        )
    return lines
