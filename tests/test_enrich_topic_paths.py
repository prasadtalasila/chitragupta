"""chitragupta/enrich/topic_paths.py + discover/_paths.py (#714).

The property under test: walking the stored next-hop matrices yields
exactly the routes the browser's own Dijkstra walks --
`tests/webapp/path_cases.json` is the contract, asserted from node by
tests/webapp/families.test.js and from here by this module.
"""

import json
from pathlib import Path

from chitragupta.discover import _paths
from chitragupta.enrich import topic_paths

CASES_PATH = Path(__file__).resolve().parent / "webapp" / "path_cases.json"


def cases() -> list:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


def graph_for(row: dict) -> dict:
    graph = {
        "topics": [{"label": label} for label in row["topics"]],
        "edges_overlap": row["edges_overlap"],
        "edges_semantic": row["edges_semantic"],
    }
    graph["paths"] = topic_paths.next_hop_matrices(
        row["topics"], row["edges_overlap"], row["edges_semantic"]
    )
    return graph


def test_every_shared_case_matches_when_walked():
    rows = cases()
    assert len(rows) >= 2  # non-vacuity
    for row in rows:
        graph = graph_for(row)
        for family, expected in row["expected"].items():
            for pair, want in expected.items():
                start, goal = pair.split("->")
                result = _paths.walk_path(graph, family, start, goal)
                assert result["labels"] == want, f"{row['name']} {family} {pair}"
                assert result["family"] == family


def test_hops_carry_strength_and_evidence():
    row = cases()[0]
    result = _paths.walk_path(graph_for(row), "overlap", "A", "Z")
    assert [h["evidence"] for h in result["hops"]] == [["p1"], ["p2"], ["p3"]]
    assert all(h["strength"] == 0.9 for h in result["hops"])
    prose = _paths.render_path(result)
    assert "A -> B -> C -> Z" in prose
    assert "via: p1" in prose


def test_the_no_path_answer_renders_as_one():
    row = cases()[1]
    result = _paths.walk_path(graph_for(row), "overlap", "A", "Z")
    assert result["labels"] is None
    assert "no path over shared papers" in _paths.render_path(result)


def test_an_older_artefact_walks_nothing():
    row = cases()[0]
    graph = graph_for(row)
    del graph["paths"]
    assert _paths.walk_path(graph, "overlap", "A", "Z") is None
