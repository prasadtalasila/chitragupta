"""The interactive graph app (`corpus discover --app DIR`): a directory
a reader can download whole and open from file://.

The properties under test: the builder is a pure renderer of the same
artefacts every other view reads (it derives no edge and no membership),
the written directory is self-contained (static files copied verbatim
from assets/webapp/, data as a JS assignment because fetch() is blocked
under file://), each topic is annotated with where its phrase came from
(hand-written seed file, extracted keywords file, both, or neither), and
a hostile label cannot break out of the data script -- `<` is escaped
exactly as the --html page escapes it.
"""

import json
import re

import pytest

from chitragupta import config, discover
from chitragupta.discover import _app, _data

from tests.test_discover import GRAPH, TOPIC_SET, prepare


def write_phrase_files(hand=(), extracted=()):
    """The two TOML files `_seed_phrases()` unions, in the shape
    `seed_topics.load()` reads. Either may be absent in a real project,
    which is why both default to "do not write it"."""
    if hand:
        lines = ", ".join(f'"{phrase}"' for phrase in hand)
        config.SEED_TOPICS_PATH.write_text(f"topics = [{lines}]\n", encoding="utf-8")
    if extracted:
        lines = ", ".join(f'"{phrase}"' for phrase in extracted)
        config.KEYWORDS_PATH.write_text(f"topics = [{lines}]\n", encoding="utf-8")


def payload_of(app_dir) -> dict:
    text = (app_dir / "data.js").read_text(encoding="utf-8")
    prefix = "window.CHITRAGUPTA_TOPICS = "
    assert text.startswith(prefix)
    assert text.rstrip().endswith(";")
    return json.loads(text[len(prefix) :].rstrip().removesuffix(";"))


class TestOrigins:
    def origin(self, isolated_config, hand=(), extracted=()) -> dict:
        prepare(isolated_config)
        write_phrase_files(hand, extracted)
        payload = _app.build_app_payload(GRAPH, TOPIC_SET, {})
        return {t["label"]: t["origin"] for t in payload["topics"]}

    def test_a_hand_written_phrase_is_a_seed(self, isolated_config):
        origins = self.origin(isolated_config, hand=("digital twin",))
        assert origins["digital twin"] == "seed"

    def test_an_extracted_phrase_is_a_keyword(self, isolated_config):
        origins = self.origin(isolated_config, extracted=("digital twin",))
        assert origins["digital twin"] == "keyword"

    def test_a_phrase_in_both_files_says_so(self, isolated_config):
        """Case-insensitively, matching `_seed_phrases()`'s dedup rule:
        the hand-written spelling won the union, so the label in the
        artefacts may differ in case from the keywords.toml entry."""
        origins = self.origin(isolated_config, hand=("digital twin",), extracted=("Digital TWIN",))
        assert origins["digital twin"] == "both"

    def test_emergent_stays_emergent_whatever_the_files_say(self, isolated_config):
        origins = self.origin(isolated_config, extracted=("machine learning",))
        assert origins["machine learning"] == "emergent"

    def test_a_seed_topic_in_neither_file_defaults_to_seed(self, isolated_config):
        """The files can move after the stages ran (a deleted phrase, a
        regenerated keywords.toml); the graph's own provenance is still
        true, so the annotation degrades to it rather than refusing."""
        origins = self.origin(isolated_config)
        assert origins["digital twin"] == "seed"

    def test_drift_refuses_like_every_other_view(self, isolated_config):
        prepare(isolated_config)
        topic_set = json.loads(json.dumps(TOPIC_SET))
        topic_set["topics"] = [t for t in topic_set["topics"] if t["label"] != "digital twin"]
        with pytest.raises(_data.MissingArtefact, match="drifted"):
            _app.build_app_payload(GRAPH, topic_set, {})


