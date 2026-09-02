"""chitragupta/enrich/topic_graph.py: the topic graph, derived not divined.

The property under test throughout: **every edge is explainable by
naming real papers**. An overlap edge carries the shared citekeys; a
semantic edge carries the closest bridging pair; neither family is ever
collapsed into the other's score.
"""

import json

import pytest

from chitragupta import config
from chitragupta.enrich import topic_graph


class TestOverlapEdges:
    def test_a_shared_paper_makes_an_edge_when_surprising(self):
        # 3 of a's 3 members inside b's 3, in an 8-doc corpus: the tail
        # is 1/56, well under the floor. (At n_docs=6 it is exactly
        # 0.05 and correctly gated -- the boundary is exclusive.)
        edges = topic_graph.overlap_edges(
            {"a": {"p1", "p2", "p3"}, "b": {"p1", "p2", "p3"}}, n_docs=8, p_value=0.05
        )
        assert len(edges) == 1
        assert edges[0]["shared"] == ["p1", "p2", "p3"]

    def test_no_shared_paper_means_no_edge(self):
        assert topic_graph.overlap_edges({"a": {"p1"}, "b": {"p2"}}, n_docs=4, p_value=0.5) == []

    def test_chance_overlap_is_gated_out(self):
        """Two topics covering most of a small corpus share a paper by
        arithmetic necessity, not by affinity -- the hypergeometric tail
        reads that as unsurprising and the edge is withheld."""
        edges = topic_graph.overlap_edges(
            {"a": {"p1", "p2", "p3"}, "b": {"p3", "p4", "p5"}}, n_docs=5, p_value=0.05
        )
        assert edges == []

    def test_both_coefficients_travel_on_the_edge(self):
        """Jaccard punishes a small topic nested in a big one; the
        overlap coefficient reads containment as containment. Both are
        reported so neither reading is lost."""
        members = {"small": {"p1", "p2"}, "big": {"p1", "p2", "p3", "p4", "p5", "p6"}}
        edges = topic_graph.overlap_edges(members, n_docs=40, p_value=0.05)
        assert edges[0]["jaccard"] == pytest.approx(2 / 6)
        assert edges[0]["overlap_coeff"] == pytest.approx(1.0)

    def test_edges_are_ordered_and_labels_sorted_for_diffability(self):
        members = {
            "zulu": {"p1", "p2"},
            "alpha": {"p1", "p2"},
            "mike": {"p1", "p2"},
        }
        edges = topic_graph.overlap_edges(members, n_docs=50, p_value=0.05)
        pairs = [(e["a"], e["b"]) for e in edges]
        assert all(a < b for a, b in pairs)
        assert pairs == sorted(pairs)


class TestSemanticEdges:
    def test_mutual_neighbours_get_an_edge_with_a_bridge(self):
        vectors = {
            "a": {"p1": [1.0, 0.0], "p2": [0.9, 0.1]},
            "b": {"p3": [0.8, 0.2], "p4": [0.7, 0.3]},
        }
        edges = topic_graph.semantic_edges(vectors, neighbors=1)
        assert len(edges) == 1
        assert edges[0]["bridge"] == ["p1", "p3"] or edges[0]["bridge"] == ["p2", "p3"]
        assert 0.0 < edges[0]["similarity"] <= 1.0

    def test_the_bridge_names_the_closest_pair_across_the_edge(self):
        vectors = {
            "a": {"far": [0.0, 1.0], "near": [1.0, 0.0]},
            "b": {"other": [1.0, 0.05]},
        }
        edges = topic_graph.semantic_edges(vectors, neighbors=1)
        assert edges[0]["bridge"] == ["near", "other"]

    def test_one_sided_affinity_is_not_an_edge(self):
        """c sits closer to a than b does, but a's top-1 neighbour is b
        and b's is a -- so a-c exists only if c also ranks a first AND a
        ranks c within its top k. With k=1 the mutual test prunes the
        asymmetric pair."""
        vectors = {
            "a": {"p1": [1.0, 0.0, 0.0]},
            "b": {"p2": [0.98, 0.2, 0.0]},
            "c": {"p3": [0.0, 0.0, 1.0]},
        }
        edges = topic_graph.semantic_edges(vectors, neighbors=1)
        pairs = {(e["a"], e["b"]) for e in edges}
        assert ("a", "c") not in pairs and ("c", "a") not in pairs

    def test_best_match_average_respects_cluster_shape(self):
        """A crescent's centroid sits outside it. Best-match averaging
        scores by the members that actually face each other, so two
        interlocking clusters keep a high similarity where a
        centroid-to-centroid cosine would dilute it."""
        interlocked = {
            "a": {"p1": [1.0, 0.0], "p2": [-1.0, 0.0]},
            "b": {"p3": [1.0, 0.05], "p4": [-1.0, -0.05]},
        }
        edges = topic_graph.semantic_edges(interlocked, neighbors=1)
        assert edges[0]["similarity"] > 0.95

    def test_a_singleton_corpus_of_topics_has_no_edges(self):
        assert topic_graph.semantic_edges({"a": {"p1": [1.0, 0.0]}}, neighbors=3) == []

    def test_a_zero_vector_scores_zero_instead_of_poisoning_the_json(self):
        """In a one-document corpus the centred vector is exactly zero;
        dividing by its norm would spread NaN through every similarity,
        and json.dumps emits NaN as a bare token no parser accepts."""
        edges = topic_graph.semantic_edges(
            {"a": {"p1": [0.0, 0.0]}, "b": {"p2": [1.0, 0.0]}}, neighbors=1
        )
        assert edges[0]["similarity"] == 0.0
        json.dumps(edges)


