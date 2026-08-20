"""chitragupta/enrich/topic_seeding.py: seed phrases matched against the
corpus, many-to-many.

The embedding model is faked throughout, as in
tests/test_enrich_topic_model.py, so these verify the *arithmetic and the
shape of the artefact* precisely rather than depending on a real model to
happen to place two strings near each other. numpy is real -- it is a
transitive dependency of the enrich group these tests already require.

The property worth stating once: a citekey may appear under any number of
phrases. Several tests below assert that directly, because it is the one
thing an artefact keyed by document rather than by phrase could not
express, and it is why this stage exists beside BERTopic rather than
inside it.
"""

import json

import pytest

from chitragupta import config
from chitragupta.enrich import embed_index, topic_model, topic_seeding
from chitragupta.enrich.corpus import CorpusDoc


class FakeArray(list):
    def tolist(self):
        return list(self)


class FakeModel:
    """Encodes a string to the vector `VECTORS` names for it, so a test
    can place a phrase and a document at a chosen angle to each other."""

    VECTORS: dict = {}
    encode_calls: list = []

    def encode(self, texts, show_progress_bar=False):
        FakeModel.encode_calls.append(list(texts))
        return FakeArray([FakeArray(FakeModel.VECTORS[t]) for t in texts])


@pytest.fixture
def fake_model(monkeypatch):
    FakeModel.VECTORS = {}
    FakeModel.encode_calls = []
    model = FakeModel()
    monkeypatch.setattr(embed_index, "get_client_and_model", lambda: (None, model))
    return model


def make_docs(tmp_path, texts: dict):
    docs = []
    for citekey, text in texts.items():
        path = tmp_path / f"{citekey}.txt"
        path.write_text(text, encoding="utf-8")
        docs.append(CorpusDoc(citekey=citekey, title=citekey,
                              pdf_path=None, text_path=str(path)))
    return docs


class TestCosine:
    def test_identical_vectors_are_one(self):
        assert topic_seeding.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_are_zero(self):
        assert topic_seeding.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_magnitude_does_not_matter(self):
        assert topic_seeding.cosine([1.0, 0.0], [7.0, 0.0]) == pytest.approx(1.0)

    def test_opposite_vectors_are_minus_one(self):
        assert topic_seeding.cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_zero_vector_matches_nothing_rather_than_raising(self):
        """A degenerate embedding has no direction. 0.0 keeps it under
        every threshold instead of failing the whole corpus run."""
        assert topic_seeding.cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


class TestAssign:
    def test_a_document_lands_under_every_phrase_it_clears(self, isolated_config):
        """The many-to-many property. `both` is close to each phrase; an
        artefact permitting one topic per document could not say so."""
        result = topic_seeding.assign(
            doc_embeddings={"both": [1.0, 1.0], "only_x": [1.0, 0.0]},
            phrase_embeddings={"x": [1.0, 0.0], "y": [0.0, 1.0]},
            min_similarity=0.5,
        )
        under = {topic["phrase"]: [m["citekey"] for m in topic["matches"]]
                 for topic in result["topics"]}
        assert under["x"] == ["only_x", "both"]
        assert under["y"] == ["both"]

    def test_below_threshold_is_excluded(self, isolated_config):
        result = topic_seeding.assign(
            doc_embeddings={"far": [0.0, 1.0]},
            phrase_embeddings={"x": [1.0, 0.0]},
            min_similarity=0.5,
        )
        assert result["topics"][0]["matches"] == []
        assert result["unmatched"] == ["far"]

    def test_threshold_is_inclusive(self, isolated_config):
        result = topic_seeding.assign(
            doc_embeddings={"exact": [1.0, 0.0]},
            phrase_embeddings={"x": [1.0, 0.0]},
            min_similarity=1.0,
        )
        assert [m["citekey"] for m in result["topics"][0]["matches"]] == ["exact"]

    def test_matches_are_ranked_best_first(self, isolated_config):
        result = topic_seeding.assign(
            doc_embeddings={"weak": [1.0, 0.9], "strong": [1.0, 0.0]},
            phrase_embeddings={"x": [1.0, 0.0]},
            min_similarity=0.5,
        )
        assert [m["citekey"] for m in result["topics"][0]["matches"]] == ["strong", "weak"]

    def test_ties_break_on_citekey_so_runs_do_not_shuffle(self, isolated_config):
        """Two papers at the same score must come back in the same order
        every run, whatever order the ledger handed them over in."""
        forward = topic_seeding.assign(
            doc_embeddings={"zeta": [1.0, 0.0], "alpha": [1.0, 0.0]},
            phrase_embeddings={"x": [1.0, 0.0]}, min_similarity=0.5,
        )
        reverse = topic_seeding.assign(
            doc_embeddings={"alpha": [1.0, 0.0], "zeta": [1.0, 0.0]},
            phrase_embeddings={"x": [1.0, 0.0]}, min_similarity=0.5,
        )
        assert ([m["citekey"] for m in forward["topics"][0]["matches"]]
                == [m["citekey"] for m in reverse["topics"][0]["matches"]]
                == ["alpha", "zeta"])

    def test_unmatched_is_every_document_no_phrase_described(self, isolated_config):
        result = topic_seeding.assign(
            doc_embeddings={"hit": [1.0, 0.0], "miss_b": [0.0, 1.0], "miss_a": [0.0, 1.0]},
            phrase_embeddings={"x": [1.0, 0.0]}, min_similarity=0.5,
        )
        assert result["unmatched"] == ["miss_a", "miss_b"]

    def test_threshold_defaults_to_config(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "SEED_TOPIC_MIN_SIMILARITY", 0.99)
        result = topic_seeding.assign(
            doc_embeddings={"near": [1.0, 0.2]}, phrase_embeddings={"x": [1.0, 0.0]},
        )
        assert result["min_similarity"] == 0.99
        assert result["topics"][0]["matches"] == []

    def test_provenance_is_recorded(self, isolated_config, monkeypatch):
        """Which model and which threshold produced these numbers, since
        neither is inferable from the scores and both change them."""
        monkeypatch.setattr(config, "EMBEDDING_MODEL", "some/model")
        result = topic_seeding.assign({"a": [1.0]}, {"x": [1.0]}, min_similarity=0.5)
        assert result["model"] == "some/model"
        assert result["n_docs"] == 1


