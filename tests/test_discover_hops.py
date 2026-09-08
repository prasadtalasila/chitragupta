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
        # A row naming its families is what pins the per-family walk to
        # the app's; a table of both-family rows only would let the two
        # surfaces disagree the moment either narrowed.
        assert any("families" in row for row in rows)
        for row in rows:
            graph = {
                "edges_overlap": row["edges_overlap"],
                "edges_semantic": row["edges_semantic"],
            }
            families = row.get("families")
            walked = _hops.hops_from(graph, row["roots"], families)
            assert walked == row["expected_hops"], row["name"]
            typed = _hops.reached_via(graph, row["roots"], families)
            assert typed == row["expected_via"], row["name"]


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

    def test_a_fully_reached_corpus_needs_no_unreached_apology(self):
        graph = self.graph()
        graph["topics"] = [t for t in graph["topics"] if t["label"] != "island"]
        prose = _hops.render_hops(_hops.build_hops(graph, "E", None))
        assert "unreached" not in prose

    def test_an_edge_between_two_roots_types_neither(self):
        """ego.js's mark() skips a pinned end; the port must too, or a
        two-root walk would label a root by the family that reached its
        sibling."""
        graph = self.graph()
        via = _hops.reached_via(graph, ["E", "a"])
        assert "E" not in via
        assert "a" not in via
        assert via["b"] == "semantic"


class TestOneFamily:
    """`--hops N --family F`: the rings over one family, which the app's
    Edges picker asks of the same walk. Until it existed the terminal
    measured over the union whatever the reader wanted, the same defect
    the app had -- so this is the twin, not a new capability."""

    def graph(self) -> dict:
        row = cases()[0]
        return {
            "topics": [{"label": label} for label in ("E", "a", "b", "c", "island")],
            "edges_overlap": row["edges_overlap"],
            "edges_semantic": row["edges_semantic"],
        }

    def test_the_walk_narrows_and_the_payload_says_which(self):
        both = _hops.build_hops(self.graph(), "E", 2)
        assert both["families"] == ["overlap", "semantic"]
        assert [t["label"] for t in both["rings"][1]["topics"]] == ["c"]

        one = _hops.build_hops(self.graph(), "E", 2, ["overlap"])
        assert one["families"] == ["overlap"]
        # `c` was two hops out over a path that changed family. Over
        # shared papers alone it is not two hops out; it is unreached.
        assert [ring["hop"] for ring in one["rings"]] == [1]
        assert [t["label"] for t in one["rings"][0]["topics"]] == ["a"]
        assert one["unreached"] == 3

    def test_ring_one_is_typed_over_the_family_walked(self):
        graph = self.graph()
        graph["edges_semantic"] = graph["edges_semantic"] + [
            {"a": "E", "b": "a", "similarity": 0.5, "bridge": ["p1", "p2"]}
        ]
        assert _hops.reached_via(graph, ["E"])["a"] == "both"
        assert _hops.reached_via(graph, ["E"], ["overlap"])["a"] == "overlap"

    def test_the_prose_names_the_family_it_walked(self):
        prose = _hops.render_hops(_hops.build_hops(self.graph(), "E", 2, ["semantic"]))
        assert "over semantic nearness" in prose
        # With both walked there is nothing to qualify, and a header
        # saying "over both families" on every default run is noise.
        assert "over" not in _hops.render_hops(_hops.build_hops(self.graph(), "E", 2))

    def test_an_unreachable_topic_says_which_family_could_not_reach_it(self):
        prose = _hops.render_hops(_hops.build_hops(self.graph(), "island", 2, ["overlap"]))
        assert "no topic is reachable from here over shared papers" in prose
        assert "in either family" in _hops.render_hops(_hops.build_hops(self.graph(), "island", 2))

    def test_the_families_default_to_both(self):
        """Every caller written before the flag passes three arguments."""
        assert _hops.build_hops(self.graph(), "E", 2) == _hops.build_hops(
            self.graph(), "E", 2, ["overlap", "semantic"]
        )


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

    def test_family_composes_with_hops(self, isolated_config, capsys):
        """The flag existed for --path only and was silently ignored
        everywhere else: `--hops 2 --family semantic` measured over both
        families and said nothing about it."""
        write_artefacts(isolated_config, graph=WHY_GRAPH, topic_set=WHY_TOPIC_SET)
        assert discover.main(["machine learning", "--hops", "all", "--family", "overlap"]) == 0
        out = capsys.readouterr().out
        assert "over shared papers" in out
        assert "formal methods  (via shared papers)" in out

        # WHY_GRAPH holds no semantic edges at all, so the same
        # neighbourhood over that family is empty -- and says so.
        assert discover.main(["machine learning", "--hops", "all", "--family", "semantic"]) == 0
        assert "no topic is reachable from here over semantic nearness" in capsys.readouterr().out

    def test_json_carries_the_families_walked(self, isolated_config, capsys):
        write_artefacts(isolated_config, graph=WHY_GRAPH, topic_set=WHY_TOPIC_SET)
        assert (
            discover.main(["--json", "machine learning", "--hops", "1", "--family", "overlap"]) == 0
        )
        data = json.loads(capsys.readouterr().out)
        assert data["families"] == ["overlap"]

    def test_without_hops_the_flat_topic_view_stays(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["digital twin"]) == 0
        assert "hop distance" not in capsys.readouterr().out
