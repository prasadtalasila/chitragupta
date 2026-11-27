import shutil

import pytest

from chitragupta import style_check, style_quotes


def _finding(line, start, end, check="Microsoft.Wordiness"):
    return {"Check": check, "Line": line, "Span": [start, end], "Match": "x"}


def _kept(text, *findings):
    return style_quotes.drop_quoted(list(findings), text)


def test_a_finding_inside_straight_quotes_is_dropped():
    text = 'A study says "we need it in order to scale" [@a].\n'
    start = text.index("in order to") + 1
    assert _kept(text, _finding(1, start, start + 10)) == []


def test_a_finding_inside_curly_quotes_is_dropped():
    text = "A study says \u201cwe need it in order to scale\u201d [@a].\n"
    start = text.index("in order to") + 1
    assert _kept(text, _finding(1, start, start + 10)) == []


def test_a_finding_inside_latex_quotes_is_dropped():
    text = "A study says ``it's what we need in order to scale'' \\citep{a}.\n"
    start = text.index("in order to") + 1
    assert _kept(text, _finding(1, start, start + 10)) == []


def test_a_quote_wrapped_over_two_lines_still_counts():
    text = (
        'A study says "the coupling of such models\nrequires a standard in order to ensure it".\n'
    )
    start = "requires a standard in order to".index("in order to") + 1
    assert _kept(text, _finding(2, start, start + 10)) == []


def test_the_same_words_outside_the_quote_are_kept():
    text = 'We wrote this in order to test "a quote".\n'
    finding = _finding(1, 15, 25)
    assert _kept(text, finding) == [finding]


def test_a_finding_that_runs_past_the_closing_quote_is_kept():
    text = 'It was "not only fast" but also cheap.\n'
    finding = _finding(1, 9, len('It was "not only fast" but also cheap'))
    assert _kept(text, finding) == [finding]


def test_an_unclosed_quote_does_not_reach_the_next_paragraph():
    text = 'He said "this never closes.\n\nWe wrote this in order to test it.\n'
    start = text.split("\n")[2].index("in order to") + 1
    finding = _finding(3, start, start + 10)
    assert _kept(text, finding) == [finding]


def test_one_character_quotations_do_not_swallow_the_words_between():
    text = 'The "A" variant was built in order to scale, unlike the "B" variant.\n'
    start = text.index("in order to") + 1
    finding = _finding(1, start, start + 10)
    assert _kept(text, finding) == [finding]


def test_a_finding_on_the_second_backtick_of_a_latex_quote_is_kept():
    text = "So ``it holds'' here.\n"
    finding = _finding(1, 5, 9)
    assert _kept(text, finding) == [finding]


def test_an_empty_quotation_does_not_swallow_the_words_after_it():
    text = 'Set it to "" and run it in order to test "a quote".\n'
    start = text.index("in order to") + 1
    finding = _finding(1, start, start + 10)
    assert _kept(text, finding) == [finding]


def test_an_inch_mark_does_not_open_a_quotation():
    text = 'A 6" pipe was used in order to test it. "Short."\n'
    start = text.index("in order to") + 1
    finding = _finding(1, start, start + 10)
    assert _kept(text, finding) == [finding]


def test_an_unclosed_latex_quote_does_not_reach_the_next_paragraph():
    text = "He said ``this never closes.\n\nWe wrote it in order to test ''.\n"
    start = text.split("\n")[2].index("in order to") + 1
    finding = _finding(3, start, start + 10)
    assert _kept(text, finding) == [finding]


def test_the_acronyms_rule_is_never_dropped():
    text = 'It is "a digital twin (DT) of the asset".\n'
    start = text.index("DT") + 1
    finding = _finding(1, start, start + 1, check="chitragupta.Acronyms")
    assert _kept(text, finding) == [finding]


def test_a_finding_on_a_line_past_the_text_is_kept():
    finding = _finding(9, 1, 2)
    assert _kept('"a quote"\n', finding) == [finding]


def test_a_finding_without_a_position_is_kept():
    finding = {"Check": "proselint.Very", "Match": "very"}
    assert _kept('"very"\n', finding) == [finding]


@pytest.mark.skipif(shutil.which("vale") is None, reason="vale not installed")
def test_draft_style_reports_the_draft_and_not_its_source(tmp_path):
    draft = tmp_path / "q.md"
    draft.write_text(
        'We built it in order to test. A study adds that "the coupling\n'
        'requires a standard in order to ensure interoperability" [@a].\n',
        encoding="utf-8",
    )
    found = style_check.check(draft, override="en-GB", propose=False)["findings"]
    wordy = [f for f in found if f["rule"] == "Microsoft.Wordiness"]
    assert [(f["line"], f["count"]) for f in wordy] == [(1, 1)]
