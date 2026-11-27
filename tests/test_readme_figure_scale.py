import re
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"

COLUMN_PX = 830
SMALLEST_SCALE = 0.75

PIXEL_DENSITY = {"docs/images/demo-webapp.png": 2}

NOT_FIGURES = {"docs/logo.svg"}


def _images(text: str) -> "list[tuple[str, str | None]]":
    found = []
    for tag in re.findall(r"<img\b[^>]*>", text, re.DOTALL):
        src = re.search(r'\bsrc="([^"]+)"', tag).group(1)
        width = re.search(r'\bwidth="([^"]+)"', tag)
        found.append((src, width.group(1) if width else None))
    return found


def _drawn_width(path: Path) -> float:
    if path.suffix == ".png":
        with path.open("rb") as image:
            pixels = struct.unpack(">I", image.read(24)[16:20])[0]
        return pixels / PIXEL_DENSITY.get(path.relative_to(REPO_ROOT).as_posix(), 1)
    head = path.read_text(encoding="utf-8")[:4000]
    max_width = re.search(r"max-width:\s*([\d.]+)px", head)
    if max_width:
        return float(max_width.group(1))
    return float(re.search(r'<svg\b[^>]*\bwidth="([\d.]+)"', head).group(1))


def _shown_width(width: "str | None", drawn: float) -> float:
    if width is None:
        return min(drawn, COLUMN_PX)
    if width.endswith("%"):
        return COLUMN_PX * float(width[:-1]) / 100
    return min(float(width), COLUMN_PX)


FIGURES = [
    (src, width)
    for src, width in _images(README.read_text(encoding="utf-8"))
    if src not in NOT_FIGURES
]


def test_the_readme_has_figures_to_check():
    assert len(FIGURES) >= 3


@pytest.mark.parametrize(("src", "width"), FIGURES, ids=[src for src, _ in FIGURES])
def test_a_readme_figure_is_not_shrunk_below_three_quarters(src, width):
    drawn = _drawn_width(REPO_ROOT / src)
    scale = _shown_width(width, drawn) / drawn
    assert scale >= SMALLEST_SCALE, (
        f"{src} is drawn {drawn:.0f}px wide and shown at {scale:.0%} of that on "
        f"github.com, so its labels are smaller than the README's text. Draw it "
        f"narrower (a top-to-bottom layout, fewer terminal columns, a smaller "
        f"viewport) rather than shrinking it."
    )


@pytest.mark.parametrize(
    ("width", "drawn", "shown"),
    [
        (None, 500, 500),
        (None, 2000, COLUMN_PX),
        ("100%", 2000, COLUMN_PX),
        ("50%", 2000, COLUMN_PX / 2),
        ("380", 1280, 380),
        ("1040", 1040, COLUMN_PX),
    ],
)
def test_shown_width_follows_github_column(width, drawn, shown):
    assert _shown_width(width, drawn) == pytest.approx(shown)
