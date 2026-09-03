"""chitragupta/config.py: env-var overrides, config.toml defaults, and the two
pure helpers (_get/_get_float) that implement the override precedence."""

import importlib
import os

import pytest

from chitragupta import config


class TestGetHelpers:
    def test_env_var_wins_over_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"section": {"key": "from-toml"}})
        monkeypatch.setenv("MY_VAR", "from-env")
        assert config._get("MY_VAR", "section", "key", default="fallback") == "from-env"

    def test_falls_back_to_toml_path(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"section": {"key": "from-toml"}})
        monkeypatch.delenv("MY_VAR", raising=False)
        assert config._get("MY_VAR", "section", "key", default="fallback") == "from-toml"

    def test_default_when_toml_path_missing(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"section": {}})
        monkeypatch.delenv("MY_VAR", raising=False)
        assert config._get("MY_VAR", "section", "key", default="fallback") == "fallback"

    def test_default_when_toml_path_not_a_dict(self, monkeypatch):
        # "section" resolves to a string, not a dict -- the next path
        # segment ("key") can't be looked up in it.
        monkeypatch.setattr(config, "_toml", {"section": "not-a-dict"})
        monkeypatch.delenv("MY_VAR", raising=False)
        assert config._get("MY_VAR", "section", "key", default="fallback") == "fallback"

    def test_raises_when_leaf_is_not_a_string(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"section": {"key": 123}})
        monkeypatch.delenv("MY_VAR", raising=False)
        with pytest.raises(ValueError, match="must be a string"):
            config._get("MY_VAR", "section", "key", default="fallback")

    def test_float_env_var_wins(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"timeout": 3.0}})
        monkeypatch.setenv("MY_TIMEOUT", "9.5")
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.0) == 9.5

    def test_float_falls_back_to_toml_number(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"timeout": 3}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.0) == 3.0

    def test_float_default_when_missing(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5) == 1.5

    def test_float_default_when_not_a_dict(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": "nope"})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        assert config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5) == 1.5

    def test_float_raises_when_bool_in_toml(self, monkeypatch):
        # bool is a subclass of int in Python -- must not be silently
        # accepted as a numeric timeout.
        monkeypatch.setattr(config, "_toml", {"enrich": {"timeout": True}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        with pytest.raises(ValueError, match="must be a number"):
            config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5)

    def test_float_raises_when_string_in_toml(self, monkeypatch):
        # A quoted number in TOML used to silently default instead of
        # signalling the value was never read as a float.
        monkeypatch.setattr(config, "_toml", {"enrich": {"timeout": "3.0"}})
        monkeypatch.delenv("MY_TIMEOUT", raising=False)
        with pytest.raises(ValueError, match="must be a number"):
            config._get_float("MY_TIMEOUT", "enrich", "timeout", default=1.5)

    def test_float_raises_named_error_on_unparseable_env_var(self, monkeypatch):
        # A bare float() call raises "could not convert string to float"
        # with no indication of which setting was misconfigured -- this
        # getter's own error names the key and env var like every other
        # wrong-value case here does.
        monkeypatch.setattr(config, "_toml", {"enrich": {"timeout": 3.0}})
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
            # The whole point of _get_bool: bool("false") is True, so a plain
            # cast would make every documented way of switching a setting off
            # via the environment switch it on instead.
            ("0", False),
            ("false", False),
            ("FALSE", False),
            ("no", False),
            ("off", False),
            ("", False),
        ],
    )
    def test_bool_env_var_parses_words_not_truthiness(self, monkeypatch, raw, expected):
        monkeypatch.setattr(config, "_toml", {"enrich": {"flag": not expected}})
        monkeypatch.setenv("MY_FLAG", raw)
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=not expected) is expected

    def test_bool_falls_back_to_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"flag": False}})
        monkeypatch.delenv("MY_FLAG", raising=False)
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=True) is False

    def test_bool_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("MY_FLAG", raising=False)
        monkeypatch.setattr(config, "_toml", {"enrich": {}})
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=True) is True
        monkeypatch.setattr(config, "_toml", {"enrich": "nope"})
        assert config._get_bool("MY_FLAG", "enrich", "flag", default=True) is True

    def test_bool_raises_when_toml_leaf_is_not_a_bool(self, monkeypatch):
        # A quoted `collapse_citations = "false"` used to silently mean
        # `default` (often True) instead of the False actually written.
        monkeypatch.delenv("MY_FLAG", raising=False)
        monkeypatch.setattr(config, "_toml", {"enrich": {"flag": "yes"}})
        with pytest.raises(ValueError, match="must be true or false"):
            config._get_bool("MY_FLAG", "enrich", "flag", default=False)

    def test_int_env_var_wins(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": 3}})
        monkeypatch.setenv("MY_COUNT", "9")
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 9

    def test_int_falls_back_to_toml_number(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": 3}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 3

    def test_int_default_when_missing(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=5) == 5

    def test_int_accepts_a_whole_valued_float(self, monkeypatch):
        # TOML's own `count = 3.0` and a whole-number env var string both
        # denote an integer; only the fractional case is rejected below.
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": 3.0}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 3

    def test_int_accepts_a_quoted_whole_number_in_toml(self, monkeypatch):
        # Matches _get_positive_int and _get_workers, which have always
        # accepted a quoted integer -- the same value spelled either way
        # in a config file is intentionally not a type error here.
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": "3"}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        assert config._get_int("MY_COUNT", "enrich", "count", default=1) == 3

    def test_int_raises_on_fractional_toml_value(self, monkeypatch):
        # int(_get_float(...)) used to silently truncate 3.9 to 3; this
        # is the defect the getter exists to close.
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": 3.9}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    def test_int_raises_on_fractional_env_var(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": 3}})
        monkeypatch.setenv("MY_COUNT", "3.5")
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    def test_int_raises_on_bool_in_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": True}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    @pytest.mark.parametrize("raw", ["3.0", "1e3"])
    def test_int_raises_on_a_float_shaped_string(self, monkeypatch, raw):
        # A string is parsed with int(), not float(): "3.0"/"1e3" read as
        # a whole number only by a much looser standard than the PR's
        # own "quoted whole number" contract, and float(str(huge_int))
        # can lose precision that int() never would.
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": raw}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)

    def test_int_raises_on_non_numeric_string(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"count": "many"}})
        monkeypatch.delenv("MY_COUNT", raising=False)
        with pytest.raises(ValueError, match="must be a whole number"):
            config._get_int("MY_COUNT", "enrich", "count", default=1)


