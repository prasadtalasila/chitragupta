import importlib
import os
from pathlib import Path

import pytest

from chitragupta import config, config_load
from tests.conftest import run_python


class TestGetHelpers:
    def test_env_var_wins_over_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"section": {"key": "from-toml"}})
        monkeypatch.setenv("MY_VAR", "from-env")
        assert config._get("MY_VAR", "section", "key", default="fallback") == "from-env"

    def test_falls_back_to_toml_path(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"section": {"key": "from-toml"}})
        monkeypatch.delenv("MY_VAR", raising=False)
        assert config._get("MY_VAR", "section", "key", default="fallback") == "from-toml"

    def test_default_when_toml_path_missing(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"section": {}})
        monkeypatch.delenv("MY_VAR", raising=False)
        assert config._get("MY_VAR", "section", "key", default="fallback") == "fallback"

    def test_default_when_toml_path_not_a_dict(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"section": "not-a-dict"})
        monkeypatch.delenv("MY_VAR", raising=False)
        assert config._get("MY_VAR", "section", "key", default="fallback") == "fallback"

    def test_raises_when_leaf_is_not_a_string(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"section": {"key": 123}})
        monkeypatch.delenv("MY_VAR", raising=False)
        with pytest.raises(ValueError, match="must be a string"):
            config._get("MY_VAR", "section", "key", default="fallback")

    def test_float_env_var_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"timeout": 3.0}})
        monkeypatch.setenv("MY_TIMEOUT", "9.5")
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.0) == 9.5

    def test_float_falls_back_to_toml_number(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"timeout": 3}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.0) == 3.0

    def test_float_default_when_missing(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5) == 1.5

    def test_float_default_when_not_a_dict(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": "nope"})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5) == 1.5

    def test_float_raises_when_bool_in_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"timeout": True}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        with pytest.raises(ValueError, match="must be a number"):
            config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5)

    def test_float_raises_when_string_in_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"timeout": "3.0"}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        with pytest.raises(ValueError, match="must be a number"):
            config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5)

    def test_float_raises_named_error_on_unparseable_env_var(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"timeout": 3.0}})
        monkeypatch.setenv("MY_TIMEOUT", "not-a-number")
        with pytest.raises(ValueError, match="MY_TIMEOUT.*must be a number"):
            config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5)

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("1", True),
            ("true", True),
            ("TRUE", True),
            ("yes", True),
            ("on", True),
            (" true ", True),
            ("0", False),
            ("false", False),
            ("FALSE", False),
            ("no", False),
            ("off", False),
            ("", False),
        ],
    )
    def test_bool_env_var_parses_words_not_truthiness(self, monkeypatch, raw, expected):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"flag": not expected}})
        monkeypatch.setenv("MY_FLAG", raw)
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=not expected) is expected

    @pytest.mark.parametrize("raw", ["ture", "flase", "2", "enabled", "y", "nope"])
    def test_bool_env_var_rejects_a_word_it_does_not_know(self, monkeypatch, raw):
        monkeypatch.setenv("MY_FLAG", raw)
        with pytest.raises(ValueError, match="MY_FLAG.*must be true or false"):
            config._get_bool("MY_FLAG", "enrich", "flag", default=True)

    @pytest.mark.parametrize("value", [True, False])
    def test_bool_env_and_toml_agree_on_every_value_toml_can_spell(self, monkeypatch, value):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"flag": value}})
        monkeypatch.delenv("MY_FLAG", raising=False)
        from_toml = config._get_bool("MY_FLAG", "enrich", "flag", default=not value)
        monkeypatch.setenv("MY_FLAG", str(value).lower())
        from_env = config._get_bool("MY_FLAG", "enrich", "flag", default=not value)
        assert from_toml is from_env is value

    @pytest.mark.parametrize(
        "getter,kwargs",
        [
            (config_load._get_bool, {"default": False}),
            (config_load._get_float, {"default": 1.0}),
            (config_load._get_int, {"default": 1}),
            (config_load._get_positive_int, {"default": 1}),
            (config_load._get_optional_positive_int, {}),
            (config_load._get_optional_float, {"default": 1.0}),
            (config_load._get_workers, {"default": 1}),
            (config_load._get_choice, {"default": "a", "choices": ("a", "b")}),
        ],
    )
    @pytest.mark.parametrize("raw", ["ture", "1.5x", "nope"])
    def test_every_typed_getter_rejects_an_unreadable_env_string(
        self, monkeypatch, getter, kwargs, raw
    ):
        monkeypatch.setenv("MY_SETTING", raw)
        with pytest.raises(ValueError, match="MY_SETTING"):
            getter("MY_SETTING", "enrich", "setting", **kwargs)

    def test_bool_falls_back_to_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"flag": False}})
        monkeypatch.delenv("MY_FLAG", raising=False)
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=True) is False

    def test_bool_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("MY_FLAG", raising=False)
        monkeypatch.setattr(config_load, "_toml", {"enrich": {}})
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=True) is True
        monkeypatch.setattr(config_load, "_toml", {"enrich": "nope"})
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=True) is True

    def test_bool_raises_when_toml_leaf_is_not_a_bool(self, monkeypatch):
        monkeypatch.delenv("MY_FLAG", raising=False)
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"flag": "yes"}})
        with pytest.raises(ValueError, match="must be true or false"):
            config._get_bool("MY_FLAG", "enrich", "flag", default=False)

    def test_int_env_var_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": 3}})
        monkeypatch.setenv("MY_COUNT", "9")
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 9

    def test_int_falls_back_to_toml_number(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": 3}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 3

    def test_int_default_when_missing(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=5) == 5

    def test_int_accepts_a_whole_valued_float(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": 3.0}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 3

    def test_int_accepts_a_quoted_whole_number_in_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": "3"}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 3

    def test_int_raises_on_fractional_toml_value(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": 3.9}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    def test_int_raises_on_fractional_env_var(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": 3}})
        monkeypatch.setenv("MY_COUNT", "3.5")
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    def test_int_raises_on_bool_in_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": True}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    @pytest.mark.parametrize("raw", ["3.0", "1e3"])
    def test_int_raises_on_a_float_shaped_string(self, monkeypatch, raw):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": raw}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    def test_int_raises_on_non_numeric_string(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"count": "many"}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)


