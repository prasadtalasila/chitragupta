import json
import re

import pytest


from chitragupta import discover
from chitragupta.discover import _data, _page

from tests.test_discover import GRAPH, TOPIC_SET, prepare


class TestPayload:
    def test_every_graph_node_carries_members_titles_and_links(self, isolated_config):
        prepare(isolated_config)
        payload = _page.build_payload(GRAPH, TOPIC_SET, {"digital twin": ["twin"]})
        dt = next(t for t in payload["topics"] if t["label"] == "digital twin")
        assert [m["citekey"] for m in dt["members"]] == ["p1", "p2"]
        assert dt["members"][0]["title"] == "Title of p1"
        assert dt["linked"]["overlap"][0]["shared"] == ["p2"]
        assert payload["hierarchy"] == GRAPH["hierarchy"]

    def test_a_graph_node_the_topic_set_does_not_know_refuses(self, isolated_config):
        prepare(isolated_config)
        topic_set = json.loads(json.dumps(TOPIC_SET))
        topic_set["topics"] = [t for t in topic_set["topics"] if t["label"] != "digital twin"]
        with pytest.raises(_data.MissingArtefact, match="drifted"):
            _page.build_payload(GRAPH, topic_set, {})

    def test_ids_in_the_page_are_index_based(self, isolated_config):
        prepare(isolated_config)
        html = _page.build_html(_page.build_payload(GRAPH, TOPIC_SET, {}))
        assert '"dot-" + index' in html
        assert '"dot-" + label' not in html

    def test_an_empty_topic_set_needs_no_ledger(self, isolated_config):
        empty = {"n_docs": 0, "topics": []}
        graph = {
            "n_docs": 0,
            "topics": [],
            "edges_overlap": [],
            "edges_semantic": [],
            "hierarchy": [],
        }
        payload = _page.build_payload(graph, empty, {})
        assert payload["topics"] == []

    def test_uncovered_seeds_travel_to_the_exported_views(self, isolated_config):
        prepare(isolated_config)
        topic_set = json.loads(json.dumps(TOPIC_SET))
        topic_set["uncovered"] = ["swarm robotics"]
        payload = _page.build_payload(GRAPH, topic_set, {})
        assert payload["uncovered"] == ["swarm robotics"]

    def test_an_artefact_predating_the_field_defaults_to_none_uncovered(self, isolated_config):
        prepare(isolated_config)
        topic_set = {k: v for k, v in json.loads(json.dumps(TOPIC_SET)).items() if k != "uncovered"}
        assert _page.build_payload(GRAPH, topic_set, {})["uncovered"] == []

    def test_stored_analysis_travels_per_topic(self, isolated_config):
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        block = {
            "overlap": {"degree": 1, "ego_density": None, "effective_size": 1.0, "constraint": 1.0}
        }
        graph["topics"][0]["analysis"] = block
        graph["topics"][1]["analysis"] = block
        payload = _page.build_payload(graph, TOPIC_SET, {})
        assert payload["topics"][0]["analysis"] == block
        older = _page.build_payload(GRAPH, TOPIC_SET, {})
        assert all("analysis" not in t for t in older["topics"])

    def test_stored_analysis_travels_per_topic(self, isolated_config):
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        block = {
            "overlap": {"degree": 1, "ego_density": None, "effective_size": 1.0, "constraint": 1.0}
        }
        graph["topics"][0]["analysis"] = block
        graph["topics"][1]["analysis"] = block
        payload = _page.build_payload(graph, TOPIC_SET, {})
        assert payload["topics"][0]["analysis"] == block
        older = _page.build_payload(GRAPH, TOPIC_SET, {})
        assert all("analysis" not in t for t in older["topics"])

    def test_withheld_edges_travel_to_the_exported_views(self, isolated_config):
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["edges_withheld"] = [
            {"a": "digital twin", "b": "machine learning", "shared": ["p2"], "p_value": 0.83}
        ]
        payload = _page.build_payload(graph, TOPIC_SET, {})
        assert payload["edges_withheld"] == graph["edges_withheld"]
        assert _page.build_payload(GRAPH, TOPIC_SET, {})["edges_withheld"] == []


class TestCircleOrder:
    TREE = [
        {"id": "node-0", "a": "b", "b": "c", "distance": 0.1},
        {"id": "node-1", "a": "node-0", "b": "a", "distance": 0.4},
    ]

    def test_leaves_come_out_in_merge_tree_order(self):
        order = _page.dendrogram_order(self.TREE, ["a", "b", "c"])
        assert order == ["b", "c", "a"]

    def test_a_topic_the_tree_never_merged_is_kept(self):
        assert _page.dendrogram_order(self.TREE, ["a", "b", "c", "d"]) == ["b", "c", "a", "d"]

    def test_no_tree_leaves_the_payload_order_alone(self):
        assert _page.dendrogram_order([], ["a", "b"]) == ["a", "b"]

    def test_a_topic_labelled_like_a_merge_id_stays_a_leaf(self):
        tree = [{"id": "node-0", "a": "node-0", "b": "z", "distance": 0.2}]
        assert _page.dendrogram_order(tree, ["node-0", "z"]) == ["node-0", "z"]

    def test_a_tree_naming_one_topic_twice_still_draws_it_once(self):
        tree = [
            {"id": "node-0", "a": "a", "b": "b", "distance": 0.1},
            {"id": "node-1", "a": "a", "b": "c", "distance": 0.2},
        ]
        assert _page.dendrogram_order(tree, ["a", "b", "c"]) == ["a", "b", "c"]

    def test_a_merge_naming_nothing_that_exists_is_skipped(self):
        tree = [{"id": "node-1", "a": "node-0", "b": "a", "distance": 0.3}]
        assert _page.dendrogram_order(tree, ["a", "b"]) == ["a", "b"]

    def test_the_page_embeds_the_topics_in_that_order(self, isolated_config):
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["hierarchy"] = [
            {"id": "node-0", "a": "machine learning", "b": "digital twin", "distance": 0.3}
        ]
        html = _page.build_html(_page.build_payload(graph, TOPIC_SET, {}))
        embedded = re.search(
            r'<script id="data" type="application/json">(.*?)</script>', html, re.S
        ).group(1)
        assert [t["label"] for t in json.loads(embedded)["topics"]] == [
            "machine learning",
            "digital twin",
        ]

    def test_the_payload_the_app_shares_is_not_reordered(self, isolated_config):
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["hierarchy"] = [
            {"id": "node-0", "a": "machine learning", "b": "digital twin", "distance": 0.3}
        ]
        payload = _page.build_payload(graph, TOPIC_SET, {})
        _page.build_html(payload)
        assert [t["label"] for t in payload["topics"]] == ["digital twin", "machine learning"]


