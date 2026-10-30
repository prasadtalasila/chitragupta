"""The house vocabulary's rules (#1016): a figure that loads the house
block and then writes past it.

- `type-below-floor`: text set smaller than the body. The size is the
  one TeX set (`CGTEXT`), so `\\scriptsize`, a size inherited from a
  group and a macro that expands to one are all seen. A math run is
  exempt, since a subscript sets at script size on purpose, unless the
  node has nothing larger: a label all in math under `\\scriptsize`.
- `colour-off-palette`: a border, fill, text run or line in a colour the
  block does not define, a white tint of one excepted. A framed node
  with no `draw=` colour strokes in the current one, and is the half-
  styled node #1016 called `raw-node-in-styled-figure`.
- `tint-outside-band`: a card filled with a house hue mixed with white
  outside 6 to 12, or solid: the hue itself, or its `Line` or `Text`
  shade. A step badge is a `Text`-shade disc on purpose.
- `unnamed-pic`, from source: a `\\pic` not placed in a named `cgwell`,
  which no rule measures (`node-overlap` sees nodes, not a pic's paths).
- `focal-count` lives here too: the accent is house vocabulary.

**Both colour rules read the colour pgf used**, not the expression: a
`\\foreach` variable (`\\c Text`) or `\\cgPicColour!55` reaches the log
unexpanded, and a colour is what a reader sees. The expression is only
how a finding names it. A path's fill outside a node is not logged per
line, so a raw `\\fill[red]` is not seen. Nothing here needs the nodes
in one frame, so these run where the connector rules do not (several
pictures, `transform canvas`); a line's name there is a best guess.
"""

import re

from chitragupta._tex_comments import strip_comments
from chitragupta.figure._block import _END_RE, _START_RE
from chitragupta.figure._colour import RGB, WHITE, hex_code, mix
from chitragupta.figure._connector_check import NO_DRAWN
from chitragupta.figure._connectors import MM, connectors, shown_as
from chitragupta.figure._contrast import colour_names
from chitragupta.figure._focal import cgkey_nodes, declaration, styled_nodes
from chitragupta.figure._overlap import is_badge
from chitragupta.figure._rules import FIGURE, Finding
from chitragupta.review.figure_layout import Drawn, DrawnNode, FigureResult
from chitragupta.review.figure_layout._paint import Paint

# The rules that need the probe's drawn nodes.
HOUSE = ("type-below-floor", "colour-off-palette", "tint-outside-band")
NO_BLOCK = "the figure carries no house block to read its palette from"

# The probe document's body (`_probe.py`'s `[12pt]`), which is the
# render's; a size TeX rounded to 11.96pt is still the body.
FLOOR_PT = 12.0
_ROUNDING_PT = 0.05
# docs/TIKZ-STYLE.md's tint band, "the band the house block's cards and
# zones use". #1016 said 15; the block's darkest card is `cgWarm!12`.
BAND = (6, 12)
# How far a channel may sit from a house colour or tint and still be it:
# xcolor keeps five decimal places and this module mixes from the
# two-digit hex, so the two part by up to a step of the hex (#1016's
# review found 381 of the 2,100 `cg*!1..100` tints a step off).
_SAME = 1.5 / 255

_PIC_RE = re.compile(r"\\pic\b")
_AT_RE = re.compile(r"\bat\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)")
_WELL_RE = re.compile(r"(?<![\w-])cgwell(?![\w-])")
# A hue is a palette name the block gives a `Text` shade.
_HUE_RE = re.compile(r"\\colorlet\{(\w+)Text\}")


def house_check(source: str, figure: FigureResult) -> tuple[list[Finding], list[tuple[str, str]]]:
    """The three rules that read the probe, or each listed as not
    measured: all of them without drawn nodes, the two colour rules
    without a house block to read the palette from."""
    if figure.drawn is None:
        return [], [(rule, NO_DRAWN) for rule in HOUSE]
    found = type_floor(figure.drawn)
    if _block(source) is None:
        return found, [(rule, NO_BLOCK) for rule in HOUSE[1:]]
    return found + paint_rules(source, figure.drawn), []


def source_rules(source: str) -> list[Finding]:
    """`focal-count` and `unnamed-pic`, which hold whether or not the
    figure compiled."""
    keyed = cgkey_nodes(source)
    found = []
    if len(keyed) > 1:
        found.append(
            Finding("focal-count", FIGURE, f"{len(keyed)} accented nodes: {', '.join(keyed)}")
        )
    return found + unnamed_pics(source)


def type_floor(drawn: Drawn) -> list[Finding]:
    """One finding per node, at its smallest text run below the floor."""
    limit = FLOOR_PT - _ROUNDING_PT
    found = []
    for name, node in drawn.nodes.items():
        sizes = [run.size_pt for run in node.runs]
        low = [run.size_pt for run in node.runs if not run.math and run.size_pt < limit]
        if not low and sizes and max(sizes) < limit:
            low = sizes
        if low:
            measured = f"{min(low):.1f}pt, floor {FLOOR_PT:g}pt"
            found.append(Finding("type-below-floor", shown_as(name, node), measured))
    return found


