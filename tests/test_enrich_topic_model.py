import json
import sys
import types
from pathlib import Path

import pytest

from chitragupta import config, ledger
from chitragupta.enrich import doc_vectors, embed_index, topic_model
from chitragupta.enrich.corpus import CorpusDoc


@pytest.fixture(autouse=True)
def _a_synced_ledger(isolated_config):
    ledger.connect().close()


class FakeUMAP:
    last_kwargs = None

    def __init__(self, **kwargs):
        FakeUMAP.last_kwargs = kwargs


class FakeHDBSCAN:
    last_kwargs = None

    def __init__(self, **kwargs):
        FakeHDBSCAN.last_kwargs = kwargs


class FakeTopicInfo:
    def to_json(self, orient):
        return json.dumps([{"Topic": -1, "Count": 2, "Name": "-1_outlier"}])


class FakeBERTopic:
    last_kwargs = None
    topics_returned = None

    def __init__(self, **kwargs):
        FakeBERTopic.last_kwargs = kwargs
        self.hdbscan_model = kwargs.get("hdbscan_model")

    def fit_transform(self, texts, embeddings):
        if FakeBERTopic.topics_returned is not None:
            return list(FakeBERTopic.topics_returned), None
        return [-1 for _ in texts], None

    def get_topic_info(self):
        return FakeTopicInfo()


class FakeArray(list):
    def tolist(self):
        return list(self)


class FakeModel:
    encode_call_texts = []  # records each call's input, for cache-hit assertions

    def encode(self, texts, show_progress_bar=False):
        FakeModel.encode_call_texts.append(list(texts))
        return FakeArray([FakeArray([float(len(t))]) for t in texts])


@pytest.fixture
def fake_bertopic_stack(monkeypatch):
    FakeUMAP.last_kwargs = None
    FakeHDBSCAN.last_kwargs = None
    FakeBERTopic.last_kwargs = None
    FakeBERTopic.topics_returned = None
    FakeModel.encode_call_texts = []

    umap_module = types.ModuleType("umap")
    umap_module.UMAP = FakeUMAP
    monkeypatch.setitem(sys.modules, "umap", umap_module)

    hdbscan_module = types.ModuleType("hdbscan")
    hdbscan_module.HDBSCAN = FakeHDBSCAN
    monkeypatch.setitem(sys.modules, "hdbscan", hdbscan_module)

    bertopic_module = types.ModuleType("bertopic")
    bertopic_module.BERTopic = FakeBERTopic
    monkeypatch.setitem(sys.modules, "bertopic", bertopic_module)

    monkeypatch.setattr(embed_index, "get_client_and_model", lambda: (None, FakeModel()))
    return types.SimpleNamespace(umap=FakeUMAP, hdbscan=FakeHDBSCAN, bertopic=FakeBERTopic)


def make_docs_with_text(n, tmp_path):
    docs = []
    for i in range(n):
        path = tmp_path / f"doc{i}.txt"
        path.write_text(f"document number {i} " * 5)
        docs.append(
            CorpusDoc(
                citekey=f"doc{i}",
                title=f"T{i}",
                pdf_path=None,
                text_path=str(path),
            )
        )
    return docs


