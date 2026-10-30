"""#1046: a TikZ library loaded in horizontal mode sets blank width.

A library file's own line ends are spaces. Loaded where a figure is set
in a box, inline, or in a `standalone` preview, they become glue ahead
of the picture: 135pt for the house line on the probe's page (12pt,
LuaLaTeX, the render's fonts), 147pt with `matrix` or `trees` added,
about 30% of the render's 453pt text width. Loaded in the preamble,
they are set in vertical mode and dropped. The `%` ending a figure's
own `\\usetikzlibrary` line cannot help, because the spaces come from
inside the library files.

The documents `figure check` and `figure look` compile load the
figure's libraries in the preamble for this reason. These tests pin both halves
through the real boxed probe: preloaded, every scaffold's box is its
picture; loaded inside the box, it is far wider. Without the second
half, the preload is a line nobody could tell was load-bearing. Both
compile with LuaLaTeX and self-skip where TeX is missing.
"""

from pathlib import Path

import pytest

from chitragupta.review.figure_layout import BBOX_NAME, _probe
from tests.conftest import needs_tikz

TIKZ = Path(__file__).resolve().parent.parent / "assets" / "tikz"
SCAFFOLDS = [
    "pipeline",
    "zoned-spine",
    "branching-tree",
    "hub-and-spoke-network",
    "map",
    "control-loop",
    "layered-stack",
]
# `figure check`'s own threshold: half a point is rounding, not a space.
_STRAY_PT = 0.5
# Well under the 135pt the house line measured on 2026-10-30, and well
# over anything a stray `%`-less line in a figure sets (about 4pt).
_BODY_LOAD_PT = 100.0


def _stray(name: str) -> float:
    """How much wider than its picture the boxed probe sets `name`."""
    measured = _probe.measure(TIKZ / f"{name}.tex", boxed=True)
    x1, _, x2, _ = measured.boxes[BBOX_NAME]
    return measured.input_width - (x2 - x1)


def test_the_scaffold_list_is_every_scaffold():
    on_disk = {path.stem for path in TIKZ.glob("*.tex")} - {"cg-figstyle"}

    assert set(SCAFFOLDS) == on_disk


@needs_tikz
@pytest.mark.parametrize("name", SCAFFOLDS)
class TestStrayWidth:
    def test_preloaded_the_box_is_the_picture(self, name):
        assert _stray(name) <= _STRAY_PT

    def test_loaded_inside_the_box_it_adds_a_blank_band(self, name, monkeypatch):
        # The probe's preload is the one line this removes: the figure's
        # own `\usetikzlibrary` line then loads in the box, as it does in
        # a thesis that sets the figure in `\resizebox` or `\sbox`.
        monkeypatch.setattr(_probe, "libraries_in", lambda source: [])

        assert _stray(name) > _BODY_LOAD_PT
