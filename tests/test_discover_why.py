"""`discover --why A B`: the absence verdict's terminal twin (#708).

The property under test: the terminal names the same shared papers, the
same hypergeometric tail and the same drawn/withheld verdict the app's
`assets/webapp/absence.js` computes -- from the same artefacts -- and
does one thing the app cannot: it names the gate's own threshold, which
the artefact stores and the app payload drops.
"""

import json

from test_discover import GRAPH, TOPIC_SET, prepare, write_artefacts
from test_webapp_hypergeometric import cases

from chitragupta import discover
from chitragupta.discover import _absence

# A withheld pair: the documented worked example (one shared paper
# between topics of size 2 and 3 in a 4-paper corpus, p = 1.0) with a
# third topic sharing nothing, so every verdict below has a subject.
WHY_GRAPH = {
    "model": "the-model",
    "n_docs": 4,
    "n_topics": 3,
    "p_value": 0.01,
    "corpus_mean": [0.5, 0.5],
    "topics": [
        {"label": "digital twin", "provenance": "seed", "size": 2, "centroid": [0.5, -0.5]},
        {"label": "machine learning", "provenance": "emergent", "size": 3, "centroid": [-0.5, 0.5]},
        {"label": "formal methods", "provenance": "seed", "size": 1, "centroid": [0.1, 0.9]},
    ],
    # An edge between a *different* pair, so the stored-edge scan has
    # something to walk past for every pair the tests ask about.
    "edges_overlap": [
        {
            "a": "machine learning",
            "b": "formal methods",
            "jaccard": 0.2,
            "overlap_coeff": 0.4,
            "p_value": 0.004,
            "shared": ["p4"],
        }
    ],
    "edges_semantic": [],
    "hierarchy": [],
}

WHY_TOPIC_SET = {
    "model": "the-model",
    "n_docs": 4,
    "topics": [
        {
            "label": "digital twin",
            "provenance": "seed",
            "topic_id": 0,
            "members": [{"citekey": "p1", "score": 0.9}, {"citekey": "p2", "score": 0.8}],
        },
        {
            "label": "machine learning",
            "provenance": "emergent",
            "topic_id": 1,
            "members": [
                {"citekey": "p2", "score": 0.7},
                {"citekey": "p3", "score": 0.6},
                {"citekey": "p4", "score": 0.5},
            ],
        },
        {
            "label": "formal methods",
            "provenance": "seed",
            "topic_id": 2,
            "members": [{"citekey": "p5", "score": 0.4}],
        },
    ],
    "uncovered": [],
}


class TestSurvival:
    def test_every_shared_case_matches(self):
        """The same contract absence.js honours: every row of
        tests/webapp/hypergeometric_cases.js, to the same precision the
        node suite demands of the browser."""
        rows = cases()
        assert len(rows) >= 10  # non-vacuity, as the scipy twin asserts
        for row in rows:
            got = _absence.survival(row["k"], row["docs"], row["a"], row["b"])
            assert abs(got - row["p"]) <= 1e-12 * max(row["p"], 1e-300), row

    def test_the_boundaries_short_circuit(self):
        assert _absence.survival(0, 10, 3, 4) == 1.0
        assert _absence.survival(4, 10, 3, 4) == 0.0

    def test_choosing_more_than_there_is_has_no_weight(self):
        """The same guard absence.js's logChoose carries: k outside
        [0, n] is log(0), not an error."""
        assert _absence._log_choose(3, 5) == float("-inf")


