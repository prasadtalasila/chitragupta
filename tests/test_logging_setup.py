"""src/logging_setup.py: one log file, logs/pipeline.log, shared by
everything that holds the pipeline write lock.

These cases moved here from tests/test_sync.py when configure() was
lifted out of src/sync.py so src/enrich/__main__.py could share it -- the
behaviour they pin (level applies to the file and not the console,
third-party records reach the file only, `file_only` suppresses the
console copy) is now a property of the shared module rather than of
sync.

configure() is CLI-entrypoint-only and must be called inside the
pipeline lock (see its docstring), so unlike almost everything else in
this suite it is called directly here -- which means the two handlers
it attaches to the root logger have to be removed afterwards or they
leak into every other test in the process. Removing them is also what
resets configure()'s own guard, which asks whether a handler is
already attached rather than tracking a flag.
"""

import logging
import logging.handlers

import pytest

from src import config, logging_setup


@pytest.fixture(autouse=True)
def _reset_logging():
    root = logging.getLogger()
    before = list(root.handlers)
    yield
    for handler in root.handlers[:]:
        if handler not in before:
            root.removeHandler(handler)
            handler.close()
    logging.getLogger("src").setLevel(logging.NOTSET)
    logging.getLogger("scripts").setLevel(logging.NOTSET)


@pytest.fixture
def src_logger():
    return logging.getLogger("src.sync")


