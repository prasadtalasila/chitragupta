"""The colours `figure check`'s probe reports paths and text in (#1055).

Three log lines `_drawn.py` reads, for k1 and k2's contrast: `CGPAINT`
(a path's stroke and fill as `r,g,b`, plus the `draw=`/`fill=` as
written), `CGTEXT` (a run of a node's glyphs: colour, size, bold, math
font -- #1016, a subscript is small on purpose) and `CGTEXTCOLOR`.
Colours are resolved in TeX by xcolor after TikZ expanded the styles, so
`\\textcolor`, `\\colorlet` and macros are all seen.
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
