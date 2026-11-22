"""chitragupta/retrieval_spelling.py: opt-in spelling correction (#1232).

The rules are pinned against a fixed vocabulary, so each test names the
word counts it depends on; only the `vocabulary` tests build one from a
real ledger. Two properties carry the file. **Off means off**: nothing is
corrected and no vocabulary is built. And **a word the corpus has seen is
never touched**, however rare: a correction exists for words that would
otherwise score zero everywhere.
"""

import pytest

from chitragupta import config, ledger, retrieval, retrieval_cache, retrieval_spelling
from chitragupta.retrieval_spelling import correct, one_slip_variants

from tests.conftest import add_citable

VOCAB = {
    "structural": 9,
    "structure": 4,
    "ageing": 3,
    "being": 40,
    "architecutre": 1,
    "simulation": 30,
    "where": 50,
    "ginger": 3,
    "abcde": 3,
    "abcdf": 3,
}
NONE: frozenset[str] = frozenset()


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(config, "SPELLING_CORRECTION", True)
    monkeypatch.setattr(retrieval_spelling, "vocabulary", lambda _tokenize_item: dict(VOCAB))


class TestOffIsStructural:
    def test_the_shipped_default_is_off(self):
        """Off until a bench shows it helps, and until existing dossiers'
        drift baselines have a plan: `dossier status` re-ranks every
        recorded query, so turning this on moves rankings."""
        assert config.SPELLING_CORRECTION is False

    def test_off_never_builds_a_vocabulary(self, monkeypatch):
        monkeypatch.setattr(config, "SPELLING_CORRECTION", False)
        monkeypatch.setattr(retrieval_spelling, "vocabulary", lambda _: pytest.fail("built"))
        assert correct(["strucutral"], None, NONE) == []

    def test_a_query_with_nothing_eligible_builds_no_vocabulary(self, monkeypatch):
        monkeypatch.setattr(config, "SPELLING_CORRECTION", True)
        monkeypatch.setattr(retrieval_spelling, "vocabulary", lambda _: pytest.fail("built"))
        assert correct(["dt", "twin", "iso23247"], None, NONE) == []


class TestWhatIsCorrected:
    def test_an_unseen_typo_gains_its_corpus_spelling(self, on):
        assert correct(["strucutral", "health"], None, NONE) == [("strucutral", "structural")]

    def test_a_word_in_one_paper_is_never_corrected(self, on):
        assert correct(["architecutre"], None, NONE) == []

    def test_a_word_in_one_paper_is_never_a_target(self, on):
        assert correct(["architecure"], None, NONE) == []

    def test_under_five_characters_is_never_corrected(self, on):
        assert correct(["beng"], None, NONE) == []

    def test_two_slips_away_is_not_corrected(self, on):
        assert correct(["strcutrul"], None, NONE) == []

    def test_a_token_with_a_digit_is_never_corrected(self, on):
        assert correct(["iso23247", "simul4tion"], None, NONE) == []

    def test_an_interrogative_is_never_a_target(self, on):
        """`_query_terms` drops these on purpose; a correction must not
        add one back."""
        assert correct(["wherre"], None, frozenset({"where"})) == []

    def test_a_non_ascii_fragment_is_treated_as_a_word(self, on):
        """`Schrödinger` tokenizes to `schr` and `dinger`. The fragment is
        indistinguishable from a typed word, so it is corrected like one:
        accepted, and announced like any other correction."""
        assert correct(["dinger"], None, NONE) == [("dinger", "ginger")]


class TestWhichCorrection:
    def test_the_word_in_most_papers_wins(self, on):
        """`aeing` is one slip from both `ageing` and `being`; nothing but
        context could tell them apart, and the commoner word is the
        better guess."""
        assert correct(["aeing"], None, NONE) == [("aeing", "being")]

    def test_a_tie_goes_to_the_alphabetically_first(self, on):
        assert correct(["abcdx"], None, NONE) == [("abcdx", "abcde")]

    def test_nothing_is_added_when_the_correction_was_typed(self, on):
        assert correct(["strucutral", "structural"], None, NONE) == []

    def test_the_same_typo_twice_adds_once(self, on):
        assert correct(["strucutral", "strucutral"], None, NONE) == [("strucutral", "structural")]

    def test_two_typos_of_one_word_add_it_once(self, on):
        assert correct(["strucutral", "structurl"], None, NONE) == [("strucutral", "structural")]


@pytest.mark.parametrize(
    ("typed", "word", "expected"),
    [
        ("acorss", "across", True),  # adjacent swap
        ("acorss", "actors", False),
        ("abert", "alert", True),  # substitution
        ("strctural", "structural", True),  # a letter missing from the typo
        ("structurral", "structural", True),  # a letter extra in the typo
        ("strcutrul", "structural", False),  # two slips
    ],
)
def test_one_slip_variants(typed, word, expected):
    assert (word in one_slip_variants(typed)) is expected


class TestVocabulary:
    def test_it_counts_papers_not_occurrences(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Structural Structural Structural")
        add_citable(ledger_con, "b2024", title="Structural Health")
        vocab = retrieval_spelling.vocabulary(retrieval._tokenize_item)
        assert vocab["structural"] == 2
        assert vocab["health"] == 1

    def test_it_is_empty_without_a_ledger(self, isolated_config):
        assert retrieval_spelling.vocabulary(retrieval._tokenize_item) == {}

    def test_it_is_empty_for_an_unreadable_ledger(self, isolated_config):
        config.LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.LEDGER_PATH.write_bytes(b"not a database")
        assert retrieval_spelling.vocabulary(retrieval._tokenize_item) == {}

    def test_only_parsed_papers_count(self, ledger_con):
        from tests.conftest import make_reference

        ledger.upsert_reference(ledger_con, make_reference("c2024", title="Unparsed Words"))
        add_citable(ledger_con, "a2024", title="Structural Health")
        assert "unparsed" not in retrieval_spelling.vocabulary(retrieval._tokenize_item)

    def test_it_is_rebuilt_after_the_ledger_changes(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Structural Health")
        first = retrieval_spelling.vocabulary(retrieval._tokenize_item)
        add_citable(ledger_con, "b2024", title="Simulation Study")
        second = retrieval_spelling.vocabulary(retrieval._tokenize_item)
        assert "simulation" not in first
        assert second["simulation"] == 1

    def test_an_unchanged_ledger_is_served_from_the_memo(self, ledger_con):
        add_citable(ledger_con, "a2024", title="Structural Health")
        first = retrieval_spelling.vocabulary(retrieval._tokenize_item)
        assert retrieval_spelling.vocabulary(retrieval._tokenize_item) is first

    def test_it_never_writes_the_cache(self, ledger_con, monkeypatch):
        add_citable(ledger_con, "a2024", title="Structural Health")
        monkeypatch.setattr(retrieval_cache, "_save_cache", lambda *_: pytest.fail("saved"))
        assert retrieval_spelling.vocabulary(retrieval._tokenize_item)["structural"] == 1
