"""Filtering the topic graph by where each topic's phrase came from
(#742): `corpus discover --origins seed,keyword,corroborated,emergent`.

The properties under test: origin is defined once and every view reads
the same definition; a corroborated topic -- one both the hand-written
seed file and the extracted keywords file name -- satisfies the seed
predicate and the keyword predicate, so either ticked class shows it;
the flag filters the artefacts the views read, so the terminal list,
`--json`, `--html` and `--app` cannot disagree about what is in the
graph; an unknown or empty selection is a refusal rather than a
silently empty graph; and no flag at all leaves every view exactly as
it was.
"""

import json

import pytest

from chitragupta import config, discover
from chitragupta.discover import _origin

from tests.test_discover import GRAPH, TOPIC_SET, prepare
from tests.test_discover_app import payload_of, write_phrase_files


class TestParse:
    def test_no_flag_selects_every_class(self):
        assert _origin.parse(None) == set(_origin.CLASSES)

    def test_a_subset_parses_to_itself(self):
        assert _origin.parse("seed,emergent") == {"seed", "emergent"}

    def test_spacing_and_case_are_tolerated(self):
        assert _origin.parse(" Seed , EMERGENT ") == {"seed", "emergent"}

    def test_an_unknown_class_refuses_naming_it_and_the_vocabulary(self):
        with pytest.raises(ValueError) as raised:
            _origin.parse("seed,bogus")
        assert "bogus" in str(raised.value)
        assert "corroborated" in str(raised.value)

    def test_an_empty_selection_refuses(self):
        """`--origins ""` and `--origins ,` ask for a graph with no
        topics in it, which is not a view -- and would otherwise render
        as an empty canvas the reader would read as an empty corpus."""
        for value in ("", "  ", ","):
            with pytest.raises(ValueError):
                _origin.parse(value)


class TestClassify:
    def annotate(self, isolated_config, hand=(), extracted=()) -> dict:
        prepare(isolated_config)
        write_phrase_files(hand, extracted)
        topics = json.loads(json.dumps(GRAPH))["topics"]
        _origin.annotate(topics)
        return {t["label"]: t["origin"] for t in topics}

    def test_a_phrase_in_both_files_is_corroborated(self, isolated_config):
        """Case-insensitively, matching `_seed_phrases()`'s dedup rule.
        Named for what it says -- two independent sources agree on this
        topic -- rather than for the set operation behind it."""
        origins = self.annotate(
            isolated_config, hand=("digital twin",), extracted=("Digital TWIN",)
        )
        assert origins["digital twin"] == "corroborated"

    def test_the_graph_nodes_take_the_same_annotation_as_the_app(self, isolated_config):
        """One definition of origin: the app payload and the graph nodes
        the terminal views read are annotated by the same function, so a
        `--json` run and the canvas cannot disagree about a class."""
        prepare(isolated_config)
        write_phrase_files(hand=("digital twin",))
        from chitragupta.discover import _app

        payload = _app.build_app_payload(GRAPH, TOPIC_SET, {})
        nodes = json.loads(json.dumps(GRAPH))["topics"]
        _origin.annotate(nodes)
        assert {t["label"]: t["origin"] for t in payload["topics"]} == {
            t["label"]: t["origin"] for t in nodes
        }


