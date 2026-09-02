"""`python -m chitragupta.corpus ledger`: read-only status for the corpus layer.

Deliberately its own entrypoint rather than a `sync --inspect` flag, for
two reasons that are both about what a *reader* needs:

  - `sync` takes the pipeline write lock, so an inspect flag on it would
    exit 2 exactly when you most want to look -- while a sync is running.
    This takes no lock at all, which is the property the separate lock
    file was built to preserve.
  - `sync` needs bibtexparser. Reading the ledger needs sqlite3, so this
    runs under the bare system interpreter like citation_gate and
    references do.
"""

import sqlite3
import subprocess
import sys
import threading
import time

import pytest

from chitragupta import config, ledger, ledger_cli
from tests.conftest import make_reference


# How long TestReadOnly's lock test holds a writer's EXCLUSIVE lock.
# Comfortably inside sqlite's 5s default timeout, so the reader recovers
# with room to spare, and long enough that half of it is an unambiguous
# "this call blocked" on a loaded CI runner.
_HOLD = 0.5


def _run(args=(), cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "chitragupta.corpus", "ledger", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or config.PROJECT_ROOT),
    )


@pytest.fixture
def corpus(isolated_config, ledger_con, tmp_path):
    for i, status in enumerate(["parsed", "parsed", "no_pdf", "discovered"]):
        pdf = None
        if status != "no_pdf":
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + bytes([i]))
        ref = make_reference(citekey=f"key_{i}", pdf_path=str(pdf) if pdf else None)
        ledger.upsert_reference(ledger_con, ref)
        if status == "parsed":
            ledger.mark_parsed(ledger_con, ref.citekey, tmp_path / f"{ref.citekey}.txt")
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-bad")
    ref = make_reference(citekey="broken_1", pdf_path=str(bad))
    ledger.upsert_reference(ledger_con, ref)
    ledger.mark_parse_failed(ledger_con, "broken_1", "cannot read", transient=False)
    return isolated_config


class TestSummary:
    def test_it_summarises_rather_than_dumping_every_row(self, corpus, capsys):
        assert ledger_cli.main([]) == 0
        out = capsys.readouterr().out
        assert "2  parsed" in out
        assert "1  no PDF attachment" in out
        # The whole point: the old snippet printed a ~200-char dict per
        # item, which is unreadable for a real corpus.
        assert "citekey" not in out.lower() or "key_0" not in out

    def test_a_deterministic_failure_is_called_out_with_what_to_do(self, corpus, capsys):
        ledger_cli.main([])
        out = capsys.readouterr().out
        assert "need attention" in out
        assert "--reparse" in out

    def test_a_clean_corpus_says_so(self, isolated_config, ledger_con, tmp_path, capsys):
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parsed(ledger_con, ref.citekey, tmp_path / "a.txt")
        ledger_cli.main([])
        assert "nothing needs attention" in capsys.readouterr().out.lower()

    def test_an_empty_ledger_says_to_run_sync(self, isolated_config, capsys):
        assert ledger_cli.main([]) == 0
        assert "chitragupta.corpus sync" in capsys.readouterr().out


class TestFilters:
    def test_status_filter_lists_matching_items(self, corpus, capsys):
        assert ledger_cli.main(["--status", "parse_failed"]) == 0
        out = capsys.readouterr().out
        assert "broken_1" in out
        assert "key_0" not in out

    def test_citekey_shows_one_item_in_full(self, corpus, capsys):
        assert ledger_cli.main(["--citekey", "broken_1"]) == 0
        out = capsys.readouterr().out
        assert "broken_1" in out
        assert "cannot read" in out

    def test_an_unknown_citekey_is_reported_not_silent(self, corpus, capsys):
        assert ledger_cli.main(["--citekey", "nope_2024"]) == 1
        assert "not in the ledger" in capsys.readouterr().out

    def test_list_shows_every_item(self, corpus, capsys):
        assert ledger_cli.main(["--list"]) == 0
        out = capsys.readouterr().out
        assert all(f"key_{i}" in out for i in range(4))