class TestRealConfigToml:
    """Sanity-checks the constants computed from this repo's actual
    config.toml + ambient environment at real import time."""

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
        # Vendored, not fetched: rendering has to work with no network.
        assert config.CSL_STYLE_PATH.is_file()

    def test_citations_collapse_by_default(self):
        assert config.RENDER_COLLAPSE_CITATIONS is True

    def test_acronyms_defaults_to_the_vendored_toml(self):
        assert config.ACRONYMS_PATH == config.ACRONYMS_DEFAULT_PATH
        assert config.ACRONYMS_DEFAULT_PATH == (config.shipped("assets", "style", "acronyms.toml"))
        # Vendored, not fetched: the loader has to work with no network.
        assert config.ACRONYMS_DEFAULT_PATH.is_file()


class TestGetWorkers:
    """[parser].workers is the one setting that isn't a plain str/float/
    bool: it's a positive int OR the literal "auto", and a wrong value
    has to be rejected at load rather than turning into a nonsense pool
    size much later."""

    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {}})

    def test_missing_key_uses_default(self):
        assert config._get_workers("W", "parser", "workers", default=1) == 1

    def test_int_from_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {"workers": 8}})
        assert config._get_workers("W", "parser", "workers", default=1) == 8

    def test_auto_from_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {"workers": "auto"}})
        assert config._get_workers("W", "parser", "workers", default=1) == "auto"

    @pytest.mark.parametrize("raw", ["auto", "AUTO", " Auto "])
    def test_auto_is_case_and_space_insensitive(self, monkeypatch, raw):
        monkeypatch.setenv("W", raw)
        assert config._get_workers("W", "parser", "workers", default=1) == "auto"

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {"workers": 8}})
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
        """TOML `workers = true` parses as a bool, and bool is an int
        subclass in Python -- so without an explicit check this would
        silently mean "1 worker" instead of being called out."""
        monkeypatch.setattr(config, "_toml", {"parser": {"workers": True}})
        with pytest.raises(ValueError, match="positive integer"):
            config._get_workers("W", "parser", "workers", default=1)