class TestKeep:
    def filtered(self, isolated_config, origins, hand=(), extracted=()):
        prepare(isolated_config)
        write_phrase_files(hand, extracted)
        graph, topic_set = _origin.keep(GRAPH, TOPIC_SET, set(origins))
        return graph, topic_set

    def labels(self, isolated_config, origins, hand=(), extracted=()):
        graph, _ = self.filtered(isolated_config, origins, hand, extracted)
        return [t["label"] for t in graph["topics"]]

    def test_every_class_leaves_the_artefacts_alone(self, isolated_config):
        graph, topic_set = self.filtered(isolated_config, _origin.CLASSES)
        assert graph == GRAPH
        assert topic_set == TOPIC_SET

    def test_emergent_drops_the_seeded_topic(self, isolated_config):
        assert self.labels(isolated_config, {"emergent"}) == ["machine learning"]

    def test_seed_keeps_a_corroborated_topic(self, isolated_config):
        """A corroborated topic *is* seeded, so asking for hand-written
        topics must not hide the ones the corpus also named."""
        labels = self.labels(
            isolated_config, {"seed"}, hand=("digital twin",), extracted=("digital twin",)
        )
        assert labels == ["digital twin"]

    def test_keyword_keeps_a_corroborated_topic(self, isolated_config):
        labels = self.labels(
            isolated_config, {"keyword"}, hand=("digital twin",), extracted=("digital twin",)
        )
        assert labels == ["digital twin"]

    def test_keyword_drops_a_purely_hand_written_topic(self, isolated_config):
        assert self.labels(isolated_config, {"keyword"}, hand=("digital twin",)) == []

    def test_corroborated_keeps_the_intersection(self, isolated_config):
        labels = self.labels(
            isolated_config, {"corroborated"}, hand=("digital twin",), extracted=("digital twin",)
        )
        assert labels == ["digital twin"]

    def test_corroborated_keeps_nothing_else(self, isolated_config):
        assert self.labels(isolated_config, {"corroborated"}, hand=("digital twin",)) == []

    def test_an_edge_with_a_dropped_end_goes_with_it(self, isolated_config):
        """Both families: an edge is a claim about a pair, and half a
        pair is not a weaker claim -- it is a line to a node the reader
        cannot see."""
        graph, _ = self.filtered(isolated_config, {"emergent"})
        assert graph["edges_overlap"] == []
        assert graph["edges_semantic"] == []

    def test_the_topic_set_is_filtered_in_step(self, isolated_config):
        """Or the views refuse for drift: `_page.build_payload` compares
        the two artefacts and raises when one knows a topic the other
        does not."""
        _, topic_set = self.filtered(isolated_config, {"emergent"})
        assert [t["label"] for t in topic_set["topics"]] == ["machine learning"]

    def test_the_stages_own_numbers_are_left_alone(self, isolated_config):
        """`uncovered` and `edges_withheld` are the stage's statements
        about the corpus, not about the reader's current view. Rescaling
        them to a filtered subset would publish a number no stage ever
        produced."""
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["edges_withheld"] = [{"a": "digital twin", "b": "machine learning", "why": "gate"}]
        topic_set = json.loads(json.dumps(TOPIC_SET))
        topic_set["uncovered"] = ["quantum sensing"]
        kept_graph, kept_set = _origin.keep(graph, topic_set, {"emergent"})
        assert kept_graph["edges_withheld"] == graph["edges_withheld"]
        assert kept_set["uncovered"] == ["quantum sensing"]

    def test_a_drifted_topic_set_label_survives_the_filter(self, isolated_config):
        """The filter is subtractive: it removes what the *graph* says is
        an unselected origin, and never a label the graph does not know.
        A topic_set label absent from the graph is drift, and the views
        refuse by name for it -- filtering it away here instead would
        take the refusal with it."""
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["topics"] = [t for t in graph["topics"] if t["label"] != "digital twin"]
        _, topic_set = _origin.keep(graph, TOPIC_SET, {"emergent"})
        assert "digital twin" in [t["label"] for t in topic_set["topics"]]

    def test_a_stored_partition_is_filtered_in_step_with_the_topics(self, isolated_config):
        """`communities` is one cluster id per topic *by position*. Left
        alone while the topic list shrinks, every surviving topic reads
        back the id of whichever topic now sits at its index -- silently
        wrong, which is worse than a crash."""
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["communities"] = {
            "overlap": {"partitions": {"2.0": [7, 9]}},
            "semantic": {"partitions": {"2.0": [1, 2]}},
        }
        kept, _ = _origin.keep(graph, TOPIC_SET, {"emergent"})
        assert [t["label"] for t in kept["topics"]] == ["machine learning"]
        assert kept["communities"]["overlap"]["partitions"]["2.0"] == [9]
        assert kept["communities"]["semantic"]["partitions"]["2.0"] == [2]

    def test_the_stored_path_matrices_go_rather_than_mislead(self, isolated_config):
        """They hold next-hop indices into the edge lists, and a stored
        route may run through a topic the filter removed -- so a
        truncated matrix would point at edges that are gone. Dropping
        them leaves both consumers on the honest path they already have
        for an older artefact."""
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["paths"] = {"overlap": {"next": [[-1, 0], [0, -1]]}}
        kept, _ = _origin.keep(graph, TOPIC_SET, {"emergent"})
        assert "paths" not in kept

    def test_an_unfiltered_run_keeps_both_stored_fields(self, isolated_config):
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["paths"] = {"overlap": {"next": [[-1, 0], [0, -1]]}}
        graph["communities"] = {"overlap": {"partitions": {"2.0": [7, 9]}}}
        kept, _ = _origin.keep(graph, TOPIC_SET, set(_origin.CLASSES))
        assert kept["paths"] == graph["paths"]
        assert kept["communities"]["overlap"]["partitions"]["2.0"] == [7, 9]

    def test_the_originals_are_not_mutated(self, isolated_config):
        before = json.loads(json.dumps(GRAPH))
        self.filtered(isolated_config, {"emergent"})
        assert GRAPH == before


