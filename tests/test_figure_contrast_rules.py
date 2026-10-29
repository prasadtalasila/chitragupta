"""`k1-stroke` and `k2-text` (#1055), over synthetic drawn figures.

The colours are the house block's hues: `cgAccent` text on its own 10%
tint is 3.4:1 and fails 4.5:1; `cgAux` on white is 2.3:1 and fails
3:1; their `Text` and `Line` shades clear both. The probe's own colours
are checked against a real compile in tests/test_figure_drawn.py.
"""

from chitragupta.figure._colour import mix
from chitragupta.figure._contrast import colour_names, contrast_rules
from chitragupta.review.figure_layout._paint import Paint, TextRun
from tests.figure_drawn_fixtures import drawn, line, node

INK = (0x1A / 255, 0x1A / 255, 0x1A / 255)
ACCENT = (0xD5 / 255, 0x5E / 255, 0.0)
ACCENT_TINT = mix(ACCENT, (1.0, 1.0, 1.0), 0.10)
ACCENT_TEXT = mix(ACCENT, INK, 0.75)
AUX = (0x56 / 255, 0xB4 / 255, 0xE9 / 255)
AUX_TINT = mix(AUX, (1.0, 1.0, 1.0), 0.10)
AUX_LINE = mix(AUX, INK, 0.75)
WHITE = (1.0, 1.0, 1.0)

SOURCE = (
    "\\definecolor{cgInk}{HTML}{1A1A1A}\\definecolor{cgAccent}{HTML}{D55E00}"
    "\\definecolor{cgAux}{HTML}{56B4E9}"
    "\\colorlet{cgAccentText}{cgAccent!75!cgInk}\\colorlet{cgAuxLine}{cgAux!75!cgInk}"
)


def _run(colour, size=12.0, bold=False):
    return TextRun(colour, size, bold, 5)


def _box(name, box=(0, 0, 40, 20), **kw):
    return node(name, box, **kw)


def _findings(*nodes, lines=()):
    return [(f.rule, f.target, f.measurement) for f in contrast_rules(SOURCE, drawn(nodes, lines))]


class TestText:
    def test_accent_text_on_its_own_tint_fails(self):
        found = _findings(
            _box("decide", fill=Paint(ACCENT_TINT, "cgAccent!10"), runs=[_run(ACCENT)])
        )

        assert found == [
            ("k2-text", "decide", "text cgAccent on fill cgAccent!10: 3.42:1, needs 4.5:1")
        ]

    def test_its_text_shade_passes(self):
        assert (
            _findings(_box("decide", fill=Paint(ACCENT_TINT, "x"), runs=[_run(ACCENT_TEXT)])) == []
        )

    def test_large_bold_text_needs_only_3(self):
        """The same colour at 12pt fails: the size is measured, not read
        from `\\large`."""
        large = _box("a", fill=Paint(ACCENT_TINT, "t"), runs=[_run(ACCENT, 14.4, bold=True)])
        body = _box("b", fill=Paint(ACCENT_TINT, "t"), runs=[_run(ACCENT, 12.0, bold=True)])

        assert [f[1] for f in _findings(large, body)] == ["b"]

    def test_one_colour_at_two_sizes_reports_once_at_its_worst(self):
        """The regular run is short by more than the large bold one."""
        found = _findings(
            _box(
                "a",
                runs=[_run(AUX, 18.5), _run(AUX, 12.0), _run(AUX, 12.0, bold=True)],
            )
        )

        assert len(found) == 1 and found[0][2].endswith("needs 4.5:1")

    def test_a_badges_white_digit_on_its_text_fill_passes(self):
        flow_text = mix((0.0, 0x72 / 255, 0xB2 / 255), INK, 0.95)
        assert (
            _findings(_box("cgu-1", fill=Paint(flow_text, "cgFlowText"), runs=[_run(WHITE)])) == []
        )

    def test_an_unnamed_node_is_named_by_its_centre(self):
        found = _findings(_box("cgu-3", box=(0, 0, 28.45, 28.45), runs=[_run(AUX)]))

        assert found[0][1] == "(5.0,5.0)"

    def test_a_node_tikz_named_itself_is_named_by_its_centre(self):
        """An unnamed `fit` is `tikz@f@1` inside TikZ."""
        found = _findings(_box("tikz@f@1", box=(0, 0, 28.45, 28.45), stroke=Paint(AUX, "cgAux")))

        assert found[0][1] == "(5.0,5.0)"

    def test_a_colour_no_source_names_is_shown_as_hex(self):
        found = _findings(_box("a", runs=[_run((0.8, 0.8, 0.8))]))

        assert found[0][2].startswith("text #CCCCCC on white:")