class TestRealConfigToml:
    def test_bib_file_path_under_repo_root(self):
        assert config.BIB_FILE_PATH == config.PROJECT_ROOT / "papers" / "bibliography.bib"

    def test_content_dir_layout(self):
        assert config.CONTENT_DIR == config.PROJECT_ROOT / "content"
        assert config.PARSED_DIR == config.CONTENT_DIR / "parsed"
        assert config.LEDGER_PATH == config.CONTENT_DIR / "ledger.sqlite"
        assert config.RETRIEVAL_INDEX_PATH == config.CONTENT_DIR / "retrieval_index.json"

    def test_embedding_model_default(self):
        assert config.EMBEDDING_MODEL == "sentence-transformers/all-mpnet-base-v2"

    def test_csl_style_defaults_to_the_vendored_ieee_style(self):
        assert config.CSL_STYLE_PATH == config.shipped("assets", "csl", "ieee.csl")
        assert config.CSL_STYLE_PATH.is_file()

    def test_citations_collapse_by_default(self):
        assert config.RENDER_COLLAPSE_CITATIONS is True

    def test_acronyms_points_at_the_projects_own_file(self):
        assert config.ACRONYMS_PATH == config.PROJECT_ROOT / "content" / "acronyms.toml"

    def test_the_vendored_floor_is_still_vendored_and_still_loads(self):
        assert config.ACRONYMS_DEFAULT_PATH == (config.shipped("assets", "style", "acronyms.toml"))
        assert config.ACRONYMS_DEFAULT_PATH.is_file()

    def test_acronym_expansion_is_on_in_the_shipped_config(self):
        assert config.ACRONYM_EXPANSION is True


class TestGetWorkers:
    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {}})

    def test_missing_key_uses_default(self):
        assert config._get_workers("W", "parser", "workers", default=1) == 1

    def test_int_from_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"workers": 8}})
        assert config._get_workers("W", "parser", "workers", default=1) == 8

    def test_auto_from_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"workers": "auto"}})
        assert config._get_workers("W", "parser", "workers", default=1) == "auto"

    @pytest.mark.parametrize("raw", ["auto", "AUTO", " Auto "])
    def test_auto_is_case_and_space_insensitive(self, monkeypatch, raw):
        monkeypatch.setenv("W", raw)
        assert config._get_workers("W", "parser", "workers", default=1) == "auto"

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"workers": 8}})
        monkeypatch.setenv("W", "3")
        assert config._get_workers("W", "parser", "workers", default=1) == 3

    @pytest.mark.parametrize("raw", ["0", "-1"])
    def test_below_one_is_rejected(self, monkeypatch, raw):
        monkeypatch.setenv("W", raw)
        with pytest.raises(ValueError, match="positive integer"):
            config._get_workers("W", "parser", "workers", default=1)

    def test_nonsense_string_is_rejected(self, monkeypatch):
        monkeypatch.setenv("W", "lots")
        with pytest.raises(ValueError, match="positive integer"):
            config._get_workers("W", "parser", "workers", default=1)

    def test_bool_is_rejected(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"workers": True}})
        with pytest.raises(ValueError, match="positive integer"):
            config._get_workers("W", "parser", "workers", default=1)


