"""chitragupta/corpus.py: the corpus layer's single entry point.

What each of the two commands *does* is covered in their own test files
(tests/test_sync.py, tests/test_ledger.py, tests/test_ledger_cli.py).
This file pins only the dispatch, and the invariant the dispatch exists
to serve: **one entry point per layer, one level deep**, the same shape
`python -m chitragupta.draft <verb>` and `python -m chitragupta.review <aid>` already
give their layers.

Modeled on tests/test_draft_entrypoint.py, which pinned the same
invariant for the drafting layer. Two things are specific to this layer
and have no counterpart there:

  - **The dispatcher imports lazily.** `chitragupta/draft.py` can import all
    five of its modules at the top of the file because all five are
    stdlib-only. Here `sync` needs bibtexparser and `ledger` needs only
    sqlite3, and docs/LADDERS.md puts `ledger` in the bare-`python`,
    no-venv tier. A top-level `from chitragupta import sync` would take that
    tier away silently -- it would still work on any host with the venv,
    which is every host CI runs on.
  - **The two verbs differ on the write lock**, and must keep differing:
    `sync` holds it for its whole run, `ledger` takes none so it keeps
    working *during* a sync. A shared front door must not quietly become
    a shared lock.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import corpus as entrypoint
from chitragupta import runlock
from tests.conftest import make_reference

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every module the dispatcher forwards to, keyed by the verb chitragupta/corpus.py
# uses for it.
BACKING_MODULES = {
    "sync": "sync",
    "ledger": "ledger_cli",
    "topics": "seed_topics",
    "discover": "discover",
}

# The backing modules that keep the silent-no-op trap docs/ARCHITECTURE.md
# accepts: no `__main__` block, so running one directly imports it and
# exits 0. `sync` is deliberately not among them -- `python -m chitragupta.sync`
# was a real command until 5.2.0 and is the one spelling in this project
# that plausibly sits in a crontab, so it refuses out loud instead (#153).
# See TestTheRemovedSyncCommandRefuses.
SILENT_NO_OP_MODULES = ["ledger_cli", "seed_topics"]

# A real top-level entry-point block, anchored at column 0 -- not the
# string wherever it appears. Same reasoning as test_draft_entrypoint.py:
# a substring check can be fooled by a comment discussing
# `if __name__ == "__main__":` in prose, and chitragupta/sync.py's module-level
# comments discuss its own former entrypoint at length.
_MAIN_BLOCK = re.compile(r'^if __name__ == ["\']__main__["\']:', re.MULTILINE)


def _run(*argv):
    return subprocess.run(
        [sys.executable, *argv],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


class TestTheVerbsAreTheCorpusLayersCommands:
    def test_the_verb_set_is_exactly_the_backing_modules(self):
        assert set(entrypoint.VERBS) == set(BACKING_MODULES)

    @pytest.mark.parametrize("verb", sorted(BACKING_MODULES))
    def test_every_verb_is_reachable_and_declares_its_own_flags(self, verb):
        """--help rather than a run: this pins that the verb's own parser
        was wired in, without touching a corpus or taking a lock."""
        result = _run("-m", "chitragupta.corpus", verb, "--help")
        assert result.returncode == 0, result.stderr
        assert f"chitragupta.corpus {verb}" in result.stdout

    def test_no_verb_prints_the_layers_usage_and_exits_zero(self):
        """ "Tell me how to use this" is not an error -- the same rule
        chitragupta/draft.py and chitragupta/review/__main__.py already apply."""
        result = _run("-m", "chitragupta.corpus")
        assert result.returncode == 0
        for verb in BACKING_MODULES:
            assert verb in result.stdout

    def test_an_unknown_verb_is_a_usage_error(self):
        result = _run("-m", "chitragupta.corpus", "bogus")
        assert result.returncode == 2
        assert "invalid choice: 'bogus'" in result.stderr


class TestTheCommandSurfaceStaysOneLevelDeep:
    """The invariant this file exists for. See docs/ARCHITECTURE.md."""

    @pytest.mark.parametrize("module", sorted(SILENT_NO_OP_MODULES))
    def test_a_backing_module_has_no_main_block(self, module):
        """A backing module must not survive as a second, undocumented way
        in. Without a __main__ block it imports the module and exits 0
        having done nothing -- a trap, but the silent and harmless one
        docs/ARCHITECTURE.md accepts as the price of exactly one --help
        per layer."""
        source = (REPO_ROOT / "chitragupta" / f"{module}.py").read_text(encoding="utf-8")
        assert not _MAIN_BLOCK.search(source)

    @pytest.mark.parametrize("module", sorted(SILENT_NO_OP_MODULES))
    def test_running_a_backing_module_directly_does_nothing(self, module):
        """The observable half of the assertion above."""
        result = _run("-m", f"chitragupta.{module}")
        assert result.returncode == 0
        assert result.stdout == ""


class TestTheRemovedSyncCommandRefuses:
    """`python -m chitragupta.sync` is gone, and says so.

    5.2.0 dropped `chitragupta/sync.py`'s `__main__` block without replacing it,
    which left the spelling exiting 0 while doing nothing -- the one
    place in this project where that trap is not harmless, because that
    command is what a crontab or a systemd unit runs unattended. #151
    found the same silent success in `bench/`, where it turned two
    measurement harnesses into producers of wrong data rather than no
    data. So the module refuses instead (#153).

    This is not a second entry point: it parses no arguments, has no
    `--help`, takes no lock, and runs nothing. It is a signpost with an
    exit code."""

    def test_it_exits_nonzero_and_names_the_replacement(self):
        result = _run("-m", "chitragupta.sync")
        assert result.returncode != 0
        assert "chitragupta corpus sync" in result.stderr

    def test_it_avoids_every_exit_code_sync_publishes(self):
        """docs/CLI.md publishes `0`, `1` and `2` as `sync`'s API, and
        tells an unattended caller that `2` -- the lock is held -- means
        do nothing. A refusal wearing that number would be ignored by the
        very crontab this change exists to reach."""
        result = _run("-m", "chitragupta.sync")
        assert result.returncode not in (0, 1, runlock.EXIT_ALREADY_RUNNING)

    def test_it_says_nothing_on_stdout(self):
        """A refusal belongs on stderr. `sync`'s stdout is a documented,
        diffable contract, and anything parsing it must see an empty one
        rather than a line that reads like a result."""
        result = _run("-m", "chitragupta.sync")
        assert result.stdout == ""

    def test_the_real_command_is_unaffected(self):
        """The refusal lives in the `__main__` block, so dispatching
        through chitragupta/corpus.py must not trip it."""
        result = _run("-m", "chitragupta.corpus", "sync", "--help")
        assert result.returncode == 0
        assert "python -m chitragupta.corpus sync" in result.stdout


class TestLedgerKeepsItsBarePythonTier:
    """docs/LADDERS.md puts `ledger` on rung 1 -- bare `python`, stdlib
    only, no venv -- and `sync` nowhere near it, because bibtexparser is
    not in the standard library. Routing both through one file is only
    safe while that file imports the verb it was actually given.

    Asserted by what ends up in sys.modules rather than by reading the
    imports, because the failure is invisible on any host that has the
    venv -- which is every host this suite runs on.
    """

    def test_importing_the_dispatcher_imports_neither_verb(self):
        result = _run(
            "-c",
            "import sys; from chitragupta import corpus; "
            "print('chitragupta.sync' in sys.modules, 'chitragupta.ledger_cli' in sys.modules)",
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "False False"

    def test_dispatching_ledger_does_not_drag_in_syncs_dependency(self):
        result = _run(
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
    """Each command's own contract, unchanged by being dispatched to. `0`
    on success, `1` on a refusal the command already reported gracefully,
    `2` for a malformed invocation or a lock another run holds. A
    dispatcher that swallowed a return value or mis-forwarded argv so a
    flag landed on the wrong parser would show up here."""

    def test_ledger_on_an_unknown_citekey_exits_one(self, isolated_config, ledger_con):
        from chitragupta import ledger

        ledger.upsert_reference(ledger_con, make_reference())
        assert entrypoint.main(["ledger", "--citekey", "nope_2024"]) == 1

    def test_ledger_summary_exits_zero(self, isolated_config, ledger_con):
        assert entrypoint.main(["ledger"]) == 0

    def test_a_ledger_flag_reaches_ledgers_own_parser(self, isolated_config, ledger_con, capsys):
        """--status is `ledger`'s flag, not the dispatcher's. If argv were
        forwarded to the wrong parser this is where it would surface."""
        assert entrypoint.main(["ledger", "--status", "parse_failed"]) == 0
        assert "No items with status" in capsys.readouterr().out

    def test_sync_against_a_held_lock_exits_two(self, isolated_config):
        """The one exit code the dispatcher could plausibly lose: it is
        produced in an `except` around the whole run, not returned by
        `run()`."""
        with runlock.pipeline_lock(isolated_config.PIPELINE_LOCK_PATH):
            assert entrypoint.main(["sync"]) == runlock.EXIT_ALREADY_RUNNING

    def test_ledger_takes_no_lock_so_it_works_during_a_sync(self, isolated_config, ledger_con):
        """The asymmetry the shared front door must not erase."""
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
        result = _run("-m", "chitragupta.corpus", "sync", "--bogus-flag")
        assert result.returncode == 2
        assert "--bogus-flag" in result.stderr
