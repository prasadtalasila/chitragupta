"""A shadowed node drawn after an `on background layer` scope (#1111).

Each `cgsoft` shadow declares a fading, which pgf typesets as a picture
of its own; closing it took every layer's box, so the figure's zone
cards went into the fading and never printed. The house block now saves
and restores the layers around a fading. The check is the rendered
page: the same figure with the shadowed node drawn before the scope and
after it must look the same.
"""

import shutil
from pathlib import Path

import pytest

from chitragupta.figure import _look
from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
LAYERED = REPO_ROOT / "assets" / "tikz" / "layered-stack.tex"
CACHE = "  \\node[cgkey, right=of queue] (cache) {cache};\n"
SCOPE_END = "  \\end{scope}\n"
CARDS = "  % Cards go on the background layer"

needs_poppler = pytest.mark.skipif(
    shutil.which("pdftoppm") is None or shutil.which("pdfinfo") is None,
    reason="needs poppler-utils (pdftoppm, pdfinfo)",
)


def _look_of(tmp_path: Path, name: str, source: str) -> bytes:
    folder = tmp_path / name
    folder.mkdir()
    figure = folder / "fig.tex"
    figure.write_text(source, encoding="utf-8")
    return Path(_look.look(figure, folder).png).read_bytes()


@pytest.mark.slow
@needs_tikz
@needs_poppler
def test_a_shadow_after_the_background_scope_keeps_the_zone_cards(tmp_path):
    source = LAYERED.read_text(encoding="utf-8")
    assert source.count(SCOPE_END) == 1 and source.count(CARDS) == 1

    after = _look_of(tmp_path, "after", source.replace(SCOPE_END, SCOPE_END + CACHE))
    before = _look_of(tmp_path, "before", source.replace(CARDS, CACHE + CARDS))

    assert after == before
