import re
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta.figure._colour import LINE, TEXT, WHITE, contrast
from chitragupta.figure._colour import mix as _mix
from tests.conftest import needs_tikz

REPO_ROOT = Path(__file__).resolve().parent.parent
TIKZ = REPO_ROOT / "assets" / "tikz"
BLOCK = TIKZ / "cg-figstyle.tex"
_REGION_END = "% >>> end chitragupta figure style <<<\n"

_DEFINE_RE = re.compile(r"\\definecolor\{(\w+)\}\{HTML\}\{([0-9A-Fa-f]{6})\}")
_SHADE_RE = re.compile(r"\\colorlet\{(cg\w+?)(Line|Text)\}\{(cg\w+)!(\d+)!cgInk\}")
_TINT_RE = re.compile(r"fill=(#1|cg\w+)!(\d+)")
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
    return {(hue, kind): (base, int(share)) for hue, kind, base, share in _SHADE_RE.findall(text)}


def _hues(text: str) -> list[str]:
    return sorted({hue for hue, _ in _shades(text)})


def _grounds(text: str) -> list[tuple[float, float, float]]:
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
    return [(match.group(2) or match.group(3)).strip() for match in _USE_RE.finditer(text)]


def _fill_only(value: str, hues: list[str]) -> bool:
    bare = value.split("!", 1)[0].strip()
    return bare in hues or bare in ("#1", "\\cgPicColour")


class TestTheCalculator:
    def test_black_on_white_is_21(self):
        assert round(contrast((0, 0, 0), WHITE), 2) == 21.0

    def test_a_colour_against_itself_is_1(self):
        assert contrast((0.3, 0.5, 0.7), (0.3, 0.5, 0.7)) == pytest.approx(1.0)

    def test_the_v2_aux_border_failed(self):
        aux = _palette(_block())["cgAux"]
        assert contrast(aux, _mix(aux, WHITE, 0.10)) < LINE


class TestTheBlockWasRead:
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
    @pytest.mark.parametrize("path", [BLOCK, *_carriers()], ids=lambda p: p.stem)
    def test_nothing_draws_in_a_fill_colour(self, path):
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
