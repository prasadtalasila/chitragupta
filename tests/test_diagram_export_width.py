import re
from pathlib import Path

import pytest

SVG_DIR = Path(__file__).resolve().parent.parent / "docs" / "diagrams" / "svg"
WIDEST_PX = 920

EXPORTS = sorted(SVG_DIR.glob("*.svg"))


def _width(svg: Path) -> float:
    match = re.search(r"max-width:\s*([\d.]+)px", svg.read_text(encoding="utf-8")[:4000])
    assert match, f"{svg.name} carries no max-width; is it still a Mermaid export?"
    return float(match.group(1))


def test_there_are_exports_to_check():
    assert len(EXPORTS) >= 20


@pytest.mark.parametrize("svg", EXPORTS, ids=[svg.stem for svg in EXPORTS])
def test_an_export_is_no_wider_than_the_site_can_show(svg):
    width = _width(svg)
    assert width <= WIDEST_PX, (
        f"{svg.stem} is {width:.0f}px wide; the docs site shows it at "
        f"{690 / width:.0%}, so its labels shrink below readable. Redraw it "
        f"top to bottom with shorter labels, then re-render."
    )