class TestHierarchy:
    def test_the_tree_merges_the_closest_topics_first(self):
        merges = topic_graph.hierarchy(
            ["a", "b", "c"],
            [[1.0, 0.0], [0.95, 0.05], [0.0, 1.0]],
        )
        assert len(merges) == 2
        assert {merges[0]["a"], merges[0]["b"]} == {"a", "b"}
        assert merges[0]["distance"] <= merges[1]["distance"]

    def test_a_merge_can_be_referenced_by_a_later_one(self):
        merges = topic_graph.hierarchy(
            ["a", "b", "c"],
            [[1.0, 0.0], [0.95, 0.05], [0.0, 1.0]],
        )
        assert merges[1]["a"] == merges[0]["id"] or merges[1]["b"] == merges[0]["id"]

    def test_fewer_than_two_topics_yield_no_tree(self):
        assert topic_graph.hierarchy(["only"], [[1.0, 0.0]]) == []


class TestBuild:
    def prepare(self):
        topic_set = {
            "n_docs": 4,
            "topics": [
                {
                    "label": "alpha",
                    "provenance": "seed",
                    "topic_id": 0,
                    "members": [{"citekey": "p1", "score": 0.9}, {"citekey": "p2", "score": 0.8}],
                },
                {
                    "label": "beta",
                    "provenance": "emergent",
                    "topic_id": 1,
                    "members": [{"citekey": "p2", "score": 0.7}, {"citekey": "p3", "score": 0.6}],
                },
            ],
        }
        vectors = {
            "p1": [1.0, 0.0, 0.0],
            "p2": [0.9, 0.1, 0.0],
            "p3": [0.8, 0.2, 0.0],
            "p4": [0.0, 0.0, 1.0],
        }
        return topic_set, vectors

    def test_every_topic_is_a_node_with_size_and_centroid(self, isolated_config):
        topic_set, vectors = self.prepare()
        result = topic_graph.build(topic_set, vectors, p_value=0.9, neighbors=2)
        nodes = {t["label"]: t for t in result["topics"]}
        assert nodes["alpha"]["size"] == 2
        assert nodes["beta"]["provenance"] == "emergent"
        assert len(nodes["alpha"]["centroid"]) == 3

    def test_centroids_live_in_centred_space(self, isolated_config):
        """The corpus mean is stored so a reader can move a query into
        the same space; a centroid must therefore be centred, not raw."""
        topic_set, vectors = self.prepare()
        result = topic_graph.build(topic_set, vectors, p_value=0.9, neighbors=2)
        alpha = next(t for t in result["topics"] if t["label"] == "alpha")
        raw = [(1.0 + 0.9) / 2, (0.0 + 0.1) / 2, 0.0]
        mean = result["corpus_mean"]
        assert alpha["centroid"] == pytest.approx([r - m for r, m in zip(raw, mean)])

    def test_a_member_without_a_vector_still_counts_for_overlap(self, isolated_config):
        """Overlap edges are set arithmetic on the ledger's citekeys;
        a paper that never parsed has no vector but is still a member."""
        topic_set, vectors = self.prepare()
        del vectors["p2"]
        result = topic_graph.build(topic_set, vectors, p_value=0.9, neighbors=2)
        overlap = result["edges_overlap"]
        assert overlap and overlap[0]["shared"] == ["p2"]

    def test_a_topic_with_no_vectored_member_gets_no_centroid(self, isolated_config):
        """A seed topic whose every member failed to parse still appears
        as a node (its overlap edges are set arithmetic), but it has no
        centroid, joins no semantic edge, and sits outside the tree."""
        topic_set, vectors = self.prepare()
        del vectors["p1"], vectors["p2"]
        result = topic_graph.build(topic_set, vectors, p_value=0.9, neighbors=2)
        alpha = next(t for t in result["topics"] if t["label"] == "alpha")
        assert alpha["centroid"] == []
        assert all("alpha" not in (e["a"], e["b"]) for e in result["edges_semantic"])

    def test_the_two_edge_families_stay_separate(self, isolated_config):
        topic_set, vectors = self.prepare()
        result = topic_graph.build(topic_set, vectors, p_value=0.9, neighbors=2)
        assert "edges_overlap" in result and "edges_semantic" in result
        for edge in result["edges_overlap"]:
            assert "similarity" not in edge
        for edge in result["edges_semantic"]:
            assert "jaccard" not in edge

    def test_the_stamps_travel_with_the_artefact(self, isolated_config):
        topic_set, vectors = self.prepare()
        result = topic_graph.build(topic_set, vectors, p_value=0.9, neighbors=2)
        assert result["model"] == config.EMBEDDING_MODEL
        assert result["n_docs"] == 4
        assert result["n_topics"] == 2
        assert result["p_value"] == 0.9
        assert result["neighbors"] == 2


