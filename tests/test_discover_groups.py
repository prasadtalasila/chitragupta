"""`discover --groups N`: the merge-tree cut's terminal twin (#709).

The property under test: the terminal cuts the same stored `hierarchy`
the app cuts, with the same union-find, the same id-collision
hardening, the same labels and the same nearest-cut honesty --
`tests/webapp/cut_cases.json` is the contract, asserted from node by
tests/webapp/groups.test.js and from here by this module.
"""

import json
from pathlib import Path

from test_discover import GRAPH, TOPIC_SET, write_artefacts

from chitragupta import discover
from chitragupta.discover import _groups

CASES_PATH = Path(__file__).resolve().parent / "webapp" / "cut_cases.json"


def cases() -> list:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]


class TestSharedCases:
    def test_every_shared_cut_case_matches(self):
        rows = cases()
        assert len(rows) >= 5  # non-vacuity
        for row in rows:
            cut = _groups.cut_tree(row["hierarchy"], row["topics"], row["threshold"])
            got = [{"label": g["label"], "members": g["members"]} for g in cut["groups"]]
            assert got == row["expected_groups"], row["name"]

    def test_every_shared_target_case_matches(self):
        targeted = [row for row in cases() if "target" in row]
        assert len(targeted) >= 3  # non-vacuity
        for row in targeted:
            got = _groups.threshold_for_groups(row["hierarchy"], row["topics"], row["target"])
            assert got == row["expected_threshold"], row["name"]


# The standard fixture's graph, given the hierarchy the app's own group
# tests use: the two topics merge at 0.31.
def grouped_graph() -> dict:
    graph = json.loads(json.dumps(GRAPH))
    graph["topics"][0]["size"] = 2
    graph["topics"][1]["size"] = 3
    graph["hierarchy"] = [
        {"id": "node-0", "a": "digital twin", "b": "machine learning", "distance": 0.31}
    ]
    return graph


class TestBuildGroups:
    def test_the_reached_count_is_honest(self):
        data = _groups.build_groups(grouped_graph(), 1)
        assert data == {
            "target": 1,
            "reached": 1,
            "threshold": 0.31,
            "groups": [
                {"label": "machine learning +1", "members": ["digital twin", "machine learning"]}
            ],
        }

    def test_an_unreachable_target_says_what_it_reached(self):
        data = _groups.build_groups(grouped_graph(), 5)
        assert data["target"] == 5
        assert data["reached"] == 2
        prose = _groups.render_groups(data)
        assert "asked for 5" in prose

    def test_a_reached_target_needs_no_apology(self):
        prose = _groups.render_groups(_groups.build_groups(grouped_graph(), 1))
        assert "asked for" not in prose
        assert "machine learning +1" in prose
        assert "  digital twin" in prose


class TestGroupsCli:
    def prepare_grouped(self, cfg):
        write_artefacts(cfg, graph=grouped_graph(), topic_set=TOPIC_SET)

    def test_the_cut_reaches_the_terminal(self, isolated_config, capsys):
        self.prepare_grouped(isolated_config)
        assert discover.main(["--groups", "1"]) == 0
        out = capsys.readouterr().out
        assert "machine learning +1" in out
        assert "cut at merge distance 0.31" in out

    def test_json_carries_the_same_cut(self, isolated_config, capsys):
        self.prepare_grouped(isolated_config)
        assert discover.main(["--json", "--groups", "1"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["reached"] == 1
        assert data["groups"][0]["members"] == ["digital twin", "machine learning"]

    def test_a_treeless_artefact_refuses_and_names_the_stage(self, isolated_config, capsys):
        write_artefacts(isolated_config, graph=GRAPH, topic_set=TOPIC_SET)
        assert discover.main(["--groups", "8"]) == 1
        err = capsys.readouterr().err
        assert "hierarchy" in err
        assert "enrich" in err

    def test_a_target_below_one_is_a_usage_error(self, isolated_config, capsys):
        self.prepare_grouped(isolated_config)
        assert discover.main(["--groups", "0"]) == 2
        assert "--groups" in capsys.readouterr().err

    def test_groups_composes_with_no_other_view(self, isolated_config, capsys):
        self.prepare_grouped(isolated_config)
        assert discover.main(["--groups", "2", "stray phrase"]) == 2
        assert "--groups" in capsys.readouterr().err
        assert discover.main(["--groups", "2", "--why", "a", "b"]) == 2
