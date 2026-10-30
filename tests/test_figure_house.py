"""The house-vocabulary rules (#1016): `type-below-floor`,
`colour-off-palette`, `tint-outside-band` and `unnamed-pic`.

The paint and type rules run over synthetic drawn figures, so they run
on every host; the colours are the house block's own. The end-to-end
cases under `TestAgainstRealLualatex` compile the fixtures under
tests/fixtures/figure/house/, and every shipped scaffold and exemplar,
and self-skip where TeX is missing.
"""

from pathlib import Path

import pytest

from chitragupta.figure import _check, _house
from chitragupta.figure._colour import mix
from chitragupta.figure._connectors import MM
from chitragupta.review.figure_layout import BBOX_NAME, FigureResult
from chitragupta.review.figure_layout._paint import Paint, TextRun
from tests.conftest import needs_tikz
from tests.figure_drawn_fixtures import drawn, line, node

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "figure" / "house"
TIKZ = REPO_ROOT / "assets" / "tikz"

WHITE = (1.0, 1.0, 1.0)
INK = (0x1A / 255, 0x1A / 255, 0x1A / 255)
FLOW = (0.0, 0x72 / 255, 0xB2 / 255)
FLOW_TEXT = mix(FLOW, INK, 0.95)
BLUE = (0.0, 0.0, 1.0)

# The house block's colours as a figure carries them: inside its region.
BLOCK = (
    "% >>> chitragupta figure style v6 -- copy, do not edit <<<\n"
    "\\definecolor{cgInk}{HTML}{1A1A1A}%\n"
    "\\definecolor{cgFlow}{HTML}{0072B2}%\n"
    "\\definecolor{cgPaper}{HTML}{FAFAF8}%\n"
    "\\colorlet{cgFlowLine}{cgFlow!100!cgInk}\\colorlet{cgFlowText}{cgFlow!95!cgInk}%\n"
    "% >>> end chitragupta figure style <<<\n"
)


def _tint(share):
    return Paint(mix(FLOW, WHITE, share / 100), f"cgFlow!{share}")


def _run(size=12.0, colour=INK, math=False):
    return TextRun(colour, size, False, 5, math)


def _card(name="a", box=(0, 0, 60, 30), **kw):
    kw.setdefault("stroke", Paint(FLOW, "cgFlowLine"))
    return node(name, box, **kw)


def _found(*nodes, lines=(), source=BLOCK):
    figure = drawn(nodes, lines)
    return [(f.rule, f.target, f.measurement) for f in _house.paint_rules(source, figure)]


class TestTypeFloor:
    def test_text_at_the_body_size_is_clean(self):
        assert _house.type_floor(drawn([_card(runs=[_run(12.0)])], [])) == []

    def test_scriptsize_text_fires_with_its_size(self):
        found = _house.type_floor(drawn([_card("parse", runs=[_run(12.0), _run(8.0)])], []))

        assert [(f.rule, f.target, f.measurement) for f in found] == [
            ("type-below-floor", "parse", "8.0pt, floor 12pt")
        ]

    def test_a_subscript_beside_body_text_is_typesetting(self):
        node_ = _card("bm", runs=[_run(12.0), _run(12.0, math=True), _run(8.4, math=True)])

        assert _house.type_floor(drawn([node_], [])) == []

    def test_a_label_all_in_small_math_still_fires(self):
        node_ = _card("x", runs=[_run(8.0, math=True)])

        assert [f.measurement for f in _house.type_floor(drawn([node_], []))] == [
            "8.0pt, floor 12pt"
        ]

    def test_the_smallest_text_run_is_the_one_reported(self):
        node_ = _card("a", runs=[_run(10.95), _run(8.0), _run(12.0)])

        assert [f.measurement for f in _house.type_floor(drawn([node_], []))] == [
            "8.0pt, floor 12pt"
        ]

    def test_a_node_with_no_text_is_not_measured(self):
        assert _house.type_floor(drawn([_card()], [])) == []

    def test_an_unnamed_node_is_named_by_its_centre(self):
        node_ = _card("tikz@f@3", box=(0, 0, 20 * MM, 10 * MM), runs=[_run(6.0)])

        assert [f.target for f in _house.type_floor(drawn([node_], []))] == ["(10.0,5.0)"]


