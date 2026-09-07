"""The topic view's stored-brokerage section (#713).

The property under test: the terminal prints the artefact's own four
numbers with the same reading the app panel gives, and prints nothing
-- recomputing nothing -- for an artefact from an older run.
"""

import json

from test_discover import GRAPH, TOPIC_SET, prepare

from chitragupta import discover
from chitragupta.discover import _render

BLOCK = {
    "overlap": {"degree": 3, "ego_density": 0.0, "effective_size": 3.0, "constraint": 0.39},
    "semantic": {"degree": 0, "ego_density": None, "effective_size": 0, "constraint": None},
}


def analysed_graph() -> dict:
    graph = json.loads(json.dumps(GRAPH))
    for node in graph["topics"]:
        node["analysis"] = json.loads(json.dumps(BLOCK))
    return graph


class TestTopicView:
    def test_the_stored_numbers_reach_the_terminal_with_the_reading(self, isolated_config, capsys):
        prepare(isolated_config)
        write = isolated_config.TOPIC_GRAPH_PATH.write_text
        write(json.dumps(analysed_graph()), encoding="utf-8")
        assert discover.main(["digital twin"]) == 0
        out = capsys.readouterr().out
        assert "brokerage (from the artefact):" in out
        assert "over shared papers: 3 neighbours, density 0.00" in out
        assert "reads as a bridge" in out
        assert "over semantic nearness: no neighbours in this family" in out

    def test_json_carries_the_same_block(self, isolated_config, capsys):
        prepare(isolated_config)
        isolated_config.TOPIC_GRAPH_PATH.write_text(json.dumps(analysed_graph()), encoding="utf-8")
        assert discover.main(["--json", "digital twin"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["brokerage"] == BLOCK

    def test_an_older_artefact_shows_no_section_and_recomputes_nothing(
        self, isolated_config, capsys
    ):
        prepare(isolated_config)
        assert discover.main(["--json", "digital twin"]) == 0
        assert "brokerage" not in json.loads(capsys.readouterr().out)


class TestReadings:
    def test_a_dense_neighbourhood_reads_as_a_theme(self):
        line = _render._brokerage_line(
            {"degree": 2, "ego_density": 1.0, "effective_size": 1.08, "constraint": 1.06}
        )
        assert "reads as a theme" in line

    def test_a_single_neighbour_is_named_not_scored(self):
        line = _render._brokerage_line(
            {"degree": 1, "ego_density": None, "effective_size": 1.0, "constraint": 1.0}
        )
        assert "one neighbour" in line
        assert "density —" in line
