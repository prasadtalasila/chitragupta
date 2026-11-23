"""Schema version 5: the importer's collection names and recorded renames
(plans/1211-cg-collections-and-renames.md, Task 3)."""

import sqlite3

import pytest

from chitragupta import bib_collections, ledger, ledger_tables

from tests.conftest import make_reference


def _tables(con) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _v4_ledger(path) -> None:
    """A ledger as 6.x left it: version 4, a `groups` path in a row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = ledger.connect()
    con.close()
    raw = sqlite3.connect(path)
    raw.execute("DROP TABLE collection_names")
    raw.execute("DROP TABLE renames")
    raw.execute("DROP TABLE stale_citekeys")
    raw.execute(
        "INSERT INTO items (citekey, status, last_synced, collections) VALUES (?, ?, ?, ?)",
        ("old_2020", "discovered", "2020-01-01T00:00:00+00:00", '["Digital twins > Modelling"]'),
    )
    raw.execute("PRAGMA user_version = 4")
    raw.commit()
    raw.close()


class TestMigration:
    def test_fresh_ledger_has_v5_tables(self, ledger_con):
        assert {"collection_names", "renames", "stale_citekeys"} <= _tables(ledger_con)
        assert ledger_con.execute("PRAGMA user_version").fetchone()[0] == 5

    def test_v4_ledger_migrates_and_clears_groups_paths(self, isolated_config):
        _v4_ledger(isolated_config.LEDGER_PATH)
        con = ledger.connect()
        try:
            assert {"collection_names", "renames"} <= _tables(con)
            assert con.execute("PRAGMA user_version").fetchone()[0] == 5
            (stored,) = con.execute(
                "SELECT collections FROM items WHERE citekey = 'old_2020'"
            ).fetchone()
            assert stored is None
        finally:
            con.close()

    def test_a_migrated_ledger_keeps_new_collections_on_reconnect(self, ledger_con):
        """The clearing step runs on the v4 -> v5 move only, never again."""
        ledger.upsert_reference(ledger_con, make_reference(citekey="k_2024", collections=("a.b",)))
        ledger_con.commit()
        again = ledger.connect()
        try:
            row = again.execute("SELECT collections FROM items WHERE citekey = 'k_2024'").fetchone()
            assert row[0] == '["a.b"]'
        finally:
            again.close()


class TestCollectionNames:
    def test_replace_and_read(self, ledger_con):
        ledger_tables.replace_collection_names(ledger_con, {"a": "A", "a.b": "B"})
        assert ledger_tables.collection_names(ledger_con) == {"a": "A", "a.b": "B"}
        ledger_tables.replace_collection_names(ledger_con, {"a": "Renamed"})
        assert ledger_tables.collection_names(ledger_con) == {"a": "Renamed"}

    def test_a_renamed_collection_keeps_its_slug_working(self, ledger_con):
        """#1211: renaming `Plants DT` in the reference manager changes the
        name row, never the slug a `scope.md` recorded."""
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="k_2024", collections=("plants-dt",))
        )
        ledger_tables.replace_collection_names(ledger_con, {"plants-dt": "Plants DT"})
        ledger_tables.replace_collection_names(ledger_con, {"plants-dt": "Plant Digital Twins"})
        names = ledger_tables.collection_names(ledger_con)
        row = ledger_con.execute("SELECT collections FROM items").fetchone()
        stored = bib_collections.of_row({"collections": row[0]})
        assert bib_collections.resolve("plants-dt", names, stored) == "plants-dt"
        assert bib_collections.resolve("Plant Digital Twins", names, stored) == "plants-dt"
        assert bib_collections.matches(stored, "plants-dt")

    def test_works_with_a_row_factory(self, ledger_con):
        ledger_tables.replace_collection_names(ledger_con, {"a": "A"})
        ledger_con.row_factory = sqlite3.Row
        try:
            assert ledger_tables.collection_names(ledger_con) == {"a": "A"}
        finally:
            ledger_con.row_factory = None


class TestRenames:
    def test_read(self, ledger_con):
        ledger_con.execute(
            "INSERT INTO renames VALUES ('old_2020', 'new_2020', 'pdf_hash', 1, '2026-11-22')"
        )
        ledger_con.execute(
            "INSERT INTO renames VALUES ('a_2021', 'b_2021', 'cg-renames', 0, '2026-11-22')"
        )
        assert ledger_tables.renames(ledger_con) == {
            "old_2020": ("new_2020", "pdf_hash", True),
            "a_2021": ("b_2021", "cg-renames", False),
        }

    def test_source_is_constrained(self, ledger_con):
        with pytest.raises(sqlite3.IntegrityError):
            ledger_con.execute("INSERT INTO renames VALUES ('a', 'b', 'guess', 1, '2026-11-22')")


class TestStale:
    def test_replace_and_read(self, ledger_con):
        ledger_tables.replace_stale(ledger_con, {"a_2020", "b_2020"})
        assert ledger_tables.stale(ledger_con) == {"a_2020", "b_2020"}
        ledger_tables.replace_stale(ledger_con, set())
        assert ledger_tables.stale(ledger_con) == set()


class TestWithoutTheTables:
    """A connection to a database without v5's tables -- a caller's own
    sqlite3 handle, say -- reads as "nothing recorded", like `of_row`."""

    @pytest.mark.parametrize(
        "reader", [ledger_tables.collection_names, ledger_tables.renames, ledger_tables.stale]
    )
    def test_reads_as_empty(self, reader):
        con = sqlite3.connect(":memory:")
        try:
            assert not reader(con)
        finally:
            con.close()


class TestSyncWritesNames:
    BIB = (
        "@comment{cg-collections v1\n"
        "plants-dt\t{name}\n"
        "}\n\n"
        "@article{plant_twin_2024,\n"
        "\ttitle = {A plant twin},\n"
        "\tyear = {2024},\n"
        "\tcg-collections = {plants-dt},\n"
        "}\n"
    )

    def _sync(self, cfg, name):
        from chitragupta import sync

        cfg.BIB_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cfg.BIB_FILE_PATH.write_text(self.BIB.replace("{name}", name), encoding="utf-8")
        sync.run()
        con = ledger.connect()
        try:
            return ledger_tables.collection_names(con)
        finally:
            con.close()

    def test_sync_records_and_replaces_names(self, isolated_config, capsys):
        assert self._sync(isolated_config, "Plants DT") == {"plants-dt": "Plants DT"}
        assert self._sync(isolated_config, "Plant Digital Twins") == {
            "plants-dt": "Plant Digital Twins"
        }
