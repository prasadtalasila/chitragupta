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
    assert [(r.sentences, r.citekeys, r.pages) for r in found] == [
        (("One.", "Two.", "Three."), (KEY,), (4, 5)),
        (("A connecting sentence of my own.", "Four."), (OTHER,), (12, 12)),
    ]
    assert found[0].citation == f"[@{KEY}, p. 4-5]"
    assert found[0].text == "One. Two. Three."
    assert found[0].words == 3


def test_a_block_ending_in_a_citation_has_no_tail():
    text = f"Copied sentence. [@{KEY}]\n"
    assert [r.citekeys for r in runs_mod.runs(text)] == [(KEY,)]


def test_sentences_after_the_last_citation_are_an_uncited_tail():
    text = f"Copied. [@{KEY}] My own closing thought. And another.\n"
    found = runs_mod.runs(text)
    assert found[1].citekeys == ()
    assert found[1].citation is None
    assert found[1].pages is None
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
