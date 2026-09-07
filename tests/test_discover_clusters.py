"""chitragupta/discover/_clusters.py: the disagreement grid's terminal
twin over stored partitions (#712).

The property under test: the view reads the builder's partitions and
derives the same two disagreement lists the app's grid shows -- and
refuses (None) for an artefact from an older run rather than clustering
anything itself.
"""

import json

from chitragupta.discover import _clusters
from chitragupta.enrich import topic_mcl

TOPICS = ["a", "b", "c", "d", "e"]
EDGES_OVERLAP = [
    {"a": "a", "b": "b", "overlap_coeff": 0.9, "jaccard": 0.5, "p_value": 0.001, "shared": ["p1"]},
    {"a": "b", "b": "c", "overlap_coeff": 0.2, "jaccard": 0.1, "p_value": 0.005, "shared": ["p2"]},
    {"a": "c", "b": "d", "overlap_coeff": 0.9, "jaccard": 0.5, "p_value": 0.001, "shared": ["p3"]},
]
EDGES_SEMANTIC = [
    {"a": "a", "b": "e", "similarity": 0.8, "bridge": ["p1", "p4"]},
    {"a": "b", "b": "e", "similarity": 0.7, "bridge": ["p2", "p4"]},
]


def graph() -> dict:
    return {
        "topics": [{"label": label} for label in TOPICS],
        "edges_overlap": EDGES_OVERLAP,
        "edges_semantic": EDGES_SEMANTIC,
        "communities": topic_mcl.communities(TOPICS, EDGES_OVERLAP, EDGES_SEMANTIC),
    }


def topic_set() -> dict:
    members = {"a": ["p1"], "b": ["p1", "p2"], "c": ["p2", "p3"], "d": ["p3"], "e": ["p4"]}
    return {
        "topics": [
            {"label": label, "members": [{"citekey": c, "score": 0.5} for c in cites]}
            for label, cites in members.items()
        ]
    }


def test_the_disagreement_lists_read_from_stored_partitions():
    data = _clusters.build_clusters(graph(), topic_set(), 2.0)
    assert data["inflation"] == 2.0
    disagreeing = {(p["a"], p["b"]) for p in data["semantic_only"] + data["overlap_only"]}
    # At inflation 2.0 the stored partitions are overlap [0,0,1,1,2]
    # and semantic [2,2,0,1,2] (mcl_cases.json's own row): a-b agree in
    # both, a-e and b-e are semantic-only, and c-d -- one paper-sharing
    # cluster, two semantic ones -- is the overlap-only reading.
    assert ("a", "e") in disagreeing
    assert ("b", "e") in disagreeing
    assert [(p["a"], p["b"]) for p in data["overlap_only"]] == [("c", "d")]
    assert data["dropped"] == 0
    prose = _clusters.render_clusters(data)
    assert "read from the artefact" in prose
    assert "talk alike, do not share papers" in prose
    assert "no shared papers at all" in prose


def test_shared_counts_sort_the_lists():
    data = _clusters.build_clusters(graph(), topic_set(), 2.0)
    counts = [p["shared"] for p in data["semantic_only"]]
    assert counts == sorted(counts)


def test_an_agreeing_inflation_says_so():
    plain = graph()
    # One family's partitions copied over the other: agreement everywhere.
    plain["communities"]["semantic"] = json.loads(json.dumps(plain["communities"]["overlap"]))
    data = _clusters.build_clusters(plain, topic_set(), 2.0)
    assert data["semantic_only"] == [] and data["overlap_only"] == []
    assert "agree about every pair" in _clusters.render_clusters(data)


def test_the_cap_reports_what_it_dropped(monkeypatch):
    monkeypatch.setattr(_clusters, "MAX_PAIRS", 1)
    data = _clusters.build_clusters(graph(), topic_set(), 2.0)
    assert len(data["semantic_only"]) == 1
    assert data["dropped"] >= 1
    assert "not listed" in _clusters.render_clusters(data)


def test_an_older_artefact_yields_none_not_a_computation():
    old = graph()
    del old["communities"]
    assert _clusters.build_clusters(old, topic_set(), 2.0) is None
    partial = graph()
    # 5.0 is outside the slider's stored range, so no partition exists
    # for it -- unlike 3.05, which would format onto a stored "3.0".
    assert _clusters.build_clusters(partial, topic_set(), 5.0) is None