class TestGetPositiveInt:
    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {}})

    def test_missing_key_uses_default(self):
        assert config._get_positive_int("N", "enrich", "embed_top_k", default=5) == 5

    def test_int_from_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"embed_top_k": 9}})
        assert config._get_positive_int("N", "enrich", "embed_top_k", default=5) == 9

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"embed_top_k": 9}})
        monkeypatch.setenv("N", "2")
        assert config._get_positive_int("N", "enrich", "embed_top_k", default=5) == 2

    @pytest.mark.parametrize("raw", ["0", "-1"])
    def test_below_one_is_rejected(self, monkeypatch, raw):
        monkeypatch.setenv("N", raw)
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)

    def test_nonsense_string_is_rejected(self, monkeypatch):
        monkeypatch.setenv("N", "several")
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)

    def test_bool_is_rejected(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"embed_top_k": True}})
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)

    def test_a_float_is_rejected_rather_than_truncated(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"embed_top_k": 2.7}})
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)


class TestGetStartMethod:
    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {}})

    def test_missing_key_uses_default(self):
        assert (
            config._get_choice(
                "M", "parser", "start_method", default="auto", choices=config.PARSER_START_METHODS
            )
            == "auto"
        )

    def test_value_from_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"start_method": "spawn"}})
        assert (
            config._get_choice(
                "M", "parser", "start_method", default="auto", choices=config.PARSER_START_METHODS
            )
            == "spawn"
        )

    @pytest.mark.parametrize("raw", ["FORKSERVER", " forkserver "])
    def test_case_and_space_insensitive(self, monkeypatch, raw):
        monkeypatch.setenv("M", raw)
        assert (
            config._get_choice(
                "M", "parser", "start_method", default="auto", choices=config.PARSER_START_METHODS
            )
            == "forkserver"
        )

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"start_method": "spawn"}})
        monkeypatch.setenv("M", "forkserver")
        assert (
            config._get_choice(
                "M", "parser", "start_method", default="auto", choices=config.PARSER_START_METHODS
            )
            == "forkserver"
        )

    def test_a_typo_is_rejected_with_the_alternatives(self, monkeypatch):
        monkeypatch.setenv("M", "forkserv")
        with pytest.raises(ValueError, match="auto, forkserver, spawn"):
            config._get_choice(
                "M", "parser", "start_method", default="auto", choices=config.PARSER_START_METHODS
            )

    def test_fork_is_rejected(self, monkeypatch):
        monkeypatch.setenv("M", "fork")
        with pytest.raises(ValueError, match="auto, forkserver, spawn"):
            config._get_choice(
                "M", "parser", "start_method", default="auto", choices=config.PARSER_START_METHODS
            )


class TestGetLogLevel:
    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"logging": {}})

    def test_missing_key_uses_default(self):
        assert (
            config._get_choice("M", "logging", "level", default="INFO", choices=config.LOG_LEVELS)
            == "INFO"
        )

    def test_value_from_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"logging": {"level": "DEBUG"}})
        assert (
            config._get_choice("M", "logging", "level", default="INFO", choices=config.LOG_LEVELS)
            == "DEBUG"
        )

    @pytest.mark.parametrize("raw", ["warning", " WARNING "])
    def test_case_and_space_insensitive(self, monkeypatch, raw):
        monkeypatch.setenv("M", raw)
        assert (
            config._get_choice("M", "logging", "level", default="INFO", choices=config.LOG_LEVELS)
            == "WARNING"
        )

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"logging": {"level": "DEBUG"}})
        monkeypatch.setenv("M", "ERROR")
        assert (
            config._get_choice("M", "logging", "level", default="INFO", choices=config.LOG_LEVELS)
            == "ERROR"
        )

    def test_a_typo_is_rejected_with_the_alternatives(self, monkeypatch):
        monkeypatch.setenv("M", "WARN")
        with pytest.raises(ValueError, match="DEBUG, INFO, WARNING, ERROR, CRITICAL"):
            config._get_choice("M", "logging", "level", default="INFO", choices=config.LOG_LEVELS)


