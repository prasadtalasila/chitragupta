from pathlib import Path

import pytest

from chitragupta.review.figure_layout import BBOX_NAME, _probe
from tests.conftest import needs_tikz

TIKZ = Path(__file__).resolve().parent.parent / "assets" / "tikz"
SCAFFOLDS = sorted(path.stem for path in TIKZ.glob("*.tex") if path.stem != "cg-figstyle")
_BODY_LOAD_PT = 100.0


def _stray(name: str) -> float:
    measured = _probe.measure(TIKZ / f"{name}.tex", boxed=True)
    x1, _, x2, _ = measured.boxes[BBOX_NAME]
    return measured.input_width - (x2 - x1)


def test_the_scaffolds_are_found():
    assert "pipeline" in SCAFFOLDS


@pytest.mark.slow
@needs_tikz
@pytest.mark.parametrize("name", SCAFFOLDS)
def test_a_library_loaded_inside_the_box_adds_a_blank_band(name, monkeypatch):
    monkeypatch.setattr(_probe, "libraries_in", lambda source: [])

    assert _stray(name) > _BODY_LOAD_PT