class TestGetPositiveInt:
    """The three settings that size embed_index.search()'s stages
    (#380). Validated at load, unlike every other numeric key here,
    because each nonsense value fails as a quietly wrong result set
    rather than as an error -- `embed_top_k = 0` simply returns
    nothing."""

    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {}})

    def test_missing_key_uses_default(self):
        assert config._get_positive_int("N", "enrich", "embed_top_k", default=5) == 5

    def test_int_from_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"embed_top_k": 9}})
        assert config._get_positive_int("N", "enrich", "embed_top_k", default=5) == 9

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"embed_top_k": 9}})
        monkeypatch.setenv("N", "2")
        assert config._get_positive_int("N", "enrich", "embed_top_k", default=5) == 2

    @pytest.mark.parametrize("raw", ["0", "-1"])
    def test_below_one_is_rejected(self, monkeypatch, raw):
        """A cap, a k or a multiplier of 0 each produce an empty or
        pointless result rather than an error, so silence here is the
        expensive option."""
        monkeypatch.setenv("N", raw)
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)

    def test_nonsense_string_is_rejected(self, monkeypatch):
        monkeypatch.setenv("N", "several")
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)

    def test_bool_is_rejected(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"enrich": {"embed_top_k": True}})
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)

    def test_a_float_is_rejected_rather_than_truncated(self, monkeypatch):
        """2.7 passages is not a thing, and int(2.7) == 2 would silently
        honour a value nobody wrote."""
        monkeypatch.setattr(config, "_toml", {"enrich": {"embed_top_k": 2.7}})
        with pytest.raises(ValueError, match="whole number >= 1"):
            config._get_positive_int("N", "enrich", "embed_top_k", default=5)


class TestGetStartMethod:
    """[parser].start_method decides how the docling pool creates its
    workers. A typo has to be rejected at load, naming the alternatives,
    rather than surfacing as a ValueError out of get_context() once a
    pool is already half-built."""

    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {}})

    def test_missing_key_uses_default(self):
        assert config._get_start_method("M", "parser", "start_method", default="auto") == "auto"

    def test_value_from_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {"start_method": "spawn"}})
        assert config._get_start_method("M", "parser", "start_method", default="auto") == "spawn"

    @pytest.mark.parametrize("raw", ["FORKSERVER", " forkserver "])
    def test_case_and_space_insensitive(self, monkeypatch, raw):
        monkeypatch.setenv("M", raw)
        assert (
            config._get_start_method("M", "parser", "start_method", default="auto") == "forkserver"
        )

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {"start_method": "spawn"}})
        monkeypatch.setenv("M", "forkserver")
        assert (
            config._get_start_method("M", "parser", "start_method", default="auto") == "forkserver"
        )

    def test_a_typo_is_rejected_with_the_alternatives(self, monkeypatch):
        monkeypatch.setenv("M", "forkserv")
        with pytest.raises(ValueError, match="auto, forkserver, spawn"):
            config._get_start_method("M", "parser", "start_method", default="auto")

    def test_fork_is_rejected(self, monkeypatch):
        """Not an accepted value: this process holds the run lock and the
        ledger open as live sqlite connections, which a forked worker
        must not inherit."""
        monkeypatch.setenv("M", "fork")
        with pytest.raises(ValueError, match="auto, forkserver, spawn"):
            config._get_start_method("M", "parser", "start_method", default="auto")


