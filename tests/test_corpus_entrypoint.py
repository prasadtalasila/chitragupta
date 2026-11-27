import re
from pathlib import Path

import pytest

from chitragupta import corpus as entrypoint
from chitragupta import runlock
from tests.conftest import make_reference, run_python

REPO_ROOT = Path(__file__).resolve().parent.parent

BACKING_MODULES = {
    "sync": "sync",
    "ledger": "ledger_cli",
    "topics": "seed_topics",
    "discover": "discover",
}

SILENT_NO_OP_MODULES = ["ledger_cli", "seed_topics"]

_MAIN_BLOCK = re.compile(r'^if __name__ == ["\']__main__["\']:', re.MULTILINE)


class TestTheVerbsAreTheCorpusLayersCommands:
    def test_the_verb_set_is_exactly_the_backing_modules(self):
        assert set(entrypoint.VERBS) == set(BACKING_MODULES)

    @pytest.mark.parametrize("verb", sorted(BACKING_MODULES))
    def test_every_verb_is_reachable_and_declares_its_own_flags(self, verb):
        result = run_python("-m", "chitragupta.corpus", verb, "--help")
        assert result.returncode == 0, result.stderr
        assert f"chitragupta.corpus {verb}" in result.stdout

    def test_no_verb_prints_the_layers_usage_and_exits_zero(self):
        result = run_python("-m", "chitragupta.corpus")
        assert result.returncode == 0
        for verb in BACKING_MODULES:
            assert verb in result.stdout

    def test_no_verb_in_process_prints_the_usage_too(self, capsys):
        assert entrypoint.main([]) == 0
        out = capsys.readouterr().out
        for verb in BACKING_MODULES:
            assert verb in out

    def test_an_unknown_verb_is_a_usage_error(self):
        result = run_python("-m", "chitragupta.corpus", "bogus")
        assert result.returncode == 2
        assert "invalid choice: 'bogus'" in result.stderr


class TestTheCommandSurfaceStaysOneLevelDeep:
    @pytest.mark.parametrize("module", sorted(SILENT_NO_OP_MODULES))
    def test_a_backing_module_has_no_main_block(self, module):
        source = (REPO_ROOT / "chitragupta" / f"{module}.py").read_text(encoding="utf-8")
        assert not _MAIN_BLOCK.search(source)

    @pytest.mark.parametrize("module", sorted(SILENT_NO_OP_MODULES))
    def test_running_a_backing_module_directly_does_nothing(self, module):
        result = run_python("-m", f"chitragupta.{module}")
        assert result.returncode == 0
        assert result.stdout == ""


class TestTheRemovedSyncCommandRefuses:
    def test_it_exits_nonzero_and_names_the_replacement(self):
        result = run_python("-m", "chitragupta.sync")
        assert result.returncode != 0
        assert "chitragupta corpus sync" in result.stderr

    def test_it_avoids_every_exit_code_sync_publishes(self):
        result = run_python("-m", "chitragupta.sync")
        assert result.returncode not in (0, 1, runlock.EXIT_ALREADY_RUNNING)

    def test_it_says_nothing_on_stdout(self):
        result = run_python("-m", "chitragupta.sync")
        assert result.stdout == ""

    def test_the_real_command_is_unaffected(self):
        result = run_python("-m", "chitragupta.corpus", "sync", "--help")
        assert result.returncode == 0
        assert "python -m chitragupta.corpus sync" in result.stdout