class TestCli:
    def test_the_list_view_shows_only_the_selected_classes(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--origins", "emergent", "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert [t["label"] for t in data["topics"]] == ["machine learning"]

    def test_no_flag_leaves_the_list_view_as_it_was(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert [t["label"] for t in data["topics"]] == ["digital twin", "machine learning"]

    def test_a_topic_the_filter_dropped_is_no_longer_resolvable(self, isolated_config, capsys):
        """The filter applies to the artefacts, not to one view, so a
        phrase that names a filtered-out topic falls through the
        resolution ladder exactly as an unknown phrase does."""
        prepare(isolated_config)
        assert discover.main(["--origins", "emergent", "digital twin", "--json"]) == 1
        assert "digital twin" in capsys.readouterr().err

    def test_an_unknown_class_is_a_refusal_not_a_traceback(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--origins", "bogus"]) == 1
        assert "bogus" in capsys.readouterr().err

    def test_the_refusal_goes_to_stderr_under_json_too(self, isolated_config, capsys):
        """Nothing has reached stdout on this path, so a --json caller
        reads an empty document and a nonzero exit rather than a
        sentence in the stream they opened expecting one."""
        prepare(isolated_config)
        assert discover.main(["--origins", "bogus", "--json"]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "bogus" in captured.err

    def test_the_page_carries_only_the_selected_classes(self, isolated_config, tmp_path):
        prepare(isolated_config)
        page = tmp_path / "graph.html"
        assert discover.main(["--html", str(page), "--origins", "emergent"]) == 0
        text = page.read_text(encoding="utf-8")
        assert "machine learning" in text
        assert '"digital twin"' not in text

    def test_the_app_carries_only_the_selected_classes(self, isolated_config, tmp_path):
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        assert discover.main(["--app", str(app_dir), "--origins", "emergent"]) == 0
        payload = payload_of(app_dir)
        assert [t["label"] for t in payload["topics"]] == ["machine learning"]

    def test_the_app_payload_records_what_shipped(self, isolated_config, tmp_path):
        """So a checkbox for a class the export excluded can say *why*
        it is unavailable, instead of doing nothing when clicked -- the
        reader can tell "filtered out at export" from "this corpus has
        none".

        What it records is the classes that *can* appear, not the words
        the caller typed: `--origins seed` ships corroborated topics
        too, and a corroborated checkbox disabled over corroborated
        topics on the canvas would be a lie."""
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        assert discover.main(["--app", str(app_dir), "--origins", "keyword"]) == 0
        assert payload_of(app_dir)["origins"] == ["keyword", "corroborated"]

    def test_an_unfiltered_app_records_every_class(self, isolated_config, tmp_path):
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        assert discover.main(["--app", str(app_dir)]) == 0
        assert payload_of(app_dir)["origins"] == list(_origin.CLASSES)

    def test_a_paper_view_reads_the_filtered_artefacts(self, isolated_config, capsys):
        """And says the filter is why, rather than sending the reader to
        re-run enrich over a pipeline that is working fine."""
        prepare(isolated_config)
        assert discover.main(["--paper", "p1", "--origins", "emergent", "--json"]) == 1
        err = capsys.readouterr().err
        assert "p1" in err
        assert "emergent" in err
        assert "enrich" not in err

    def test_an_unfiltered_paper_refusal_still_names_the_pipeline(self, isolated_config, capsys):
        prepare(isolated_config)
        assert discover.main(["--paper", "nobody2020"]) == 1
        assert "enrich" in capsys.readouterr().err

    def test_path_refuses_to_compose_with_a_narrowed_graph(self, isolated_config, capsys):
        """The stored next-hop matrices are indexed over the whole graph
        and their routes may run through a filtered-out topic. Exit 2 --
        argparse's usage code, as every other view-combination refusal
        here uses -- rather than a plausible-looking wrong walk."""
        prepare(isolated_config)
        assert (
            discover.main(
                [
                    "--path",
                    "digital twin",
                    "machine learning",
                    "--family",
                    "overlap",
                    "--origins",
                    "emergent",
                ]
            )
            == 2
        )
        assert "--origins" in capsys.readouterr().err

    def test_the_help_says_seed_includes_corroborated(self):
        """The one misreadable thing about the flag, so it belongs where
        the reader meets it rather than only in docs/CLI.md."""
        text = discover.build_parser().format_help()
        assert "corroborated" in text


class TestConfigPaths:
    def test_the_annotation_reads_both_phrase_files(self, isolated_config):
        """A tripwire on the two paths the annotation depends on: if
        either moves, origin silently degrades to provenance and every
        keyword topic reads as a plain seed."""
        assert config.SEED_TOPICS_PATH.name.endswith(".toml")
        assert config.KEYWORDS_PATH.name.endswith(".toml")
