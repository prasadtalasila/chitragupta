"""chitragupta/review/_digest_runs.py: a verbatim digest read as runs.

The draft format has no markup: copied text is ordinary prose and a
citation ends each copied run (discussion #991). The attribution rule is
that a citation covers every sentence back to the previous citation, or
to the start of the block. These tests pin that rule, and the two
shapes it has to survive: a block that ends in a citation with nothing
after it, and a bracket that only looks like a citation.
"""

from chitragupta.review import _digest_runs as runs_mod

KEY = "shao_analysis_2023"
OTHER = "smith_example_2024"


def test_a_citation_covers_back_to_the_previous_citation():
    text = (
        "# Notes\n\n"
        f"One. Two. Three. [@{KEY}, p. 4-5]\n"
        "A connecting sentence of my own.\n"
        f"Four. [@{OTHER}, p. 12]\n"
    )
    found = runs_mod.runs(text)
    assert [(r.sentences, r.citekeys, r.cited) for r in found] == [
        (("One.", "Two.", "Three."), (KEY,), (4, 5)),
        (("A connecting sentence of my own.", "Four."), (OTHER,), (12, 12)),
    ]
    assert found[0].text == "One. Two. Three."
    assert found[0].words == 3


def test_a_block_ending_in_a_citation_has_no_tail():
    text = f"Copied sentence. [@{KEY}]\n"
    assert [r.citekeys for r in runs_mod.runs(text)] == [(KEY,)]


def test_sentences_after_the_last_citation_are_an_uncited_tail():
    text = f"Copied. [@{KEY}] My own closing thought. And another.\n"
    found = runs_mod.runs(text)
    assert found[1].citekeys == ()
    assert found[1].cited is None
    assert found[1].sentences == ("My own closing thought.", "And another.")


def test_a_block_with_no_citation_is_one_uncited_run():
    found = runs_mod.runs("Only my words here. Two of them.\n")
    assert len(found) == 1 and found[0].citekeys == ()


def test_a_bracket_without_a_citekey_does_not_close_a_run():
    text = f"Shown [see 3] earlier. More [sic] text. [@{KEY}]\n"
    found = runs_mod.runs(text)
    assert len(found) == 1
    assert found[0].sentences == ("Shown [see 3] earlier.", "More [sic] text.")


def test_an_at_sign_in_a_bracket_is_not_a_citation_unless_the_extractor_says_so():
    """`[@ 3]` has the `@` the bracket pattern looks for and no citekey
    pandoc would read; the extractor, not the pattern, decides."""
    found = runs_mod.runs(f"Shown [@ 3] earlier. Copied. [@{KEY}]\n")
    assert [r.sentences for r in found] == [("Shown [@ 3] earlier.", "Copied.")]


def test_a_citation_before_the_full_stop_leaves_no_bare_punctuation_run():
    """`... text [@key].` is pandoc's and the survey's convention; the
    stop after the bracket must not become a one-word uncited run."""
    found = runs_mod.runs(f"Copied sentence [@{KEY}]. Another one [@{OTHER}].\n")
    assert [(r.sentences, r.citekeys) for r in found] == [
        (("Copied sentence",), (KEY,)),
        (("Another one",), (OTHER,)),
    ]


def test_several_citekeys_in_one_bracket_close_one_run():
    found = runs_mod.runs(f"Copied. [@{KEY}; @{OTHER}]\n")
    assert found[0].citekeys == (KEY, OTHER)


def test_a_mid_sentence_citation_closes_the_run_there():
    found = runs_mod.runs(f"The first half [@{KEY}] and the rest.\n")
    assert [r.sentences for r in found] == [("The first half",), ("and the rest.",)]


def test_lines_are_the_drafts_own():
    text = f"# Title\n\nLine three. [@{KEY}]\n\nLine five. [@{OTHER}]\nLine six.\n"
    assert [r.line for r in runs_mod.runs(text)] == [3, 5, 6]


def test_each_sentence_of_a_wrapped_paragraph_keeps_its_own_line():
    """Hard-wrapped Markdown is the normal shape of a draft: a sentence
    that spans a line break is joined with a space, and every sentence
    carries the line it starts on (#496), not the block's first line."""
    text = (
        "# Title\n\n"
        "First sentence here.\n"
        "Second one, continued\n"
        "across lines. Third one.\n"
        f"[@{KEY}]\n"
    )
    (run,) = runs_mod.runs(text)
    assert run.sentences == (
        "First sentence here.",
        "Second one, continued across lines.",
        "Third one.",
    )
    assert run.lines == (3, 4, 5)
    assert run.line == 3


def test_headings_code_and_the_reference_list_are_not_runs():
    text = (
        "# Title\n\n```\nnot [@fake_key_2020] prose\n```\n\n"
        f"Real. [@{KEY}]\n\n## References\n\n[1] Entry.\n"
    )
    assert [r.sentences for r in runs_mod.runs(text)] == [("Real.",)]


