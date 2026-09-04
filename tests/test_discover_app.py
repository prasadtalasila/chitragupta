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
        for name in ("index.html", "style.css", "app.js", "data.js"):
            assert (app_dir / name).is_file(), name
        copied = app_dir / "vendor" / "cytoscape.min.js"
        source = config.shipped("assets", "webapp", "vendor", "cytoscape.min.js")
        assert copied.read_bytes() == source.read_bytes()

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