class TestOffPalette:
    def test_house_colours_and_their_tints_are_on_it(self):
        card = _card(fill=_tint(7), runs=[_run(colour=INK), _run(colour=FLOW_TEXT)])
        paper = _card("p", fill=Paint((0xFA / 255, 0xFA / 255, 0xF8 / 255), "cgPaper"))
        badge_text = _card("b", runs=[_run(colour=WHITE)])

        assert _found(card, paper, badge_text) == []

    def test_a_raw_hue_in_a_border_fires_as_written(self):
        assert _found(_card("index", stroke=Paint(BLUE, "blue"))) == [
            ("colour-off-palette", "index", "border blue")
        ]

    def test_a_raw_tint_in_a_fill_fires(self):
        red_tint = Paint(mix((1.0, 0.0, 0.0), WHITE, 0.10), "red!10")

        assert _found(_card("a", fill=red_tint)) == [("colour-off-palette", "a", "fill red!10")]

    def test_an_unwritten_border_is_a_raw_node(self):
        """`\\node[draw]`: the current colour, black."""
        assert _found(_card("a", stroke=Paint((0.0, 0.0, 0.0), ""))) == [
            ("colour-off-palette", "a", "border (current colour)")
        ]

    def test_black_is_not_the_house_ink(self):
        assert _found(_card("a", stroke=Paint((0.0, 0.0, 0.0), "black"))) == [
            ("colour-off-palette", "a", "border black")
        ]

    def test_a_house_shade_is_on_it_whatever_xcolor_rounded(self):
        """xcolor's `cgFlow!95!cgInk` parts from the hex mix by a step."""
        rounded = tuple(min(1.0, channel + 1 / 255) for channel in FLOW_TEXT)

        assert _found(_card("a", stroke=Paint(rounded, "cgFlowText"))) == []

    def test_a_tint_is_on_it_as_xcolor_rounds_it(self):
        """`cgFlow!50` as xcolor logs it, a hex step off the hex mix."""
        assert _found(_card("a", stroke=Paint((0.5, 0.72354, 0.84903), "cgFlow!50"))) == []

    def test_a_hue_darkened_by_hand_is_a_shade_nobody_chose(self):
        dark = Paint(mix(FLOW, INK, 0.45), "cgFlow!45!cgInk")

        assert _found(_card("a", stroke=dark)) == [
            ("colour-off-palette", "a", "border cgFlow!45!cgInk")
        ]

    def test_a_colour_written_through_a_macro_is_read_by_its_value(self):
        """`\\cgPicColour!55` in a pic, `\\c Text` from a `\\foreach`."""
        pic = line((0, 0), (10, 0), stroke=Paint(mix(FLOW, WHITE, 0.55), "\\cgPicColour !55"))
        loop = _card("a", stroke=Paint(BLUE, "\\c Text"))

        assert _found(loop, lines=[pic]) == [("colour-off-palette", "a", "border #0000FF")]

    def test_off_palette_text_is_named_by_its_colour(self):
        assert _found(_card("a", runs=[_run(colour=BLUE), _run(colour=BLUE)])) == [
            ("colour-off-palette", "a", "text #0000FF")
        ]

    def test_a_connector_is_named_by_its_ends(self):
        ends = [_card("a", box=(0, 0, 20, 20)), _card("b", box=(60, 0, 80, 20))]
        raw = line((20, 10), (60, 10), end_tip=True, stroke=Paint(BLUE, "blue"))

        assert _found(*ends, lines=[raw]) == [("colour-off-palette", "a->b", "line blue")]

    def test_each_loose_line_is_named_by_its_first_point(self):
        raw = Paint(BLUE, "blue")
        pieces = [
            line((10 * MM, 0), (20 * MM, 0), stroke=raw),
            line((20 * MM, 0), (20 * MM, 9 * MM), stroke=raw),
        ]

        assert _found(lines=pieces) == [
            ("colour-off-palette", "(10.0,0.0)", "line blue"),
            ("colour-off-palette", "(20.0,0.0)", "line blue"),
        ]

    def test_a_line_with_no_paint_logged_is_skipped(self):
        assert _found(lines=[line((0, 0), (10, 0))]) == []

    def test_one_colour_is_reported_once_per_target(self):
        raw = Paint(BLUE, "blue")
        twice = [line((0, 0), (5, 0), stroke=raw), line((0, 0), (5, 0), stroke=raw)]

        assert len(_found(lines=twice)) == 1


