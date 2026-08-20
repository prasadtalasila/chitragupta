"""chitragupta/seed_topics.py: the hand-authored seed list and the reader
for what it matched.

Stdlib-only on both sides, so these tests need no venv, no model and no
corpus -- which is the property the module was split out for and is
worth keeping true.
"""

import json

import pytest

from chitragupta import config, seed_topics


def write_seed_file(cfg, body: str):
    cfg.SEED_TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg.SEED_TOPICS_PATH.write_text(body, encoding="utf-8")
    return cfg.SEED_TOPICS_PATH


class TestLoad:
    def test_missing_file_is_not_an_error(self, isolated_config):
        """The common case, and the one #206 required stay unchanged: a
        library with no seed file gets no seeding, not a failure."""
        assert not isolated_config.SEED_TOPICS_PATH.exists()
        assert seed_topics.load() == ()

    def test_phrases_survive_whole(self, isolated_config):
        """The invariant the whole feature rests on. A three-word topic
        stays one topic; nothing splits it on whitespace."""
        write_seed_file(isolated_config, 'topics = ["structural health monitoring"]')
        assert seed_topics.load() == ("structural health monitoring",)

    def test_order_is_the_authors_order(self, isolated_config):
        write_seed_file(isolated_config, 'topics = ["zebra", "apple", "mango"]')
        assert seed_topics.load() == ("zebra", "apple", "mango")

    def test_internal_whitespace_normalised_without_splitting(self, isolated_config):
        write_seed_file(isolated_config, 'topics = ["  digital   twin  "]')
        assert seed_topics.load() == ("digital twin",)

    def test_case_insensitive_duplicates_collapse_to_first_spelling(self, isolated_config):
        write_seed_file(isolated_config, 'topics = ["Digital Twin", "digital twin"]')
        assert seed_topics.load() == ("Digital Twin",)

    def test_explicit_path_overrides_config(self, isolated_config, tmp_path):
        elsewhere = tmp_path / "other.toml"
        elsewhere.write_text('topics = ["from elsewhere"]', encoding="utf-8")
        assert seed_topics.load(elsewhere) == ("from elsewhere",)

    def test_absent_topics_key_is_empty_not_an_error(self, isolated_config):
        """A file holding only comments is a seed list the author has not
        filled in yet, not a malformed one."""
        write_seed_file(isolated_config, "# nothing here yet\n")
        assert seed_topics.load() == ()

    def test_malformed_toml_raises(self, isolated_config):
        write_seed_file(isolated_config, "topics = [unclosed")
        with pytest.raises(seed_topics.SeedTopicsError, match="could not be parsed as TOML"):
            seed_topics.load()

    def test_unreadable_file_raises(self, isolated_config, monkeypatch):
        """OSError takes the same path as a parse error: both mean the
        author wrote something that is in force and cannot be applied."""
        write_seed_file(isolated_config, 'topics = ["ok"]')

        def boom(*args, **kwargs):
            raise OSError("permission denied")

        monkeypatch.setattr("builtins.open", boom)
        with pytest.raises(seed_topics.SeedTopicsError, match="could not be parsed"):
            seed_topics.load()

    def test_topics_must_be_an_array(self, isolated_config):
        write_seed_file(isolated_config, 'topics = "digital twin"')
        with pytest.raises(seed_topics.SeedTopicsError, match="must be an array"):
            seed_topics.load()

    def test_entries_must_be_strings(self, isolated_config):
        write_seed_file(isolated_config, "topics = [42]")
        with pytest.raises(seed_topics.SeedTopicsError, match=r"topics\[0\]. must be a string"):
            seed_topics.load()

    def test_empty_entry_raises_rather_than_matching_everything(self, isolated_config):
        write_seed_file(isolated_config, 'topics = ["digital twin", "   "]')
        with pytest.raises(seed_topics.SeedTopicsError, match="is empty"):
            seed_topics.load()


class TestLoadReport:
    def test_missing_artefact_is_an_empty_dict(self, isolated_config):
        assert seed_topics.load_report() == {}

    def test_reads_what_the_stage_wrote(self, isolated_config):
        isolated_config.TOPIC_SEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.TOPIC_SEEDS_PATH.write_text(json.dumps({"n_docs": 3}), encoding="utf-8")
        assert seed_topics.load_report()["n_docs"] == 3

    def test_explicit_path_overrides_config(self, isolated_config, tmp_path):
        elsewhere = tmp_path / "elsewhere.json"
        elsewhere.write_text(json.dumps({"n_docs": 9}), encoding="utf-8")
        assert seed_topics.load_report(elsewhere)["n_docs"] == 9


