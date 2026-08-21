"""chitragupta/enrich/topic_model.py: BERTopic clustering, with the small-corpus
UMAP/HDBSCAN scaling formula this module relies on to not crash outright
on a handful of documents.

bertopic/umap/hdbscan are mocked via sys.modules so these stay fast and
verify the *scaling arithmetic* precisely, rather than depending on a
real (slow) clustering run to happen to produce a particular topic
count. A slow, real end-to-end run was already verified by hand during
installation smoke-testing (see the Task-1 conversation) -- not
duplicated here.
"""

import json
import sys
import types
from pathlib import Path

import pytest

from chitragupta import config
from chitragupta.enrich import embed_index, topic_model
from chitragupta.enrich.corpus import CorpusDoc


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
    # What fit_transform() hands back, so a test can put the model in the
    # all-outlier state approximate_distribution() cannot answer for.
    topics_returned = None

    def __init__(self, **kwargs):
        FakeBERTopic.last_kwargs = kwargs
        # Real BERTopic keeps the clusterer it was handed; topic_memberships
        # reads it back off the fitted model to ask for soft memberships.
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
        docs.append(CorpusDoc(
            citekey=f"doc{i}", title=f"T{i}",
            pdf_path=None, text_path=str(path),
        ))
    return docs


class TestRunTopicModel:
    def test_raises_below_minimum_doc_count(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(1, tmp_path)
        with pytest.raises(ValueError, match="Need at least 2 documents"):
            topic_model.run_topic_model(docs)

    def test_scaling_formula_for_small_corpus(self, isolated_config, fake_bertopic_stack, tmp_path):
        # n_docs=6: n_neighbors=min(15,5)=5, n_components=min(5,max(2,4))=4,
        # min_cluster_size=max(2,min(10,3))=3.
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)

        assert FakeUMAP.last_kwargs["n_neighbors"] == 5
        assert FakeUMAP.last_kwargs["n_components"] == 4
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == 3

    @pytest.mark.parametrize("n_docs,expected_n_neighbors,expected_n_components,expected_min_cluster_size", [
        # n_docs=2: n_neighbors computes to 1 -- real UMAP's
        # `_validate_parameters` rejects this outright ("n_neighbors
        # must be greater than 1"), found by hand while installation
        # smoke-testing with a 2-document toy corpus (Task-1). Flagged
        # there as "worth a unit test in Task-2" rather than silently
        # patched, since it's a pre-existing edge case unrelated to
        # installation and real corpora are never this small. Pinned
        # here as documented, known-bad behavior against the *fake*
        # UMAP/HDBSCAN (which don't validate), not fixed.
        (2, 1, 2, 2),
        # n_docs=3: n_neighbors=2 clears UMAP's own n_neighbors>1 check,
        # but real UMAP's spectral initialization separately needs
        # n_components + 1 < n_samples (2+1 !< 3) and fails at a
        # different step (scipy.sparse.linalg.eigsh) -- also verified by
        # hand in Task-1, also not fixed here for the same reason.
        (3, 2, 2, 2),
    ])
    def test_small_corpus_boundary_values_are_pinned_not_fixed(
        self, isolated_config, fake_bertopic_stack, tmp_path,
        n_docs, expected_n_neighbors, expected_n_components, expected_min_cluster_size,
    ):
        docs = make_docs_with_text(n_docs, tmp_path)
        topic_model.run_topic_model(docs)  # doesn't raise -- fakes don't validate like real UMAP would

        assert FakeUMAP.last_kwargs["n_neighbors"] == expected_n_neighbors
        assert FakeUMAP.last_kwargs["n_components"] == expected_n_components
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == expected_min_cluster_size

    def test_a_large_corpus_gets_the_configured_granularity(self, isolated_config,
                                                            fake_bertopic_stack, tmp_path):
        """The defect this replaced: every parameter saturated at n_docs>=20,
        so a 497-document corpus got the settings written for a 20-document
        one and could never yield more than ~13 topics however large it grew.
        Past the small-corpus clamps, config decides."""
        docs = make_docs_with_text(30, tmp_path)
        topic_model.run_topic_model(docs)

        assert FakeUMAP.last_kwargs["n_neighbors"] == config.TOPIC_NEIGHBORS
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == config.TOPIC_MIN_CLUSTER_SIZE
        assert FakeHDBSCAN.last_kwargs["min_samples"] == config.TOPIC_MIN_SAMPLES

    def test_depth_is_tunable_without_touching_code(self, isolated_config,
                                                   fake_bertopic_stack, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_MIN_CLUSTER_SIZE", 8)
        monkeypatch.setattr(config, "TOPIC_NEIGHBORS", 15)
        topic_model.run_topic_model(make_docs_with_text(40, tmp_path))
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == 8
        assert FakeUMAP.last_kwargs["n_neighbors"] == 15

    def test_a_small_corpus_still_clamps_below_the_configured_value(self, isolated_config,
                                                                   fake_bertopic_stack,
                                                                   tmp_path, monkeypatch):
        """The clamps only ever reduce. UMAP's spectral initialisation
        genuinely fails when n_neighbors >= n_samples, which is what the
        original formula existed for and what must survive the change."""
        monkeypatch.setattr(config, "TOPIC_NEIGHBORS", 50)
        monkeypatch.setattr(config, "TOPIC_MIN_CLUSTER_SIZE", 50)
        topic_model.run_topic_model(make_docs_with_text(6, tmp_path))
        assert FakeUMAP.last_kwargs["n_neighbors"] == 5
        assert FakeHDBSCAN.last_kwargs["min_cluster_size"] == 3

    def test_writes_result_and_returns_assignments(self, isolated_config, fake_bertopic_stack, tmp_path):
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
    def test_second_run_with_unchanged_docs_encodes_nothing(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 1  # one batch call for all 6 new docs

        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 1  # no second call -- every doc was cache-hit

    def test_changed_doc_triggers_encode_for_only_that_doc(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)

        Path(docs[0].text_path).write_text("completely different content now")
        topic_model.run_topic_model(docs)

        assert len(FakeModel.encode_call_texts) == 2
        assert FakeModel.encode_call_texts[1] == ["completely different content now"]

    def test_cache_persisted_to_disk_between_calls(self, isolated_config, fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)

        assert isolated_config.TOPIC_EMBED_CACHE_PATH.exists()
        cache = json.loads(isolated_config.TOPIC_EMBED_CACHE_PATH.read_text())
        assert set(cache) == {d.citekey for d in docs}
        assert all("hash" in v and "embedding" in v for v in cache.values())

    def test_model_change_re_embeds_every_cached_doc(
        self, isolated_config, fake_bertopic_stack, tmp_path, monkeypatch
    ):
        # Regression test: the cache previously keyed staleness only off the
        # doc's text hash, so swapping config.toml's embedding_model (e.g.
        # MiniLM-L6-v2 -> mpnet-base-v2, a real change made in this repo)
        # would keep serving cached vectors from the old model -- silently
        # mixing dimensions in the `embeddings` array BERTopic is fit on.
        monkeypatch.setattr(config, "EMBEDDING_MODEL", "model-a")
        docs = make_docs_with_text(6, tmp_path)
        topic_model.run_topic_model(docs)
        assert len(FakeModel.encode_call_texts) == 1
        assert len(FakeModel.encode_call_texts[0]) == 6

        monkeypatch.setattr(config, "EMBEDDING_MODEL", "model-b")
        topic_model.run_topic_model(docs)

        assert len(FakeModel.encode_call_texts) == 2
        assert len(FakeModel.encode_call_texts[1]) == 6  # every doc re-embedded, not just changed ones

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
            citekey="doc_new", title="New",
            pdf_path=None, text_path=str(new_doc_path),
        )
        topic_model.run_topic_model(docs + [new_doc])

        assert len(FakeModel.encode_call_texts) == 2
        assert FakeModel.encode_call_texts[1] == ["a brand new document"]


class TestSeedPhrases:
    """The zero-shot half of #206: BERTopic steered by phrases a person
    wrote, and -- just as much the requirement -- left exactly as it was
    for the libraries that have none."""

    def test_unseeded_run_passes_no_zeroshot_list(self, isolated_config,
                                                  fake_bertopic_stack, tmp_path):
        """None rather than [], because BERTopic branches on falsiness to
        decide whether to run zero-shot assignment at all."""
        topic_model.run_topic_model(make_docs_with_text(6, tmp_path))
        assert FakeBERTopic.last_kwargs["zeroshot_topic_list"] is None

    def test_unseeded_output_carries_no_seed_key(self, isolated_config,
                                                 fake_bertopic_stack, tmp_path):
        """The "unchanged, not degraded" bar: a library with no seed file
        gets the same content/topics.json shape it got before seeding
        existed, with no empty list to interpret."""
        result = topic_model.run_topic_model(make_docs_with_text(6, tmp_path))
        assert "seed_phrases" not in result
        assert "seed_phrases" not in json.loads(
            isolated_config.TOPICS_PATH.read_text(encoding="utf-8"))

    def test_phrases_reach_bertopic_whole(self, isolated_config,
                                          fake_bertopic_stack, tmp_path):
        """A three-word seed arrives as one list element, never split into
        terms -- the property `seed_topic_list` could not have given."""
        topic_model.run_topic_model(make_docs_with_text(6, tmp_path),
                                    ("structural health monitoring", "digital twin"))
        assert FakeBERTopic.last_kwargs["zeroshot_topic_list"] == [
            "structural health monitoring", "digital twin"]

    def test_threshold_comes_from_its_own_config_key(self, isolated_config,
                                                     fake_bertopic_stack, tmp_path,
                                                     monkeypatch):
        monkeypatch.setattr(config, "ZEROSHOT_MIN_SIMILARITY", 0.72)
        topic_model.run_topic_model(make_docs_with_text(6, tmp_path), ("digital twin",))
        assert FakeBERTopic.last_kwargs["zeroshot_min_similarity"] == 0.72

    def test_the_assignment_bar_is_not_the_reports_floor(self, isolated_config,
                                                         fake_bertopic_stack, tmp_path,
                                                         monkeypatch):
        """One key drove both until a 497-document corpus proved it wrong:
        a floor loose enough to rank a report against assigns nearly the
        whole corpus by zero-shot, starving HDBSCAN of the points its own
        min_samples needs. They must not be able to drift back together."""
        monkeypatch.setattr(config, "SEED_TOPIC_MIN_SIMILARITY", 0.15)
        monkeypatch.setattr(config, "ZEROSHOT_MIN_SIMILARITY", 0.55)
        topic_model.run_topic_model(make_docs_with_text(6, tmp_path), ("digital twin",))
        assert FakeBERTopic.last_kwargs["zeroshot_min_similarity"] == 0.55

    def test_seeded_output_records_the_phrases(self, isolated_config,
                                               fake_bertopic_stack, tmp_path):
        """So a reader can tell topic names a person chose from ones the
        clustering invented."""
        result = topic_model.run_topic_model(make_docs_with_text(6, tmp_path),
                                             ("digital twin",))
        assert result["seed_phrases"] == ["digital twin"]

    def test_one_topic_per_document_is_still_all_bertopic_gives(self, isolated_config,
                                                                fake_bertopic_stack, tmp_path):
        """Stated as a test because it is the whole reason
        chitragupta/enrich/topic_seeding.py exists: this artefact maps each
        citekey to exactly one topic id and cannot express a paper that
        belongs under two."""
        result = topic_model.run_topic_model(make_docs_with_text(6, tmp_path),
                                             ("digital twin", "lifecycle"))
        assert all(isinstance(topic_id, int)
                   for topic_id in result["assignments"].values())


class TestDocumentEmbeddingsSeam:
    def test_returns_one_vector_per_citekey(self, isolated_config,
                                            fake_bertopic_stack, tmp_path):
        docs = make_docs_with_text(3, tmp_path)
        texts = topic_model.corpus_texts(docs)
        vectors = topic_model.document_embeddings(texts, FakeModel())
        assert set(vectors) == set(texts)

    def test_reuses_the_cache_across_callers(self, isolated_config,
                                             fake_bertopic_stack, tmp_path):
        """topic_seeding.py scores against the same vectors this stage
        clusters, so the second caller must encode nothing."""
        docs = make_docs_with_text(3, tmp_path)
        texts = topic_model.corpus_texts(docs)
        model = FakeModel()
        topic_model.document_embeddings(texts, model)
        FakeModel.encode_call_texts = []
        topic_model.document_embeddings(texts, model)
        assert FakeModel.encode_call_texts == []


class FakeClusterer:
    """Stands in for a fitted HDBSCAN. `labels_` are HDBSCAN's own cluster
    ids, deliberately *not* BERTopic's topic ids -- BERTopic renumbers by
    size, and conflating the two is the bug these tests exist to catch."""

    def __init__(self, labels):
        self.labels_ = labels


class Placeholder:
    """What BERTopic leaves in hdbscan_model on a zero-shot run: a
    BaseCluster carrying no labels_ at all."""


class TestTopicMemberships:
    """A document can belong to more than one topic BERTopic *discovered*,
    not only to more than one phrase a person wrote.

    The soft-membership matrix is supplied directly rather than computed,
    so these pin the selection and the id translation. That the numbers
    themselves are right is HDBSCAN's business, and was checked against
    the real library on 497 documents: its own assignment appears in the
    memberships it produces for 100% of them, against 30-45% for every
    centroid rule tried first.
    """

    def soft(self, monkeypatch, matrix):
        monkeypatch.setattr(topic_model, "_soft_membership", lambda clusterer: matrix)

    def test_a_document_between_two_topics_belongs_to_both(self, isolated_config,
                                                           monkeypatch):
        self.soft(monkeypatch, [[0.9, 0.1], [0.5, 0.5]])
        got = topic_model.topic_memberships(FakeClusterer([0, 1]), ["solo", "spans"], [0, 1])
        assert len(got["spans"]) == 2
        assert list(got["solo"]) == ["0"]

    def test_hdbscan_cluster_ids_are_translated_to_topic_ids(self, isolated_config,
                                                             monkeypatch):
        """BERTopic renumbers topics by size -- on the real corpus its
        cluster 0 was topic 6. Reporting the cluster id would name the
        wrong topic in every artefact."""
        self.soft(monkeypatch, [[0.9, 0.1], [0.2, 0.8]])
        got = topic_model.topic_memberships(
            FakeClusterer([0, 1]), ["a", "b"], [6, 8])
        assert list(got["a"])[0] == "6"
        assert list(got["b"])[0] == "8"

    def test_a_weaker_second_topic_is_dropped(self, isolated_config, monkeypatch):
        self.soft(monkeypatch, [[0.9, 0.1], [0.1, 0.9]])
        got = topic_model.topic_memberships(FakeClusterer([0, 1]), ["a", "b"], [0, 1])
        assert list(got["a"]) == ["0"]

    def test_the_ratio_decides_how_weak_a_second_may_be(self, isolated_config, monkeypatch):
        self.soft(monkeypatch, [[0.9, 0.1], [0.1, 0.9]])
        monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_RATIO", 0.05)
        got = topic_model.topic_memberships(FakeClusterer([0, 1]), ["a", "b"], [0, 1])
        assert len(got["a"]) == 2

    def test_the_cap_bounds_a_plural_document(self, isolated_config, monkeypatch):
        self.soft(monkeypatch, [[0.4, 0.3, 0.3], [0.1, 0.9, 0.0], [0.0, 0.1, 0.9]])
        monkeypatch.setattr(config, "TOPIC_MEMBERSHIP_MAX", 2)
        got = topic_model.topic_memberships(FakeClusterer([0, 1, 2]), ["a", "b", "c"],
                                            [0, 1, 2])
        assert len(got["a"]) == 2

    def test_a_seeded_run_has_no_clusterer_to_ask(self, isolated_config):
        """BERTopic swaps in a BaseCluster placeholder when
        zeroshot_topic_list is set. None, not an empty dict: the question
        is unanswerable, not answered with nothing."""
        assert topic_model.topic_memberships(Placeholder(), ["a"], [0]) is None

    def test_an_all_outlier_corpus_has_no_cluster_to_belong_to(self, isolated_config):
        assert topic_model.topic_memberships(FakeClusterer([-1, -1]), ["a", "b"],
                                             [-1, -1]) is None

    def test_a_document_with_no_positive_strength_is_omitted(self, isolated_config,
                                                             monkeypatch):
        self.soft(monkeypatch, [[0.9, 0.1], [0.0, 0.0]])
        got = topic_model.topic_memberships(FakeClusterer([0, 1]), ["a", "b"], [0, 1])
        assert "b" not in got

    def test_switching_it_off_records_nothing(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "TOPIC_DISTRIBUTION", False)
        assert topic_model.topic_memberships(FakeClusterer([0]), ["a"], [0]) is None

    def test_it_reaches_the_artefact(self, isolated_config, fake_bertopic_stack,
                                     tmp_path, monkeypatch):
        """Wired into run_topic_model(), with the scalar surviving beside
        it rather than being replaced."""
        self.soft(monkeypatch, [[0.9, 0.1], [0.1, 0.9]])
        monkeypatch.setattr(FakeHDBSCAN, "labels_", [0, 1], raising=False)
        docs = make_docs_with_text(2, tmp_path)
        FakeBERTopic.topics_returned = [0, 1]
        result = topic_model.run_topic_model(docs)
        assert result["memberships"]["doc0"] == {"0": 0.9}
        assert result["assignments"] == {"doc0": 0, "doc1": 1}


class TestSoftMembershipSeam:
    """The one place the real hdbscan library is exercised rather than
    stubbed. Small and real on purpose: everything above it supplies a
    matrix, so if `all_points_membership_vectors` ever changes shape or
    name, this is what says so."""

    def test_real_hdbscan_yields_a_row_per_point(self, isolated_config):
        import hdbscan
        import numpy as np

        # Two clearly separated blobs, min_cluster_size low enough that a
        # handful of points is a legitimate cluster rather than noise.
        points = np.array([[0.0, 0.0], [0.1, 0.1], [0.0, 0.2], [0.2, 0.0],
                           [9.0, 9.0], [9.1, 9.1], [9.0, 9.2], [9.2, 9.0]])
        clusterer = hdbscan.HDBSCAN(min_cluster_size=3, prediction_data=True).fit(points)
        soft = topic_model._soft_membership(clusterer)
        assert soft.shape[0] == len(points)
        # Always 2-D, even for a single cluster -- topic_memberships zips
        # each row against the column list and a 1-D return would zip the
        # wrong axis silently.
        assert soft.ndim == 2
