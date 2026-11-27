import json
from pathlib import Path

from chitragupta.enrich import topic_mcl

CASES_PATH = Path(__file__).resolve().parent / "webapp" / "mcl_cases.json"


def cases() -> list:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def test_every_shared_case_matches():
    rows = cases()
    assert len(rows) >= 2  # non-vacuity
    for row in rows:
        edges = {"overlap": row["edges_overlap"], "semantic": row["edges_semantic"]}
        for family, expected in row["expected"].items():
            for inflation, want in expected.items():
                result = topic_mcl.cluster(
                    row["topics"],
                    edges[family],
                    topic_mcl._WEIGHT_KEY[family],
                    float(inflation),
                )
                got = [
                    int(result["cluster_of"][label].removeprefix("mcl-")) for label in row["topics"]
                ]
                assert got == want, f"{row['name']} {family} @{inflation}"


def test_communities_cover_every_slider_step():
    row = cases()[0]
    block = topic_mcl.communities(row["topics"], row["edges_overlap"], row["edges_semantic"])
    for family in ("overlap", "semantic"):
        held = block[family]
        assert held["method"] == "mcl"
        assert held["iterations"] == topic_mcl.MAX_ITERATIONS
        assert sorted(held["partitions"]) == sorted(f"{i:.1f}" for i in topic_mcl.INFLATIONS)
        for assignments in held["partitions"].values():
            assert len(assignments) == len(row["topics"])
    assert block["overlap"]["partitions"]["2.0"] == row["expected"]["overlap"]["2.0"]


def test_the_slider_steps_are_the_stored_steps():
    assert topic_mcl.INFLATIONS[0] == 1.2
    assert topic_mcl.INFLATIONS[-1] == 4.0
    assert len(topic_mcl.INFLATIONS) == 29


def test_no_topics_cluster_to_nothing():
    result = topic_mcl.cluster([], [], "overlap_coeff", 2.0)
    assert result == {"clusters": [], "cluster_of": {}}


def test_an_edge_naming_an_unknown_label_is_skipped():
    result = topic_mcl.cluster(
        ["a", "b"], [{"a": "a", "b": "ghost", "overlap_coeff": 0.9}], "overlap_coeff", 2.0
    )
    assert result["cluster_of"] == {"a": "mcl-0", "b": "mcl-1"}


def test_a_capped_iteration_count_still_reads_clusters(monkeypatch):
    monkeypatch.setattr(topic_mcl, "MAX_ITERATIONS", 1)
    row = cases()[0]
    result = topic_mcl.cluster(row["topics"], row["edges_overlap"], "overlap_coeff", 2.0)
    assert sorted(result["cluster_of"]) == sorted(row["topics"])


def test_an_unclaimed_column_stands_alone():
    import numpy as np

    matrix = np.array([[1.0, 0.0], [0.0, 0.0]])
    result = topic_mcl._read_clusters(matrix, ["kept", "orphan"])
    assert result["cluster_of"] == {"kept": "mcl-0", "orphan": "mcl-1"}
    assert result["clusters"][1]["members"] == ["orphan"]
