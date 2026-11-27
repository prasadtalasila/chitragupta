import json
import os
import shutil
from pathlib import Path

import pytest

from chitragupta import _tokens, overlap_index, passages, retrieval
from chitragupta import retrieval_cache, retrieval_passages_cache

from tests.conftest import run_python

REPO = Path(__file__).resolve().parent.parent

EDGE_STRINGS = [
    "",
    "AI and DT for 5G networks",
    "a b c x y 1 2 3",
    "of in at by on is AI",
    "Configuration-based self-adaptive systems",
    "ISO-9001 x86_64 COVID-19",
    "it's the twin's state, not its model",
    "naïve café résumé",
    "ﬁnite-element models",
    "page one\fpage two",
    "e.g. i.e. et al. vs.",
    "which these those their than then but also",
]


class TestTheRuleItself:
    def test_words_lowercase_and_split_on_anything_not_ascii_alphanumeric(self):
        rule = _tokens.Rule(floor=1, stopwords=frozenset())
        assert _tokens.words("ISO-9001 Café x86_64", rule) == ["iso", "9001", "caf", "x86", "64"]

    def test_the_floor_is_the_shortest_word_kept(self):
        rule = _tokens.Rule(floor=2, stopwords=frozenset())
        assert _tokens.words("a 5G net", rule) == ["5g", "net"]

    def test_stopwords_are_dropped_whatever_their_length(self):
        rule = _tokens.Rule(floor=1, stopwords=frozenset({"a", "the"}))
        assert _tokens.words("a twin the model", rule) == ["twin", "model"]

    def test_index_is_the_rule_bm25_shipped_with_before_the_split(self):
        assert _tokens.words("AI and DT for 5G networks", _tokens.INDEX) == [
            "ai",
            "dt",
            "5g",
            "networks",
        ]
        assert _tokens.words("a b c x y 1 2 3", _tokens.INDEX) == []
        assert _tokens.words("it can also be seen", _tokens.INDEX) == [
            "it",
            "can",
            "also",
            "seen",
        ]

    def test_distinctive_is_the_rule_passages_shipped_with_before_the_split(self):
        assert _tokens.words("AI and DT for 5G networks", _tokens.DISTINCTIVE) == ["networks"]
        assert _tokens.words("it can also be seen", _tokens.DISTINCTIVE) == ["seen"]

    def test_distinctive_is_index_with_more_dropped_never_less(self):
        assert _tokens.DISTINCTIVE.floor >= _tokens.INDEX.floor
        assert _tokens.DISTINCTIVE.stopwords >= _tokens.INDEX.stopwords


class TestEveryConsumerAgreesOnTheWords:
    @pytest.mark.parametrize("text", EDGE_STRINGS)
    def test_bm25_tokenizes_by_the_index_setting(self, text):
        assert retrieval._tokenize(text) == _tokens.words(text, _tokens.INDEX)

    @pytest.mark.parametrize("text", EDGE_STRINGS)
    def test_passages_match_claims_by_the_distinctive_setting(self, text):
        assert passages.distinctive(text) == set(_tokens.words(text, _tokens.DISTINCTIVE))

    @pytest.mark.parametrize("text", EDGE_STRINGS)
    def test_every_word_list_is_a_filter_of_one_split(self, text):
        split = overlap_index._norm(text)
        assert split == _tokens.WORD.findall(text.lower())
        assert set(retrieval._tokenize(text)) <= set(split)
        assert passages.distinctive(text) <= set(retrieval._tokenize(text))

    def test_short_query_terms_names_exactly_what_the_index_floor_drops(self):
        query = "a x 5G digital twin of y"
        kept = set(retrieval._tokenize(query))
        short = retrieval.short_query_terms(query)
        assert short == ["x", "y"]
        assert all(len(w) < _tokens.INDEX.floor for w in short)
        assert not kept & set(short)


class TestTheVocabularyDigest:
    def test_it_moves_when_a_stopword_is_added(self):
        wider = _tokens.INDEX._replace(stopwords=_tokens.INDEX.stopwords | {"twin"})
        assert _tokens.vocabulary_digest(wider) != _tokens.vocabulary_digest(_tokens.INDEX)

    def test_it_moves_when_the_floor_moves(self):
        higher = _tokens.INDEX._replace(floor=3)
        assert _tokens.vocabulary_digest(higher) != _tokens.vocabulary_digest(_tokens.INDEX)

    def test_it_does_not_depend_on_set_iteration_order(self):
        forward = _tokens.Rule(floor=2, stopwords=frozenset(["of", "the", "and"]))
        backward = _tokens.Rule(floor=2, stopwords=frozenset(["and", "the", "of"]))
        assert _tokens.vocabulary_digest(forward) == _tokens.vocabulary_digest(backward)

    def test_both_caches_carry_it_beside_their_own_schema_number(self):
        digest = _tokens.vocabulary_digest(_tokens.INDEX)
        assert retrieval_cache._INDEX_SCHEMA_VERSION == f"5-{digest}"
        assert retrieval_passages_cache._INDEX_SCHEMA_VERSION == f"2-{digest}"


_PROBE = (
    "import json\n"
    "from chitragupta import retrieval_cache, retrieval_passages_cache\n"
    "print(json.dumps([retrieval_cache._INDEX_SCHEMA_VERSION,"
    " retrieval_passages_cache._INDEX_SCHEMA_VERSION]))\n"
)


def _versions_under(tmp_path: Path, edit) -> list[str]:
    shutil.copytree(
        REPO / "chitragupta", tmp_path / "chitragupta", ignore=shutil.ignore_patterns("__pycache__")
    )
    source = tmp_path / "chitragupta" / "_tokens.py"
    original = source.read_text(encoding="utf-8")
    edited = edit(original)
    assert edited != original or edit is _unchanged, "the edit did not apply"
    source.write_text(edited, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(tmp_path), "CHITRAGUPTA_PROJECT": str(REPO)}
    out = run_python("-c", _PROBE, cwd=tmp_path, env=env, encoding="utf-8", check=True)
    return json.loads(out.stdout)


def _unchanged(source: str) -> str:
    return source


class TestEditingTheSourceInvalidatesTheCaches:
    def test_an_unedited_copy_reports_this_process_versions(self, tmp_path):
        assert _versions_under(tmp_path, _unchanged) == [
            retrieval_cache._INDEX_SCHEMA_VERSION,
            retrieval_passages_cache._INDEX_SCHEMA_VERSION,
        ]

    def test_a_new_core_stopword_invalidates_both_caches(self, tmp_path):
        versions = _versions_under(
            tmp_path, lambda s: s.replace('"the",', '"the",\n        "twin",', 1)
        )
        assert versions[0] != retrieval_cache._INDEX_SCHEMA_VERSION
        assert versions[1] != retrieval_passages_cache._INDEX_SCHEMA_VERSION

    def test_a_moved_index_floor_invalidates_both_caches(self, tmp_path):
        versions = _versions_under(
            tmp_path, lambda s: s.replace("INDEX = Rule(floor=2", "INDEX = Rule(floor=3", 1)
        )
        assert versions[0] != retrieval_cache._INDEX_SCHEMA_VERSION
        assert versions[1] != retrieval_passages_cache._INDEX_SCHEMA_VERSION

    def test_a_distinctive_only_stopword_leaves_both_caches_valid(self, tmp_path):
        versions = _versions_under(
            tmp_path, lambda s: s.replace('"also",', '"also",\n        "twin",', 1)
        )
        assert versions == [
            retrieval_cache._INDEX_SCHEMA_VERSION,
            retrieval_passages_cache._INDEX_SCHEMA_VERSION,
        ]
