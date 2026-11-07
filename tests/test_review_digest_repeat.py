"""chitragupta/review/_digest_repeat.py: is a passage copied twice?

#1172's dogfood draft carried one source's heat-balance equations and
their symbol definitions in three sections, every copy verified against
the source, and no check said so. These pin the comparison: per
sentence, per citekey, flattened the way every match is, and only above
a length a stock phrase does not reach.
"""

from chitragupta.review._digest_model import Span
from chitragupta.review._digest_repeat import MIN_CHARS, repeats

KEY = "fitzgerald_engineering_2024"
OTHER = "carreira_foundations_2020"
DEFINITION = "where T_h is the temperature of the heater, measured in degrees Celsius."
LATER = "The controller switches the heater on below the lower limit."


def span(line: int, text: str, citekeys=(KEY,)) -> Span:
    return Span(line, tuple(citekeys), text, "exact", (114,), None, None)


def test_a_sentence_copied_again_from_the_same_source_is_reported_on_the_later_copy():
    found = repeats([span(10, f"{DEFINITION} {LATER}"), span(40, DEFINITION)])
    assert [(f.cls, f.line, f.text, f.detail) for f in found] == [
        ("repeated-text", 40, DEFINITION, {"first_line": 10})
    ]


def test_typography_does_not_hide_a_repeat():
    """The two copies were cleaned differently; the source's words are
    the same, so the flattened stream is."""
    respaced = DEFINITION.replace("T_h", "𝑇 ℎ").replace(", measured", " , measured")
    assert len(repeats([span(10, DEFINITION), span(40, respaced)])) == 1


def test_the_same_words_from_another_source_are_not_a_repeat():
    assert repeats([span(10, DEFINITION), span(40, DEFINITION, citekeys=(OTHER,))]) == []


def test_a_short_stock_sentence_is_not_a_repeat():
    short = "Thus the box cools."
    assert len(short) < MIN_CHARS
    assert repeats([span(10, short), span(40, short)]) == []


def test_a_sentence_repeated_inside_one_span_is_not_reported():
    assert repeats([span(10, f"{DEFINITION} {DEFINITION}")]) == []


def test_a_third_copy_names_the_first():
    found = repeats([span(10, DEFINITION), span(40, DEFINITION), span(70, DEFINITION)])
    assert [(f.line, f.detail["first_line"]) for f in found] == [(40, 10), (70, 10)]


def test_one_finding_per_sentence_however_many_keys_its_bracket_names():
    both = (KEY, OTHER)
    found = repeats([span(10, DEFINITION, both), span(40, DEFINITION, both)])
    assert len(found) == 1