class TestHtml:
    def payload(self, cfg) -> dict:
        prepare(cfg)
        return _page.build_payload(GRAPH, TOPIC_SET, {"digital twin": ["twin"]})

    def test_the_page_is_self_contained(self, isolated_config):
        html = _page.build_html(self.payload(isolated_config))
        assert not re.search(r'src\s*=\s*"http', html)
        assert not re.search(r'href\s*=\s*"http', html)
        assert "@import" not in html
        assert "fetch(" not in html

    def test_the_embedded_json_round_trips(self, isolated_config):
        html = _page.build_html(self.payload(isolated_config))
        embedded = re.search(
            r'<script id="data" type="application/json">(.*?)</script>', html, re.S
        ).group(1)
        data = json.loads(embedded)
        assert {t["label"] for t in data["topics"]} == {"digital twin", "machine learning"}

    def test_a_hostile_label_cannot_close_the_script_tag(self, isolated_config):
        prepare(isolated_config)
        graph = json.loads(json.dumps(GRAPH))
        graph["topics"][0]["label"] = "</script><script>alert(1)</script>"
        topic_set = json.loads(json.dumps(TOPIC_SET))
        topic_set["topics"][0]["label"] = graph["topics"][0]["label"]
        html = _page.build_html(_page.build_payload(graph, topic_set, {}))
        payload_zone = html.split('<script id="data"', 1)[1]
        assert "</script><script>alert" not in payload_zone

    def test_both_edge_families_are_drawn_distinctly(self, isolated_config):
        html = _page.build_html(self.payload(isolated_config))
        assert "edge-overlap" in html and "edge-semantic" in html
        assert "stroke-dasharray" in html


class TestPanelFurniture:
    def page(self, cfg) -> str:
        prepare(cfg)
        return _page.build_html(_page.build_payload(GRAPH, TOPIC_SET, {"digital twin": ["twin"]}))

    def show_body(self, html: str) -> str:
        return re.search(r"function show\(index\) \{(.*?)\n\}", html, re.S).group(1)

    def test_the_click_target_is_a_container_of_its_own(self, isolated_config):
        html = self.page(isolated_config)
        body = self.show_body(html)
        assert 'getElementById("detail")' in body
        assert "detail.innerHTML" in body

    def test_a_click_never_writes_over_the_panel_itself(self, isolated_config):
        body = self.show_body(self.page(isolated_config))
        assert "panel.innerHTML" not in body
        assert 'getElementById("panel")' not in body

    def test_the_hierarchy_sits_outside_the_rewritten_container(self, isolated_config):
        html = self.page(isolated_config)
        panel = re.search(r'<div id="panel">.*?</div>\s*<script id="data"', html, re.S).group(0)
        assert '<details id="treebox">' in panel
        detail = panel.split('<div id="detail">', 1)[1]
        assert "treebox" not in detail

    def test_the_empty_tree_branch_still_names_the_disclosure(self, isolated_config):
        html = self.page(isolated_config)
        assert 'getElementById("treebox").style.display = "none"' in html


class TestCli:
    def test_html_writes_the_page_and_exits_zero(self, isolated_config, tmp_path, capsys):
        prepare(isolated_config)
        target = tmp_path / "topics.html"
        assert discover.main(["--html", str(target)]) == 0
        text = target.read_text(encoding="utf-8")
        assert "digital twin" in text
        assert str(target) in capsys.readouterr().out

    def test_html_under_json_emits_a_payload_rather_than_a_sentence(
        self, isolated_config, tmp_path, capsys
    ):
        prepare(isolated_config)
        target = tmp_path / "topics.html"
        assert discover.main(["--html", str(target), "--json"]) == 0
        assert json.loads(capsys.readouterr().out) == {"written": str(target)}

    def test_missing_artefacts_refuse_with_the_stage_to_run(
        self, isolated_config, tmp_path, capsys
    ):
        assert discover.main(["--html", str(tmp_path / "t.html")]) == 1
        assert "topic-graph" in capsys.readouterr().err

    def test_an_unwritable_target_exits_one(self, isolated_config, tmp_path, capsys):
        prepare(isolated_config)
        target = tmp_path / "no-dir" / "t.html"
        assert discover.main(["--html", str(target)]) == 1
        streams = capsys.readouterr()
        assert str(target) in streams.err
        assert str(target) not in streams.out

    def test_an_unwritable_target_under_json_keeps_prose_off_stdout(
        self, isolated_config, tmp_path, capsys
    ):
        prepare(isolated_config)
        target = tmp_path / "no-dir" / "t.html"
        assert discover.main(["--html", str(target), "--json"]) == 1
        streams = capsys.readouterr()
        assert streams.out == ""
        assert str(target) in streams.err