class TestModuleReloadWithEnvOverrides:
    @pytest.fixture(autouse=True)
    def _restore_config_after(self):
        yield
        os.environ.pop("CONFIG_PATH", None)
        importlib.reload(config)

    @pytest.fixture
    def _empty_config_toml(self, tmp_path, monkeypatch):
        empty_toml = tmp_path / "config.toml"
        empty_toml.write_text("", encoding="utf-8")
        monkeypatch.setenv("CONFIG_PATH", str(empty_toml))

    def test_old_collections_field_key_loads_and_is_flagged(self, tmp_path, monkeypatch):
        toml = tmp_path / "config.toml"
        toml.write_text('[bib]\ncollections_field = "groups"\n', encoding="utf-8")
        monkeypatch.setenv("CONFIG_PATH", str(toml))
        monkeypatch.delenv("BIB_COLLECTIONS_FIELD", raising=False)
        importlib.reload(config)
        assert config.LEGACY_COLLECTIONS_FIELD is True
        assert not hasattr(config, "BIB_COLLECTIONS_FIELD")

    def test_old_collections_field_env_var_is_flagged(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("BIB_COLLECTIONS_FIELD", "groups")
        importlib.reload(config)
        assert config.LEGACY_COLLECTIONS_FIELD is True

    def test_no_old_collections_field_setting(self, monkeypatch, _empty_config_toml):
        monkeypatch.delenv("BIB_COLLECTIONS_FIELD", raising=False)
        importlib.reload(config)
        assert config.LEGACY_COLLECTIONS_FIELD is False

    def test_retrieval_field_weights_default_to_one(self, monkeypatch, _empty_config_toml):
        for field in ("TITLE", "ABSTRACT"):
            monkeypatch.delenv(f"RETRIEVAL_WEIGHT_{field}", raising=False)
        importlib.reload(config)
        assert config.RETRIEVAL_FIELD_WEIGHTS == {"title": 1.0, "abstract": 1.0}

    @pytest.mark.parametrize("bad", ["-1.0", "inf", "-inf"])
    def test_a_negative_or_infinite_field_weight_is_rejected(
        self, monkeypatch, _empty_config_toml, bad
    ):
        monkeypatch.setenv("RETRIEVAL_WEIGHT_TITLE", bad)
        with pytest.raises(ValueError) as excinfo:
            importlib.reload(config)
        assert "weight_title" in str(excinfo.value)
        monkeypatch.delenv("RETRIEVAL_WEIGHT_TITLE")
        importlib.reload(config)

    def test_a_parser_backend_is_folded_to_its_spelling_at_load(
        self, monkeypatch, _empty_config_toml
    ):
        monkeypatch.setenv("PARSER", "Docling")
        importlib.reload(config)
        assert config.PARSER == "docling"

    def test_an_unknown_parser_backend_is_rejected_at_load(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("PARSER", "ocrmypdf")
        with pytest.raises(ValueError, match="pdftotext, docling, not 'ocrmypdf'"):
            importlib.reload(config)
        monkeypatch.delenv("PARSER")
        importlib.reload(config)

    def test_acronyms_unset_falls_back_to_the_vendored_floor(self, _empty_config_toml):
        importlib.reload(config)
        assert config.ACRONYMS_PATH == config.ACRONYMS_DEFAULT_PATH

    def test_acronym_expansion_defaults_to_on(self, _empty_config_toml):
        assert config.ACRONYM_EXPANSION is True

    def test_acronym_expansion_can_be_switched_off(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("RETRIEVAL_ACRONYM_EXPANSION", "false")
        importlib.reload(config)
        assert config.ACRONYM_EXPANSION is False
        monkeypatch.delenv("RETRIEVAL_ACRONYM_EXPANSION")
        importlib.reload(config)

    def test_spelling_correction_defaults_to_off(self, _empty_config_toml):
        assert config.SPELLING_CORRECTION is False

    def test_spelling_correction_can_be_switched_on(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("RETRIEVAL_SPELLING_CORRECTION", "true")
        importlib.reload(config)
        assert config.SPELLING_CORRECTION is True
        monkeypatch.delenv("RETRIEVAL_SPELLING_CORRECTION")
        importlib.reload(config)

    def test_a_zero_field_weight_is_allowed(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("RETRIEVAL_WEIGHT_ABSTRACT", "0")
        importlib.reload(config)
        assert config.RETRIEVAL_FIELD_WEIGHTS["abstract"] == 0.0

    def test_bm25_constants_default_to_the_swept_values(self, monkeypatch, _empty_config_toml):
        for name in ("RETRIEVAL_K1", "RETRIEVAL_B"):
            monkeypatch.delenv(name, raising=False)
        importlib.reload(config)
        assert (config.RETRIEVAL_K1, config.RETRIEVAL_B) == (1.5, 0.75)

    @pytest.mark.parametrize("bad", ["-0.5", "inf", "nan"])
    def test_a_negative_or_non_finite_k1_is_rejected(self, monkeypatch, _empty_config_toml, bad):
        monkeypatch.setenv("RETRIEVAL_K1", bad)
        with pytest.raises(ValueError) as excinfo:
            importlib.reload(config)
        assert "[retrieval].k1" in str(excinfo.value)
        monkeypatch.delenv("RETRIEVAL_K1")
        importlib.reload(config)

    @pytest.mark.parametrize("bad", ["-0.1", "1.5"])
    def test_a_b_outside_the_unit_interval_is_rejected(self, monkeypatch, _empty_config_toml, bad):
        monkeypatch.setenv("RETRIEVAL_B", bad)
        with pytest.raises(ValueError) as excinfo:
            importlib.reload(config)
        assert "[retrieval].b" in str(excinfo.value)
        monkeypatch.delenv("RETRIEVAL_B")
        importlib.reload(config)

    @pytest.mark.parametrize("edge", ["0", "1"])
    def test_both_ends_of_b_are_allowed(self, monkeypatch, _empty_config_toml, edge):
        monkeypatch.setenv("RETRIEVAL_B", edge)
        importlib.reload(config)
        assert config.RETRIEVAL_B == float(edge)

    def test_a_k1_of_zero_is_allowed(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("RETRIEVAL_K1", "0")
        importlib.reload(config)
        assert config.RETRIEVAL_K1 == 0.0

    def test_bib_file_env_override(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("BIB_FILE", "/tmp/other.bib")
        importlib.reload(config)
        assert config.BIB_FILE_PATH == config.PROJECT_ROOT / "/tmp/other.bib"

    def test_parser_ocr_defaults_off(self, monkeypatch, _empty_config_toml):
        monkeypatch.delenv("PARSER_OCR", raising=False)
        importlib.reload(config)
        assert config.PARSER_OCR is False

    def test_parser_ocr_env_override(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("PARSER_OCR", "true")
        importlib.reload(config)
        assert config.PARSER_OCR is True

    def test_embedding_model_env_override(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("EMBEDDING_MODEL", "sentence-transformers/other-model")
        importlib.reload(config)
        assert config.EMBEDDING_MODEL == "sentence-transformers/other-model"

    def test_docling_formulas_defaults_off(self, monkeypatch, _empty_config_toml):
        monkeypatch.delenv("DOCLING_FORMULAS", raising=False)
        importlib.reload(config)
        assert config.DOCLING_FORMULAS is False

    def test_docling_formulas_env_override(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("DOCLING_FORMULAS", "true")
        importlib.reload(config)
        assert config.DOCLING_FORMULAS is True

    def test_keyword_extraction_defaults(self, monkeypatch, _empty_config_toml):
        for var in ("KEYWORD_TOP_N", "KEYWORD_MIN_DF", "KEYWORDS_PATH"):
            monkeypatch.delenv(var, raising=False)
        importlib.reload(config)
        assert config.KEYWORD_TOP_N == 40
        assert config.KEYWORD_MIN_DF == 2
        assert config.KEYWORDS_PATH == config.CONTENT_DIR / "keywords.toml"

    def test_keyword_extraction_env_overrides(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("KEYWORD_TOP_N", "7")
        monkeypatch.setenv("KEYWORD_MIN_DF", "3")
        monkeypatch.setenv("KEYWORDS_PATH", "elsewhere/kw.toml")
        importlib.reload(config)
        assert config.KEYWORD_TOP_N == 7
        assert config.KEYWORD_MIN_DF == 3
        assert config.KEYWORDS_PATH == config.CONTENT_DIR / "elsewhere/kw.toml"

    def test_keywords_path_absolute_stays_absolute(self, monkeypatch, tmp_path, _empty_config_toml):
        absolute = tmp_path / "kw.toml"
        monkeypatch.setenv("KEYWORDS_PATH", str(absolute))
        importlib.reload(config)
        assert config.KEYWORDS_PATH == absolute

    def test_missing_config_file_names_the_fix(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONFIG_PATH", str(tmp_path / "config.toml"))
        with pytest.raises(FileNotFoundError) as excinfo:
            importlib.reload(config)
        message = str(excinfo.value)
        assert "cp config.toml.example config.toml" in message
        assert str(tmp_path / "config.toml") in message

    def test_custom_config_path(self, monkeypatch, tmp_path):
        custom_toml = tmp_path / "custom.toml"
        custom_toml.write_text(
            '[bib]\npath = "elsewhere.bib"\n[enrich]\nembedding_model = "custom/model"\n'
        )
        monkeypatch.setenv("CONFIG_PATH", str(custom_toml))
        importlib.reload(config)
        assert config.CONFIG_PATH == custom_toml
        assert config.BIB_FILE_PATH == config.PROJECT_ROOT / "elsewhere.bib"
        assert config.EMBEDDING_MODEL == "custom/model"


class TestGetOptionalPositiveInt:
    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {}})

    def test_missing_key_is_uncapped(self):
        assert config_load._get_optional_positive_int("K", "enrich", "k") is None

    def test_number_from_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"k": 32}})
        assert config_load._get_optional_positive_int("K", "enrich", "k") == 32

    @pytest.mark.parametrize("raw", ["", "off", "none", "false", "OFF", " off "])
    def test_off_words_work_from_either_source(self, monkeypatch, raw):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"k": raw}})
        assert config_load._get_optional_positive_int("K", "enrich", "k") is None

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"k": 32}})
        monkeypatch.setenv("K", "8")
        assert config_load._get_optional_positive_int("K", "enrich", "k") == 8

    def test_a_quoted_integer_is_accepted(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"k": "16"}})
        assert config_load._get_optional_positive_int("K", "enrich", "k") == 16

    @pytest.mark.parametrize("raw", ["0", "-5"])
    def test_non_positive_is_rejected(self, monkeypatch, raw):
        monkeypatch.setenv("K", raw)
        with pytest.raises(ValueError, match=">= 1"):
            config_load._get_optional_positive_int("K", "enrich", "k")

    def test_nonsense_is_rejected(self, monkeypatch):
        monkeypatch.setenv("K", "lots")
        with pytest.raises(ValueError, match=">= 1"):
            config_load._get_optional_positive_int("K", "enrich", "k")

    def test_bool_in_toml_is_rejected(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"k": True}})
        with pytest.raises(ValueError, match=">= 1"):
            config_load._get_optional_positive_int("K", "enrich", "k")

    def test_a_float_is_rejected(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"enrich": {"k": 8.5}})
        with pytest.raises(ValueError, match=">= 1"):
            config_load._get_optional_positive_int("K", "enrich", "k")