class TestCitedPages:
    def test_a_range(self):
        assert runs_mod.cited_pages("[@k, pp. 4-5]") == (4, 5)

    def test_a_single_page(self):
        assert runs_mod.cited_pages("[@k, p. 12]") == (12, 12)

    def test_an_en_dash_and_reversed_order(self):
        assert runs_mod.cited_pages("[@k, p. 9–7]") == (7, 9)

    def test_no_locator(self):
        assert runs_mod.cited_pages("[@k]") is None

    def test_digits_inside_a_citekey_are_not_a_locator(self):
        assert runs_mod.cited_pages("[@page2020web]") is None
        assert runs_mod.cited_pages("[@pages2021x; @p2019]") is None
        assert runs_mod.cited_pages("[@page2020web, p. 7]") == (7, 7)


class TestOwnRuns:
    """#1172: three ways a run is declared the drafter's own words."""

    def test_a_see_prefixed_citation_closes_an_own_run(self):
        found = runs_mod.runs(f"Copied. [@{KEY}] Both agree on this. [see @{KEY}; @{OTHER}]\n")
        assert [(r.sentences, r.own) for r in found] == [
            (("Copied.",), False),
            (("Both agree on this.",), True),
        ]

    def test_see_also_counts_and_case_does_not_matter(self):
        (run,) = runs_mod.runs(f"Mine. [See also @{KEY}]\n")
        assert run.own and run.citekeys == (KEY,)

    def test_an_own_marker_above_a_block_makes_every_run_in_it_own(self):
        text = f"# T\n\n<!-- own: framing -->\nMine. [@{KEY}] Also mine.\n\nCopied. [@{KEY}]\n"
        found = runs_mod.runs(text)
        assert [(r.sentences, r.own, r.line) for r in found] == [
            (("Mine.",), True, 4),
            (("Also mine.",), True, 4),
            (("Copied.",), False, 6),
        ]

    def test_an_own_marker_must_touch_its_block(self):
        text = f"<!-- own: framing -->\n\nCopied. [@{KEY}]\n"
        assert [r.own for r in runs_mod.runs(text)] == [False]

    def test_a_table_row_is_own(self):
        text = f"| Approach | Idea |\n|---|---|\n| Layers | Separate them [@{KEY}] |\n"
        (run,) = runs_mod.runs(text)
        assert run.own and run.citekeys == (KEY,)


class TestContext:
    def test_follows_is_the_previous_runs_keys_in_the_same_block(self):
        text = f"One. [@{KEY}] Two. [@{OTHER}]\n\nThree. [@{KEY}]\n"
        assert [r.follows for r in runs_mod.runs(text)] == [None, (KEY,), None]

    def test_a_block_after_a_math_fence_is_after_math(self):
        text = (
            "Intro. [@k1]\n\n<!-- math -->\n```\nx = 1\n```\n\n"
            f"where x is one. [@{KEY}]\n\nLater. [@{KEY}]\n"
        )
        assert [r.after_math for r in runs_mod.runs(text)] == [False, True, False]

    def test_dollar_and_latex_display_close_count_too(self):
        dollars = f"$$\nx = 1\n$$\n\nwhere x is one. [@{KEY}]\n"
        latex = f"\\[\nx = 1\n\\]\n\nwhere x is one. [@{KEY}]\n"
        assert runs_mod.runs(latex)[-1].after_math is True
        assert runs_mod.runs(dollars)[-1].after_math is True

    def test_a_code_fence_is_not_an_equation(self):
        text = f"Intro.\n\n```\nprint(1)\n```\n\nwhere x is one. [@{KEY}]\n"
        assert runs_mod.runs(text)[-1].after_math is False

    def test_a_fence_at_the_top_of_the_file_is_not_an_equation(self):
        text = f"```\n\n```\n\nwhere x is one. [@{KEY}]\n"
        assert [r.after_math for r in runs_mod.runs(text)] == [False]

    def test_nothing_above_is_not_after_math(self):
        assert runs_mod.runs(f"where x is one. [@{KEY}]\n")[0].after_math is False


def test_shown_figures_reads_the_digests_captions():
    text = (
        f"![Parts of a model: Figure 3.6 of [@{KEY}], p. 74](figures/a.png)\n\n"
        f"![Another, Fig. 2 of [@{OTHER}]](figures/b.png)\n"
    )
    assert runs_mod.shown_figures(text) == {(KEY, "3.6"), (OTHER, "2")}


def test_a_table_rows_citekey_cell_attributes_the_cells_after_it():
    """#1172 review: with the citekey column first, the remaining cells
    used to arrive as an uncited tail and skip the support check."""
    text = f"| Key | Idea |\n|---|---|\n| [@{KEY}] | lumped parameter model |\n"
    (run,) = runs_mod.runs(text)
    assert run.own and run.citekeys == (KEY,)
    assert "lumped parameter model" in run.text


def test_an_uncited_table_row_stays_uncited():
    (run,) = runs_mod.runs("| Key | Idea |\n|---|---|\n| none | an idea |\n")
    assert run.own and run.citekeys == ()
