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


def a_run(*sentences: str, citekeys=(KEY,), pages=None, line=3) -> Run:
    citation = f"[@{KEY}]" if citekeys else None
    return Run(line, tuple(sentences), tuple(citekeys), citation, pages)


def test_a_run_found_whole_is_one_span_and_no_finding():
    checked = match.Checked()
    run = a_run(
        "Layered twins separate the physical entity from its models.",
        "Each layer exposes one interface to the next.",
        pages=(4, 4),
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
    run = a_run("Operators can start developing against the interface alone.", pages=(4, 5))
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


def test_an_unsupported_sentence_carries_both_classes_and_is_counted_once(monkeypatch):
    monkeypatch.setattr(config, "PROVENANCE_WEAK_SCORE", 0.5)
    checked = match.Checked()
    run = a_run("Pelicans migrate in autumn along the coast.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert checked.findings[1].detail["support_score"] < 0.5
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
        {
            "line": 3,
            "citekeys": [KEY],
            "words": run.words,
            "reason": f"{KEY}: no reading-ordered passages -- only page-level text",
        }
    ]
    assert checked.words_total == run.words
    assert checked.words_unverifiable == run.words
    assert checked.unverifiable_fraction == 1.0
    assert checked.words_flagged == 0


def test_a_citekey_the_ledger_lacks_carries_the_lookups_reason():
    checked = match.Checked()
    lookup = a_lookup(reason="not in the ledger -- run `python -m chitragupta.corpus sync`")
    match.check_run(a_run("Anything."), lookup, checked)
    assert checked.unverifiable[0]["reason"].startswith(f"{KEY}: not in the ledger")


def test_two_citekeys_pool_their_passages():
    checked = match.Checked()
    seen = {}

    def lookup(citekey):
        seen[citekey] = True
        return ([passage(4, SOURCE_P4)] if citekey == KEY else [passage(2, SOURCE_P7)]), None

    run = Run(
        3,
        ("Operators can start developing against the interface alone.",),
        (KEY, "smith_example_2024"),
        f"[@{KEY}; @smith_example_2024]",
        None,
    )
    match.check_run(run, lookup, checked)
    assert set(seen) == {KEY, "smith_example_2024"}
    assert checked.spans[0].pages == (2,)
    assert checked.spans[0].citekeys == (KEY, "smith_example_2024")


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
