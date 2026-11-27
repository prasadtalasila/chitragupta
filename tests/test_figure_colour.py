import pytest

from chitragupta.figure._colour import LINE, TEXT, WHITE, hex_code, mix, text_threshold


class TestLargeText:
    def test_body_text_needs_4_5(self):
        assert text_threshold(12.0, bold=True) == TEXT

    def test_large_bold_needs_3(self):
        assert text_threshold(14.4, bold=True) == LINE
        assert text_threshold(14.4, bold=False) == TEXT

    def test_the_boundary_is_in_postscript_points(self):
        assert text_threshold(14.0, bold=True) == TEXT
        assert text_threshold(14.06, bold=True) == LINE
        assert text_threshold(18.07, bold=False) == LINE


class TestHexCode:
    def test_it_writes_what_definecolor_reads(self):
        assert hex_code((0.8353, 0.36864, 0.0)) == "#D55E00"
        assert hex_code(WHITE) == "#FFFFFF"


def test_mix_is_xcolors_share_of_the_first():
    assert mix((1.0, 0.0, 0.0), WHITE, 0.1) == pytest.approx((1.0, 0.9, 0.9))