class TestLedgerKeepsItsBarePythonTier:
    def test_importing_the_dispatcher_imports_neither_verb(self):
        result = run_python(
            "-c",
            "import sys; from chitragupta import corpus; "
            "print('chitragupta.sync' in sys.modules, 'chitragupta.ledger_cli' in sys.modules)",
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "False False"

    def test_dispatching_ledger_does_not_drag_in_syncs_dependency(self):
        result = run_python(
            "-c",
            "import sys\n"
            "from chitragupta import corpus\n"
            "try:\n"
            "    corpus.main(['ledger', '--help'])\n"
            "except SystemExit:\n"
            "    pass\n"
            "print('bibtexparser' in sys.modules, 'chitragupta.sync' in sys.modules)\n",
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().endswith("False False")


class TestTheExitCodeContractSurvivesTheDispatch:
    def test_ledger_on_an_unknown_citekey_exits_one(self, isolated_config, ledger_con):
        from chitragupta import ledger

        ledger.upsert_reference(ledger_con, make_reference())
        assert entrypoint.main(["ledger", "--citekey", "nope_2024"]) == 1

    def test_ledger_summary_exits_zero(self, isolated_config, ledger_con):
        assert entrypoint.main(["ledger"]) == 0

    def test_a_ledger_flag_reaches_ledgers_own_parser(self, isolated_config, ledger_con, capsys):
        assert entrypoint.main(["ledger", "--status", "parse_failed"]) == 0
        assert "No items with status" in capsys.readouterr().out

    def test_sync_against_a_held_lock_exits_two(self, isolated_config):
        with runlock.pipeline_lock(isolated_config.PIPELINE_LOCK_PATH):
            assert entrypoint.main(["sync"]) == runlock.EXIT_ALREADY_RUNNING

    def test_ledger_takes_no_lock_so_it_works_during_a_sync(self, isolated_config, ledger_con):
        with runlock.pipeline_lock(isolated_config.PIPELINE_LOCK_PATH):
            assert entrypoint.main(["ledger"]) == 0

    def test_sync_forwards_its_flags_and_returns_runs_exit_code(self, isolated_config, monkeypatch):
        from chitragupta import logging_setup, sync

        seen = {}
        monkeypatch.setattr(logging_setup, "configure", lambda: None)
        monkeypatch.setattr(sync, "run", lambda **kwargs: seen.update(kwargs) or 1)

        assert entrypoint.main(["sync", "--reparse", "--remove-stale"]) == 1
        assert seen == {"remove_stale": True, "reparse": True}

    def test_sync_with_no_flags_defaults_both_off(self, isolated_config, monkeypatch):
        from chitragupta import logging_setup, sync

        seen = {}
        monkeypatch.setattr(logging_setup, "configure", lambda: None)
        monkeypatch.setattr(sync, "run", lambda **kwargs: seen.update(kwargs) or 0)

        assert entrypoint.main(["sync"]) == 0
        assert seen == {"remove_stale": False, "reparse": False}

    def test_a_malformed_sync_invocation_exits_two(self):
        result = run_python("-m", "chitragupta.corpus", "sync", "--bogus-flag")
        assert result.returncode == 2
        assert "--bogus-flag" in result.stderr


class TestHelpIsOneCommandPerLine:
    def test_help_matches_click(self, monkeypatch, capsys):
        monkeypatch.setenv("COLUMNS", "80")
        monkeypatch.setattr("sys.argv", ["chitragupta"])
        with pytest.raises(SystemExit) as excinfo:
            entrypoint.main(["--help"])
        assert excinfo.value.code == 0
        assert capsys.readouterr().out == (
            "Usage: chitragupta corpus [OPTIONS] COMMAND [ARGS]...\n\n"
            "  The corpus layer: bring the ledger up to date, or read what it recorded.\n\n"
            "Options:\n  -h, --help  Show this message and exit.\n\n"
            "Commands:\n"
            "  sync      Bib file -> ledger -> PDF text: the deterministic corpus run\n"
            "  ledger    Read-only view of what that run recorded -- takes no lock\n"
            "  topics    Read-only view of which papers each seed topic matched\n"
            "  discover  Resolve a phrase to a topic and walk its papers and neighbours\n\n"
            "  Run 'chitragupta corpus COMMAND --help' for a command's flags.\n"
        )

    def test_verbs_and_help_index_agree(self):
        from chitragupta import command_help

        assert {verb: text for verb, (_, text) in entrypoint.VERBS.items()} == (
            command_help.verbs("corpus")
        )