class TestConfigure:
    def test_creates_the_log_file_and_sets_the_configured_level(
        self, isolated_config, monkeypatch
    ):
        monkeypatch.setattr(config, "LOGGING_LEVEL", "WARNING")
        root_level_before = logging.getLogger().level
        logging_setup.configure()
        assert (config.LOGS_DIR / "pipeline.log").exists()
        file_handlers = [
            h for h in logging.getLogger().handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1
        # LOGGING_LEVEL is a handler-level filter on file_handler alone
        # -- not a logger level -- see test_console_output_ignores_
        # logging_level below for why that distinction is load-bearing.
        assert file_handlers[0].level == logging.WARNING
        assert logging.getLogger().level == root_level_before

    def test_a_second_call_does_not_attach_a_second_pair_of_handlers(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        """The hazard the single shared module introduced: two
        entrypoints now import this, and src/enrich/__main__.py runs several
        stages in one process. An unguarded second call would double
        every subsequent line in both the file and the console, which
        reads as corrupt output rather than as a configuration bug."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.configure()

        root = logging.getLogger()
        assert len([
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]) == 1

        src_logger.info("said once")
        assert (config.LOGS_DIR / "pipeline.log").read_text().count("said once") == 1
        assert capsys.readouterr().err.count("said once") == 1

    def test_a_second_call_with_a_new_logs_dir_replaces_the_old_handlers(
        self, isolated_config, monkeypatch, tmp_path, capsys, src_logger
    ):
        """The guard asks whether a handler is already open on *this*
        target, not whether configure() has ever run -- so pointing
        LOGS_DIR somewhere else and calling again is a real
        reconfiguration. A bookkeeping flag would have swallowed the
        second call and sent those records to the first call's file,
        which is a much harder failure to spot than an extra handler.

        "Reconfigure" has to mean *replace*, and asserting only that the
        new file receives the record does not check that: the first
        version of this passed while both handler pairs stayed attached,
        so every record went to both files and every console line
        printed twice. Each half below is pinned separately."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        first = config.LOGS_DIR / "pipeline.log"

        second = tmp_path / "elsewhere"
        monkeypatch.setattr(config, "LOGS_DIR", second)
        logging_setup.configure()

        root = logging.getLogger()
        assert len([
            h for h in root.handlers
            if isinstance(h, logging.handlers.RotatingFileHandler)
        ]) == 1, "the old file handler must be detached, not accumulated"

        src_logger.info("after the move")

        assert "after the move" in (second / "pipeline.log").read_text()
        assert "after the move" not in first.read_text()   # old file is done
        assert capsys.readouterr().err.count("after the move") == 1  # not doubled

    def test_console_output_ignores_logging_level(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        """The bug this guards against: setting LOGGING_LEVEL on the
        project's logger trees (an earlier version of this function
        did) gates whether a record is created at all, before any
        handler is reached -- so WARNING would have silently suppressed
        the [n/N] progress line (INFO) on the console too, contradicting
        "only affects the file". Confirmed here at the strictest
        setting: an INFO record must still reach the console even when
        LOGGING_LEVEL is CRITICAL."""
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
        """docling and torch already use stdlib logging. Their WARNING+
        should land in logs/pipeline.log "for free" -- but not flood the
        console, which is exactly the "docling's own OCR chatter"
        problem the [n/N] progress line's own comment describes."""
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
        """The other entrypoint that holds the lock logs as `src.enrich`.

        It logged as `scripts.enrich` until 5.0.0, when the enrichment
        layer's entry point moved from scripts/enrich.py into the package
        as src/enrich/__main__.py and _TREES collapsed from
        ("src", "scripts") to ("src",). What this pins is unchanged by
        that move: an enrich line must reach both the file and the
        console. The bug it guards against -- every enrich line landing
        in the file and vanishing from the console -- was a half-failure
        much harder to notice than no logging at all.
        """
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging.getLogger("src.enrich").info("an enrich line")

        assert "an enrich line" in (config.LOGS_DIR / "pipeline.log").read_text()
        assert "an enrich line" in capsys.readouterr().err

    def test_the_enrich_entrypoints_logger_is_pinned_permissive(
        self, isolated_config, monkeypatch, capsys
    ):
        """The console-vs-file split has to hold for the enrichment
        entrypoint too, not just for sync: leaving it at the root's level
        would reintroduce exactly the bug
        test_console_output_ignores_logging_level covers, but only for
        enrich."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "CRITICAL")
        logging_setup.configure()
        logging.getLogger("src.enrich").info("enrich progress")

        assert "enrich progress" not in (config.LOGS_DIR / "pipeline.log").read_text()
        assert "enrich progress" in capsys.readouterr().err

    def test_a_logger_outside_the_src_tree_stays_off_the_console(
        self, isolated_config, monkeypatch, capsys
    ):
        """_TREES lost its "scripts" root in 5.0.0. Nothing in this repo
        logs under that name any more, so a record that still arrives
        under it is by definition not ours and belongs with the
        third-party chatter -- on the console's far side of the filter.
        This is the assertion that would fail if the collapse had been
        done by widening the match rather than by narrowing the roots."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging.getLogger("scripts.enrich").warning("a stale-tree line")

        assert "a stale-tree line" in (config.LOGS_DIR / "pipeline.log").read_text()
        assert "a stale-tree line" not in capsys.readouterr().err

    def test_a_file_only_record_reaches_the_file_but_not_the_console(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        """Confirmed against a real `python -m src.corpus sync` run: without
        this filter, run()'s summary line -- already printed to stdout
        -- prints a second time via the console handler, once for each
        handler on the same logger call."""
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
        """Explicit encoding, not the platform default: a citekey or
        title carrying an accented or non-Latin name (this corpus has
        real ones -- Schroder-with-an-umlaut, Greek in formulae) must
        not depend on whatever locale the host happens to be in."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        src_logger.info("Wüllnerstraße αβγ")
        log_text = (config.LOGS_DIR / "pipeline.log").read_text(encoding="utf-8")
        assert "Wüllnerstraße αβγ" in log_text

    def test_importing_the_module_creates_no_logs_directory(self, isolated_config):
        """The entrypoint-only invariant, from the other side: importing
        this module (every test in this suite does, transitively) must
        not make a logs/ directory appear. configure() is what creates
        it, and only a CLI entrypoint holding the lock calls that."""
        assert not config.LOGS_DIR.exists()


class TestSay:
    def test_prints_to_stdout_and_mirrors_into_the_file_once(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        """Both halves matter. stdout, because a caller's stdout is a
        human-facing report or a documented CLI contract and the console
        handler writes to stderr. The file, because that is the whole
        point of the mirror. Exactly one copy on the console, because
        `file_only` is what stops the handler echoing the line stdout
        already carried."""
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
        """say(level=WARNING) is how a swallowed stage error still shows
        up for someone grepping the log at a raised LOGGING_LEVEL. If
        the level were ignored, that line would be filtered out of the
        file at exactly the setting an unattended operator is most
        likely to use."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "WARNING")
        logging_setup.configure()
        logging_setup.say(src_logger, "routine progress")
        logging_setup.say(src_logger, "a real problem", level=logging.WARNING)

        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "routine progress" not in log_text
        assert "a real problem" in log_text
        # Both still reached stdout -- LOGGING_LEVEL gates the file, and
        # a raised setting must not silently shorten the terminal report.
        out = capsys.readouterr().out
        assert "routine progress" in out
        assert "a real problem" in out

    def test_section_spacing_stays_on_stdout_and_out_of_the_record(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        """Callers space sections apart with a leading newline for the
        terminal. Left in the record it produces an entry whose first
        line is blank and whose text is on the next -- breaking the
        one-line-per-record shape grep and every log reader assume.
        Indentation is not whitespace to strip, though: the summary
        table is indented and must stay that way."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.say(src_logger, "\n=== a stage ===")
        logging_setup.say(src_logger, "  indented detail")

        assert "\n=== a stage ===" in capsys.readouterr().out
        for line in (config.LOGS_DIR / "pipeline.log").read_text().splitlines():
            assert line.strip(), "a record must not be an empty line"
        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert "src.sync: === a stage ===" in log_text
        assert "src.sync:   indented detail" in log_text

    def test_log_as_gives_the_file_a_different_rendering(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        """The terminal and the log want different shapes of the same
        object: indented JSON reads well for a human, one line greps
        well. Neither should be sacrificed to the other."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.say(
            src_logger, '[ok] {\n  "a": 3\n}', log_as='[ok] {"a": 3}'
        )

        assert '{\n  "a": 3\n}' in capsys.readouterr().out
        log_text = (config.LOGS_DIR / "pipeline.log").read_text()
        assert '[ok] {"a": 3}' in log_text
        assert len(log_text.strip().splitlines()) == 1

    def test_an_internal_newline_cannot_split_one_event_into_several(
        self, isolated_config, monkeypatch, capsys, src_logger
    ):
        """The structural backstop, and the bug it exists for. A message
        carrying embedded newlines -- json.dumps(indent=2) is how this
        first appeared -- wrote a record per line, only the first of them
        timestamped, so one event read as six and `grep` found the
        header without the content. The terminal still gets the
        multi-line form; the record must be one line regardless of
        whether the caller remembered `log_as`."""
        monkeypatch.setattr(config, "LOGGING_LEVEL", "INFO")
        logging_setup.configure()
        logging_setup.say(src_logger, '[ok] {\n  "a": 3,\n  "b": 4\n}')

        assert '"a": 3,\n' in capsys.readouterr().out  # terminal keeps it
        log_lines = (config.LOGS_DIR / "pipeline.log").read_text().strip().splitlines()
        assert len(log_lines) == 1
        assert '[ok] { "a": 3, "b": 4 }' in log_lines[0]

    def test_a_warning_before_configure_does_not_echo_via_lastresort(
        self, capsys, src_logger
    ):
        """say() promises nothing beyond the bare print until configure()
        has run, and stdlib logging quietly breaks that promise: with no
        handler anywhere up the chain, `Logger.callHandlers` falls back
        to `logging.lastResort`, a stderr handler fixed at WARNING. So a
        WARNING went to stdout via the print *and* to stderr via the
        fallback -- one message, printed twice, on two streams.

        The NullHandler this module attaches to its own logger trees at
        import is what stops the fallback being reached. This test pins
        the effect, not the mechanism: no handlers of ours, a WARNING,
        and stderr must stay empty.

        Deliberately without `isolated_config` or `configure()` -- the
        whole point is the unconfigured process.

        The root logger's handlers are cleared for the duration, and
        that is what makes this test mean anything: pytest's own logging
        plugin attaches a handler there, so `callHandlers` would find it,
        never reach the fallback, and the test would pass just as
        happily with the NullHandler deleted. Checked by deleting it --
        this fails without the fix only once the root is bare.
        """
        root = logging.getLogger()
        saved = root.handlers[:]
        root.handlers = []
        try:
            for tree in logging_setup._TREES:
                assert all(
                    isinstance(h, logging.NullHandler)
                    for h in logging.getLogger(tree).handlers
                ), "only meaningful when no real handler is attached"

            logging_setup.say(src_logger, "a complaint", level=logging.WARNING)
        finally:
            root.handlers = saved

        captured = capsys.readouterr()
        assert "a complaint" in captured.out
        assert "a complaint" not in captured.err

    def test_still_prints_when_configure_has_not_run(self, capsys, src_logger):
        """Library callers (src/enrich/*) use say() but are imported by
        tests that never configure logging. With no handler attached the
        logger call goes nowhere, and the print must still behave
        exactly as it did before logging existed here."""
        logging_setup.say(src_logger, "unconfigured but still printed")
        assert "unconfigured but still printed" in capsys.readouterr().out