class FakeModel:
    def encode(self, texts, show_progress_bar=False):  # pragma: no cover - unused
        raise AssertionError("the graph stage embeds nothing new")


class TestRunTopicGraph:
    def prepare(self, cfg, monkeypatch, vectors, topic_set=None):
        from chitragupta.enrich import doc_vectors, embed_index

        cfg.TOPIC_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg.TOPIC_SET_PATH.write_text(
            json.dumps(
                topic_set
                or {
                    "model": cfg.EMBEDDING_MODEL,
                    "n_docs": 3,
                    "topics": [
                        {
                            "label": "alpha",
                            "provenance": "seed",
                            "topic_id": 0,
                            "members": [
                                {"citekey": "p1", "score": 0.9},
                                {"citekey": "p2", "score": 0.8},
                            ],
                        },
                        {
                            "label": "beta",
                            "provenance": "emergent",
                            "topic_id": 1,
                            "members": [
                                {"citekey": "p2", "score": 0.7},
                                {"citekey": "p3", "score": 0.6},
                            ],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(doc_vectors, "corpus_texts", lambda docs: {c: "text" for c in vectors})
        monkeypatch.setattr(doc_vectors, "document_embeddings", lambda texts, model: vectors)
        monkeypatch.setattr(embed_index, "get_client_and_model", lambda: (None, FakeModel()))

    def test_it_writes_the_artefact(self, isolated_config, monkeypatch):
        self.prepare(
            isolated_config,
            monkeypatch,
            vectors={"p1": [1.0, 0.0], "p2": [0.9, 0.1], "p3": [0.8, 0.2]},
        )
        result = topic_graph.run_topic_graph([])
        written = json.loads(config.TOPIC_GRAPH_PATH.read_text(encoding="utf-8"))
        assert written["n_topics"] == result["n_topics"] == 2
        assert {t["label"] for t in written["topics"]} == {"alpha", "beta"}

    def test_it_refuses_without_a_topic_set(self, isolated_config, monkeypatch):
        with pytest.raises(ValueError, match="converge"):
            topic_graph.run_topic_graph([])

    def test_a_different_embedding_model_refuses_to_graph(self, isolated_config, monkeypatch):
        self.prepare(
            isolated_config,
            monkeypatch,
            vectors={"p1": [1.0, 0.0]},
            topic_set={"model": "someone-elses-model", "n_docs": 1, "topics": []},
        )
        with pytest.raises(ValueError, match="model"):
            topic_graph.run_topic_graph([])


class TestRunStage:
    def test_the_stage_wrapper_skips_rather_than_failing(self, isolated_config):
        result = topic_graph.run_stage([])
        assert result["status"] == "skipped"
        assert "converge" in result["detail"]["reason"]

    def test_the_stage_reports_the_graph_it_built(self, isolated_config, monkeypatch):
        TestRunTopicGraph().prepare(
            isolated_config,
            monkeypatch,
            vectors={"p1": [1.0, 0.0], "p2": [0.9, 0.1], "p3": [0.8, 0.2]},
        )
        result = topic_graph.run_stage([])
        assert result["status"] == "ok"
        detail = result["detail"]
        assert detail["n_topics"] == 2
        assert set(detail) >= {"n_topics", "overlap_edges", "semantic_edges"}