class TestTintBand:
    @pytest.mark.parametrize("share", [6, 11, 12])
    def test_a_tint_inside_the_band_is_clean(self, share):
        assert _found(_card(fill=_tint(share))) == []

    @pytest.mark.parametrize("share", [5, 13, 45])
    def test_a_tint_outside_the_band_fires_with_its_share(self, share):
        assert _found(_card("parse", fill=_tint(share))) == [
            ("tint-outside-band", "parse", f"cgFlow!{share}, band 6 to 12")
        ]

    def test_the_bare_hue_fires(self):
        assert _found(_card("a", fill=Paint(FLOW, "cgFlow"))) == [
            ("tint-outside-band", "a", "cgFlow, band 6 to 12")
        ]

    def test_a_shade_as_a_fill_fires(self):
        assert _found(_card("a", fill=Paint(FLOW_TEXT, "cgFlowText"))) == [
            ("tint-outside-band", "a", "cgFlowText, band 6 to 12")
        ]

    def test_a_tint_written_through_a_macro_is_named_by_hue_and_share(self):
        assert _found(_card("a", fill=Paint(mix(FLOW, WHITE, 0.45), "\\c !45"))) == [
            ("tint-outside-band", "a", "cgFlow!45, band 6 to 12")
        ]

    def test_a_tint_of_a_shade_is_not_a_hue_tint(self):
        assert _found(_card("a", fill=Paint(mix(FLOW_TEXT, WHITE, 0.5), "cgFlowText!50"))) == []

    def test_a_step_badge_is_a_shade_on_purpose(self):
        badge = _card(
            "cgu-1", box=(0, 0, 5.8 * MM, 5.8 * MM), shape="circle", fill=Paint(FLOW_TEXT, "x")
        )

        assert _found(badge) == []

    def test_a_large_circle_is_held_to_the_band(self):
        state = _card("s", box=(0, 0, 18 * MM, 18 * MM), shape="circle", fill=_tint(45))

        assert [f[0] for f in _found(state)] == ["tint-outside-band"]

    def test_an_unframed_node_is_not_a_card(self):
        assert _found(node("t", (0, 0, 10, 10), framed=False, fill=_tint(45))) == []

    def test_white_paper_and_ink_tints_are_not_hues(self):
        ink_tint = Paint(mix(INK, WHITE, 0.30), "cgInk!30")

        assert _found(_card("a", fill=Paint(WHITE, "white")), _card("b", fill=ink_tint)) == []


class TestUnnamedPic:
    WELL = "\\node[cgwell, above=2.5mm of a] (well) {};\n"

    def _pics(self, body):
        return [(f.rule, f.target, f.measurement) for f in _house.unnamed_pics(body)]

    def test_a_pic_in_a_named_well_is_clean(self):
        assert self._pics(self.WELL + "\\pic[cg pic colour=cgFlow] at (well) {cgstore};") == []

    def test_a_pic_at_a_well_anchor_is_still_in_the_well(self):
        assert self._pics(self.WELL + "\\pic at (well.center) {cgdocs};") == []

    def test_a_pic_at_a_coordinate_fires(self):
        assert self._pics("\\pic[cg pic colour=cgAlt] at (0,1.5) {cgstore};") == [
            ("unnamed-pic", "cgstore at (0,1.5)", "not in a named cgwell")
        ]

    def test_a_computed_position_is_read_whole(self):
        assert [f[1] for f in self._pics("\\pic at ($(w)+(0,1)$) {cgstore};")] == [
            "cgstore at ($(w)+(0,1)$)"
        ]

    def test_a_pic_with_no_position_is_at_the_origin(self):
        assert [f[1] for f in self._pics("\\pic {cgchip};")] == ["cgchip at (0,0)"]

    def test_a_pic_at_a_node_that_is_not_a_well_fires(self):
        body = "\\node[cgbox] (a) {A};\n\\pic at (a) {cgshield};"

        assert [f[1] for f in self._pics(body)] == ["cgshield at (a)"]

    def test_a_commented_out_pic_is_not_read(self):
        assert self._pics("% \\pic at (0,0) {cgstore};\n") == []

    def test_the_house_blocks_pic_definitions_are_not_pics(self):
        assert self._pics(BLOCK + "\\tikzset{pics/cgstore/.style={code={}}}") == []

    def test_a_pic_cut_off_before_its_type_is_read_without_one(self):
        assert [f[1] for f in self._pics("\\pic at (0,1)")] == ["pic at (0,1)"]


class TestSourceRules:
    def test_two_accents_and_a_loose_pic_are_both_reported(self):
        source = "\\node[cgkey] (a) {A};\n\\node[cgkey] (b) {B};\n\\pic at (0,1) {cgstore};"

        assert [(f.rule, f.target) for f in _house.source_rules(source)] == [
            ("focal-count", "figure"),
            ("unnamed-pic", "cgstore at (0,1)"),
        ]

    def test_one_accent_is_not_a_finding(self):
        assert _house.source_rules("\\node[cgkey] (a) {A};") == []