class TestRunTopicSeeding:
    def test_writes_the_artefact_and_returns_it(self, isolated_config, fake_model, tmp_path):
        FakeModel.VECTORS = {"text about twins": [1.0, 0.0], "digital twin": [1.0, 0.0]}
        docs = make_docs(tmp_path, {"alpha_2020": "text about twins"})

        result = topic_seeding.run_topic_seeding(docs, ("digital twin",))

        assert isolated_config.TOPIC_SEEDS_PATH.exists()
        on_disk = json.loads(isolated_config.TOPIC_SEEDS_PATH.read_text(encoding="utf-8"))
        assert on_disk == result
        assert [m["citekey"] for m in result["topics"][0]["matches"]] == ["alpha_2020"]

    def test_phrase_reaches_the_model_whole(self, isolated_config, fake_model, tmp_path):
        """The invariant, at the one seam where it could still be lost:
        the model is handed the phrase as one string, not its words."""
        FakeModel.VECTORS = {"body": [1.0, 0.0], "structural health monitoring": [1.0, 0.0]}
        docs = make_docs(tmp_path, {"a_2020": "body"})

        topic_seeding.run_topic_seeding(docs, ("structural health monitoring",))

        assert ["structural health monitoring"] in FakeModel.encode_calls

    def test_all_phrases_are_encoded_in_one_call(self, isolated_config, fake_model, tmp_path):
        FakeModel.VECTORS = {"body": [1.0, 0.0], "one": [1.0, 0.0], "two": [0.0, 1.0]}
        docs = make_docs(tmp_path, {"a_2020": "body"})

        topic_seeding.run_topic_seeding(docs, ("one", "two"))

        assert ["one", "two"] in FakeModel.encode_calls

    def test_reuses_the_embeddings_the_topic_model_clusters(self, isolated_config,
                                                            fake_model, tmp_path):
        """Scored against the same cached vectors BERTopic clusters, so a
        similarity in the report explains the assignment beside it."""
        FakeModel.VECTORS = {"body": [1.0, 0.0], "one": [1.0, 0.0]}
        docs = make_docs(tmp_path, {"a_2020": "body"})

        topic_seeding.run_topic_seeding(docs, ("one",))

        cached = json.loads(config.TOPIC_EMBED_CACHE_PATH.read_text(encoding="utf-8"))
        assert cached["a_2020"]["embedding"] == [1.0, 0.0]
        assert cached["a_2020"]["model"] == config.EMBEDDING_MODEL

    def test_refuses_an_empty_phrase_list(self, isolated_config, fake_model, tmp_path):
        """An artefact with no topics reads identically to one whose every
        phrase matched nothing, and the two call for opposite responses."""
        docs = make_docs(tmp_path, {"a_2020": "body"})
        with pytest.raises(ValueError, match="No seed topics to match"):
            topic_seeding.run_topic_seeding(docs, ())
        assert not config.TOPIC_SEEDS_PATH.exists()

    def test_refuses_a_corpus_with_no_text(self, isolated_config, fake_model):
        docs = [CorpusDoc(citekey="no_text", title="t", pdf_path=None)]
        with pytest.raises(ValueError, match="No documents with text"):
            topic_seeding.run_topic_seeding(docs, ("one",))


class TestSharedSeamWithTopicModel:
    def test_corpus_texts_drops_documents_with_none(self, isolated_config, tmp_path):
        docs = make_docs(tmp_path, {"has_text": "words here"})
        docs.append(CorpusDoc(citekey="no_text", title="t", pdf_path=None))
        assert set(topic_model.corpus_texts(docs)) == {"has_text"}
