"""chitragupta/review/_digest_dangling.py: does each run stand on its own?

#1172's sample digest carried all three shapes this module reports: a
run naming "Fig. 5.13" and "Eq. (5.1)" the digest never showed, a `[2]`
left from the source's bibliography, and runs opening on "where" and
"Thus" with nothing before them from the same source.
"""

import pytest

from chitragupta.review._digest_dangling import dangling
from chitragupta.review._digest_runs import Run

KEY = "fitzgerald_engineering_2024"
OTHER = "oakes_case_2024"


def a_run(*sentences, citekeys=(KEY,), own=False, follows=None, after_math=False) -> Run:
    lines = tuple(range(3, 3 + len(sentences)))
    return Run(3, lines, sentences, citekeys, None, own, follows, after_math)


def kinds(run, shown=frozenset()):
    return [(d["kind"], d["match"]) for _, _, d in dangling(run, shown)]


class TestCrossReferences:
    @pytest.mark.parametrize(
        ("sentence", "match"),
        [
            ("This leads to the FSM depicted in Fig. 5.13.", "Fig. 5.13"),
            ("Eq. (5.1) is an instance of the first law.", "Eq. (5.1)"),
            ("Procedures introduced in Sect. 6.4.3 apply.", "Sect. 6.4.3"),
            ("As Chapter 7 shows, the model holds.", "Chapter 7"),
            ("The values are in Table 2.", "Table 2"),
            ("See Figure 3 for the loop.", "Figure 3"),
            ("These loops (recall Section 4.3.2) are solved.", "Section 4.3.2"),
        ],
    )
    def test_a_numbered_item_is_named(self, sentence, match):
        assert ("cross-reference", match) in kinds(a_run(sentence, follows=(KEY,)))

    def test_a_figure_the_digest_shows_is_not_dangling(self):
        run = a_run("The parts are shown in Fig. 3.6.", follows=(KEY,))
        assert kinds(run, frozenset({(KEY, "3.6")})) == []

    def test_a_shown_figure_of_another_source_does_not_excuse_it(self):
        run = a_run("The parts are shown in Fig. 3.6.", follows=(KEY,))
        assert kinds(run, frozenset({(OTHER, "3.6")})) == [("cross-reference", "Fig. 3.6")]

    def test_a_shown_figure_does_not_excuse_an_equation_of_that_number(self):
        run = a_run("As Eq. 3.6 states.", follows=(KEY,))
        assert kinds(run, frozenset({(KEY, "3.6")})) == [("cross-reference", "Eq. 3.6")]

    def test_own_text_may_point_into_the_digest(self):
        """#1172 review: a framing paragraph says how the sections divide
        the topic; "Section 2" there is the digest's own."""
        run = a_run("Section 2 covers heaters and Table 1 compares them.", own=True)
        assert kinds(run) == []

    def test_own_text_still_has_its_reference_markers_read(self):
        assert kinds(a_run("Boxes [2] compare.", own=True)) == [("reference-marker", "[2]")]

    def test_a_word_without_a_number_is_not_a_reference(self):
        assert kinds(a_run("The table and the figure agree.", follows=(KEY,))) == []


class TestReferenceMarkers:
    @pytest.mark.parametrize("marker", ["[2]", "[ 24]", "[3, 5]", "[14–15]"])
    def test_a_bracketed_number_is_named(self, marker):
        run = a_run(f"Organ preservation boxes {marker}.", follows=(KEY,))
        assert kinds(run) == [("reference-marker", marker)]


class TestOpeners:
    @pytest.mark.parametrize("word", ["where", "Thus", "This", "Finally", "These"])
    def test_a_run_opening_its_paragraph_on_an_anaphor_dangles(self, word):
        run = a_run(f"{word} the heater warms the box.")
        assert kinds(run) == [("opener", word)]

    def test_after_another_sources_run_it_still_dangles(self):
        run = a_run("Thus the model is a hybrid.", follows=(OTHER,))
        assert kinds(run) == [("opener", "Thus")]

    def test_after_an_own_sentence_citing_the_same_source_is_fine(self):
        """#1172 review: the skill's own shape, a `see` sentence naming
        both papers and then a run from one of them."""
        assert kinds(a_run("Then the box cools.", follows=(OTHER, KEY))) == []

    def test_continuing_the_same_source_is_fine(self):
        assert kinds(a_run("Thus the model is a hybrid.", follows=(KEY,))) == []

    def test_a_paragraph_after_a_displayed_equation_may_open_on_where(self):
        assert kinds(a_run("where T_h is the heater temperature.", after_math=True)) == []

    def test_after_math_does_not_excuse_a_run_mid_paragraph(self):
        run = a_run("where T_h is the heater temperature.", follows=(OTHER,), after_math=True)
        assert kinds(run) == [("opener", "where")]

    def test_leading_punctuation_is_skipped(self):
        assert kinds(a_run("(Thus) the box cools.")) == [("opener", "Thus")]

    def test_an_ordinary_opening_word_is_fine(self):
        assert kinds(a_run("The incubator keeps the tempeh warm.")) == []

    def test_a_sentence_with_no_word_is_fine(self):
        assert kinds(a_run("37.5 degrees.")) == []

    def test_own_and_uncited_runs_are_not_read_for_openers(self):
        assert kinds(a_run("This holds in both.", own=True)) == []
        assert kinds(a_run("This holds in both.", citekeys=())) == []

    def test_only_the_first_sentence_is_an_opener(self):
        run = a_run("The heater warms.", "Thus the box warms.")
        assert kinds(run) == []

    def test_the_finding_names_its_own_line_and_sentence(self):
        run = a_run("The heater warms.", "See Fig. 2 for it.")
        assert dangling(run, frozenset())[0][:2] == (4, "See Fig. 2 for it.")