class _Palette:
    """The block's colours, each standing for every white tint of it."""

    def __init__(self, block: str) -> None:
        self.hues = set(_HUE_RE.findall(block))
        self.colours = [
            (tuple(int(code[i : i + 2], 16) / 255 for i in (1, 3, 5)), name)
            for code, name in colour_names(block).items()
        ]

    def find(self, colour: RGB) -> tuple[str, int] | None:
        """`(name, share)` of the house colour, tinted with white at a
        whole-number share (100 for the colour itself), nearest `colour`
        within xcolor's rounding, or `None`. Nearest, because a grey
        tint of `cgMute` is also near some tint of `cgInk`."""
        near = []
        for rgb, name in self.colours:
            share = _share(rgb, colour)
            tint = mix(rgb, WHITE, share / 100)
            error = max(abs(a - b) for a, b in zip(tint, colour))
            if error <= _SAME:
                near.append((error, name, share))
        if not near:
            return None
        _, name, share = min(near, key=lambda candidate: candidate[0])
        return name, share

    def has(self, colour: RGB) -> bool:
        return self.find(colour) is not None

    def hue(self, colour: RGB) -> tuple[str, int] | None:
        """`(name, share)` where `colour` is a hue or a shade of one, tinted
        or not; `None` for anything else (white, paper, ink)."""
        name, share = self.find(colour) or ("", 0)
        if name in self.hues or name.removesuffix("Line").removesuffix("Text") in self.hues:
            return name, share
        return None


def _share(base: RGB, colour: RGB) -> int:
    """The whole-number share of `base` a white tint at `colour` would
    have, read on the channel `base` sits farthest from white on."""
    reach, channel = max((1 - value, i) for i, value in enumerate(base))
    if reach == 0:
        return 100
    return max(1, min(100, round(100 * (1 - colour[channel]) / reach)))


def paint_rules(source: str, drawn: Drawn) -> list[Finding]:
    """`colour-off-palette` and `tint-outside-band` over every node and
    line the probe drew, each colour once per target."""
    palette = _Palette(_block(source) or "")
    found = []
    for name, node in drawn.nodes.items():
        target = shown_as(name, node)
        found += _node_paint(target, node, palette)
        if node.fill is not None and node.framed and not is_badge(node):
            found += _tint(target, node.fill, palette)
    found += _line_paint(drawn, palette)
    return list(dict.fromkeys(found))


def _node_paint(target: str, node: DrawnNode, palette: _Palette) -> list[Finding]:
    painted = [("border", node.stroke), ("fill", node.fill)]
    found = [
        Finding("colour-off-palette", target, f"{what} {_written(paint)}")
        for what, paint in painted
        if paint is not None and not palette.has(paint.colour)
    ]
    found += [
        Finding("colour-off-palette", target, f"text {hex_code(run.colour)}")
        for run in node.runs
        if not palette.has(run.colour)
    ]
    return found


def _line_paint(drawn: Drawn, palette: _Palette) -> list[Finding]:
    """A connector is named by its ends, any other line by where it
    starts, in mm, as an unnamed node is."""
    named = {id(con.line): con.name for con in connectors(drawn)[0]}
    found = []
    for line in drawn.lines:
        if line.stroke is None or palette.has(line.stroke.colour):
            continue
        x, y = line.points[0]
        target = named.get(id(line)) or f"({x / MM:.1f},{y / MM:.1f})"
        found.append(Finding("colour-off-palette", target, f"line {_written(line.stroke)}"))
    return found


def _tint(target: str, fill: Paint, palette: _Palette) -> list[Finding]:
    hue = palette.hue(fill.colour)
    if hue is None:
        return []
    name, share = hue
    is_hue = name in palette.hues
    if is_hue and BAND[0] <= share <= BAND[1]:
        return []
    if share < 100 and not is_hue:
        return []
    shown = fill.written if _readable(fill) else (name if share == 100 else f"{name}!{share}")
    return [Finding("tint-outside-band", target, f"{shown}, band {BAND[0]} to {BAND[1]}")]


def unnamed_pics(source: str) -> list[Finding]:
    """Every `\\pic` not placed `at` a node the figure declares as a
    `cgwell`, named by its type and where it was put."""
    text = strip_comments(source)
    wells = set(styled_nodes(text, _WELL_RE))
    found = []
    for match in _PIC_RE.finditer(text):
        # Read as a node is: options nested, name and `at` group skipped.
        end = declaration(text, match.end())[2]
        at = _AT_RE.search(text, match.end(), end)
        where = at.group(1).strip() if at else "0,0"
        if where.split(".")[0] in wells:
            continue
        close = text.find("}", end)
        kind = text[end + 1 : close].strip() if text.startswith("{", end) else "pic"
        found.append(Finding("unnamed-pic", f"{kind} at ({where})", "not in a named cgwell"))
    return found


def _written(paint: Paint) -> str:
    """How a finding names a colour: as written, `(current colour)` where
    nothing was, and by its code where a macro wrote it."""
    if not paint.written:
        return "(current colour)"
    return paint.written if _readable(paint) else hex_code(paint.colour)


def _readable(paint: Paint) -> bool:
    return bool(paint.written) and "\\" not in paint.written


def _block(source: str) -> str | None:
    """The figure's house block, markers included, or `None`."""
    start, end = _START_RE.search(source), _END_RE.search(source)
    if start is None or end is None or end.start() < start.start():
        return None
    return source[start.start() : end.end()]