class TestStdlibOnly:
    def test_it_runs_under_the_bare_system_interpreter(self):
        """It joins citation_gate and references in README's stdlib-only
        list -- reading the ledger needs sqlite3, not bibtexparser."""
        result = _run(["--help"])
        assert result.returncode == 0, result.stderr
        assert "--status" in result.stdout

    def test_it_takes_no_lock_so_it_works_during_a_sync(self, isolated_config, tmp_path):
        """The reason this is not `sync --inspect`: an inspect flag on
        sync would exit 2 exactly when you most want to look."""
        from chitragupta import runlock

        with runlock.pipeline_lock(isolated_config.PIPELINE_LOCK_PATH):
            assert ledger_cli.main([]) == 0


class TestEdges:
    def test_a_status_with_no_matches_says_so(self, corpus, capsys):
        assert ledger_cli.main(["--status", "discovered_typo"]) == 0
        assert "No items with status" in capsys.readouterr().out

    def test_an_existing_but_empty_ledger_says_to_run_sync(
        self, isolated_config, ledger_con, capsys
    ):
        """Distinct from "no ledger file": the file exists because
        something connected, but sync has never populated it."""
        assert ledger_cli.main([]) == 0
        out = capsys.readouterr().out
        assert "empty" in out.lower()
        assert "chitragupta.corpus sync" in out

    def test_transient_failures_are_reported_as_self_healing(
        self, isolated_config, ledger_con, tmp_path, capsys
    ):
        """A user seeing failures needs to know which ones they must act
        on -- these are not those."""
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parse_failed(ledger_con, ref.citekey, "worker died", transient=True)

        ledger_cli.main([])
        out = capsys.readouterr().out
        assert "retried on the next sync" in out
        assert "need attention" not in out


class TestReadOnly:
    def test_it_does_not_write_to_the_ledger(self, corpus):
        """connect() runs migrations and commits; this must not. Checked
        by mtime rather than by inspection, because the failure mode is a
        write nobody notices."""
        before = config.LEDGER_PATH.stat().st_mtime_ns
        assert ledger_cli.main([]) == 0
        assert config.LEDGER_PATH.stat().st_mtime_ns == before

    def test_it_waits_out_a_writers_commit_window(self, corpus):
        """m-72: nothing here sets `journal_mode = WAL`, so the default
        rollback journal *does* lock a reader out for the length of a
        writer's commit -- and `timeout=0` turned that short, certain
        window into an immediate `SQLITE_BUSY`, i.e. this command failing
        exactly when its own docstring says it is most worth running.

        A real held lock rather than an assertion about the `timeout`
        argument, because the argument is not the claim; surviving the
        window is. `_HOLD` is released well inside sqlite's default
        timeout, so the reader only has to outlast that much waiting.

        The elapsed assertion is what makes exiting 0 mean anything: a
        reader that did not reach `main()` until after the rollback would
        succeed without ever meeting a lock, and pass against the very
        `timeout=0` this test exists to reject. It cannot have returned
        before the lock was released, so a run that took an appreciable
        fraction of `_HOLD` is one that blocked and recovered.
        """
        writer = sqlite3.connect(config.LEDGER_PATH, isolation_level=None)
        writer.execute("BEGIN EXCLUSIVE")
        entered = threading.Event()
        result = {}

        def read():
            entered.set()
            start = time.monotonic()
            result["code"] = ledger_cli.main([])
            result["waited"] = time.monotonic() - start

        reader = threading.Thread(target=read)
        try:
            reader.start()
            assert entered.wait(timeout=30)
            time.sleep(_HOLD)
        finally:
            writer.execute("ROLLBACK")
            writer.close()
        reader.join(timeout=30)

        assert not reader.is_alive()
        assert result["code"] == 0
        assert result["waited"] >= _HOLD / 2

    def test_a_pre_failure_kind_ledger_still_summarises(
        self, isolated_config, ledger_con, tmp_path, capsys
    ):
        """Read-only means it cannot migrate, so a ledger older than the
        failure_kind column must degrade rather than crash."""
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        ledger.upsert_reference(ledger_con, make_reference(pdf_path=str(pdf)))
        ledger_con.execute("ALTER TABLE items RENAME COLUMN failure_kind TO fk_old")
        ledger_con.commit()

        assert ledger_cli.main([]) == 0
        assert "1  found, not yet parsed" in capsys.readouterr().out
