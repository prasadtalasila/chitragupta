"""chitragupta/ledger.py's read side (issue #843): the one read-only
opener every reader goes through, and the writer's migration taken under
a write lock so two first-touches of an old ledger cannot race.

A reader must never create, migrate or lock the ledger. It used to open
it through `connect()`, the writer, so a genre skill's first `search()`
before any sync created an empty `content/ledger.sqlite` -- after which
`corpus ledger` said "empty" rather than "no ledger", which is the
distinction the skills refuse on.
"""

import sqlite3
import threading
import time

import pytest

from chitragupta import ledger

# The original, schema-version-0 table: what a ledger written before any
# migration looks like on disk.
_V0_TABLE = """
    CREATE TABLE items (
        citekey TEXT PRIMARY KEY, item_type TEXT, title TEXT, year TEXT,
        doi TEXT, url TEXT, pdf_path TEXT, pdf_hash TEXT,
        status TEXT NOT NULL DEFAULT 'discovered', parsed_path TEXT,
        parse_error TEXT, last_synced TEXT NOT NULL
    )
"""


def _v0_ledger(isolated_config) -> None:
    isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(isolated_config.LEDGER_PATH)
    raw.execute(_V0_TABLE)
    raw.commit()
    raw.close()


def _user_version(path) -> int:
    raw = sqlite3.connect(path)
    try:
        return raw.execute("PRAGMA user_version").fetchone()[0]
    finally:
        raw.close()


class TestReadConnection:
    def test_a_missing_ledger_raises_and_creates_nothing(self, isolated_config):
        with pytest.raises(ledger.NoLedger) as caught:
            ledger.read_connection()
        assert not isolated_config.LEDGER_PATH.exists()
        assert not isolated_config.CONTENT_DIR.exists()
        # The two lines `corpus ledger` has always printed, which the
        # session-start hook matches on its shared instruction.
        assert str(caught.value) == (
            f"No ledger at {isolated_config.LEDGER_PATH}.\n"
            "Run `python -m chitragupta.corpus sync` to build it from your bib file."
        )

    def test_a_ledger_needing_migration_is_refused_not_migrated(self, isolated_config):
        _v0_ledger(isolated_config)
        with pytest.raises(ledger.StaleLedger) as caught:
            ledger.read_connection()
        # A subclass, so a caller refusing on NoLedger refuses on this too.
        assert isinstance(caught.value, ledger.NoLedger)
        assert "chitragupta.corpus sync" in str(caught.value)
        assert _user_version(isolated_config.LEDGER_PATH) == 0

    def test_an_empty_file_is_a_ledger_needing_sync(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True)
        isolated_config.LEDGER_PATH.write_bytes(b"")
        with pytest.raises(ledger.StaleLedger):
            ledger.read_connection()
        assert isolated_config.LEDGER_PATH.read_bytes() == b""

    def test_a_current_ledger_opens_read_only(self, isolated_config):
        ledger.connect().close()
        con = ledger.read_connection()
        try:
            assert ledger.all_items(con) == []
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                con.execute("INSERT INTO items (citekey, last_synced) VALUES ('x_2024', 'now')")
        finally:
            con.close()

    def test_reading_closes_the_connection(self, isolated_config):
        ledger.connect().close()
        with ledger.reading() as con:
            assert ledger.known_citekeys(con) == set()
        with pytest.raises(sqlite3.ProgrammingError):
            con.execute("SELECT 1")


class TestMigrationIsOneTransaction:
    def test_a_second_writer_waits_for_the_first_migration(self, isolated_config):
        # Deterministic form of the race: B is part-way through migrating a
        # v0 ledger (write lock held, nothing committed) when A connects.
        # Without the write lock A read user_version 0 and the pre-migration
        # columns, then re-ran ALTER TABLE after B committed and died on
        # "duplicate column name".
        _v0_ledger(isolated_config)
        other = sqlite3.connect(isolated_config.LEDGER_PATH, isolation_level=None)
        other.execute("BEGIN IMMEDIATE")
        for steps in ledger._MIGRATIONS:
            for _column, statement in steps:
                other.execute(statement)
        other.execute(f"PRAGMA user_version = {len(ledger._MIGRATIONS)}")

        errors = []

        def connect_a():
            try:
                ledger.connect().close()
            except sqlite3.Error as exc:  # the failure being guarded
                errors.append(exc)

        thread = threading.Thread(target=connect_a)
        thread.start()
        time.sleep(0.3)
        other.execute("COMMIT")
        other.close()
        thread.join()
        assert errors == []
        assert _user_version(isolated_config.LEDGER_PATH) == len(ledger._MIGRATIONS)

    def test_two_threads_first_touching_a_v0_ledger_both_succeed(self, isolated_config):
        _v0_ledger(isolated_config)
        barrier = threading.Barrier(2)
        errors = []

        def first_touch():
            barrier.wait()
            try:
                ledger.connect().close()
            except sqlite3.Error as exc:  # the failure being guarded
                errors.append(exc)

        threads = [threading.Thread(target=first_touch) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert errors == []
        assert _user_version(isolated_config.LEDGER_PATH) == len(ledger._MIGRATIONS)

    def test_a_failed_migration_rolls_back_entirely(self, isolated_config, monkeypatch):
        _v0_ledger(isolated_config)
        monkeypatch.setattr(
            ledger,
            "_MIGRATIONS",
            [(("pdf_size", "ALTER TABLE items ADD COLUMN pdf_size INTEGER"),), (("x", "BOGUS"),)],
        )
        with pytest.raises(sqlite3.OperationalError):
            ledger.connect()
        raw = sqlite3.connect(isolated_config.LEDGER_PATH)
        try:
            cols = {row[1] for row in raw.execute("PRAGMA table_info(items)")}
        finally:
            raw.close()
        assert "pdf_size" not in cols
        assert _user_version(isolated_config.LEDGER_PATH) == 0