class TestGetLogLevel:
    """[logging].level decides how much python -m chitragupta.corpus sync writes to
    logs/pipeline.log. A typo has to be rejected at load, naming the
    alternatives, same reasoning as _get_start_method above."""

    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"logging": {}})

    def test_missing_key_uses_default(self):
        assert config._get_log_level("M", "logging", "level", default="INFO") == "INFO"

    def test_value_from_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"logging": {"level": "DEBUG"}})
        assert config._get_log_level("M", "logging", "level", default="INFO") == "DEBUG"

    @pytest.mark.parametrize("raw", ["warning", " WARNING "])
    def test_case_and_space_insensitive(self, monkeypatch, raw):
        monkeypatch.setenv("M", raw)
        assert config._get_log_level("M", "logging", "level", default="INFO") == "WARNING"

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"logging": {"level": "DEBUG"}})
        monkeypatch.setenv("M", "ERROR")
        assert config._get_log_level("M", "logging", "level", default="INFO") == "ERROR"

    def test_a_typo_is_rejected_with_the_alternatives(self, monkeypatch):
        monkeypatch.setenv("M", "WARN")
        with pytest.raises(ValueError, match="DEBUG, INFO, WARNING, ERROR, CRITICAL"):
            config._get_log_level("M", "logging", "level", default="INFO")


class TestModuleReloadWithEnvOverrides:
    """Full module-level reload, to cover the constant-computation lines
    themselves (BIB_FILE_PATH = REPO_ROOT / _get(...), etc.) under a real
    env-var override -- not just the _get helper in isolation."""

    @pytest.fixture(autouse=True)
    def _restore_config_after(self):
        yield
        # Reload once more with a clean environment so later test modules
        # see the real repo config.toml, not whatever this test overrode.
        #
        # CONFIG_PATH is cleared here rather than left to monkeypatch's own
        # teardown: fixture finalisation order depends on which fixtures
        # requested monkeypatch, so this reload can run while a test's
        # deliberately-bogus CONFIG_PATH is still set -- and since v1.0.0
        # that is a hard FileNotFoundError, turning an unrelated passing
        # test into a teardown error.
        os.environ.pop("CONFIG_PATH", None)
        importlib.reload(config)

    @pytest.fixture
    def _empty_config_toml(self, tmp_path, monkeypatch):
        """Pins CONFIG_PATH to an empty, tmp_path TOML before a reload.

        `importlib.reload(config)` re-reads config.toml for every constant
        it recomputes, not just the one a test overrides its own env var
        for -- so a test that sets e.g. BIB_FILE but leaves CONFIG_PATH
        alone still reads this developer's real, gitignored config.toml
        for everything else the reload computes. That was harmless until
        test_parser_ocr_defaults_off (below) hit the case where it wasn't:
        falling through to a real `ocr = true` turned "the code defaults
        OCR off" into "you enabled OCR", on one machine, invisibly to CI
        (CI copies config.toml.example -- see
        tests/test_unversioned_data_scan.py::test_ci_creates_config_toml_from_the_tracked_example).

        Empty rather than config.toml.example: the example ships real
        values (`ocr = false`, etc.), so pinning to it would assert what
        the example says while claiming to assert what the code defaults
        to. With no tables at all, each `_get*` helper's own default is
        the only thing left to answer -- correct for every test below
        except test_missing_config_file_names_the_fix and
        test_custom_config_path, which pin their own CONFIG_PATH content
        on purpose and so do not use this fixture.
        """
        empty_toml = tmp_path / "config.toml"
        empty_toml.write_text("", encoding="utf-8")
        monkeypatch.setenv("CONFIG_PATH", str(empty_toml))

    def test_bib_file_env_override(self, monkeypatch, _empty_config_toml):
        monkeypatch.setenv("BIB_FILE", "/tmp/other.bib")
        importlib.reload(config)
        assert config.BIB_FILE_PATH == config.PROJECT_ROOT / "/tmp/other.bib"

    def test_parser_ocr_defaults_off(self, monkeypatch, _empty_config_toml):
        """The code's default, not this developer's setting.

        Every sibling test in this class sets its own env var, which
        wins over the TOML regardless of what CONFIG_PATH points at -- so
        only this one, which deletes PARSER_OCR instead of setting it,
        ever depended on which config.toml a reload picked up. See
        `_empty_config_toml` for why every test here pins one anyway, and
        for why an empty TOML rather than config.toml.example.
        """
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

    def test_keyword_extraction_defaults(self, monkeypatch, _empty_config_toml):
        """The documented defaults (#604): the values the exploratory run
        used to produce the list that was read by hand and judged useful."""
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
        """The same resolution rule CONTENT_DIR itself uses: pathlib's
        `/` yields the right-hand side unchanged when it is absolute.
        tmp_path rather than a literal `/tmp/...`, because a rooted,
        driveless path is not absolute on Windows and joins onto
        CONTENT_DIR's drive instead of surviving unchanged."""
        absolute = tmp_path / "kw.toml"
        monkeypatch.setenv("KEYWORDS_PATH", str(absolute))
        importlib.reload(config)
        assert config.KEYWORDS_PATH == absolute

    def test_missing_config_file_names_the_fix(self, monkeypatch, tmp_path):
        """config.toml is gitignored per-host data, so "it isn't there"
        is the *normal* state of a fresh clone -- the first thing anyone
        hits. Deliberately a hard failure rather than a silent fallback
        to config.toml.example: a host quietly running settings its owner
        never chose is worse than one that won't start. The message has
        to carry the actual command, since the file it names is not
        obviously related to the traceback that brought you here."""
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


