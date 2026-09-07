"""The HTML graph page (G9): one self-contained file over the same
artefacts the terminal views read.

The properties under test: the page is a pure renderer of derived data
(never computing an edge), references nothing on the network, and
cannot be broken out of by a hostile label -- the embedded JSON escapes
`<` so no title closes the script tag early.
"""

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
        """One stage re-run without the other is drift; the page must
        refuse like the terminal views, not render empty member lists
        that disagree with --json."""
        prepare(isolated_config)
        topic_set = json.loads(json.dumps(TOPIC_SET))
        topic_set["topics"] = [t for t in topic_set["topics"] if t["label"] != "digital twin"]
        with pytest.raises(_data.MissingArtefact, match="drifted"):
            _page.build_payload(GRAPH, topic_set, {})

    def test_ids_in_the_page_are_index_based(self, isolated_config):
        """A topic label is free text and HTML forbids whitespace in an
        id, so the circles must be addressed by index, never by label."""
        prepare(isolated_config)
        html = _page.build_html(_page.build_payload(GRAPH, TOPIC_SET, {}))
        assert '"dot-" + index' in html
        assert '"dot-" + label' not in html

    def test_an_empty_topic_set_needs_no_ledger(self, isolated_config):
        """No members, no titles to look up -- and therefore no refusal
        for the ledger a fresh project does not have yet."""
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
        """The terminal list view has always reported the seed phrases
        no topic covers; the payload carries the same list so the app
        and the static page can show it too (#717)."""
        prepare(isolated_config)
        topic_set = json.loads(json.dumps(TOPIC_SET))
        topic_set["uncovered"] = ["swarm robotics"]
        payload = _page.build_payload(GRAPH, topic_set, {})
        assert payload["uncovered"] == ["swarm robotics"]

    def test_an_artefact_predating_the_field_defaults_to_none_uncovered(self, isolated_config):
        prepare(isolated_config)
        topic_set = {k: v for k, v in json.loads(json.dumps(TOPIC_SET)).items() if k != "uncovered"}
        assert _page.build_payload(GRAPH, topic_set, {})["uncovered"] == []


class TestCircleOrder:
    """The circle's angular position is the page's strongest channel and
    used to encode nothing: topics sat in whatever order the artefact
    listed them. Ordering by the stored merge tree's leaf order makes
    adjacent positions hold similar topics, which is what shortens the
    chords -- and it is free, since the tree is already in the payload.
    """

    TREE = [
        {"id": "node-0", "a": "b", "b": "c", "distance": 0.1},
        {"id": "node-1", "a": "node-0", "b": "a", "distance": 0.4},
    ]

    def test_leaves_come_out_in_merge_tree_order(self):
        order = _page.dendrogram_order(self.TREE, ["a", "b", "c"])
        assert order == ["b", "c", "a"]

    def test_a_topic_the_tree_never_merged_is_kept(self):
        """`topic_graph.hierarchy` covers only the topics that had a
        centroid, so a topic can be missing from the tree entirely. It
        still has to be drawn, once, rather than silently dropped."""
        assert _page.dendrogram_order(self.TREE, ["a", "b", "c", "d"]) == ["b", "c", "a", "d"]

    def test_no_tree_leaves_the_payload_order_alone(self):
        """A corpus with fewer than two topics with vectors stores an
        empty hierarchy; the page degrades to the arbitrary-but-complete
        circle it drew before, not to an empty one."""
        assert _page.dendrogram_order([], ["a", "b"]) == ["a", "b"]

    def test_a_topic_labelled_like_a_merge_id_stays_a_leaf(self):
        """Merge ids are `node-N` and topic labels are free text, so a
        label can collide with one -- the same hazard as #636's
        `__proto__`. A known label is a leaf whatever the tree calls its
        internal nodes, or the collision would swallow the real topic."""
        tree = [{"id": "node-0", "a": "node-0", "b": "z", "distance": 0.2}]
        assert _page.dendrogram_order(tree, ["node-0", "z"]) == ["node-0", "z"]

    def test_a_tree_naming_one_topic_twice_still_draws_it_once(self):
        """The tree and the topic list are separate artefacts, and
        `build_payload` already refuses one kind of disagreement between
        two of them (a graph node the topic set does not know). Average
        linkage never names a leaf twice, so this is drift rather than
        arithmetic -- and a topic drawn on the circle twice would be a
        page that disagrees with `--json` about how many topics exist."""
        tree = [
            {"id": "node-0", "a": "a", "b": "b", "distance": 0.1},
            {"id": "node-1", "a": "a", "b": "c", "distance": 0.2},
        ]
        assert _page.dendrogram_order(tree, ["a", "b", "c"]) == ["a", "b", "c"]

    def test_a_merge_naming_nothing_that_exists_is_skipped(self):
        """The other direction of the same drift: a merge referring to an
        id that is neither a topic nor another merge. Walking into it
        would raise, and the ordering is a rendering nicety -- losing the
        page over it would be the wrong trade."""
        tree = [{"id": "node-1", "a": "node-0", "b": "a", "distance": 0.3}]
        assert _page.dendrogram_order(tree, ["a", "b"]) == ["a", "b"]

    def test_the_page_embeds_the_topics_in_that_order(self, isolated_config):
        """The template needs no change to benefit: `dot-N` ids, the
        label placement and the panel all index the embedded list, so
        ordering the list is what orders the circle."""
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
        """Ordering is the page's rendering decision, taken at the page
        boundary. `_app.build_app_payload` is `build_payload` plus
        `origin`, and the app has its own layouts -- so reordering in the
        join would have changed the app's payload too, which #670's
        decision puts out of scope."""
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
        # No external fetch of any kind: script/link/img sources, CSS
        # imports, or webfonts would all rot and violate file:// use.
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
        """`--json` means "stdout is a JSON document" on every other
        discover invocation, and `--html` is one more view of the same
        artefacts -- so the write is reported as a payload here too,
        not as the prose line a caller cannot parse."""
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
        # The stream is pinned, not just the text, and unconditionally:
        # a failure line is diagnostics in either mode, which is the rule
        # _topic_view's --out write failure already follows. Reporting it
        # on stdout in one mode and stderr in the other would be two
        # rules for one module.
        assert str(target) in streams.err
        assert str(target) not in streams.out

    def test_an_unwritable_target_under_json_keeps_prose_off_stdout(
        self, isolated_config, tmp_path, capsys
    ):
        """The `--json` half of the rule above: nothing has reached stdout
        by the time the write fails, so an empty stdout and a nonzero exit
        is what the caller reads -- never a sentence in the stream they
        opened expecting a document."""
        prepare(isolated_config)
        target = tmp_path / "no-dir" / "t.html"
        assert discover.main(["--html", str(target), "--json"]) == 1
        streams = capsys.readouterr()
        assert streams.out == ""
        assert str(target) in streams.err