SAMPLE = {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "min_similarity": 0.5,
    "n_docs": 3,
    "topics": [
        {"phrase": "digital twin",
         "matches": [{"citekey": "alpha_2020", "score": 0.81},
                     {"citekey": "beta_2021", "score": 0.62}]},
        {"phrase": "structural health monitoring",
         "matches": [{"citekey": "alpha_2020", "score": 0.55}]},
    ],
    "unmatched": ["gamma_2022"],
}


class TestReport:
    def test_no_artefact_says_what_to_run(self, isolated_config):
        assert "seed-topics" in seed_topics.report({})

    def test_a_paper_appears_under_every_phrase_it_matched(self, isolated_config):
        """The many-to-many property, asserted rather than assumed:
        alpha_2020 is under both phrases, which is exactly what a
        one-topic-per-document artefact could not represent."""
        text = seed_topics.report(SAMPLE)
        assert text.count("alpha_2020") == 2

    def test_counts_and_coverage_are_reported(self, isolated_config):
        text = seed_topics.report(SAMPLE)
        assert "digital twin  (2 papers)" in text
        assert "3 documents, 2 seed topics, 1 documents matched no topic." in text
        assert "Matched no topic: gamma_2022" in text

    def test_full_coverage_omits_the_unmatched_line(self, isolated_config):
        data = dict(SAMPLE, unmatched=[])
        text = seed_topics.report(data)
        assert "Matched no topic:" not in text
        assert "0 documents matched no topic." in text

    def test_single_topic_view_filters(self, isolated_config):
        text = seed_topics.report(SAMPLE, "digital twin")
        assert "beta_2021" in text
        assert "structural health monitoring" not in text
        # The corpus-wide summary belongs to the whole-corpus view only.
        assert "seed topics," not in text

    def test_single_topic_view_matches_case_and_spacing_insensitively(self, isolated_config):
        assert "alpha_2020" in seed_topics.report(SAMPLE, "  Digital   Twin ")

    def test_unknown_topic_lists_the_known_ones(self, isolated_config):
        text = seed_topics.report(SAMPLE, "quantum gravity")
        assert "No seed topic named" in text
        assert "digital twin" in text

    def test_unknown_topic_with_no_topics_recorded_says_none(self, isolated_config):
        text = seed_topics.report({"topics": []}, "anything")
        assert "none" in text


class TestMain:
    def test_reports_every_topic_and_exits_zero(self, isolated_config, capsys):
        isolated_config.TOPIC_SEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.TOPIC_SEEDS_PATH.write_text(json.dumps(SAMPLE), encoding="utf-8")
        assert seed_topics.main([]) == 0
        assert "digital twin" in capsys.readouterr().out

    def test_missing_artefact_exits_one(self, isolated_config, capsys):
        assert seed_topics.main([]) == 1
        assert "No seed-topic matches recorded yet" in capsys.readouterr().out

    def test_known_topic_exits_zero(self, isolated_config, capsys):
        isolated_config.TOPIC_SEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.TOPIC_SEEDS_PATH.write_text(json.dumps(SAMPLE), encoding="utf-8")
        assert seed_topics.main(["--topic", "digital twin"]) == 0
        assert "beta_2021" in capsys.readouterr().out

    def test_unknown_topic_exits_one(self, isolated_config, capsys):
        isolated_config.TOPIC_SEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
        isolated_config.TOPIC_SEEDS_PATH.write_text(json.dumps(SAMPLE), encoding="utf-8")
        assert seed_topics.main(["--topic", "quantum gravity"]) == 1

    def test_help_names_the_console_script_form(self, isolated_config, monkeypatch):
        monkeypatch.setattr("sys.argv", ["chitragupta"])
        assert seed_topics.build_parser().prog == "chitragupta corpus topics"


class TestDispatch:
    def test_corpus_layer_routes_topics_here(self):
        """The verb is reachable from the corpus layer, which is what
        makes it readable without the venv."""
        from chitragupta import corpus

        assert corpus.VERBS["topics"][0] == "chitragupta.seed_topics"

    def test_config_defaults_are_the_documented_ones(self):
        assert config.SEED_TOPICS_PATH.name == "seed_topics.toml"
        assert config.TOPIC_SEEDS_PATH.name == "topic_seeds.json"
