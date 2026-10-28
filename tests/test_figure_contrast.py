"""The house block's colours clear WCAG 2 contrast (#1047).

The eight `\\definecolor` hex values are fills. Every stroke draws in a
`cg<Hue>Line` shade and every coloured label in a `cg<Hue>Text` shade,
each mixed towards `cgInk`. This file recomputes those shades from the
hex values instead of trusting the shares written in the block, and
checks them over every ground a figure puts them on: white, `cgPaper`,
and every tint the block fills with, of every hue, since a light edge
can cross another hue's zone.

The thresholds are WCAG 2's: 3:1 for a line (non-text contrast) and
4.5:1 for text. A share must also be the *largest* multiple of 5 that
clears, so a shade cannot drift darker than it needs to be and lose its
hue.

Without a toolchain the mixing is assumed to be xcolor's: `A!p!B` is
`p` percent of A plus the rest of B, channel by channel in RGB. The one
TeX test at the bottom checks that assumption against xcolor itself.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
TIKZ = REPO_ROOT / "assets" / "tikz"
BLOCK = TIKZ / "cg-figstyle.tex"
_REGION_END = "% >>> end chitragupta figure style <<<\n"

LINE, TEXT = 3.0, 4.5
WHITE = (1.0, 1.0, 1.0)

_DEFINE_RE = re.compile(r"\\definecolor\{(\w+)\}\{HTML\}\{([0-9A-Fa-f]{6})\}")
_SHADE_RE = re.compile(r"\\colorlet\{(cg\w+?)(Line|Text)\}\{(cg\w+)!(\d+)!cgInk\}")
_TINT_RE = re.compile(r"fill=(#1|cg\w+)!(\d+)")
# A colour key's value, up to the next `,` `]` or `}`. `\textcolor`'s
# first argument is the same thing spelled differently.
_USE_RE = re.compile(r"\b(draw|text)=([^,\]}]+)|\\textcolor\{([^}]+)\}")
_INK_TINT_RE = re.compile(r"cgInk!(\d+)")


def _block() -> str:
    return BLOCK.read_text(encoding="utf-8")


def _palette(text: str) -> dict[str, tuple[float, float, float]]:
    return {
        name: tuple(int(code[i : i + 2], 16) / 255 for i in (0, 2, 4))
        for name, code in _DEFINE_RE.findall(text)
    }


def _shades(text: str) -> dict[tuple[str, str], tuple[str, int]]:
    """`(hue, "Line" | "Text") -> (base colour, share)`, as the block writes them."""
    return {(hue, kind): (base, int(share)) for hue, kind, base, share in _SHADE_RE.findall(text)}


def _mix(one, other, share: float):
    return tuple(share * a + (1 - share) * b for a, b in zip(one, other))


def _luminance(colour) -> float:
    def linear(channel):
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in colour)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other) -> float:
    light, dark = sorted((_luminance(one), _luminance(other)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _hues(text: str) -> list[str]:
    """Every palette name that has derived shades."""
    return sorted({hue for hue, _ in _shades(text)})


def _grounds(text: str) -> list[tuple[float, float, float]]:
    """White, cgPaper, and every tint the block fills with, of every hue.
    A `#1!n` tint is whatever hue a caller passes, so it is every hue."""
    palette = _palette(text)
    shares = {int(share) for _, share in _TINT_RE.findall(text)}
    tints = [_mix(palette[hue], WHITE, share / 100) for hue in _hues(text) for share in shares]
    return [WHITE, palette["cgPaper"], *tints]


def _worst(colour, grounds) -> float:
    return min(contrast(colour, ground) for ground in grounds)


def _largest_share(base, ink, grounds, threshold: float) -> int:
    return max(
        share
        for share in range(0, 101, 5)
        if _worst(_mix(base, ink, share / 100), grounds) >= threshold
    )


def _carriers() -> list[Path]:
    return [path for path in sorted(TIKZ.glob("*.tex")) if path != BLOCK] + sorted(
        (TIKZ / "exemplars").glob("*.tex")
    )


def _uses(text: str) -> list[str]:
    """Every colour a stroke or a label is drawn in, as written."""
    return [(match.group(2) or match.group(3)).strip() for match in _USE_RE.finditer(text)]


def _fill_only(value: str, hues: list[str]) -> bool:
    """`value` names a palette hue, or the bare argument standing for one,
    with no Line or Text suffix: a fill colour used to draw."""
    bare = value.split("!", 1)[0].strip()
    return bare in hues or bare in ("#1", "\\cgPicColour")


class TestTheCalculator:
    """The two numbers WCAG 2 itself states, so a wrong luminance
    formula cannot pass everything below by being uniformly wrong."""

    def test_black_on_white_is_21(self):
        assert round(contrast((0, 0, 0), WHITE), 2) == 21.0

    def test_a_colour_against_itself_is_1(self):
        assert contrast((0.3, 0.5, 0.7), (0.3, 0.5, 0.7)) == pytest.approx(1.0)

    def test_the_v2_aux_border_failed(self):
        """The defect v3 exists for: cgAux drawn on its own tint."""
        aux = _palette(_block())["cgAux"]
        assert contrast(aux, _mix(aux, WHITE, 0.10)) < LINE


class TestTheBlockWasRead:
    """Non-vacuous guards: a regex that stops matching would make every
    check below pass over an empty list."""

    def test_every_hue_and_mute_has_both_shades(self):
        hues = {name for name in _palette(_block()) if name not in ("cgInk", "cgPaper")}
        assert set(_hues(_block())) == hues
        assert {kind for _, kind in _shades(_block())} == {"Line", "Text"}

    def test_there_are_tints_and_uses(self):
        assert len(_grounds(_block())) > 10 and len(_uses(_block())) > 10


@pytest.mark.parametrize("hue", _hues(_block()))
class TestTheDerivedShades:
    def test_line_is_the_largest_share_that_clears_3(self, hue):
        text = _block()
        palette, (base, share) = _palette(text), _shades(text)[(hue, "Line")]
        assert base == hue
        assert share == _largest_share(palette[base], palette["cgInk"], _grounds(text), LINE)

    def test_text_is_the_largest_share_that_clears_4_5(self, hue):
        text = _block()
        palette, (base, share) = _palette(text), _shades(text)[(hue, "Text")]
        assert base == hue
        assert share == _largest_share(palette[base], palette["cgInk"], _grounds(text), TEXT)


class TestEveryStrokeAndLabel:
    """A palette name fills; a Line or Text name draws."""

    @pytest.mark.parametrize("path", [BLOCK, *_carriers()], ids=lambda p: p.stem)
    def test_nothing_draws_in_a_fill_colour(self, path):
        """Except a `pic`'s inner texture strokes, which the block says
        stay tints: the outline is the shape, and it draws in Line."""
        hues = _hues(_block())
        drawn = _uses(path.read_text(encoding="utf-8"))
        assert [
            use for use in drawn if _fill_only(use, hues) and not use.startswith("\\cgPicColour!")
        ] == []

    def test_the_check_sees_a_fill_colour_drawing(self):
        assert _fill_only("cgAux", _hues(_block()))
        assert _fill_only("#1", _hues(_block()))
        assert not _fill_only("cgAuxLine", _hues(_block()))
        assert not _fill_only("#1Text", _hues(_block()))

    def test_every_ink_tint_clears_its_threshold(self):
        """Neutral strokes and labels are `cgInk` tints rather than
        shades, and are held to the same numbers."""
        text = _block()
        palette, grounds = _palette(text), _grounds(text)
        failing = []
        for match in _USE_RE.finditer(text):
            value = (match.group(2) or match.group(3)).strip()
            tint = _INK_TINT_RE.fullmatch(value)
            if tint is None:
                continue
            threshold = LINE if match.group(1) == "draw" else TEXT
            colour = _mix(palette["cgInk"], WHITE, int(tint.group(1)) / 100)
            if _worst(colour, grounds) < threshold:
                failing.append(value)
        assert failing == []


@needs_tikz
def test_xcolor_mixes_the_way_this_file_assumes(tmp_path):
    """Every shade, as xcolor computes it, against this file's `_mix`."""
    text = _block()
    palette, shades = _palette(text), _shades(text)
    names = [f"{hue}{kind}" for hue, kind in shades]
    body = "".join(
        f"\\extractcolorspecs{{{name}}}{{\\cgmodel}}{{\\cgspec}}"
        f"\\typeout{{CGRGB {name} \\cgmodel\\space\\cgspec}}"
        for name in names
    )
    (tmp_path / "probe.tex").write_text(
        "\\documentclass{article}\\usepackage{tikz}\n"
        f"\\input{{{BLOCK}}}\n\\begin{{document}}{body}x\\end{{document}}\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [shutil.which("lualatex"), "-interaction=nonstopmode", "probe.tex"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:]
    found = dict(re.findall(r"CGRGB (\w+) rgb ([\d.,]+)", result.stdout))
    assert set(found) == set(names)
    for (hue, kind), (base, share) in shades.items():
        expected = _mix(palette[base], palette["cgInk"], share / 100)
        actual = tuple(float(part) for part in found[f"{hue}{kind}"].split(","))
        assert actual == pytest.approx(expected, abs=1e-3), f"{hue}{kind}"
