"""The rule pictures in docs/FIGURE-DRAWER.md fire what they say (#1063).

Each row of `docs/images/figure-drawer/connector-rules.tex` and
`contrast-rules.tex` draws one rule twice: on the left so it fires, on
the right so it passes. A node's name carries its panel, `c3bad-a` or
`c3good-a`, so a finding's target says which side it came from; the
one point target (`c7-dangling-tip`) is placed by its x instead. The
pictures are compiled here, so a threshold that moves fails this test
rather than leaving the guide showing a defect the check no longer
reports.
"""

import re
from pathlib import Path

import pytest

from chitragupta.figure import _check
from tests.conftest import needs_tikz

GALLERY = Path(__file__).resolve().parent.parent / "docs" / "images" / "figure-drawer"

PICTURES = {
    "connector-rules": [
        "c1-orthogonal",
        "c2-tag-clearance",
        "c3-coincident",
        "c4-attach",
        "c5-transit",
        "c6-tag-covered",
        "c7-dangling-tip",
    ],
    "contrast-rules": ["k1-stroke", "k2-text"],
}

# The rules the pictures are about. Any other finding (no twin, no
# layout) is about the picture being a doc image, not a draft figure.
_SHOWN = re.compile(r"[ck]\d-")

# Every left panel sits left of this x, in mm; every right panel right.
_COLUMN_MM = 46.0

_POINT_RE = re.compile(r"^\((-?[\d.]+),(-?[\d.]+)\)$")
_PANEL_RE = re.compile(r"\b([ck]\d)(bad|good)-")


def side(target: str) -> tuple[str, str]:
    """`(rule prefix, "bad" or "good")` for a finding's target: from the
    node names in it, or from a point's x for a point target."""
    point = _POINT_RE.match(target)
    if point:
        return "", "bad" if float(point.group(1)) < _COLUMN_MM else "good"
    panels = set(_PANEL_RE.findall(target))
    assert len(panels) == 1, target
    return panels.pop()


def test_a_target_names_its_panel():
    assert side("c3bad-a->c3bad-b+c3bad-c->c3bad-d") == ("c3", "bad")
    assert side("k1good-a") == ("k1", "good")
    assert side("c4bad-b.west") == ("c4", "bad")
    assert side("(16.8,-142.0)") == ("", "bad")
    assert side("(72.0,-142.0)") == ("", "good")


@pytest.fixture(scope="module", params=sorted(PICTURES))
def checked(request):
    path = GALLERY / f"{request.param}.tex"
    return request.param, _check.check(path, _check.DEFAULT_WIDTH_PT)


def _shown(result) -> list[tuple[str, str, str]]:
    """`(rule, panel prefix, side)` for every finding the pictures are
    about. A point target has no prefix; any rule may own it."""
    return [(f.rule, *side(f.target)) for f in result.findings if _SHOWN.match(f.rule)]


@needs_tikz
def test_every_left_panel_fires_its_own_rule_and_no_other(checked):
    """A left panel shows one defect: its own rule fires on it, and no
    other connector or contrast rule does. A point target is c7's."""
    name, result = checked
    fired = {(rule, prefix or "c7") for rule, prefix, where in _shown(result) if where == "bad"}

    assert fired == {(rule, rule[:2]) for rule in PICTURES[name]}


@needs_tikz
def test_no_right_panel_fires_a_connector_or_contrast_rule(checked):
    _, result = checked

    assert [shown for shown in _shown(result) if shown[2] == "good"] == []
