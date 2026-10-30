"""What TikZ drew, as `figure check`'s probe reports it (#1054).

`assets/latex/cg-figure-probe.tex` wraps `\\pgfusepath` and
`\\pgfmultipartnode`, so the compile logs every path pgf used and every
node it made, in canvas coordinates (pt). This reads that log.

**Why the lines come from TeX, not the source**: a spike over the 59
figures in this repository measured 279 lines between two nodes this way
against 218 at best for a source parser, which cannot see a `\\foreach`
body, a `child`, a `pic`, or where `(a.north |- b.south)` lands without
re-implementing TikZ. Here TikZ has already done all of that.

The grammar, one item per line (`\\typeout` per segment, so a long
plotted path never reaches `max_print_line`):

- `CGNODE <wd> <ht> <dp> <shape>/<name>`: a node, as it is made, with
  its text's width, height and depth. TikZ leaves most labels unnamed;
  the hook names them `cgu-<n>`.
- `CGPATH <index> <N|E> <start-tip> <end-tip> <action>`: a path, as it
  is used. `N` is part of a node (its frame), `E` is everything else; the
  tips are `0` or `1`; `<action>` is pgf's own list (`draw,`, `fill,`).
- `CGSEG <index> <op> <x> <y>`: one point of that path. `M`ove, `L`ine,
  `C` (three per Bézier: two supports, then the end), `Z` (close), and
  `R`/`S` (a rectangle's corner and size).
- `CGNB <w> <s> <e> <n> <tx> <ty> <b> <c> <name>`: a node's box, the min
  and max over the points of its four side anchors (#1064), its `text`
  anchor (`- -` where the shape has none), and the two rotation entries
  of its transform, printed at the end of the picture. A quarter turn
  (`rotate=90` or `-90`) is measured: its box is exact, and its text box
  is turned about the `text` anchor. Any other turn is set aside.
- `CGPAINT`, `CGTEXT` and `CGTEXTCOLOR`: the colours paths and text were
  set in (#1055), whose grammar `_paint.py` documents and reads.

**Names come last**, after a fixed count of fields, because a shape
(`circle split`, `regular polygon`) or a node (`(data store)`) may have a
space in its name; split on spaces, it shifted every field after it and
`figure check` crashed (#1054's review). A shape name never holds `/`.

A node is framed when a node path (`N`) after its `CGNODE` line, made
while it was being built, was drawn or filled: the hook logs a node
before building it, so its text box can be read before the node uses it.
Its colours are its **last** such path's: `cgsoft`'s blur shadow is a
score of node paths stroked and filled in greys before the frame.

**A node logged before an `E` path is that path's label.** TikZ makes a
node on a path before it strokes the path, and a `\\node` statement is a
path of its own, whose empty `E` path consumes it -- so a standalone node
is never mistaken for the next line's tag.
"""

import re
from dataclasses import dataclass, field, replace

from chitragupta.review.figure_layout._geometry import Box
from chitragupta.review.figure_layout._paint import Colours, Paint, TextRun, frame_paint

Point = tuple[float, float]

# Points per Bézier piece when a curve is flattened into straight ones.
_CURVE_STEPS = 8

_LINE_RE = re.compile(r"^(CGNODE|CGPATH|CGSEG|CGNB|CGPAINT|CGTEXT|CGTEXTCOLOR) (.*)$", re.MULTILINE)


@dataclass(frozen=True)
class DrawnNode:
    name: str
    shape: str
    box: Box
    # Where the text was set: the `text` anchor plus the text's own
    # width, height and depth. `None` for a shape with no `text` anchor.
    text_box: Box | None
    # Whether a frame was drawn or filled for it. An unframed node that
    # contains others (an undrawn `fit` group) hides nothing; its text
    # box is no help, since `fit` sizes it to the whole group.
    framed: bool = True
    # Turned by its transform other than a quarter turn (`sloped`, a
    # slanted `rotate=`), so its box and text box, read square to the
    # page, are not where it was set.
    rotated: bool = False
    # Its frame's colours (#1055), `None` where it was not filled or not
    # drawn; its text's runs, and the `text=` it was given.
    fill: Paint | None = None
    stroke: Paint | None = None
    runs: tuple[TextRun, ...] = ()
    text_written: str = ""


@dataclass(frozen=True)
class DrawnLine:
    """One stroked subpath that is not part of a node.

    `labels` are the nodes placed on the path it belongs to. A path with
    several subpaths repeats them on each, since which piece a tag sits
    beside is for the geometry to say.
    """

    index: int
    points: tuple[Point, ...]
    curved: bool
    start_tip: bool
    end_tip: bool
    labels: tuple[str, ...]
    # What it was stroked in (#1055); `None` from a log without paint.
    stroke: Paint | None = None


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
    """The log's state as it is read in order: which nodes are waiting
    for the next path to claim them as its labels."""

    paths: dict[int, _Path] = field(default_factory=dict)
    texts: dict[str, tuple[str, float, float, float]] = field(default_factory=dict)
    nodes: dict[str, DrawnNode] = field(default_factory=dict)
    pending: list[str] = field(default_factory=list)
    # The nodes a painted frame was drawn for, and that frame's paths.
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
        elif kind == "CGNB":
            *fields, name = rest.split(None, 8)
            node = _node(name, fields, self.texts, name in self.framed)
            self.nodes[name] = self._coloured(node)
        else:
            self.colours.take(kind, rest)

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
    """A path's open and closed subpaths as lines; rectangles dropped."""
    pieces = _subpaths(path.segments)
    lines = []
    for number, (points, curved) in enumerate(pieces):
        lines.append(
            DrawnLine(
                index=index,
                points=tuple(points),
                curved=curved,
                start_tip=path.start_tip and number == 0,
                end_tip=path.end_tip and number == len(pieces) - 1,
                labels=path.labels,
                stroke=path.paint[0] if path.paint else None,
            )
        )
    return lines


def _subpaths(segments: list[tuple[str, Point]]) -> list[tuple[list[Point], bool]]:
    """`[(points, curved)]`, one per subpath of two points or more."""
    pieces: list[tuple[list[Point], bool]] = []
    points: list[Point] = []
    curved, supports, rectangle = False, [], False
    for op, point in segments:
        if op in ("M", "R"):
            if len(points) > 1 and not rectangle:
                pieces.append((points, curved))
            points, curved, supports, rectangle = [point], False, [], op == "R"
        elif op == "L":
            points.append(point)
        elif op == "Z":
            points.append(points[0])
        elif op == "C":
            supports.append(point)
            if len(supports) == 3:
                points += _bezier(points[-1], supports[0], supports[1], supports[2])
                curved, supports = True, []
    if len(points) > 1 and not rectangle:
        pieces.append((points, curved))
    return pieces


def _bezier(p0: Point, p1: Point, p2: Point, p3: Point) -> list[Point]:
    """A cubic Bézier as `_CURVE_STEPS` straight pieces, `p0` excluded."""
    out = []
    for step in range(1, _CURVE_STEPS + 1):
        t = step / _CURVE_STEPS
        u = 1 - t
        out.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return out