class TestGetOptionalFloat:
    """A duration that can be switched off. _get_float can't express
    that -- it requires a float default -- and encoding "off" as 0 in a
    config file reads as "zero seconds", which is the opposite."""

    @pytest.fixture(autouse=True)
    def _toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {}})

    def test_missing_key_is_off(self):
        assert config._get_optional_float("T", "parser", "t") is None

    def test_number_from_toml(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {"t": 600}})
        assert config._get_optional_float("T", "parser", "t") == 600.0

    @pytest.mark.parametrize("raw", ["", "off", "none", "false", "OFF"])
    def test_env_can_switch_it_off(self, monkeypatch, raw):
        monkeypatch.setattr(config, "_toml", {"parser": {"t": 600}})
        monkeypatch.setenv("T", raw)
        assert config._get_optional_float("T", "parser", "t") is None

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setattr(config, "_toml", {"parser": {"t": 600}})
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
        monkeypatch.setattr(config, "_toml", {"parser": {"t": True}})
        with pytest.raises(ValueError, match="positive number"):
            config._get_optional_float("T", "parser", "t")

    @pytest.mark.parametrize("raw", ["off", "none", "OFF", " off "])
    def test_off_words_work_from_the_toml_too_not_just_the_env(self, monkeypatch, raw):
        """The shipped config.toml.example writes `document_timeout =
        "off"`, so this is the path every new user takes. Handling the
        off-words only on the env path made the example itself fail to
        load."""
        monkeypatch.setattr(config, "_toml", {"parser": {"t": raw}})
        assert config._get_optional_float("T", "parser", "t", default=1800.0) is None

    def test_default_applies_when_absent(self):
        assert config._get_optional_float("T", "parser", "t", default=1800.0) == 1800.0

    def test_an_explicit_off_beats_a_non_none_default(self, monkeypatch):
        """Otherwise a setting with a default could never be switched
        off -- which is exactly what [parser].stall_timeout needs."""
        monkeypatch.setenv("T", "off")
        assert config._get_optional_float("T", "parser", "t", default=1800.0) is None

    @pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "Infinity"])
    def test_non_finite_durations_are_rejected(self, monkeypatch, raw):
        """float() accepts these and `seconds <= 0` doesn't catch NaN, so
        they would reach wait()/subprocess.run(timeout=...) and misbehave
        there instead of being reported here."""
        monkeypatch.setenv("T", raw)
        with pytest.raises(ValueError, match="positive number"):
            config._get_optional_float("T", "parser", "t")


