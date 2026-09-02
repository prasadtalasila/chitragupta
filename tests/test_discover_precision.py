"""The precision tier over the resolution ladder (G7): cross-encoder
rescoring of the hybrid rung's fused candidates, and a personalised-
PageRank neighbourhood when a query resolves near several topics.

The property under test: precision machinery *reorders* what the ladder
already found and never invents a candidate -- and, like the semantic
rung, it degrades honestly when the enrich extra is absent.
"""

import json

import pytest

from chitragupta import discover
from chitragupta.discover import _resolve, _walk

from tests.test_discover import GRAPH, TOPIC_SET, FakeModel, prepare


class FakeReranker:
    """Scores each (query, text) pair by a table, so a test can invert
    the fused order and assert the cross-encoder's ranking won."""

    SCORES: dict = {}

    def predict(self, pairs):
        return [self.SCORES.get(text, 0.0) for _query, text in pairs]


class TestCrossEncoderRescoring:
    def test_the_reranker_reorders_the_fused_candidates(self, isolated_config, monkeypatch):
        """BM25 and cosine both fuse 'machine learning' ahead; the
        cross-encoder disagrees, and its ordering is the contract."""
        FakeModel.VECTORS = {"learning about twins": [-1.0, 1.0]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())
        FakeReranker.SCORES = {
            "digital twin twin simulation": 9.0,
            "machine learning learning models": 1.0,
        }
        monkeypatch.setattr(_resolve, "_load_reranker", lambda: FakeReranker())
        resolution = _resolve.resolve(
            "learning about twins",
            GRAPH,
            TOPIC_SET,
            {"digital twin": ["twin", "simulation"], "machine learning": ["learning", "models"]},
            min_similarity=0.1,
        )
        assert resolution.via == "hybrid"
        assert resolution.label == "digital twin"
        assert resolution.ranked[0] == "digital twin"

    def test_without_the_reranker_the_fused_order_stands(self, isolated_config, monkeypatch):
        FakeModel.VECTORS = {"learning models": [-1.0, 1.0]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())

        def refuse():
            raise ImportError("no cross-encoder")

        monkeypatch.setattr(_resolve, "_load_reranker", refuse)
        resolution = _resolve.resolve(
            "learning models",
            GRAPH,
            TOPIC_SET,
            {"machine learning": ["learning", "models"]},
            min_similarity=0.1,
        )
        assert resolution.via == "hybrid"
        assert resolution.label == "machine learning"

    def test_the_reranker_never_invents_a_candidate(self, isolated_config, monkeypatch):
        FakeModel.VECTORS = {"twins": [1.0, 0.0]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())
        FakeReranker.SCORES = {"not a topic": 99.0}
        monkeypatch.setattr(_resolve, "_load_reranker", lambda: FakeReranker())
        resolution = _resolve.resolve("twins", GRAPH, TOPIC_SET, {}, min_similarity=0.1)
        assert set(resolution.ranked) <= {"digital twin", "machine learning"}


class TestPersonalisedPageRank:
    GRAPH_3 = {
        "topics": [
            {"label": "a"},
            {"label": "b"},
            {"label": "c"},
            {"label": "d"},
        ],
        "edges_overlap": [
            {"a": "a", "b": "b", "overlap_coeff": 0.9, "jaccard": 0.5, "shared": ["p1"]},
        ],
        "edges_semantic": [
            {"a": "b", "b": "c", "similarity": 0.8, "bridge": ["p1", "p2"]},
        ],
    }

    def test_mass_flows_from_the_seed_along_edges(self):
        ranking = _walk.personalised_pagerank(self.GRAPH_3, seeds=["a"])
        order = [label for label, _ in ranking]
        # b is adjacent to the seed, c two hops out, d disconnected.
        assert order.index("b") < order.index("c") < order.index("d")

    def test_two_seeds_pull_their_shared_neighbour_up(self):
        ranking = dict(_walk.personalised_pagerank(self.GRAPH_3, seeds=["a", "c"]))
        assert ranking["b"] > ranking["d"]

    def test_an_empty_graph_ranks_nothing(self):
        assert (
            _walk.personalised_pagerank(
                {"topics": [], "edges_overlap": [], "edges_semantic": []}, seeds=["a"]
            )
            == []
        )

    def test_scores_are_a_distribution(self):
        ranking = _walk.personalised_pagerank(self.GRAPH_3, seeds=["a"])
        assert sum(score for _, score in ranking) == pytest.approx(1.0)


class TestNeighbourhoodInTheView:
    def test_a_plural_resolution_carries_a_ppr_neighbourhood(
        self, isolated_config, capsys, monkeypatch
    ):
        prepare(isolated_config)
        FakeModel.VECTORS = {"twin learning systems": [0.4, -0.1]}
        monkeypatch.setattr(_resolve, "_load_model", lambda: FakeModel())
        FakeReranker.SCORES = {}
        monkeypatch.setattr(_resolve, "_load_reranker", lambda: FakeReranker())
        assert discover.main(["twin learning systems", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["resolved_via"] == "hybrid"
        labels = [n["label"] for n in data["neighbourhood"]]
        assert set(labels) == {"digital twin", "machine learning"}

    def test_an_exact_resolution_has_no_neighbourhood_block(self, isolated_config, capsys):
        """One rung, one answer: the linked-topics lists already cover a
        singular resolution, and a PPR over one seed would restate them."""
        prepare(isolated_config)
        assert discover.main(["digital twin", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert "neighbourhood" not in data
