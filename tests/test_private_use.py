"""chitragupta/_private_use.py: a private-use character from a source's
text layer, written as a marker a report can render (#1125)."""

import pytest

from chitragupta import _private_use


@pytest.mark.parametrize(
    ("char", "marker"),
    [
        ("\ue000", "[U+E000]"),
        ("\ue230", "[U+E230]"),
        ("\uf8ff", "[U+F8FF]"),
        ("\U000f0000", "[U+F0000]"),
        ("\U0010fffd", "[U+10FFFD]"),
    ],
)
def test_each_private_use_range_is_marked(char, marker):
    assert _private_use.mark(f"a{char}b") == (f"a{marker}b", [marker])


@pytest.mark.parametrize("char", ["\ud7ff", "\uf900", "\U000effff", "é", "→"])
def test_a_character_outside_the_ranges_is_left_alone(char):
    assert _private_use.mark(f"a{char}b") == (f"a{char}b", [])


def test_markers_are_listed_once_each_in_code_point_order():
    text, markers = _private_use.mark("\uf02d \ue230 \uf02d")
    assert text == "[U+F02D] [U+E230] [U+F02D]"
    assert markers == ["[U+E230]", "[U+F02D]"]


def test_the_note_names_every_marker():
    assert _private_use.note(["[U+E230]", "[U+F02D]"]) == (
        "  note: 2 private-use characters no font can set shown as [U+E230], [U+F02D]"
    )


def test_one_marker_reads_in_the_singular():
    assert "1 private-use character no font" in _private_use.note(["[U+E230]"])
