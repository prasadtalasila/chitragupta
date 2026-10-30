"""The colours `figure check`'s probe reports paths and text in (#1055).

Three more lines of the log `_drawn.py` reads, for k1 and k2's contrast:

- `CGPAINT <index> <stroke> <fill> <stroke-expr>|<fill-expr>`, just
  before path `<index>`'s `CGPATH`: the colours it is stroked and filled
  in, as `r,g,b`, and the `draw=` and `fill=` TikZ was given, as written
  (empty where none was and the path took the current colour).
- `CGTEXT <r,g,b> <size> <bold> <math> <glyphs> <name>`, before a
  node's `CGNODE`: one run of its typeset glyphs sharing a colour, a
  size in pt, a weight (`1` bold) and whether its font is a math font
  (`1`, #1016: a subscript sets at script size on purpose), read from
  the text box itself, so `text=`, `\\textcolor`, `\\color` and a macro
  that expands to one are all seen, and so is a size from a group.
- `CGTEXTCOLOR <text-expr>|<name>`, after its runs: the `text=` it was
  given.

The colours are resolved in TeX, by xcolor, after TikZ has expanded the
styles, `#1` arguments and `\\colorlet`s that spell them in the source.
"""

from dataclasses import dataclass, field

RGB = tuple[float, float, float]


@dataclass(frozen=True)
class Paint:
    """A colour as pgf used it, and as the figure wrote it (`""` where it
    wrote none and the current colour applied)."""

    colour: RGB
    written: str = ""


@dataclass(frozen=True)
class TextRun:
    """Glyphs of one node's text sharing a colour, a size and a weight."""

    colour: RGB
    size_pt: float
    bold: bool
    glyphs: int
    math: bool = False


@dataclass
class Colours:
    """The three lines, gathered as the log is read in order."""

    paints: dict[int, tuple[Paint, Paint]] = field(default_factory=dict)
    runs: dict[str, list[TextRun]] = field(default_factory=dict)
    written: dict[str, str] = field(default_factory=dict)

    def take(self, kind: str, rest: str) -> None:
        if kind == "CGPAINT":
            index, stroke, fill, written = rest.split(None, 3)
            stroke_written, _, fill_written = written.partition("|")
            self.paints[int(index)] = (
                Paint(_rgb(stroke), stroke_written.strip()),
                Paint(_rgb(fill), fill_written.strip()),
            )
        elif kind == "CGTEXT":
            colour, size, bold, math, glyphs, name = rest.split(None, 5)
            run = TextRun(_rgb(colour), float(size), bold == "1", int(glyphs), math == "1")
            self.runs.setdefault(name, []).append(run)
        else:
            written, _, name = rest.partition("|")
            self.written[name] = written.strip()


def frame_paint(
    paint: tuple[Paint, Paint] | None, action: str
) -> tuple[Paint | None, Paint | None]:
    """`(stroke, fill)` of a node's frame: each `None` where the frame was
    not drawn, or not filled, or where the log carried no paint."""
    if paint is None:
        return None, None
    stroke = paint[0] if "draw" in action or "stroke" in action else None
    return stroke, paint[1] if "fill" in action else None


def _rgb(text: str) -> RGB:
    red, green, blue = (float(channel) for channel in text.split(","))
    return (red, green, blue)
