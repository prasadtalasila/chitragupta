"""`discover TOPIC --hops N`: the ego rings' terminal twin (#716).

The property under test: the terminal walks the same BFS the app's ego
view walks, types ring one by the same rule, and is honest about what
the topic cannot reach -- `tests/webapp/hop_cases.json` is the
contract, asserted from node by tests/webapp/ego.test.js and from here
by this module.
"""

import json
from pathlib import Path

from test_discover import prepare
from test_discover_why import WHY_GRAPH, WHY_TOPIC_SET

from chitragupta import discover
from chitragupta.discover import _hops
from test_discover import write_artefacts

CASES_PATH = Path(__file__).resolve().parent / "webapp" / "hop_cases.json"


def cases() -> list:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


class TestSharedCases:
    def test_every_shared_hop_case_matches(self):
        rows = cases()
        assert len(rows) >= 2  # non-vacuity
        for row in rows:
            graph = {
                "edges_overlap": row["edges_overlap"],
                "edges_semantic": row["edges_semantic"],
            }
            assert _hops.hops_from(graph, row["roots"]) == row["expected_hops"], row["name"]
            assert _hops.reached_via(graph, row["roots"]) == row["expected_via"], row["name"]


class TestBuild:
    def graph(self) -> dict:
        row = cases()[0]
        return {
            "topics": [{"label": label} for label in ("E", "a", "b", "c", "island")],
            "edges_overlap": row["edges_overlap"],
            "edges_semantic": row["edges_semantic"],
        }

    def test_rings_are_typed_at_one_hop_only_and_count_the_unreached(self):
        data = _hops.build_hops(self.graph(), "E", 2)
        assert data["rings"][0]["topics"] == [
            {"label": "a", "via": "overlap"},
            {"label": "b", "via": "semantic"},
        ]
        assert data["rings"][1]["topics"] == [{"label": "c"}]
        assert data["unreached"] == 1
        prose = _hops.render_hops(data)
        assert "a  (via shared papers)" in prose
        assert "unreached from here: 1 topic" in prose

    def test_all_walks_to_the_deepest_ring(self):
        data = _hops.build_hops(self.graph(), "E", None)
        assert data["max_hops"] == "all"
        assert [ring["hop"] for ring in data["rings"]] == [1, 2]

    def test_a_bound_below_the_deepest_ring_cuts_honestly(self):
        data = _hops.build_hops(self.graph(), "E", 1)
        assert [ring["hop"] for ring in data["rings"]] == [1]

    def test_an_isolated_topic_says_so(self):
        prose = _hops.render_hops(_hops.build_hops(self.graph(), "island", 2))
        assert "no topic is reachable from here" in prose


class TestHopsCli:
    def test_the_rings_reach_the_terminal(self, isolated_config, capsys):
        write_artefacts(isolated_config, graph=WHY_GRAPH, topic_set=WHY_TOPIC_SET)
        assert discover.main(["machine learning", "--hops", "all"]) == 0
        out = capsys.readouterr().out
        assert "neighbourhood by hop distance" in out
        assert "formal methods  (via shared papers)" in out

    def test_json_carries_the_resolution(self, isolated_config, capsys):
        write_artefacts(isolated_config, graph=WHY_GRAPH, topic_set=WHY_TOPIC_SET)
        assert discover.main(["--json", "machine learning", "--hops", "1"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["resolved_via"] == "exact"
        assert data["max_hops"] == 1

    def test_a_nonsense_bound_is_a_usage_error(self, isolated_config, capsys):
        write_artefacts(isolated_config, graph=WHY_GRAPH, topic_set=WHY_TOPIC_SET)
        assert discover.main(["machine learning", "--hops", "zero"]) == 2
        assert discover.main(["machine learning", "--hops", "0"]) == 2
        assert "--hops" in capsys.readouterr().err

    def test_without_hops_the_flat_topic_view_stays(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["digital twin"]) == 0
        assert "hop distance" not in capsys.readouterr().out
