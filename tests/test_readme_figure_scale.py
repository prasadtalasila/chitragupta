"""Every figure in README.md is shown at close to the size it was drawn at.

github.com shows the README in a column about 830px wide and scales an
image down to fit it. Browser zoom scales the page and the image together,
so a figure drawn far wider than the column keeps its labels smaller than
the body text however far the reader zooms (#1229). The figures were drawn
at 2189px, 1280px and 1160px wide and shown at about 830px, 380px and 760px:
labels of roughly 5px, 4px and 11px beside 16px body text.

The invariant: no README figure is shown at less than three quarters of
its drawn width. The house type in a diagram, the viewer and the terminal
is 12px to 17px, so three quarters keeps every label at about 9px or more.
"""

import re
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"

# github.com's README column, in CSS pixels, at its widest.
COLUMN_PX = 830
SMALLEST_SCALE = 0.75

# A raster image captured at more than one device pixel per CSS pixel. Its
# drawn width is its pixel width divided by this.
PIXEL_DENSITY = {"docs/images/demo-webapp.png": 2}

# Not a figure: the logo's labels are its own lettering, set by height.
NOT_FIGURES = {"docs/logo.svg"}


def _images(text: str) -> "list[tuple[str, str | None]]":
    """Each `<img>`'s src and width attribute, in README order."""
    found = []
    for tag in re.findall(r"<img\b[^>]*>", text, re.DOTALL):
        src = re.search(r'\bsrc="([^"]+)"', tag).group(1)
        width = re.search(r'\bwidth="([^"]+)"', tag)
        found.append((src, width.group(1) if width else None))
    return found


def _drawn_width(path: Path) -> float:
    """The width the figure was drawn at, in CSS pixels."""
    if path.suffix == ".png":
        with path.open("rb") as image:
            pixels = struct.unpack(">I", image.read(24)[16:20])[0]
        return pixels / PIXEL_DENSITY.get(path.relative_to(REPO_ROOT).as_posix(), 1)
    head = path.read_text(encoding="utf-8")[:4000]
    # Mermaid writes width="100%" and the real width as a max-width.
    max_width = re.search(r"max-width:\s*([\d.]+)px", head)
    if max_width:
        return float(max_width.group(1))
    return float(re.search(r'<svg\b[^>]*\bwidth="([\d.]+)"', head).group(1))


def _shown_width(width: "str | None", drawn: float) -> float:
    """The width github.com shows the figure at, in CSS pixels."""
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
    """Guards the regex: an `<img>` reworded out of reach would pass vacuously."""
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