class TestRunTopicModel:
    def test_raises_below_minimum_doc_count(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(1, tmp_path)
        with pytest.raises(ValueError, match="Need at least 2 documents"):
            topic_model.run_topic_model(docs)

    def test_records_the_embedding_model_and_method(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        from chitragupta.enrich import doc_vectors

        docs = make_docs_with_text(2, tmp_path)
        result = topic_model.run_topic_model(docs)

        assert result["embedding_model"] == isolated_config.EMBEDDING_MODEL
        assert result["embedding_method"] == doc_vectors.EMBED_METHOD

    def test_scaling_formula_for_small_corpus(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)

        assert FakeUMAP.last_kwargs["n_neighbors"] == 5
        assert FakeUMAP.last_kwargs["n_components"] == 4
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == 3

    @pytest.mark.parametrize(
        "n_docs,expected_n_neighbors,expected_n_components,expected_min_cluster_size",
        [
            (2, 1, 2, 2),
            (3, 2, 2, 2),
        ],
    )
    def test_small_corpus_boundary_values_are_pinned_not_fixed(
        self,
        isolated_config,
        fake_bertopic_stack,
        tmp_path,
        n_docs,
        expected_n_neighbors,
        expected_n_components,
        expected_min_cluster_size,
    ):
        docs = make_docs_with_text(n_docs, tmp_path)
        topic_model.run_topic_model(
            docs
        )  # doesn't raise -- fakes don't validate like real UMAP would

        assert FakeUMAP.last_kwargs["n_neighbors"] == expected_n_neighbors
        assert FakeUMAP.last_kwargs["n_components"] == expected_n_components
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == expected_min_cluster_size

    def test_a_large_corpus_gets_the_configured_granularity(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(30, tmp_path)
        topic_model.run_topic_model(docs)

        assert FakeUMAP.last_kwargs["n_neighbors"] == config.TOPIC_NEIGHBORS
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == config.TOPIC_MIN_CLUSTER_SIZE
        assert FakeHDBSCAN.last_kwargs["min_samples"] == config.TOPIC_MIN_SAMPLES

    def test_depth_is_tunable_without_touching_code(
        self, isolated_config, fake_bertopic_stack, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(config, "TOPIC_MIN_CLUSTER_SIZE", 8)
        monkeypatch.setattr(config, "TOPIC_NEIGHBORS", 15)
        topic_model.run_topic_model(make_docs_with_text(40, tmp_path))
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == 8
        assert FakeUMAP.last_kwargs["n_neighbors"] == 15

    def test_a_small_corpus_still_clamps_below_the_configured_value(
        self, isolated_config, fake_bertopic_stack, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(config, "TOPIC_NEIGHBORS", 50)
        monkeypatch.setattr(config, "TOPIC_MIN_CLUSTER_SIZE", 50)
        topic_model.run_topic_model(make_docs_with_text(6, tmp_path))
        assert FakeUMAP.last_kwargs["n_neighbors"] == 5
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == 3

    def test_writes_result_and_returns_assignments(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(6, tmp_path)
        result = topic_model.run_topic_model(docs)

        assert result["n_docs"] == 6
        assert set(result["assignments"]) == {d.citekey for d in docs}
        assert all(v == -1 for v in result["assignments"].values())
        assert isolated_config.TOPICS_PATH.exists()
        saved = json.loads(isolated_config.TOPICS_PATH.read_text())
        assert saved["n_docs"] == 6

    def test_skips_docs_with_no_text(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(6, tmp_path)
        docs.append(CorpusDoc(citekey="no_text", title="t", pdf_path=None))

        result = topic_model.run_topic_model(docs)
        assert "no_text" not in result["assignments"]
        assert result["n_docs"] == 6


class TestEmbeddingCache:
    def test_second_run_with_unchanged_docs_encodes_nothing(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 6  # one call per new doc, carrying its chunks

        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 6  # no further calls -- every doc was cache-hit

    def test_changed_doc_triggers_encode_for_only_that_doc(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)

        Path(docs[0].text_path).write_text("completely different content now")
        topic_model.run_topic_model(docs)

        assert len(FakeModel.encode_call_texts) == 7  # 6 first run, 1 re-encode
        assert "completely different content now" in " ".join(FakeModel.encode_call_texts[-1])

    def test_cache_persisted_to_disk_between_calls(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)

        assert isolated_config.TOPIC_EMBED_CACHE_PATH.exists()
        cache = json.loads(isolated_config.TOPIC_EMBED_CACHE_PATH.read_text())
        assert set(cache) == {d.citekey for d in docs}
        assert all("hash" in v and "embedding" in v for v in cache.values())

    def test_model_change_re_embeds_every_cached_doc(
        self, isolated_config, fake_bertopic_stack, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(config, "EMBEDDING_MODEL", "model-a")
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 6  # one call per document

        monkeypatch.setattr(config, "EMBEDDING_MODEL", "model-b")
        topic_model.run_topic_model(docs)

        assert len(FakeModel.encode_call_texts) == 12

        cache = json.loads(isolated_config.TOPIC_EMBED_CACHE_PATH.read_text())
        assert all(v["model"] == "model-b" for v in cache.values())

    def test_new_doc_added_to_existing_corpus_only_encodes_the_new_one(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)

        new_doc_path = tmp_path / "doc_new.txt"
        new_doc_path.write_text("a brand new document")
        new_doc = CorpusDoc(
            citekey="doc_new",
            title="New",
            pdf_path=None,
            text_path=str(new_doc_path),
        )
        topic_model.run_topic_model(docs + [new_doc])

        assert len(FakeModel.encode_call_texts) == 7  # 6 + only the new one
        assert FakeModel.encode_call_texts[-1] == ["a brand new document"]


class TestSeedsDoNotSteerTheClustering:
    def test_bertopic_is_never_given_a_zeroshot_list(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        topic_model.run_topic_model(make_docs_with_text(6, tmp_path))
        assert "zeroshot_topic_list" not in FakeBERTopic.last_kwargs
        assert "zeroshot_min_similarity" not in FakeBERTopic.last_kwargs

    def test_the_run_takes_no_seed_argument_at_all(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        import inspect

        assert list(inspect.signature(topic_model.run_topic_model).parameters) == ["docs"]

    def test_one_topic_per_document_is_still_all_bertopic_gives(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        result = topic_model.run_topic_model(make_docs_with_text(6, tmp_path))
        assert all(isinstance(v, int) for v in result["assignments"].values())


class TestDocumentEmbeddingsSeam:
    def test_returns_one_vector_per_citekey(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(3, tmp_path)
        texts = doc_vectors.corpus_texts(docs)
        vectors = doc_vectors.document_embeddings(texts, FakeModel())
        assert set(vectors) == set(texts)

    def test_reuses_the_cache_across_callers(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(3, tmp_path)
        texts = doc_vectors.corpus_texts(docs)
        model = FakeModel()
        doc_vectors.document_embeddings(texts, model)
        FakeModel.encode_call_texts = []
        doc_vectors.document_embeddings(texts, model)
        assert FakeModel.encode_call_texts == []


THREE_CLUSTERS = [
    [1.0, 0.0, 0.0],
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0],
    [0.0, 0.0, 1.0],
]
CLUSTER_KEYS = ["a1", "a2", "b1", "b2", "c1", "c2", "spans"]
CLUSTER_TOPICS = [0, 0, 1, 1, 2, 2, -1]


def memberships_for(spans, topics=None):
    return topic_model.topic_memberships(
        THREE_CLUSTERS + [spans], CLUSTER_KEYS, topics or CLUSTER_TOPICS
    )


class TestTopicMemberships:
    def test_a_document_between_two_topics_is_about_both(self, isolated_config):
        assert set(memberships_for([1.0, 1.0, 0.0])["spans"]) == {"0", "1"}

    def test_a_document_inside_one_cluster_is_about_one(self, isolated_config):
        assert list(memberships_for([1.0, 1.0, 0.0])["a1"]) == ["0"]

    def test_a_weaker_second_topic_is_dropped(self, isolated_config):
        assert list(memberships_for([1.0, 0.7, 0.0])["spans"]) == ["0"]

    def test_the_ratio_decides_how_weak_a_second_may_be(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_RATIO", 0.01)
        loosened = memberships_for([1.0, 0.7, 0.0])["spans"]
        assert set(loosened) == {"0", "1"}
        assert list(loosened)[0] == "0"

    def test_the_cap_bounds_a_plural_document(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_MAX", 1)
        assert len(memberships_for([1.0, 1.0, 0.0])["spans"]) == 1

    def test_the_assigned_topic_is_always_a_membership(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_MAX", 1)
        got = topic_model.topic_memberships(
            THREE_CLUSTERS + [[1.0, 0.0, 0.0]], CLUSTER_KEYS, [0, 0, 1, 1, 2, 2, 2]
        )
        assert "2" in got["spans"]

    def test_the_outlier_topic_is_never_a_membership(self, isolated_config):
        every = memberships_for([1.0, 1.0, 0.0])
        assert all("-1" not in row for row in every.values())

    def test_an_all_outlier_corpus_has_no_descriptor_to_measure(self, isolated_config):
        assert topic_model.topic_memberships([[1.0], [1.0]], ["a", "b"], [-1, -1]) is None

    def test_a_document_at_the_corpus_mean_belongs_nowhere(self, isolated_config):
        assert "spans" not in memberships_for([1.0, 1.0, 1.0])

    def test_switching_it_off_records_nothing(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_DISTRIBUTION", False)
        assert topic_model.topic_memberships([[1.0], [1.0]], ["a", "b"], [0, 0]) is None

    def test_it_reaches_the_artefact_with_its_mechanism_named(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = []
        for index, size in enumerate((10, 20, 30, 40)):
            path = tmp_path / f"doc{index}.txt"
            path.write_text("x" * size, encoding="utf-8")
            docs.append(
                CorpusDoc(
                    citekey=f"doc{index}", title=f"T{index}", pdf_path=None, text_path=str(path)
                )
            )
        FakeBERTopic.topics_returned = [0, 0, 1, 1]
        result = topic_model.run_topic_model(docs)
        assert result["memberships"]
        assert result["membership_mechanism"] == topic_model.MEMBERSHIP_MECHANISM
        assert result["assignments"] == {"doc0": 0, "doc1": 0, "doc2": 1, "doc3": 1}


class TestTopicDescriptors:
    def test_the_outlier_topic_gets_no_descriptor(self, isolated_config):
        ids, _centred, descriptors = topic_model.topic_descriptors(
            THREE_CLUSTERS + [[1.0, 1.0, 0.0]], CLUSTER_TOPICS
        )
        assert ids == [0, 1, 2]
        assert len(descriptors) == 3

    def test_descriptors_are_centred(self, isolated_config):
        import numpy as np

        _ids, centred, _d = topic_model.topic_descriptors(
            THREE_CLUSTERS + [[1.0, 1.0, 0.0]], CLUSTER_TOPICS
        )
        assert np.allclose(np.asarray(centred).mean(axis=0), 0.0)


class TestWholeDocumentPooling:
    def whitespace_doc(self, tmp_path, citekey):
        path = tmp_path / f"{citekey}.txt"
        path.write_text("   \n\t ", encoding="utf-8")
        return CorpusDoc(citekey=citekey, title=citekey, pdf_path=None, text_path=str(path))

    def test_every_chunk_reaches_the_model(
        self, isolated_config, fake_bertopic_stack, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            embed_index, "chunk_text", lambda text, **kw: ["chunk one", "chunk two", "chunk three"]
        )
        path = tmp_path / "long.txt"
        path.write_text("word " * 2000, encoding="utf-8")
        docs = [
            CorpusDoc(citekey="long", title="L", pdf_path=None, text_path=str(path)),
            *make_docs_with_text(2, tmp_path),
        ]
        topic_model.run_topic_model(docs)
        assert ["chunk one", "chunk two", "chunk three"] in FakeModel.encode_call_texts

    def test_the_vector_is_the_mean_of_its_chunks(
        self, isolated_config, fake_bertopic_stack, monkeypatch
    ):
        monkeypatch.setattr(
            embed_index, "chunk_text", lambda text, **kw: ["x" * 10, "x" * 20, "x" * 30]
        )
        got = doc_vectors.pooled_embedding("anything", FakeModel())
        assert got == [20.0]

    def test_text_that_chunks_to_nothing_has_no_vector(self, isolated_config):
        assert doc_vectors.pooled_embedding("   \n\t ", FakeModel()) is None

    def test_such_a_document_is_dropped_rather_than_zeroed(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(3, tmp_path) + [self.whitespace_doc(tmp_path, "blank")]
        result = topic_model.run_topic_model(docs)
        assert "blank" not in result["assignments"]
        assert result["n_docs"] == 3

    def test_too_few_embeddable_documents_raises(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        docs = make_docs_with_text(1, tmp_path) + [self.whitespace_doc(tmp_path, "blank")]
        with pytest.raises(ValueError, match="embeddable text"):
            topic_model.run_topic_model(docs)

    def test_the_method_is_recorded_so_old_vectors_go_stale(
        self, isolated_config, fake_bertopic_stack, tmp_path
    ):
        topic_model.run_topic_model(make_docs_with_text(3, tmp_path))
        cache = json.loads(isolated_config.TOPIC_EMBED_CACHE_PATH.read_text(encoding="utf-8"))
        assert all(v["method"] == doc_vectors.EMBED_METHOD for v in cache.values())

    def test_a_method_change_re_embeds_everything(
        self, isolated_config, fake_bertopic_stack, tmp_path, monkeypatch
    ):
        docs = make_docs_with_text(3, tmp_path)
        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 3
        monkeypatch.setattr(doc_vectors, "EMBED_METHOD", "something-else-v2")
        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 6


class TestContentText:
    def test_the_reference_list_is_dropped(self):
        kept = doc_vectors.content_text(
            "## Method\nour approach\n\n## References\n[1] Kritzinger, W.\n"
        )
        assert "our approach" in kept
        assert "Kritzinger" not in kept

    def test_the_last_heading_wins(self):
        kept = doc_vectors.content_text(
            "## Intro\nalpha\n## References\n[1] x\n## Appendix\nbeta\n## References\n[2] y"
        )
        assert "beta" in kept
        assert "[2] y" not in kept

    def test_a_document_without_one_keeps_all_its_text(self):
        assert "everything" in doc_vectors.content_text("## Method\neverything here\n")

    def test_boilerplate_lines_go_at_any_depth(self):
        kept = doc_vectors.content_text(
            "real content\nfoo@bar.ac.uk\nhttps://example.com\ndoi:10.1000/xyz\n"
            "Downloaded from somewhere\n(c) 2024 Publisher\n17\nmore content"
        )
        assert "real content" in kept and "more content" in kept
        for gone in ("foo@bar", "example.com", "doi:10", "Downloaded", "2024 Publisher"):
            assert gone not in kept
        assert "\n17\n" not in kept

    def test_technical_tokens_survive(self):
        kept = doc_vectors.content_text("IEC 62304 and MQTT v5 govern the DTaaS platform")
        assert kept == "IEC 62304 and MQTT v5 govern the DTaaS platform"

    def test_it_is_applied_before_chunking(self, isolated_config, monkeypatch):
        seen = {}
        monkeypatch.setattr(
            embed_index,
            "chunk_text",
            lambda text, **kw: seen.setdefault("text", text) and ["x"] or ["x"],
        )
        doc_vectors.pooled_embedding("keep me\n## References\n[1] drop me", FakeModel())
        assert "drop me" not in seen["text"]