class TestGround:
    def test_an_unfilled_box_in_a_zone_is_measured_on_the_zone(self):
        """cgAccent text clears 3.87:1 on white, under 4.5 either way, but
        the zone's tint is what the reader sees it on."""
        zone = _box("zone", box=(-10, -10, 100, 50), fill=Paint(ACCENT_TINT, "cgAccent!10"))
        found = _findings(zone, _box("a", runs=[_run(ACCENT)]))

        assert found == [
            ("k2-text", "a", "text cgAccent on zone's fill cgAccent!10: 3.42:1, needs 4.5:1")
        ]

    def test_the_innermost_filled_holder_is_the_ground(self):
        """cgAccentText is 2.47:1 on solid cgAux, 5.69:1 on white."""
        outer = _box("outer", box=(-20, -20, 200, 100), fill=Paint(AUX, "cgAux"))
        inner = _box("inner", box=(-10, -10, 100, 50), fill=Paint(WHITE, "white"))
        found = _findings(outer, inner, _box("a", runs=[_run(ACCENT_TEXT)]))

        assert found == []

    def test_a_tag_holds_no_ground(self):
        """An unnamed node is a label, never a card behind anything."""
        tag = _box("cgu-1", box=(-10, -10, 100, 50), fill=Paint(ACCENT, "cgAccent"))
        assert _findings(tag, _box("a", runs=[_run(INK)])) == []


class TestBorder:
    def test_aux_drawn_on_its_own_tint_fails(self):
        found = _findings(_box("a", fill=Paint(AUX_TINT, "cgAux!10"), stroke=Paint(AUX, "cgAux")))

        assert found == [("k1-stroke", "a", "border cgAux on fill cgAux!10: 2.13:1, needs 3:1")]

    def test_its_line_shade_passes(self):
        assert (
            _findings(_box("a", fill=Paint(AUX_TINT, "t"), stroke=Paint(AUX_LINE, "cgAuxLine")))
            == []
        )


class TestBadge:
    def test_a_border_in_its_own_fill_colour_is_not_measured(self):
        """`cgbadge` draws and fills its disc in one Text shade."""
        flow_text = mix((0.0, 0x72 / 255, 0xB2 / 255), INK, 0.95)
        disc = _box(
            "cgu-1", fill=Paint(flow_text, "cgFlowText"), stroke=Paint(flow_text, "cgFlowText")
        )

        assert _findings(disc) == []


class TestWrittenThroughAMacro:
    def test_a_foreach_variable_is_named_by_its_colour(self):
        found = _findings(_box("a", fill=Paint(AUX_TINT, "\\c !10"), stroke=Paint(AUX, "\\c ")))

        assert found[0][2].startswith("border cgAux on fill #EEF8FD:")


class TestConnectors:
    A, B = (0, 0, 20, 20), (60, 0, 80, 20)

    def _figure(self, stroke, *extra, labels=()):
        ends = [_box("a", box=self.A), _box("b", box=self.B)]
        con = line((20, 10), (60, 10), end_tip=True, labels=labels, stroke=stroke)
        return _findings(*ends, *extra, lines=[con])

    def test_an_aux_arrow_on_white_fails(self):
        assert self._figure(Paint(AUX, "cgAux")) == [
            ("k1-stroke", "a->b", "line cgAux on white: 2.31:1, needs 3:1")
        ]

    def test_an_arrow_with_no_written_colour_is_named_from_the_source(self):
        found = self._figure(Paint(AUX, ""))

        assert found[0][2].startswith("line cgAux on white")

    def test_an_arrow_inside_a_zone_is_measured_on_the_zone(self):
        zone = _box("zone", box=(-5, -5, 90, 30), fill=Paint(AUX_TINT, "cgAux!10"))

        assert self._figure(Paint(AUX_LINE, "cgAuxLine"), zone) == []
        assert self._figure(Paint(AUX, "cgAux"), zone)[0][2].startswith(
            "line cgAux on zone's fill cgAux!10:"
        )

    def test_two_subpaths_of_one_connector_report_once(self):
        ends = [_box("a", box=self.A), _box("b", box=self.B)]
        pieces = [line((20, 10), (60, 10), stroke=Paint(AUX, "cgAux")) for _ in range(2)]

        assert len(_findings(*ends, lines=pieces)) == 1

    def test_a_line_from_a_log_without_paint_is_not_measured(self):
        assert self._figure(None) == []

    def test_a_tag_is_named_by_its_connector(self):
        tag = _box("cgu-1", box=(30, 12, 50, 22), runs=[_run(AUX)])

        found = self._figure(Paint(INK, "cgInk"), tag, labels=["cgu-1"])

        assert found == [("k2-text", "tag on a->b", "text cgAux on white: 2.31:1, needs 4.5:1")]


class TestColourNames:
    def test_palette_and_colorlet_shades_are_named(self):
        names = colour_names(SOURCE)

        assert names["#D55E00"] == "cgAccent"
        assert names["#A64D06"] == "cgAccentText"
        assert names["#FFFFFF"] == "white"

    def test_a_colorlet_of_an_unknown_colour_is_skipped(self):
        assert "x" not in colour_names("\\colorlet{x}{red!50}").values()

    def test_a_plain_colorlet_and_a_tint_of_white(self):
        names = colour_names(
            "\\definecolor{a}{HTML}{000000}\\colorlet{b}{a!50}\\colorlet{c}{white}"
        )

        assert names["#808080"] == "b"
        assert names["#FFFFFF"] == "white"
