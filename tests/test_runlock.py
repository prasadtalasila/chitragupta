import json
import contextlib
import multiprocessing
import os
import pathlib
import sqlite3
import time

import pytest

from chitragupta import config, runlock
from tests.lock_holder import hold


_CHILD_TIMEOUT = 30


class TestAcquire:
    def test_the_lock_can_be_taken_and_released(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            pass
        with runlock.pipeline_lock(path):
            pass

    def test_a_second_holder_in_the_same_process_is_refused(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            with pytest.raises(runlock.AlreadyRunning):
                with runlock.pipeline_lock(path):
                    pass

    def test_the_message_says_what_to_do(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            with pytest.raises(runlock.AlreadyRunning) as excinfo:
                with runlock.pipeline_lock(path):
                    pass
        message = str(excinfo.value)
        assert "already running" in message.lower()
        assert "nothing is lost" in message.lower()

    def test_the_lock_file_is_created_with_its_parent(self, tmp_path):
        path = tmp_path / "fresh" / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            assert path.exists()

    def test_the_lock_file_is_never_deleted(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            pass
        assert path.exists()


class TestReadersAreNotBlocked:
    def test_a_reader_can_still_read_the_ledger_while_a_run_holds_the_lock(
        self, isolated_config, tmp_path
    ):
        from chitragupta import ledger

        con = ledger.connect()
        con.close()
        with runlock.pipeline_lock(tmp_path / "pipeline.lock.db"):
            reader = sqlite3.connect(config.LEDGER_PATH, timeout=1)
            assert reader.execute("SELECT count(*) FROM items").fetchone()[0] == 0
            reader.close()


@contextlib.contextmanager
def _holder_process(path):
    ctx = multiprocessing.get_context("spawn")
    started = ctx.Event()
    holder = ctx.Process(target=hold, args=(path, started))
    holder.start()
    try:
        assert started.wait(_CHILD_TIMEOUT), (
            f"the holder never acquired the lock within {_CHILD_TIMEOUT}s "
            f"(exitcode={holder.exitcode}, alive={holder.is_alive()})"
        )
        yield holder
    finally:
        if holder.is_alive():
            holder.kill()
        holder.join(_CHILD_TIMEOUT)
        if not holder.is_alive():
            holder.close()


class TestAcrossProcesses:
    def test_a_second_process_is_refused_while_the_first_holds_it(self, tmp_path):
        path = str(tmp_path / "pipeline.lock.db")
        with _holder_process(path):
            with pytest.raises(runlock.AlreadyRunning):
                with runlock.pipeline_lock(path):
                    pass

    def test_a_killed_holder_releases_the_lock(self, tmp_path):
        path = str(tmp_path / "pipeline.lock.db")
        with _holder_process(path) as holder:
            holder.kill()
            holder.join(_CHILD_TIMEOUT)
            assert not holder.is_alive(), "the killed holder would not die"

            deadline = time.monotonic() + 10
            while True:
                try:
                    with runlock.pipeline_lock(path):
                        break
                except runlock.AlreadyRunning:
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(0.2)


class TestFailuresThatAreNotContention:
    def test_an_unusable_lock_file_is_not_reported_as_another_run(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        path.write_text("this is not a sqlite database")
        with pytest.raises(sqlite3.DatabaseError):
            with runlock.pipeline_lock(path):
                pass


class TestCleanup:
    def test_a_failure_that_is_not_busy_still_closes_the_connection(self, tmp_path, monkeypatch):
        path = tmp_path / "pipeline.lock.db"
        lock = runlock.pipeline_lock(path)
        closed = []

        class ExplodingConnection:
            def execute(self, *_args):
                raise MemoryError("boom")

            def close(self):
                closed.append(True)

        monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: ExplodingConnection())
        with pytest.raises(MemoryError):
            lock.__enter__()
        assert closed, "the connection was left open, i.e. the lock was left held"
        assert lock._con is None

        monkeypatch.undo()
        with runlock.pipeline_lock(path):
            pass

    def test_exiting_without_having_acquired_is_harmless(self, tmp_path):
        lock = runlock.pipeline_lock(tmp_path / "pipeline.lock.db")
        assert lock.__exit__(None, None, None) is False

    def test_a_non_busy_operational_error_is_reraised_not_misreported(self, tmp_path, monkeypatch):
        class FailingConnection:
            def execute(self, *_args):
                raise sqlite3.OperationalError("disk I/O error")

            def close(self):
                pass

        monkeypatch.setattr(sqlite3, "connect", lambda *a, **k: FailingConnection())
        with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
            with runlock.pipeline_lock(tmp_path / "pipeline.lock.db"):
                pass


class TestHolderVisibility:
    def test_the_refusal_reports_how_long_the_holder_has_been_running(self, tmp_path, monkeypatch):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            with pytest.raises(runlock.AlreadyRunning) as excinfo:
                with runlock.pipeline_lock(path):
                    pass
        message = str(excinfo.value)
        assert "started" in message.lower()
        assert "pid" in message.lower()

    def test_a_long_held_lock_escalates_the_wording(self, tmp_path, monkeypatch):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            monkeypatch.setattr(runlock, "_STUCK_AFTER_SECONDS", 0.0)
            with pytest.raises(runlock.AlreadyRunning) as excinfo:
                with runlock.pipeline_lock(path):
                    pass
        assert "POSSIBLY STUCK" in str(excinfo.value)

    def test_holder_details_live_beside_the_lock_not_inside_it(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            data = json.loads((tmp_path / "pipeline.lock.db.holder").read_text())
        assert data["pid"] == os.getpid()

    def test_recording_the_holder_never_costs_the_lock(self, tmp_path, monkeypatch):
        path = tmp_path / "pipeline.lock.db"

        def refuse(*_a, **_k):
            raise OSError("read-only filesystem")

        monkeypatch.setattr(pathlib.Path, "write_text", refuse)
        with runlock.pipeline_lock(path):
            monkeypatch.undo()
            with pytest.raises(runlock.AlreadyRunning):
                with runlock.pipeline_lock(path):
                    pass

    def test_a_missing_holder_row_does_not_break_the_refusal(self, tmp_path, monkeypatch):
        path = tmp_path / "pipeline.lock.db"
        with runlock.pipeline_lock(path):
            monkeypatch.setattr(runlock, "_describe_holder", lambda _p: None)
            with pytest.raises(runlock.AlreadyRunning) as excinfo:
                with runlock.pipeline_lock(path):
                    pass
        assert "already running" in str(excinfo.value).lower()

    def test_a_missing_sidecar_is_handled(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        path.write_bytes(b"")
        assert runlock._describe_holder(path) is None

    def test_a_corrupt_sidecar_is_handled(self, tmp_path):
        path = tmp_path / "pipeline.lock.db"
        (tmp_path / "pipeline.lock.db.holder").write_text("{not json")
        assert runlock._describe_holder(path) is None

    def test_the_refusal_survives_an_undescribable_holder(self, tmp_path):
        message = runlock._refusal_message(tmp_path / "never-created.db")
        assert "already running" in message.lower()
        assert "nothing is lost" in message.lower()
