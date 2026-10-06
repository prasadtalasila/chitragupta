"""`discover --compare A B [C ...]`: set comparison across topics (#715).

The property under test: the view is pure reading -- members and stored
edges, joined and formatted, with the ledger's own entries on the
bridge papers -- and its refusals are honest about the cap and about
phrases that collapse onto one topic.
"""

import json

from test_discover import make_ledger, place_nowhere, write_artefacts
from test_discover_why import WHY_GRAPH, WHY_TOPIC_SET

from chitragupta import config, discover
from chitragupta.discover import _compare, _resolve


def prepare_three(cfg):
    write_artefacts(cfg, graph=WHY_GRAPH, topic_set=WHY_TOPIC_SET)
    make_ledger(cfg, ["p1", "p2", "p3", "p4", "p5"])


class TestBuild:
    def test_pairs_intersection_union_and_bridges(self, isolated_config):
        prepare_three(isolated_config)
        data = _compare.build_compare(
            ["digital twin", "machine learning", "formal methods"], WHY_GRAPH, WHY_TOPIC_SET
        )
        assert {(p["a"], p["b"]): p["shared"] for p in data["pairs"]} == {
            ("digital twin", "machine learning"): ["p2"],
            ("digital twin", "formal methods"): [],
            ("machine learning", "formal methods"): [],
        }
        assert data["intersection"] == []
        assert data["union"] == 5
        assert [b["citekey"] for b in data["bridges"]] == ["p2"]
        assert data["bridges"][0]["topics"] == ["digital twin", "machine learning"]
        assert "Title of p2" in data["bridges"][0]["entry"]
        # The stored ml-fm overlap edge is among the named topics.
        assert [e["shared"] for e in data["edges"]["overlap"]] == [["p4"]]

    def test_mutual_edges_render_with_their_evidence(self, isolated_config):
        """Both families' edge lines, in prose: the stored ml-fm overlap
        edge, and a semantic edge added among the named topics."""
        prepare_three(isolated_config)
        graph = json.loads(json.dumps(WHY_GRAPH))
        graph["edges_semantic"] = [
            {
                "a": "machine learning",
                "b": "digital twin",
                "similarity": 0.7,
                "bridge": ["p2", "p3"],
            }
        ]
        data = _compare.build_compare(
            ["digital twin", "machine learning", "formal methods"], graph, WHY_TOPIC_SET
        )
        prose = _compare.render_compare(data)
        assert "shared members: machine learning & formal methods  (overlap 0.40, via: p4)" in prose
        assert (
            "semantically near: machine learning & digital twin  (0.70, bridge: p2 <-> p3)" in prose
        )

    def test_edges_outside_the_named_set_stay_out(self, isolated_config):
        prepare_three(isolated_config)
        data = _compare.build_compare(["digital twin", "formal methods"], WHY_GRAPH, WHY_TOPIC_SET)
        assert data["edges"]["overlap"] == []
        prose = _compare.render_compare(data)
        assert "none above the graph's floors" in prose
        assert "held by all 2: none" in prose


class TestCompareCli:
    def test_the_comparison_reaches_the_terminal(self, isolated_config, capsys):
        prepare_three(isolated_config)
        assert discover.main(["--compare", "digital twin", "machine learning"]) == 0
        out = capsys.readouterr().out
        assert "digital twin & machine learning: 1: p2" in out
        assert "bridge papers" in out
        assert "in: digital twin, machine learning" in out

    def test_json_carries_the_resolution(self, isolated_config, capsys):
        prepare_three(isolated_config)
        assert discover.main(["--json", "--compare", "digital twni", "formal methods"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["resolved_via"]["digital twin"] == "fuzzy"
        assert data["union"] == 3

    def test_phrases_collapsing_onto_one_topic_refuse(self, isolated_config, capsys):
        prepare_three(isolated_config)
        assert discover.main(["--compare", "digital twin", "Digital Twin"]) == 1
        assert "fewer than two distinct" in capsys.readouterr().err

    def test_the_cap_is_named_not_silently_truncated(self, isolated_config, capsys):
        prepare_three(isolated_config)
        assert discover.main(["--compare"] + [f"t{i}" for i in range(7)]) == 2
        err = capsys.readouterr().err
        assert "7 were given" in err

    def test_compare_composes_with_no_other_view(self, isolated_config, capsys):
        prepare_three(isolated_config)
        assert discover.main(["--compare", "a", "b", "--why", "c", "d"]) == 2
        assert discover.main(["--compare", "a", "b", "--groups", "2"]) == 2
        # A stray positional phrase reaches compare_view's own guard --
        # it has to come first, or argparse's greedy nargs="+" folds it
        # into the --compare list -- since neither --why nor --groups
        # intercepts.
        assert discover.main(["stray phrase", "--compare", "a", "b"]) == 2
        assert "--compare is its own view" in capsys.readouterr().err

    def test_an_unresolvable_topic_refuses(self, isolated_config, capsys, monkeypatch):
        prepare_three(isolated_config)
        place_nowhere(monkeypatch, "quantum blockchain")
        assert discover.main(["--compare", "digital twin", "quantum blockchain"]) == 1
        assert "quantum blockchain" in capsys.readouterr().err


class TestAModelThatWillNotLoadIsAskedOnce:
    """#1023: `optional_model` re-attempted the bi-encoder and the
    cross-encoder once per phrase, so `--compare A B C` offline paid the
    Hub timeout three times and printed three identical notes. A failure
    is remembered for the process: one attempt per loader, one note."""

    def test_three_phrases_one_attempt_each_and_one_note(
        self, isolated_config, capsys, monkeypatch
    ):
        prepare_three(isolated_config)
        monkeypatch.setattr(config, "RERANK", True)
        attempts = {"model": 0, "reranker": 0}

        def offline(which):
            def load():
                attempts[which] += 1
                raise OSError("We couldn't connect to 'https://huggingface.co'")

            return load

        monkeypatch.setattr(_resolve, "_load_model", offline("model"))
        monkeypatch.setattr(_resolve, "_load_reranker", offline("reranker"))
        phrases = ["twin replica", "learning systems", "formal proofs"]
        assert discover.main(["--compare", *phrases]) == 0
        assert attempts == {"model": 1, "reranker": 1}
        assert capsys.readouterr().out.count("semantic resolution unavailable") == 1

    def test_a_note_sharing_a_part_with_an_earlier_one_repeats_none_of_it(
        self, isolated_config, capsys, monkeypatch
    ):
        """A phrase resolved on the hybrid rung carries the semantic and
        the reranking note joined; one that resolves nowhere carries the
        semantic note alone. Deduplicated by whole note, the semantic
        part printed twice."""
        prepare_three(isolated_config)
        monkeypatch.setattr(config, "RERANK", True)

        def offline():
            raise OSError("offline")

        monkeypatch.setattr(_resolve, "_load_model", offline)
        monkeypatch.setattr(_resolve, "_load_reranker", offline)
        assert discover.main(["--compare", "twin replica", "quantum blockchain"]) == 1
        out = capsys.readouterr().out
        assert out.count("semantic resolution unavailable") == 1
        assert out.count("reranking unavailable") == 1
