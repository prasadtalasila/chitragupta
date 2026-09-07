"""`discover --path A B --family F`: the path buttons' terminal twin
(#714), walked from the stored matrices.
"""

import json

from test_discover import write_artefacts
from test_enrich_topic_paths import cases, graph_for

from chitragupta import discover


def prepare(cfg) -> None:
    row = cases()[0]
    graph = dict(graph_for(row), n_docs=9, hierarchy=[])
    for topic in graph["topics"]:
        topic["provenance"] = "seed"
        topic["size"] = 1
    topic_set = {
        "n_docs": 9,
        "topics": [
            {
                "label": t["label"],
                "provenance": "seed",
                "topic_id": i,
                "members": [{"citekey": f"p{i}", "score": 0.5}],
            }
            for i, t in enumerate(graph["topics"])
        ],
        "uncovered": [],
    }
    write_artefacts(cfg, graph=graph, topic_set=topic_set)


class TestPathCli:
    def test_the_walk_reaches_the_terminal(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--path", "A", "Z", "--family", "overlap"]) == 0
        out = capsys.readouterr().out
        assert "path over shared papers: A -> B -> C -> Z" in out
        assert "via: p1" in out

    def test_the_no_path_answer_is_exit_zero(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--path", "B", "Z", "--family", "semantic"]) == 0
        assert "no path over semantic nearness" in capsys.readouterr().out

    def test_json_carries_the_hops_and_the_resolution(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--json", "--path", "A", "Z", "--family", "semantic"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["labels"] == ["A", "Z"]
        assert data["resolved_via"] == {"a": "exact", "b": "exact"}

    def test_a_missing_family_refuses_fusion(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--path", "A", "Z"]) == 2
        assert "never one fused weight" in capsys.readouterr().err

    def test_an_unresolvable_topic_refuses(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--path", "quantum blockchain", "Z", "--family", "overlap"]) == 1
        assert "quantum blockchain" in capsys.readouterr().err

    def test_the_same_topic_twice_refuses(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--path", "A", "A", "--family", "overlap"]) == 1
        assert "same topic" in capsys.readouterr().err

    def test_an_older_artefact_names_the_stage(self, isolated_config, capsys):
        row = cases()[0]
        graph = dict(graph_for(row), n_docs=9, hierarchy=[])
        del graph["paths"]
        for topic in graph["topics"]:
            topic["provenance"] = "seed"
            topic["size"] = 1
        topic_set = {
            "n_docs": 9,
            "topics": [
                {
                    "label": t["label"],
                    "provenance": "seed",
                    "topic_id": i,
                    "members": [{"citekey": f"p{i}", "score": 0.5}],
                }
                for i, t in enumerate(graph["topics"])
            ],
            "uncovered": [],
        }
        write_artefacts(isolated_config, graph=graph, topic_set=topic_set)
        assert discover.main(["--path", "A", "Z", "--family", "overlap"]) == 1
        assert "enrich --stages topic-graph" in capsys.readouterr().err

    def test_path_composes_with_no_other_view(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["stray", "--path", "A", "Z", "--family", "overlap"]) == 2
        assert "--path is its own view" in capsys.readouterr().err
