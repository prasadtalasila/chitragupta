import logging
import logging.handlers

import pytest

from chitragupta import config, logging_setup


@pytest.fixture(autouse=True)
def _reset_logging():
    root = logging.getLogger()
    before = list(root.handlers)
    yield
    for handler in root.handlers[:]:
        if handler not in before:
            root.removeHandler(handler)
            handler.close()
    logging.getLogger("chitragupta").setLevel(logging.NOTSET)
    logging.getLogger("scripts").setLevel(logging.NOTSET)


@pytest.fixture
def src_logger():
    return logging.getLogger("chitragupta.sync")


class TestConfigure:
    def test_creates_the_log_file_and_sets_the_configured_level(self, isolated_config, monkeypatch):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "WARNING")
        root_level_before = logging.getLogger().level
        logging_setup.configure()
        assert (config.LOGS_DIR / "pipeline.log").exists()
        file_handlers = [
            h
            for h in logging.getLogger().handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1
        assert file_handlers[0].level == logging.WARNING
        assert logging.getLogger().level == root_level_before

    def test_a_second_call_does_not_attach_a_second_pair_of_handlers(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.configure()

        root = logging.getLogger()
        assert (
            len([h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)])
            == 1
        )

        src_logger.info("said once")
        assert (config.LOGS_DIR / "pipeline.log").read_text().count("said once") == 1
        assert capsys.readouterr().err.count("said once") == 1

    def test_a_second_call_with_a_new_logs_dir_replaces_the_old_handlers(
        self, isolated_config, monkeypatch, tmp_path, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        first = config.LOGS_DIR / "pipeline.log"

        second = tmp_path / "elsewhere"
        monkeypatch.setattr(config, "LOGS_DIR", second)
        logging_setup.configure()

        root = logging.getLogger()
        assert (
            len([h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)])
            == 1
        ), "the old file handler must be detached, not accumulated"

        src_logger.info("after the move")

        assert "after the move" in (second / "pipeline.log").read_text()
        assert "after the move" not in first.read_text()  # old file is done
        assert capsys.readouterr().err.count("after the move") == 1  # not doubled

    def test_console_output_ignores_logging_level(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "CRITICAL")
        logging_setup.configure()
        src_logger.info("progress line")

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "progress line" not in log_text  # correctly filtered out of the file

        err = capsys.readouterr().err
        assert "progress line" in err  # but not off the console

    def test_a_third_partys_warning_reaches_the_file_but_not_the_console(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging.getLogger("docling").warning("a third-party warning")

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "a third-party warning" in log_text

        err = capsys.readouterr().err
        assert "a third-party warning" not in err

    def test_the_enrich_entrypoints_logger_reaches_the_console(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging.getLogger("chitragupta.enrich").info("an enrich line")

        assert "an enrich line" in (config.LOGS_DIR / "pipeline.log").read_text()
        assert "an enrich line" in capsys.readouterr().err

    def test_the_enrich_entrypoints_logger_is_pinned_permissive(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "CRITICAL")
        logging_setup.configure()
        logging.getLogger("chitragupta.enrich").info("enrich progress")

        assert "enrich progress" not in (config.LOGS_DIR / "pipeline.log").read_text()
        assert "enrich progress" in capsys.readouterr().err

    def test_a_logger_outside_the_src_tree_stays_off_the_console(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging.getLogger("scripts.enrich").warning("a stale-tree line")

        assert "a stale-tree line" in (config.LOGS_DIR / "pipeline.log").read_text()
        assert "a stale-tree line" not in capsys.readouterr().err

    def test_a_file_only_record_reaches_the_file_but_not_the_console(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        src_logger.info("ordinary message")
        src_logger.info("file only message", extra={"file_only": True})

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "ordinary message" in log_text
        assert "file only message" in log_text

        err = capsys.readouterr().err
        assert "ordinary message" in err
        assert "file only message" not in err

    def test_the_log_file_is_utf8(self, isolated_config, monkeypatch, src_logger):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        src_logger.info("Wüllnerstraße αβγ")
        log_text = (config.LOGS_DIR / "pipeline.log").read_text(encoding="utf-8")
        assert "Wüllnerstraße αβγ" in log_text

    def test_a_direct_log_call_cannot_forge_a_second_record(
        self, isolated_config, monkeypatch, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        src_logger.warning(
            "skipping %s", "Weird Title\n2026-01-01 00:00:00 ERROR chitragupta.sync: forged"
        )
        log_lines = (config.LOGS_DIR / "pipeline.log").read_text().strip().splitlines()
        assert len(log_lines) == 1
        assert "forged" in log_lines[0]  # content kept, line structure not

    def test_importing_the_module_creates_no_logs_directory(self, isolated_config):
        assert not config.LOGS_DIR.exists()


class TestSay:
    def test_prints_to_stdout_and_mirrors_into_the_file_once(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.say(src_logger, "a reported line")

        captured = capsys.readouterr()
        assert "a reported line" in captured.out
        assert "a reported line" not in captured.err
        assert (config.LOGS_DIR / "pipeline.log").read_text().count("a reported line") == 1

    def test_the_level_reaches_the_file_handlers_filter(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "WARNING")
        logging_setup.configure()
        logging_setup.say(src_logger, "routine progress")
        logging_setup.say(src_logger, "a real problem", level=logging.WARNING)

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "routine progress" not in log_text
        assert "a real problem" in log_text
        out = capsys.readouterr().out
        assert "routine progress" in out
        assert "a real problem" in out

    def test_section_spacing_stays_on_stdout_and_out_of_the_record(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.say(src_logger, "\n=== a stage ===")
        logging_setup.say(src_logger, "  indented detail")

        assert "\n=== a stage ===" in capsys.readouterr().out
        for line in (config.LOGS_DIR / "pipeline.log").read_text().splitlines():
            assert line.strip(), "a record must not be an empty line"
        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "chitragupta.sync: === a stage ===" in log_text
        assert "chitragupta.sync:   indented detail" in log_text

    def test_log_as_gives_the_file_a_different_rendering(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.say(src_logger, '[ok] {\n  "a": 3\n}', log_as='[ok] {"a": 3}')

        assert '{\n  "a": 3\n}' in capsys.readouterr().out
        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert '[ok] {"a": 3}' in log_text
        assert len(log_text.strip().splitlines()) == 1

    def test_an_internal_newline_cannot_split_one_event_into_several(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.say(src_logger, '[ok] {\n  "a": 3,\n  "b": 4\n}')

        assert '"a": 3,\n' in capsys.readouterr().out  # terminal keeps it
        log_lines = (config.LOGS_DIR / "pipeline.log").read_text().strip().splitlines()
        assert len(log_lines) == 1
        assert '[ok] { "a": 3, "b": 4 }' in log_lines[0]

    def test_a_warning_before_configure_does_not_echo_via_lastresort(self, capsys, src_logger):
        root = logging.getLogger()
        saved = root.handlers[:]
        root.handlers = []
        try:
            for tree in logging_setup._TREES:
                assert all(
                    isinstance(h, logging.NullHandler) for h in logging.getLogger(tree).handlers
                ), "only meaningful when no real handler is attached"

            logging_setup.say(src_logger, "a complaint", level=logging.WARNING)
        finally:
            root.handlers = saved

        captured = capsys.readouterr()
        assert "a complaint" in captured.out
        assert "a complaint" not in captured.err

    def test_still_prints_when_configure_has_not_run(self, capsys, src_logger):
        logging_setup.say(src_logger, "unconfigured but still printed")
        assert "unconfigured but still printed" in capsys.readouterr().out
