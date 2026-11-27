import json
import re

import pytest

from chitragupta import config, discover
from chitragupta.discover import _app, _data

from tests.test_discover import GRAPH, TOPIC_SET, prepare


def write_phrase_files(hand=(), extracted=()):
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
        origins = self.origin(isolated_config, hand=("digital twin",), extracted=("Digital TWIN",))
        assert origins["digital twin"] == "corroborated"

    def test_emergent_stays_emergent_whatever_the_files_say(self, isolated_config):
        origins = self.origin(isolated_config, extracted=("machine learning",))
        assert origins["machine learning"] == "emergent"

    def test_a_seed_topic_in_neither_file_defaults_to_seed(self, isolated_config):
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
        page = config.shipped("assets", "webapp", "index.html").read_text(encoding="utf-8")
        loaded = set(re.findall(r'<script src="\./([^"]+)"></script>', page))
        assert loaded - {"data.js"} <= set(_app.APP_FILES)
        assert {"graph.js", "panel.js", "app.js"} <= loaded

    def test_the_uncovered_panel_names_papers_not_seed_phrases(self):
        page = config.shipped("assets", "webapp", "index.html").read_text(encoding="utf-8")
        panel = re.search(r'<details id="uncovered">(.*?)</details>', page, re.DOTALL).group(1)
        assert "<summary>Uncovered papers</summary>" in panel
        assert "seed" not in panel.lower()

    def test_the_page_loads_the_modules_before_the_wiring_that_uses_them(self):
        order = self.script_order()
        assert order.index("data.js") < order.index("app.js")
        assert order.index("app.js") == len(order) - 1, "the wiring must load last"

    def test_the_page_loads_each_module_after_the_ones_it_requires(self):
        order = self.script_order()
        checked = 0
        for name in order:
            if name == "data.js":  # written per corpus, not shipped
                continue
            source = config.shipped("assets", "webapp", name).read_text(encoding="utf-8")
            for required in re.findall(r'require\("\./([^"]+)"\)', source):
                assert required in order, f"{name} requires unshipped {required}"
                assert order.index(required) < order.index(name), (
                    f"{name} loads before {required}, which it requires"
                )
                checked += 1
        assert checked >= 3, f"only {checked} module dependencies found"

    @staticmethod
    def script_order() -> list:
        page = config.shipped("assets", "webapp", "index.html").read_text(encoding="utf-8")
        order = re.findall(r'<script src="\./([^"]+)"></script>', page)
        assert order, "index.html loads no scripts at all"
        return order

    def test_the_data_script_round_trips_and_escapes(self, isolated_config, tmp_path):
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


class TestPayloadContract:
    @staticmethod
    def app_required() -> list:
        source = config.shipped("assets", "webapp", "payload.js").read_text(encoding="utf-8")
        listed = re.search(r"REQUIRED_KEYS = \[([^\]]*)\]", source)
        assert listed, "payload.js no longer declares REQUIRED_KEYS"
        return re.findall(r'"([a-z_]+)"', listed.group(1))

    def test_the_app_requires_exactly_what_the_exporter_cannot_do_without(self, isolated_config):
        prepare(isolated_config)
        exported = _app.build_app_payload(GRAPH, TOPIC_SET, {})
        required = set()
        for key in GRAPH:
            partial = {name: value for name, value in GRAPH.items() if name != key}
            try:
                _app.build_app_payload(partial, TOPIC_SET, {})
            except KeyError:
                required.add(key)
        assert len(required) >= 4, required
        assert required <= set(exported), "a required graph key is renamed in the payload"
        assert sorted(self.app_required()) == sorted(required)


class TestShippedAppScriptHardening:
    @staticmethod
    def app_js() -> str:
        scripts = [name for name in _app.APP_FILES if name.endswith(".js") and "/" not in name]
        assert scripts, "no interaction scripts left to pin"
        return "\n".join(
            config.shipped("assets", "webapp", name).read_text(encoding="utf-8") for name in scripts
        )

    def test_escape_html_covers_attribute_contexts(self):
        src = self.app_js()
        for entity in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
            assert entity in src, f"escapeHtml no longer escapes {entity}"
        assert "div.innerHTML" not in src, "the quote-blind textContent trick is back"

    def test_label_keyed_tables_are_null_prototype(self):
        assert self.app_js().count("Object.create(null)") >= 4

    def test_page_template_label_keyed_tables_are_null_prototype(self):
        import inspect

        from chitragupta.discover import _page_template

        assert inspect.getsource(_page_template).count("Object.create(null)") >= 2

    def test_page_template_escaper_covers_attribute_contexts(self):
        from chitragupta.discover import _page_template

        esc = re.search(r"function esc\(text\) \{.*?\n\}", _page_template.TEMPLATE, re.S)
        assert esc, "the --html page's esc() is gone or renamed"
        for entity in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
            assert entity in esc.group(0), f"esc() no longer escapes {entity}"


class TestContentSecurityPolicy:
    POLICY = {
        "default-src": ["'none'"],
        "script-src": ["'self'"],
        "style-src": ["'self'", "'unsafe-inline'"],
        "img-src": ["data:"],
        "base-uri": ["'none'"],
        "form-action": ["'none'"],
    }

    @staticmethod
    def page() -> str:
        return config.shipped("assets", "webapp", "index.html").read_text(encoding="utf-8")

    @staticmethod
    def policy_of(page: str) -> dict:
        meta = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', page)
        assert meta, "index.html declares no Content-Security-Policy"
        directives = (d.split() for d in meta.group(1).split(";") if d.strip())
        return {name: values for name, *values in directives}

    def test_the_page_declares_exactly_the_policy(self):
        assert self.policy_of(self.page()) == self.POLICY

    def test_the_policy_precedes_everything_it_governs(self):
        page = self.page()
        meta = page.index('http-equiv="Content-Security-Policy"')
        assert meta < page.index("<link")
        assert meta < page.index("<script")

    def test_the_shipped_code_needs_nothing_the_policy_forbids(self):
        page = self.page()
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", page), "inline <script>"
        assert not re.search(r"\son[a-z]+=", page), "inline event handler in index.html"
        scripts = TestShippedAppScriptHardening.app_js()
        assert not re.search(r"\son[a-z]+=", scripts), "handler in built markup"
        assert not re.search(r"setAttribute\(\s*[\"']on", scripts), "handler set as an attribute"
        assert not re.search(r"set(Timeout|Interval)\(\s*[\"'`]", scripts), "string-form timer"
        assert "javascript:" not in scripts
        assert not re.search(r"\beval\(|new Function\(", scripts)

    def test_the_exported_directory_carries_the_policy(self, isolated_config, tmp_path):
        prepare(isolated_config)
        app_dir = tmp_path / "app"
        _app.write_app(str(app_dir))
        exported = (app_dir / "index.html").read_text(encoding="utf-8")
        assert self.policy_of(exported) == self.POLICY


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