class TestExplain:
    def test_a_withheld_pair_reads_as_chance(self):
        data = _absence.explain(WHY_GRAPH, WHY_TOPIC_SET, "digital twin", "machine learning")
        assert data["shared"] == ["p2"]
        assert data["p"] == 1.0
        assert data["sizes"] == {"a": 2, "b": 3}
        assert data["docs"] == 4
        assert data["drawn"] is False
        assert data["threshold"] == 0.01
        assert data["verdict"] == "withheld-chance"

    def test_nothing_shared_has_no_tail(self):
        data = _absence.explain(WHY_GRAPH, WHY_TOPIC_SET, "digital twin", "formal methods")
        assert data["shared"] == []
        assert data["p"] is None
        assert data["verdict"] == "nothing-shared"

    def test_a_drawn_edge_reports_the_stored_p(self):
        data = _absence.explain(GRAPH, TOPIC_SET, "machine learning", "digital twin")
        assert data["drawn"] is True
        assert data["verdict"] == "drawn"
        assert data["p"] == 0.004  # the stored edge's own p, not a recomputation

    def test_a_surprising_overlap_with_no_edge_is_named_as_such(self):
        """p below the stored threshold yet no edge: the artefact is
        internally inconsistent (an older run, usually), and the verdict
        must not blame the gate."""
        graph = dict(WHY_GRAPH) | {"n_docs": 497, "p_value": 0.01}
        topic_set = json.loads(json.dumps(WHY_TOPIC_SET))
        topic_set["topics"][0]["members"] = [
            {"citekey": f"a{i}", "score": 0.5} for i in range(17)
        ] + [{"citekey": f"s{i}", "score": 0.5} for i in range(8)]
        topic_set["topics"][1]["members"] = [
            {"citekey": f"b{i}", "score": 0.5} for i in range(32)
        ] + [{"citekey": f"s{i}", "score": 0.5} for i in range(8)]
        data = _absence.explain(graph, topic_set, "digital twin", "machine learning")
        assert data["p"] < 0.01
        assert data["verdict"] == "withheld-unexplained"
        prose = _absence.render(data)
        assert "chance does not readily explain" in prose
        assert "disagrees with itself" in prose

    def test_the_documented_default_covers_an_artefact_without_a_threshold(self):
        graph = {k: v for k, v in WHY_GRAPH.items() if k != "p_value"}
        data = _absence.explain(graph, WHY_TOPIC_SET, "digital twin", "machine learning")
        assert data["threshold"] == 0.01
        assert data["verdict"] == "withheld-chance"

    def test_prose_names_the_numbers(self):
        data = _absence.explain(WHY_GRAPH, WHY_TOPIC_SET, "digital twin", "machine learning")
        prose = _absence.render(data)
        assert "p2" in prose
        assert "p = 1.00" in prose
        assert "no edge" in prose
        prose = _absence.render(
            _absence.explain(WHY_GRAPH, WHY_TOPIC_SET, "digital twin", "formal methods")
        )
        assert "share no papers" in prose
        prose = _absence.render(
            _absence.explain(GRAPH, TOPIC_SET, "digital twin", "machine learning")
        )
        assert "carries an overlap edge" in prose


class TestWhyCli:
    def prepare_why(self, cfg):
        write_artefacts(cfg, graph=WHY_GRAPH, topic_set=WHY_TOPIC_SET)

    def test_the_verdict_reaches_the_terminal(self, isolated_config, capsys):
        self.prepare_why(isolated_config)
        assert discover.main(["--why", "digital twin", "machine learning"]) == 0
        out = capsys.readouterr().out
        assert "chance predicts" in out
        assert "0.01" in out  # the threshold the app cannot name

    def test_json_mirrors_the_app_verdict_shape(self, isolated_config, capsys):
        self.prepare_why(isolated_config)
        assert discover.main(["--json", "--why", "digital twin", "machine learning"]) == 0
        data = json.loads(capsys.readouterr().out)
        for key in ("shared", "p", "sizes", "docs", "drawn", "threshold", "verdict"):
            assert key in data
        assert data["resolved_via"] == {"a": "exact", "b": "exact"}

    def test_the_ladder_resolves_a_typo(self, isolated_config, capsys):
        self.prepare_why(isolated_config)
        assert discover.main(["--why", "digital twni", "machine learning"]) == 0
        assert "digital twin" in capsys.readouterr().out

    def test_an_unresolvable_topic_refuses(self, isolated_config, capsys):
        self.prepare_why(isolated_config)
        assert discover.main(["--why", "quantum blockchain", "machine learning"]) == 1
        assert "quantum blockchain" in capsys.readouterr().err

    def test_the_same_topic_twice_refuses(self, isolated_config, capsys):
        self.prepare_why(isolated_config)
        assert discover.main(["--why", "digital twin", "Digital Twin"]) == 1
        assert "same topic" in capsys.readouterr().err

    def test_why_composes_with_no_other_view(self, isolated_config, capsys):
        self.prepare_why(isolated_config)
        assert discover.main(["--why", "a", "b", "stray phrase"]) == 2
        assert "--why" in capsys.readouterr().err

    def test_a_drawn_pair_on_the_standard_fixture(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--why", "digital twin", "machine learning"]) == 0
        assert "carries an overlap edge" in capsys.readouterr().out