class TestGetOptionalFloat:
    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {}})

    def test_missing_key_is_off(self):
        assert config._get_optional_float("T", "parser", "t") is None

    def test_number_from_toml(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"t": 600}})
        assert config._get_optional_float("T", "parser", "t") == 600.0

    @pytest.mark.parametrize("raw", ["", "off", "none", "false", "OFF"])
    def test_env_can_switch_it_off(self, monkeypatch, raw):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"t": 600}})
        monkeypatch.setenv("T", raw)
        assert config._get_optional_float("T", "parser", "t") is None

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"t": 600}})
        monkeypatch.setenv("T", "90")
        assert config._get_optional_float("T", "parser", "t") == 90.0

    @pytest.mark.parametrize("raw", ["0", "-5"])
    def test_non_positive_is_rejected(self, monkeypatch, raw):
        monkeypatch.setenv("T", raw)
        with pytest.raises(ValueError, match="positive number"):
            config._get_optional_float("T", "parser", "t")

    def test_nonsense_is_rejected(self, monkeypatch):
        monkeypatch.setenv("T", "soon")
        with pytest.raises(ValueError, match="positive number"):
            config._get_optional_float("T", "parser", "t")

    def test_bool_in_toml_is_rejected(self, monkeypatch):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"t": True}})
        with pytest.raises(ValueError, match="positive number"):
            config._get_optional_float("T", "parser", "t")

    @pytest.mark.parametrize("raw", ["off", "none", "OFF", " off "])
    def test_off_words_work_from_the_toml_too_not_just_the_env(self, monkeypatch, raw):
        monkeypatch.setattr(config_load, "_toml", {"parser": {"t": raw}})
        assert config._get_optional_float("T", "parser", "t", default=1800.0) is None

    def test_default_applies_when_absent(self):
        assert config._get_optional_float("T", "parser", "t", default=1800.0) == 1800.0

    def test_an_explicit_off_beats_a_non_none_default(self, monkeypatch):
        monkeypatch.setenv("T", "off")
        assert config._get_optional_float("T", "parser", "t", default=1800.0) is None

    @pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "Infinity"])
    def test_non_finite_durations_are_rejected(self, monkeypatch, raw):
        monkeypatch.setenv("T", raw)
        with pytest.raises(ValueError, match="positive number"):
            config._get_optional_float("T", "parser", "t")