class TestWriteApp:
    def test_the_directory_is_complete_and_verbatim(self, isolated_config, tmp_path):
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        written = _app.write_app(str(app_dir))
        assert written == str(app_dir)
        for name in _app.APP_FILES + ("data.js",):
            assert (app_dir / name).is_file(), name
        copied = app_dir / "vendor" / "cytoscape.min.js"
        source = config.shipped("assets", "webapp", "vendor", "cytoscape.min.js")
        assert copied.read_bytes() == source.read_bytes()

    def test_every_script_the_page_loads_is_a_file_the_builder_copies(self):
        """The interaction code is several files, so the copy list and
        the page's <script> tags are now two places that must agree. A
        module added to one and not the other is a directory that opens
        to a blank canvas -- and, under file://, to a silent 404 rather
        than an error anyone would see."""
        page = config.shipped("assets", "webapp", "index.html").read_text(encoding="utf-8")
        loaded = set(re.findall(r'<script src="\./([^"]+)"></script>', page))
        # data.js is written per corpus rather than copied, so it is the
        # one script the page loads that APP_FILES does not name.
        assert loaded - {"data.js"} <= set(_app.APP_FILES)
        assert {"graph.js", "panel.js", "app.js"} <= loaded

    def test_the_page_loads_the_modules_before_the_wiring_that_uses_them(self):
        """app.js reads window.CHITRAGUPTA_APP at once, and panel.js
        reads graph.js's origin vocabulary at load: classic scripts run
        in document order, so the order in the file is the contract."""
        page = config.shipped("assets", "webapp", "index.html").read_text(encoding="utf-8")
        order = re.findall(r'<script src="\./([^"]+)"></script>', page)
        assert order.index("graph.js") < order.index("panel.js") < order.index("app.js")
        assert order.index("data.js") < order.index("app.js")

    def test_the_data_script_round_trips_and_escapes(self, isolated_config, tmp_path):
        """`<` must not survive raw: a title like `</script><script>`
        would otherwise close the data script early, the one injection
        route a static JS island has."""
        prepare(isolated_config)
        hostile = json.loads(json.dumps(TOPIC_SET))
        hostile["topics"][0]["members"][0]["citekey"] = "p1"
        config.TOPIC_SET_PATH.write_text(json.dumps(hostile), encoding="utf-8")
        app_dir = tmp_path / "app"
        _app.write_app(str(app_dir))
        text = (app_dir / "data.js").read_text(encoding="utf-8")
        assert "<" not in text.removeprefix("window.CHITRAGUPTA_TOPICS = ")
        payload = payload_of(app_dir)
        labels = [t["label"] for t in payload["topics"]]
        assert labels == ["digital twin", "machine learning"]
        assert payload["n_docs"] == GRAPH["n_docs"]

    def test_a_rerun_refreshes_the_data(self, isolated_config, tmp_path):
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        _app.write_app(str(app_dir))
        grown = json.loads(json.dumps(GRAPH))
        grown["n_docs"] = 99
        config.TOPIC_GRAPH_PATH.write_text(json.dumps(grown), encoding="utf-8")
        _app.write_app(str(app_dir))
        assert payload_of(app_dir)["n_docs"] == 99

    def test_a_missing_graph_refuses_by_name(self, isolated_config, tmp_path):
        with pytest.raises(_data.MissingArtefact):
            _app.write_app(str(tmp_path / "app"))


class TestShippedAppScriptHardening:
    """Source tripwires on the shipped interaction code (#636).

    `tests/webapp/*.test.js` now exercises the two properties below on
    the real functions under `node --test`, which is the better test --
    but it runs on a host that has node, and this suite is what CI's
    coverage leg and every developer runs unconditionally. These stay as
    the source-level tripwire, the same way other non-Python artefacts
    in this repo are pinned, and they read *all* the shipped scripts:
    the escaping lives in panel.js and the null-prototype tables in
    graph.js, and a tripwire naming one file would have been silently
    satisfied by the module split that moved them.

    The hazard, unchanged: a PDF-controlled keyword phrase survives
    `keyword_extract._clean()` with quotes intact and can become a
    seeded topic label.
    """

    @staticmethod
    def app_js() -> str:
        scripts = [name for name in _app.APP_FILES if name.endswith(".js") and "/" not in name]
        assert scripts, "no interaction scripts left to pin"
        return "\n".join(
            config.shipped("assets", "webapp", name).read_text(encoding="utf-8") for name in scripts
        )

    def test_escape_html_covers_attribute_contexts(self):
        # The old div.textContent -> div.innerHTML trick never escapes
        # quotes, and escapeHtml's output lands inside double-quoted
        # data-goto/data-label attributes: a label containing `"` closed
        # the attribute and injected event-handler attributes (stored
        # XSS in the exported page). The explicit replace chain must
        # cover all five significant characters.
        src = self.app_js()
        for entity in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
            assert entity in src, f"escapeHtml no longer escapes {entity}"
        assert "div.innerHTML" not in src, "the quote-blind textContent trick is back"

    def test_label_keyed_tables_are_null_prototype(self):
        # A topic literally labelled __proto__ made `neighbours[label]`
        # return Object.prototype (truthy, no .add) and crashed the app;
        # every table keyed by a free-text label or an origin string must
        # be created with a null prototype.
        assert self.app_js().count("Object.create(null)") >= 4

    def test_page_template_label_keyed_tables_are_null_prototype(self):
        # Same __proto__ hazard in the --html page's inline script: both
        # the position table and the hierarchy's children table are keyed
        # by free-text labels.
        import inspect

        from chitragupta.discover import _page_template

        assert inspect.getsource(_page_template).count("Object.create(null)") >= 2


class TestCli:
    def test_app_flag_writes_the_directory_and_reports_it(self, isolated_config, tmp_path, capsys):
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        assert discover.main(["--app", str(app_dir)]) == 0
        assert (app_dir / "index.html").is_file()
        assert str(app_dir) in capsys.readouterr().out

    def test_app_flag_honours_json_like_html_does(self, isolated_config, tmp_path, capsys):
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        assert discover.main(["--app", str(app_dir), "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["written"] == str(app_dir)

    def test_a_missing_artefact_is_a_refusal_not_a_traceback(
        self, isolated_config, tmp_path, capsys
    ):
        assert discover.main(["--app", str(tmp_path / "app")]) == 1
        assert "enrich" in capsys.readouterr().err

    def test_an_unwritable_target_exits_one_naming_the_path(
        self, isolated_config, tmp_path, capsys
    ):
        prepare(isolated_config)
        blocked = tmp_path / "blocked"
        blocked.write_text("a file where the directory should go", encoding="utf-8")
        assert discover.main(["--app", str(blocked)]) == 1
        assert str(blocked) in capsys.readouterr().err
