"""chitragupta/review/_digest_match.py: is this run really in the source,
and what is each sentence that is not?

Four outcomes per run, in the order the module tries them: found whole
(one span), every sentence found separately (one span, "assembled"),
some sentences found (spans for those, findings for the rest), and a
source that cannot be checked at all. The three finding classes are the
discussion's: `copy-mismatch` for a sentence most of whose words are on
one page, `unquoted-text` for everything else the drafter wrote, and
`unsupported-text` on top of that where the cited source does not
lexically support it, or nothing cites it. The headline is the
unsupported fraction: words in sentences carrying any finding, a
sentence counted once, over all words.
"""

import pytest

from chitragupta import config
from chitragupta.passages import Passage, distinctive
from chitragupta.review import _digest_match as match
from chitragupta.review._digest_runs import Run

KEY = "shao_analysis_2023"

SOURCE_P4 = (
    "Layered twins separate the physical entity from its models. "
    "Each layer exposes one interface to the next."
)
SOURCE_P7 = "Operators can start developing against the interface alone."


def passage(page: int, text: str) -> Passage:
    return Passage(page, distinctive(text), text)


def a_lookup(*passages: Passage, reason: str | None = None):
    calls = []

    def lookup(citekey: str):
        calls.append(citekey)
        return list(passages), reason

    lookup.calls = calls
    return lookup


def a_run(*sentences: str, citekeys=(KEY,), cited=None, line=3) -> Run:
    lines = tuple(range(line, line + len(sentences)))
    return Run(line, lines, tuple(sentences), tuple(citekeys), cited)