class TestDiscoverProjectRoot:
    def test_explicit_env_var_wins(self, tmp_path):
        marked = tmp_path / "marked"
        (marked / "nested").mkdir(parents=True)
        (marked / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        chosen = tmp_path / "elsewhere"
        found = config.discover_project_root(
            cwd=marked / "nested", environ={"CHITRAGUPTA_PROJECT": str(chosen)}
        )
        assert found == chosen.resolve()

    def test_a_relative_env_var_resolves_against_the_cwd(self, tmp_path):
        (tmp_path / "proj").mkdir()
        here = tmp_path / "elsewhere"
        here.mkdir()
        found = config.discover_project_root(cwd=here, environ={"CHITRAGUPTA_PROJECT": "../proj"})
        assert found == (tmp_path / "proj").resolve()
        assert found.is_absolute()

    def test_a_relative_env_var_is_absolute_in_a_real_child(self, tmp_path):
        proj = tmp_path / "proj"
        proj.mkdir()
        (proj / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        other = tmp_path / "other"
        other.mkdir()
        result = run_python(
            "-c",
            "from chitragupta import config; print(config.PARSED_DIR)",
            cwd=other,
            env={**os.environ, "CHITRAGUPTA_PROJECT": "../proj"},
            check=True,
        )
        assert Path(result.stdout.strip()) == proj.resolve() / "content" / "parsed"

    def test_walks_up_from_a_nested_cwd(self, tmp_path):
        (tmp_path / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        deep = tmp_path / "content" / "drafts" / "a"
        deep.mkdir(parents=True)
        assert config.discover_project_root(cwd=deep, environ={}) == tmp_path.resolve()

    def test_the_nearest_marker_wins(self, tmp_path):
        (tmp_path / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        inner = tmp_path / "inner"
        inner.mkdir()
        (inner / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        assert config.discover_project_root(cwd=inner, environ={}) == inner.resolve()

    def test_falls_back_to_the_directory_above_the_package(self, tmp_path, monkeypatch):
        checkout = tmp_path / "checkout"
        (checkout / "chitragupta").mkdir(parents=True)
        (checkout / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        monkeypatch.setattr(config, "PACKAGE_ROOT", checkout / "chitragupta")
        unrelated = tmp_path / "unrelated"
        unrelated.mkdir()
        assert config.discover_project_root(cwd=unrelated, environ={}) == checkout

    def test_no_project_anywhere_is_none_rather_than_a_guess(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "PACKAGE_ROOT", tmp_path / "pkg" / "src")
        bare = tmp_path / "bare"
        bare.mkdir()
        assert config.discover_project_root(cwd=bare, environ={}) is None


class TestShipped:
    def test_resolves_beside_the_package(self):
        assert config.shipped("assets", "csl", "ieee.csl") == (
            config.PACKAGE_ROOT.parent / "assets" / "csl" / "ieee.csl"
        )

    def test_the_vendored_assets_it_names_actually_exist(self):
        for path in (config.CSL_STYLE_PATH, config.VALE_CONFIG_PATH, config.ACRONYMS_DEFAULT_PATH):
            assert path.is_file(), path