class TestDiscoverProjectRoot:
    """Where the user's corpus, drafts and config live.

    Separate from PACKAGE_ROOT (where the code lives) because the two
    stop being the same directory the moment this is installed rather
    than cloned -- docs/PACKAGING.md. Every case below passes `cwd` and
    `environ` explicitly rather than chdir-ing or setting real
    variables: this function is consulted at import time, so a test that
    mutated the real ones would decide what a later reload sees.
    """

    def test_explicit_env_var_wins(self, tmp_path):
        """An answer the user gave beats one this code inferred."""
        marked = tmp_path / "marked"
        (marked / "nested").mkdir(parents=True)
        (marked / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        chosen = tmp_path / "elsewhere"
        found = config.discover_project_root(
            cwd=marked / "nested", environ={"CHITRAGUPTA_PROJECT": str(chosen)}
        )
        assert found == chosen

    def test_walks_up_from_a_nested_cwd(self, tmp_path):
        """Running from deep inside a project still finds the project."""
        (tmp_path / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        deep = tmp_path / "content" / "drafts" / "a"
        deep.mkdir(parents=True)
        assert config.discover_project_root(cwd=deep, environ={}) == tmp_path.resolve()

    def test_the_nearest_marker_wins(self, tmp_path):
        """A project inside a project is the inner one, not the outer."""
        (tmp_path / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        inner = tmp_path / "inner"
        inner.mkdir()
        (inner / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        assert config.discover_project_root(cwd=inner, environ={}) == inner.resolve()

    def test_falls_back_to_the_directory_above_the_package(self, tmp_path, monkeypatch):
        """The git checkout: invoked from anywhere, still finds its own root.

        This is the branch that keeps every existing invocation working
        -- it is what deriving the root from `__file__` used to do.
        """
        checkout = tmp_path / "checkout"
        (checkout / "chitragupta").mkdir(parents=True)
        (checkout / config.PROJECT_MARKER).write_text("", encoding="utf-8")
        monkeypatch.setattr(config, "PACKAGE_ROOT", checkout / "chitragupta")
        unrelated = tmp_path / "unrelated"
        unrelated.mkdir()
        assert config.discover_project_root(cwd=unrelated, environ={}) == checkout

    def test_no_project_anywhere_is_none_rather_than_a_guess(self, tmp_path, monkeypatch):
        """Refusing beats silently adopting some unrelated directory.

        The caller turns this into the same FileNotFoundError a fresh
        clone already gets, naming `cp config.toml.example config.toml`.
        """
        monkeypatch.setattr(config, "PACKAGE_ROOT", tmp_path / "pkg" / "src")
        bare = tmp_path / "bare"
        bare.mkdir()
        assert config.discover_project_root(cwd=bare, environ={}) is None


class TestShipped:
    """Files that arrive by installing, not by authoring."""

    def test_resolves_beside_the_package(self):
        assert config.shipped("assets", "csl", "ieee.csl") == (
            config.PACKAGE_ROOT.parent / "assets" / "csl" / "ieee.csl"
        )

    def test_the_vendored_assets_it_names_actually_exist(self):
        """A seam that resolves to nothing is worse than no seam."""
        for path in (config.CSL_STYLE_PATH, config.VALE_CONFIG_PATH, config.ACRONYMS_DEFAULT_PATH):
            assert path.is_file(), path