class TestHouseCheck:
    def _figure(self, drawn_):
        return FigureResult(
            path=Path("fig.tex"),
            boxes={"a": (0.0, 0.0, 10.0, 10.0), BBOX_NAME: (0.0, 0.0, 300.0, 12.0)},
            input_width=300.0,
            declared=["a"],
            drawn=drawn_,
        )

    def test_without_the_house_block_the_colour_rules_are_not_measured(self):
        figure = self._figure(drawn([_card(stroke=Paint(BLUE, "blue"), runs=[_run(8.0)])], []))

        found, not_measured = _house.house_check("\\begin{tikzpicture}", figure)

        assert [f.rule for f in found] == ["type-below-floor"]
        assert not_measured == [
            ("colour-off-palette", _house.NO_BLOCK),
            ("tint-outside-band", _house.NO_BLOCK),
        ]

    def test_without_drawn_nodes_nothing_is_measured(self):
        found, not_measured = _house.house_check(BLOCK, self._figure(None))

        assert found == []
        assert [rule for rule, _ in not_measured] == list(_house.HOUSE)

    def test_with_the_block_every_rule_runs(self):
        figure = self._figure(drawn([_card(fill=_tint(45))], []))

        found, not_measured = _house.house_check(BLOCK, figure)

        assert [f.rule for f in found] == ["tint-outside-band"]
        assert not_measured == []

    def test_they_are_geometry_rules_of_figure_check(self):
        assert set(_house.HOUSE) <= set(_check.GEOMETRY)

    def test_evaluate_reports_them_with_the_source_rules(self):
        # Too pale rather than too dark, which k1 would also report.
        figure = self._figure(drawn([_card("parse", fill=_tint(3))], []))
        source = BLOCK + "\\begin{tikzpicture}[cg]\n\\pic at (0,1) {cgstore};\n\\end{tikzpicture}"

        findings, _ = _check.evaluate(source, figure, 453.0)

        assert [f.rule for f in findings] == ["tint-outside-band", "unnamed-pic"]

    def test_an_unnamed_pic_is_reported_even_when_nothing_compiled(self):
        figure = FigureResult(path=Path("fig.tex"), failed="! Undefined control sequence.")

        findings, _ = _check.evaluate("\\pic at (0,1) {cgstore};", figure, 453.0)

        assert [f.rule for f in findings] == ["does-not-compile", "unnamed-pic"]


@needs_tikz
class TestAgainstRealLualatex:
    """Each fixture fires exactly its rule; the clean ones fire none of
    #1016's, and nor does any figure this repository ships."""

    @pytest.mark.parametrize(
        ("fixture", "rule"),
        [
            ("scriptsize", "type-below-floor"),
            ("group-small", "type-below-floor"),
            ("off-palette", "colour-off-palette"),
            ("raw-node", "colour-off-palette"),
            ("dark-tint", "tint-outside-band"),
            ("loose-pic", "unnamed-pic"),
            ("member-outside-zone", "node-overlap"),
            ("zones-overlap", "node-overlap"),
            ("title-collision", "node-overlap"),
            ("stranded", "content-protrusion"),
        ],
    )
    def test_the_firing_fixture_fires(self, fixture, rule):
        result = _check.check(FIXTURES / f"{fixture}.tex", _check.DEFAULT_WIDTH_PT)

        assert set(_ours(result)) == {rule}

    @pytest.mark.parametrize("fixture", ["subscript", "well-pic", "two-row-zones", "band-tints"])
    def test_the_clean_fixture_is_clean(self, fixture):
        result = _check.check(FIXTURES / f"{fixture}.tex", _check.DEFAULT_WIDTH_PT)

        assert _ours(result) == []

    @pytest.mark.parametrize(
        "path",
        sorted(
            [p for p in TIKZ.glob("*.tex") if p.stem != "cg-figstyle"]
            + list((TIKZ / "exemplars").glob("*.tex")),
        ),
        ids=lambda p: p.stem,
    )
    def test_no_shipped_figure_breaks_the_house_vocabulary(self, path):
        result = _check.check(path, _check.DEFAULT_WIDTH_PT)

        assert not set(_house.HOUSE) & set(_ours(result))
        assert "unnamed-pic" not in _ours(result)


# The rules these fixtures are about; the twin and size rules, which a
# small fixture trips for its own reasons, are other tests' business.
_OURS = {*_house.HOUSE, "unnamed-pic", "node-overlap", "content-protrusion"}


def _ours(result):
    return [f.rule for f in result.findings if f.rule in _OURS]
