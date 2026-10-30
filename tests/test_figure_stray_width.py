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
figure's libraries in the preamble for this reason. With the preload,
every scaffold's box is its picture: that half is
`tests/test_figure_check.py`'s scaffold test (no `size-stray`), and
`tests/test_figure_look.py` pins the look's preload. This file pins the
other half through `figure check`'s real boxed probe: without the
preload, the box is far wider, so the preload is a line anyone can tell
is load-bearing. It compiles with LuaLaTeX and self-skips where TeX is
missing.
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
    "comparison",
]
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
def test_a_library_loaded_inside_the_box_adds_a_blank_band(name, monkeypatch):
    # The probe's preload is the one line this removes: the figure's own
    # `\usetikzlibrary` line then loads in the box, as it does in a
    # thesis that sets the figure in `\resizebox` or `\sbox`.
    monkeypatch.setattr(_probe, "libraries_in", lambda source: [])

    assert _stray(name) > _BODY_LOAD_PT