def test_a_run_found_whole_is_one_span_and_no_finding():
    checked = match.Checked()
    run = a_run(
        "Layered twins separate the physical entity from its models.",
        "Each layer exposes one interface to the next.",
        cited=(4, 4),
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert checked.findings == []
    assert len(checked.spans) == 1
    span = checked.spans[0]
    assert (span.tier, span.pages, span.note) == ("exact", (4,), None)
    assert checked.words_total == run.words
    assert checked.words_copied == run.words
    assert checked.words_flagged == 0
    assert (checked.unsupported_fraction, checked.copied_fraction) == (0.0, 1.0)


def test_a_page_hint_the_text_is_not_on_becomes_a_note():
    checked = match.Checked()
    run = a_run("Operators can start developing against the interface alone.", cited=(4, 5))
    match.check_run(run, a_lookup(passage(7, SOURCE_P7)), checked)
    assert checked.spans[0].note == "cited p. 4-5, found on p. 7"


def test_sentences_found_in_different_places_are_one_assembled_span():
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Operators can start developing against the interface alone.",
    )
    # A passage between the two, or `locate`'s adjacent-pair window would
    # find the run contiguous and report `exact-pair` -- correctly.
    between = passage(5, "An unrelated paragraph about something else entirely.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4), between, passage(7, SOURCE_P7)), checked)
    assert checked.findings == []
    assert len(checked.spans) == 1
    assert checked.spans[0].pages == (4, 7)
    assert checked.spans[0].tier == "assembled"
    assert checked.spans[0].note == "assembled from 2 places"


def test_an_assembled_span_keeps_the_page_note_and_says_within_for_one_page():
    """Both sentences on one page but not adjacent: the note says so in
    words that make sense for one place, and the page hint's
    disagreement travels with it rather than being lost."""
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Layered twins separate the physical entity from its models.",
        cited=(9, 9),
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    (span,) = checked.spans
    assert span.note == "cited p. 9, found on p. 4; assembled within p. 4"


def test_findings_carry_each_sentences_own_line():
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Pelicans migrate in autumn along the coast.",
        line=10,
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [s.line for s in checked.spans] == [10]
    assert {f.line for f in checked.findings} == {11}


def test_a_sentence_exactly_at_the_mismatch_share_is_a_copy_mismatch():
    """`share < MISMATCH_SHARE` is the drafter's-own side, so a share of
    exactly 0.8 is a mismatch: pinned so a later `<=` cannot slip in."""
    words = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
    on_page = passage(2, words.replace("india juliet", "kilo lima"))
    checked = match.Checked()
    match.check_run(a_run(f"{words}."), a_lookup(on_page), checked)
    assert [f.cls for f in checked.findings] == ["copy-mismatch"]
    assert checked.findings[0].detail["share"] == match.MISMATCH_SHARE


def test_a_nearly_matching_sentence_is_a_copy_mismatch_naming_the_missing_words():
    checked = match.Checked()
    run = a_run("Layered twins separate the physical entity from its blueprints.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["copy-mismatch"]
    finding = checked.findings[0]
    assert finding.detail["page"] == 4
    assert finding.detail["missing"] == ["blueprints"]
    assert finding.detail["share"] >= match.MISMATCH_SHARE
    assert checked.spans == []
    assert checked.words_flagged == run.words
    assert checked.unsupported_fraction == 1.0


def test_the_drafters_own_supported_sentence_is_unquoted_only():
    checked = match.Checked()
    # Mostly the source's words, but below MISMATCH_SHARE: a paraphrase.
    run = a_run("Twins that are layered keep the physical entity apart from models of it.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text"]


def test_an_unsupported_sentence_carries_both_classes_and_is_counted_once():
    checked = match.Checked()
    run = a_run("Pelicans migrate in autumn along the coast.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    # No word of it is on the page, so it is weak at the real default too.
    assert checked.findings[1].detail["support_score"] < config.PROVENANCE_WEAK_SCORE
    assert checked.words_flagged == run.words


def test_an_uncited_tail_is_unquoted_and_unsupported_without_a_lookup():
    checked = match.Checked()
    lookup = a_lookup(passage(4, SOURCE_P4))
    match.check_run(a_run("My own closing thought.", citekeys=()), lookup, checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert lookup.calls == []
    assert checked.findings[0].citekeys == ()


def test_a_mixed_run_keeps_the_found_sentences_as_spans():
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Pelicans migrate in autumn along the coast.",
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [s.text for s in checked.spans] == ["Each layer exposes one interface to the next."]
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert checked.words_copied == 8
    assert checked.words_flagged == 7
    assert checked.words_total == 15
    assert checked.unsupported_fraction == round(7 / 15, 3)


def test_a_source_without_reading_order_is_unverifiable():
    checked = match.Checked()
    page_only = Passage(4, distinctive(SOURCE_P4), None)
    run = a_run("Layered twins separate the physical entity from its models.")
    match.check_run(run, a_lookup(page_only), checked)
    assert checked.spans == [] and checked.findings == []
    assert checked.unverifiable == [
        match.Unverifiable(3, (KEY,), run.words, f"{KEY}: {match._NO_READING_ORDER}")
    ]
    assert checked.words_total == run.words
    assert checked.words_unverifiable == run.words
    assert checked.unverifiable_fraction == 1.0
    assert checked.words_flagged == 0


def test_a_citekey_the_ledger_lacks_carries_the_lookups_reason():
    checked = match.Checked()
    lookup = a_lookup(reason="not in the ledger -- run `python -m chitragupta.corpus sync`")
    match.check_run(a_run("Anything."), lookup, checked)
    assert checked.unverifiable[0].reason.startswith(f"{KEY}: not in the ledger")


def test_two_citekeys_pool_their_passages():
    checked = match.Checked()
    seen = {}

    def lookup(citekey):
        seen[citekey] = True
        return ([passage(4, SOURCE_P4)] if citekey == KEY else [passage(2, SOURCE_P7)]), None

    run = a_run(
        "Operators can start developing against the interface alone.",
        citekeys=(KEY, "smith_example_2024"),
    )
    match.check_run(run, lookup, checked)
    assert set(seen) == {KEY, "smith_example_2024"}
    assert checked.spans[0].pages == (2,)
    assert checked.spans[0].citekeys == (KEY, "smith_example_2024")


def test_a_run_with_one_unreadable_source_is_not_checkable_as_a_whole():
    """`[@a; @b]` where only `a` has reading-ordered passages: matching
    against `a` alone would report text copied from `b` as the drafter's
    own. The run is not checkable, and the reason names `b`."""
    checked = match.Checked()

    def lookup(citekey):
        if citekey == KEY:
            return [passage(4, SOURCE_P4)], None
        return [Passage(1, distinctive(SOURCE_P7), None)], None

    run = a_run(SOURCE_P7, citekeys=(KEY, "smith_example_2024"))
    match.check_run(run, lookup, checked)
    assert checked.spans == [] and checked.findings == []
    (entry,) = checked.unverifiable
    assert entry.citekeys == (KEY, "smith_example_2024")
    assert entry.reason.startswith("smith_example_2024: no reading-ordered passages")
    assert checked.words_unverifiable == run.words


def test_a_finding_outside_the_three_classes_is_refused_at_construction():
    with pytest.raises(ValueError, match="unknown digest class"):
        match.Finding("made-up", 1, "x", ())


def test_an_empty_digest_has_fractions_zero():
    checked = match.Checked()
    assert (
        checked.unsupported_fraction,
        checked.copied_fraction,
        checked.unverifiable_fraction,
    ) == (
        0.0,
        0.0,
        0.0,
    )


class TestPageNote:
    @pytest.mark.parametrize(
        ("cited", "pages", "expected"),
        [
            (None, [4], None),
            ((4, 5), [], None),
            ((4, 5), [5], None),
            ((4, 4), [7], "cited p. 4, found on p. 7"),
            ((4, 5), [7, 8], "cited p. 4-5, found on p. 7, 8"),
        ],
    )
    def test_notes_only_a_disagreement(self, cited, pages, expected):
        assert match.page_note(cited, pages) == expected
