import collections
import json
import os
import sqlite3
import types
from pathlib import Path
import time

import pytest

from chitragupta import config, ledger, ledger_bib_fields, ledger_paths, ledger_upsert, passages

from tests.conftest import make_reference, parsed_file


class TestConnect:
    def test_creates_schema_and_content_dir(self, isolated_config):
        assert not isolated_config.CONTENT_DIR.exists()
        con = ledger.connect()
        try:
            assert isolated_config.LEDGER_PATH.exists()
            assert ledger.all_items(con) == []
        finally:
            con.close()

    def test_idempotent_across_calls(self, isolated_config):
        con1 = ledger.connect()
        con1.close()
        con2 = ledger.connect()
        try:
            assert ledger.all_items(con2) == []
        finally:
            con2.close()


class TestRowsForCitekeys:
    @staticmethod
    def _seed(con, keys):
        for key in keys:
            con.execute(
                "INSERT INTO items (citekey, title, status, last_synced)"
                " VALUES (?, ?, 'parsed', '2026-01-01')",
                (key, f"T {key}"),
            )
        con.commit()

    def test_more_citekeys_than_the_variable_ceiling_still_answers(self, isolated_config):
        con = ledger.connect()
        try:
            self._seed(con, ["a_2024", "b_2024"])
            keys = ["a_2024", "b_2024", *(f"ghost{i}" for i in range(33_000))]
            rows = ledger.rows_for_citekeys(con, "citekey, title", keys)
        finally:
            con.close()
        assert sorted(rows) == [("a_2024", "T a_2024"), ("b_2024", "T b_2024")]

    def test_chunks_are_unioned_not_truncated(self, isolated_config, monkeypatch):
        monkeypatch.setattr(ledger, "CITEKEY_CHUNK", 2)
        con = ledger.connect()
        try:
            self._seed(con, ["a_2024", "b_2024", "c_2024", "d_2024", "e_2024"])
            rows = ledger.rows_for_citekeys(
                con, "citekey", ["a_2024", "b_2024", "c_2024", "d_2024", "e_2024"]
            )
        finally:
            con.close()
        assert sorted(rows) == [("a_2024",), ("b_2024",), ("c_2024",), ("d_2024",), ("e_2024",)]

    def test_an_empty_list_runs_no_query_and_returns_nothing(self, isolated_config):
        con = ledger.connect()
        try:
            assert ledger.rows_for_citekeys(con, "citekey", []) == []
        finally:
            con.close()


class TestSchemaMigration:
    def test_fresh_database_is_at_current_schema_version(self, isolated_config):
        con = ledger.connect()
        try:
            (version,) = con.execute("PRAGMA user_version").fetchone()
            assert version == len(ledger._MIGRATIONS)
            cols = {row[1] for row in con.execute("PRAGMA table_info(items)")}
            assert {"pdf_size", "pdf_mtime_ns"} <= cols
        finally:
            con.close()

    def test_legacy_database_predating_the_migration_gets_upgraded(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(isolated_config.LEDGER_PATH)
        raw.execute("""
            CREATE TABLE items (
                citekey TEXT PRIMARY KEY,
                item_type TEXT,
                title TEXT,
                year TEXT,
                doi TEXT,
                url TEXT,
                pdf_path TEXT,
                pdf_hash TEXT,
                status TEXT NOT NULL DEFAULT 'discovered',
                parsed_path TEXT,
                parse_error TEXT,
                last_synced TEXT NOT NULL
            )
        """)
        raw.execute(
            "INSERT INTO items (citekey, status, last_synced) VALUES (?, ?, ?)",
            ("legacy_key", "discovered", "2020-01-01T00:00:00+00:00"),
        )
        raw.commit()
        raw.close()

        con = ledger.connect()
        try:
            cols = {row[1] for row in con.execute("PRAGMA table_info(items)")}
            assert {"pdf_size", "pdf_mtime_ns"} <= cols
            (version,) = con.execute("PRAGMA user_version").fetchone()
            assert version == len(ledger._MIGRATIONS)
            assert ledger.known_citekeys(con) == {"legacy_key"}
        finally:
            con.close()

    def test_already_migrated_database_is_a_no_op(self, isolated_config):
        con1 = ledger.connect()
        con1.close()

        con2 = ledger.connect()
        try:
            (version,) = con2.execute("PRAGMA user_version").fetchone()
            assert version == len(ledger._MIGRATIONS)
        finally:
            con2.close()

    def test_columns_already_present_at_user_version_zero_does_not_raise(self, isolated_config):
        isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(isolated_config.LEDGER_PATH)
        raw.execute("""
            CREATE TABLE items (
                citekey TEXT PRIMARY KEY,
                item_type TEXT,
                title TEXT,
                year TEXT,
                doi TEXT,
                url TEXT,
                pdf_path TEXT,
                pdf_hash TEXT,
                pdf_size INTEGER,
                pdf_mtime_ns INTEGER,
                status TEXT NOT NULL DEFAULT 'discovered',
                parsed_path TEXT,
                parse_error TEXT,
                last_synced TEXT NOT NULL
            )
        """)
        raw.commit()
        raw.close()

        con = ledger.connect()  # must not raise
        try:
            (version,) = con.execute("PRAGMA user_version").fetchone()
            assert version == len(ledger._MIGRATIONS)
        finally:
            con.close()


class TestBibFields:
    def test_kept_fields_round_trip_as_json(self, ledger_con):
        ref = make_reference(
            citekey="doe2024",
            fields={
                "author": "Doe, Jane",
                "journal": "J. Things",
                "pages": "1--9",
            },
        )
        ledger.upsert_reference(ledger_con, ref)
        (stored,) = ledger_con.execute(
            "SELECT bib_fields FROM items WHERE citekey = 'doe2024'"
        ).fetchone()
        assert json.loads(stored) == {
            "author": "Doe, Jane",
            "journal": "J. Things",
            "pages": "1--9",
        }

    def test_export_noise_is_dropped(self, ledger_con):
        ref = make_reference(
            citekey="noisy2024",
            fields={
                "author": "Doe, Jane",
                "file": "/home/someone/Zotero/storage/ABC/paper.pdf",
                "abstract": "...",
                "keywords": "a, b",
                "urldate": "2026-01-01",
            },
        )
        ledger.upsert_reference(ledger_con, ref)
        (stored,) = ledger_con.execute(
            "SELECT bib_fields FROM items WHERE citekey = 'noisy2024'"
        ).fetchone()
        assert json.loads(stored) == {"author": "Doe, Jane"}

    def test_empty_values_and_no_kept_fields_store_null(self, ledger_con):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="bare2024", fields={"author": "  "})
        )
        (stored,) = ledger_con.execute(
            "SELECT bib_fields FROM items WHERE citekey = 'bare2024'"
        ).fetchone()
        assert stored is None

    def test_update_path_refreshes_the_column(self, ledger_con):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="doe2024", fields={"author": "Doe, Jane"})
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="doe2024", fields={"author": "Roe, Richard"})
        )
        (stored,) = ledger_con.execute(
            "SELECT bib_fields FROM items WHERE citekey = 'doe2024'"
        ).fetchone()
        assert json.loads(stored) == {"author": "Roe, Richard"}

    def test_re_sync_of_an_unchanged_entry_writes_an_identical_value(self, ledger_con):
        a = make_reference(citekey="doe2024", fields={"author": "Doe, Jane", "journal": "J"})
        b = make_reference(citekey="doe2024", fields={"journal": "J", "author": "Doe, Jane"})
        assert ledger_bib_fields.bib_fields_json(a) == ledger_bib_fields.bib_fields_json(b)


class TestUpsertReference:
    def test_new_item_with_pdf_needs_parse(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))
        assert ledger.upsert_reference(ledger_con, ref) is True

        row = ledger_con.execute(
            "SELECT status, pdf_hash FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row[0] == "discovered"
        assert row[1] is not None

    def test_new_item_without_pdf_does_not_need_parse(self, ledger_con):
        ref = make_reference(pdf_path=None)
        assert ledger.upsert_reference(ledger_con, ref) is False

        row = ledger_con.execute(
            "SELECT status, pdf_hash FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row[0] == "no_pdf"
        assert row[1] is None

    def test_unchanged_pdf_hash_does_not_need_reparse(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"same content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        (parsed_file("parsed")).write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_file("parsed"))

        assert ledger.upsert_reference(ledger_con, ref) is False
        row = ledger_con.execute(
            "SELECT status FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row[0] == "parsed"  # status preserved, not reset

    def test_missing_parsed_text_needs_reparse(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"same content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        parsed = parsed_file("parsed")
        parsed.write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed)
        parsed.unlink()

        assert ledger.upsert_reference(ledger_con, ref) is True

    def test_missing_passage_sidecar_needs_reparse_under_docling(
        self, ledger_con, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(config, "PARSER", "docling")
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"same content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        parsed = parsed_file("parsed")
        parsed.write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed)

        assert ledger.upsert_reference(ledger_con, ref) is True

    def test_a_sidecar_is_not_required_of_pdftotext(self, ledger_con, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "PARSER", "pdftotext")
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"same content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        parsed = parsed_file("parsed")
        parsed.write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed)

        assert ledger.upsert_reference(ledger_con, ref) is False

    def test_a_present_sidecar_settles_it_under_docling(self, ledger_con, monkeypatch, tmp_path):
        monkeypatch.setattr(config, "PARSER", "docling")
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"same content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        parsed = parsed_file("parsed")
        parsed.write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed)
        passages.write_sidecar(ref.citekey, [])

        assert ledger.upsert_reference(ledger_con, ref) is False

    @pytest.mark.parametrize("parser", ["docling", "pdftotext"])
    @pytest.mark.parametrize(
        "torn",
        [
            b'[{"text": "A sentence", "pa',  # killed mid-record
            '[{"text": "café"}]'.encode()[:-5],  # split multi-byte char
            b'{"text": "not a list"}',  # parses, but not what was written
        ],
    )
    def test_an_unreadable_sidecar_needs_reparse(
        self, ledger_con, monkeypatch, tmp_path, parser, torn
    ):
        monkeypatch.setattr(config, "PARSER", parser)
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"same content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        parsed = parsed_file("parsed")
        parsed.write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed)
        passages.sidecar_path(ref.citekey).write_bytes(torn)

        assert ledger.upsert_reference(ledger_con, ref) is True

    def test_changed_pdf_hash_needs_reparse(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"version 1")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        (parsed_file("parsed")).write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_file("parsed"))

        pdf.write_bytes(b"version 2, totally different")
        assert ledger.upsert_reference(ledger_con, ref) is True
        row = ledger_con.execute(
            "SELECT status FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row[0] == "discovered"

    def test_pdf_removed_goes_back_to_no_pdf(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)

        ref_no_pdf = make_reference(pdf_path=None)
        needs_parse = ledger.upsert_reference(ledger_con, ref_no_pdf)
        assert needs_parse is False
        row = ledger_con.execute(
            "SELECT status, pdf_hash FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row == ("no_pdf", None)

    def test_updates_bibliographic_fields_in_place(self, ledger_con):
        ref = make_reference(title="Original Title")
        ledger.upsert_reference(ledger_con, ref)
        ref2 = make_reference(title="Updated Title")
        ledger.upsert_reference(ledger_con, ref2)

        row = ledger_con.execute(
            "SELECT title FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row[0] == "Updated Title"
        assert len(ledger.known_citekeys(ledger_con)) == 1

    def test_item_gaining_a_pdf_after_being_no_pdf_needs_parse(self, ledger_con, tmp_path):
        ref_no_pdf = make_reference(pdf_path=None)
        ledger.upsert_reference(ledger_con, ref_no_pdf)

        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"now has content")
        ref_with_pdf = make_reference(pdf_path=str(pdf))
        assert ledger.upsert_reference(ledger_con, ref_with_pdf) is True

        row = ledger_con.execute(
            "SELECT status, pdf_hash FROM items WHERE citekey = ?", (ref_with_pdf.citekey,)
        ).fetchone()
        assert row[0] == "discovered"
        assert row[1] is not None


class TestUpsertReferenceRehashSkip:
    def test_unchanged_size_and_mtime_skips_hashing(self, ledger_con, tmp_path, monkeypatch):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"stable content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        (parsed_file("out")).write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_file("out"))

        calls = []
        original_hash_pdf = ledger_upsert._hash_pdf

        def spy(path):
            calls.append(path)
            return original_hash_pdf(path)

        monkeypatch.setattr(ledger_upsert, "_hash_pdf", spy)

        needs_parse = ledger.upsert_reference(ledger_con, ref)

        assert needs_parse is False
        assert calls == []  # (size, mtime) matched -- hash was never recomputed

    def test_changed_mtime_with_same_size_still_rehashes(self, ledger_con, tmp_path, monkeypatch):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"AAAAAAAAAA")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)

        future = time.time() + 5
        os.utime(pdf, (future, future))

        calls = []
        original_hash_pdf = ledger_upsert._hash_pdf

        def spy(path):
            calls.append(path)
            return original_hash_pdf(path)

        monkeypatch.setattr(ledger_upsert, "_hash_pdf", spy)

        ledger.upsert_reference(ledger_con, ref)

        assert calls == [str(pdf)]

    def test_stored_size_and_mtime_are_persisted(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)

        st = pdf.stat()
        row = ledger_con.execute(
            "SELECT pdf_size, pdf_mtime_ns FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row == (st.st_size, st.st_mtime_ns)


class TestAPdfThatVanishesMidSync:
    def test_a_pdf_gone_before_the_stat_lands_as_no_pdf(self, ledger_con, tmp_path, caplog):
        pdf = tmp_path / "paper.pdf"
        ref = make_reference(pdf_path=str(pdf))  # never created: gone by the time sync looks

        needs_parse = ledger.upsert_reference(ledger_con, ref)

        assert needs_parse is False  # nothing to parse, and no traceback
        row = ledger_con.execute(
            "SELECT status, pdf_path, pdf_hash, pdf_size, pdf_mtime_ns FROM items "
            "WHERE citekey = ?",
            (ref.citekey,),
        ).fetchone()
        assert row == ("no_pdf", pdf.name, None, None, None)
        assert ref.citekey in caplog.text

    def test_a_pdf_gone_between_the_stat_and_the_hash_lands_the_same_way(
        self, ledger_con, tmp_path, monkeypatch
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"here for the stat, gone for the hash")
        ref = make_reference(pdf_path=str(pdf))

        def vanish(path):
            raise FileNotFoundError(2, "No such file or directory", path)

        monkeypatch.setattr(ledger_upsert, "_hash_pdf", vanish)

        assert ledger.upsert_reference(ledger_con, ref) is False
        row = ledger_con.execute(
            "SELECT status, pdf_hash, pdf_size, pdf_mtime_ns FROM items WHERE citekey = ?",
            (ref.citekey,),
        ).fetchone()
        assert row == ("no_pdf", None, None, None)

    def test_it_tells_a_caller_that_asked_and_nothing_more(self, ledger_con, tmp_path):
        seen = []

        gone = make_reference(citekey="gone_2024", pdf_path=str(tmp_path / "absent.pdf"))
        ledger.upsert_reference(ledger_con, gone, on_missing_pdf=seen.append)
        assert len(seen) == 1
        assert isinstance(seen[0], OSError)  # the cause, not just a signal

        del seen[:]
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="never_had_one_2024"), on_missing_pdf=seen.append
        )
        assert seen == []

        readable = tmp_path / "real.pdf"
        readable.write_bytes(b"real content")
        ledger.upsert_reference(
            ledger_con,
            make_reference(citekey="fine_2024", pdf_path=str(readable)),
            on_missing_pdf=seen.append,
        )
        assert seen == []

    def test_an_already_parsed_row_moves_to_no_pdf_and_recovers(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"real content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        parsed = parsed_file("out")
        parsed.write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed)

        def status():
            return ledger_con.execute(
                "SELECT status FROM items WHERE citekey = ?", (ref.citekey,)
            ).fetchone()[0]

        pdf.unlink()
        assert ledger.upsert_reference(ledger_con, ref) is False
        assert status() == "no_pdf"

        pdf.write_bytes(b"real content")
        assert ledger.upsert_reference(ledger_con, ref) is True
        assert status() == "discovered"


class TestUpsertReferenceParsedPathOnHashChange:
    def test_a_changed_hash_clears_parsed_path(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"v1 content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_file("out"))

        pdf.write_bytes(b"v2 content, totally different")
        ledger.upsert_reference(ledger_con, ref)

        (parsed_path,) = ledger_con.execute(
            "SELECT parsed_path FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert parsed_path is None

    def test_an_unchanged_hash_leaves_parsed_path_alone(self, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"stable content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        out = parsed_file("out")
        ledger.mark_parsed(ledger_con, ref.citekey, out)

        ledger.upsert_reference(ledger_con, ref, force=True)

        (parsed_path,) = ledger_con.execute(
            "SELECT parsed_path FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert parsed_path == out.name


class TestStoredPaths:
    def test_mark_parsed_stores_the_name_under_parsed(self, ledger_con, isolated_config):
        ledger.upsert_reference(ledger_con, make_reference(citekey="smith_example_2024"))
        out = isolated_config.PARSED_DIR / "smith_example_2024.txt"
        ledger.mark_parsed(ledger_con, "smith_example_2024", out)
        (stored,) = ledger_con.execute("SELECT parsed_path FROM items").fetchone()
        assert stored == "smith_example_2024.txt"
        assert ledger_paths.parsed_file(stored) == out

    def test_pdf_path_is_stored_relative_to_the_bib_directory(self, ledger_con, isolated_config):
        pdf = isolated_config.BIB_FILE_PATH.parent / "pdfs" / "a.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF")
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="smith_example_2024", pdf_path=str(pdf))
        )
        (stored,) = ledger_con.execute("SELECT pdf_path FROM items").fetchone()
        assert stored == "pdfs/a.pdf"
        assert ledger_paths.pdf_file(stored) == pdf

    def test_a_legacy_absolute_value_still_reads_in_place(self, isolated_config):
        out = isolated_config.PARSED_DIR / "k.txt"
        assert ledger_paths.parsed_file(str(out)) == out

    def test_a_relative_escape_is_refused_loudly(self, isolated_config, capsys):
        assert ledger_paths.parsed_file("../../secret.txt") is None
        assert "WARNING refusing" in capsys.readouterr().err

    def test_storing_a_path_outside_the_root_is_a_bug(self, isolated_config, tmp_path_factory):
        with pytest.raises(ValueError):
            ledger_paths.stored_parsed(tmp_path_factory.mktemp("x") / "k.txt")

    def test_a_symlinked_bib_roots_pdfs_at_its_real_directory(
        self, ledger_con, isolated_config, tmp_path, monkeypatch
    ):
        real = tmp_path / "zotero"
        (real / "pdfs").mkdir(parents=True)
        pdf = real / "pdfs" / "a.pdf"
        pdf.write_bytes(b"%PDF")
        (real / "library.bib").write_text("")
        link = tmp_path / "proj" / "library.bib"
        link.parent.mkdir()
        try:
            link.symlink_to(real / "library.bib")
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unavailable")
        monkeypatch.setattr(config, "BIB_FILE_PATH", link)
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="smith_example_2024", pdf_path=str(pdf))
        )
        (stored,) = ledger_con.execute("SELECT pdf_path FROM items").fetchone()
        assert stored == "pdfs/a.pdf"
        assert ledger_paths.pdf_file(stored) == pdf.resolve()

    def test_a_second_connect_leaves_null_and_relative_rows_alone(self, isolated_config):
        con = ledger.connect()
        con.execute(
            "INSERT INTO items (citekey, status, parsed_path, last_synced) VALUES "
            "('a2024', 'discovered', NULL, 'x'), ('b2024', 'parsed', 'b2024.txt', 'x')"
        )
        con.commit()
        con.close()
        con = ledger.connect()
        try:
            rows = con.execute("SELECT citekey, parsed_path FROM items ORDER BY citekey").fetchall()
        finally:
            con.close()
        assert rows == [("a2024", None), ("b2024", "b2024.txt")]

    def test_connect_rewrites_legacy_absolute_parsed_paths(self, isolated_config):
        con = ledger.connect()
        con.execute(
            "INSERT INTO items (citekey, status, parsed_path, last_synced) "
            "VALUES ('smith_example_2024', 'parsed', "
            "'/old/host/content/parsed/smith_example_2024.txt', 'x')"
        )
        con.commit()
        con.close()
        con = ledger.connect()
        try:
            (stored,) = con.execute("SELECT parsed_path FROM items").fetchone()
        finally:
            con.close()
        assert stored == "smith_example_2024.txt"


class TestMarkParsed:
    def test_sets_status_and_clears_error(self, ledger_con, tmp_path):
        ref = make_reference()
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parse_failed(ledger_con, ref.citekey, "boom")

        parsed_path = parsed_file("out")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_path)

        row = ledger_con.execute(
            "SELECT status, parsed_path, parse_error FROM items WHERE citekey = ?",
            (ref.citekey,),
        ).fetchone()
        assert row == ("parsed", parsed_path.name, None)


class TestMarkParseFailed:
    def test_sets_status_and_error(self, ledger_con):
        ref = make_reference()
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parse_failed(ledger_con, ref.citekey, "pdftotext exploded")

        row = ledger_con.execute(
            "SELECT status, parse_error FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row == ("parse_failed", "pdftotext exploded")


class TestKnownCitekeysAndAllItems:
    def test_known_citekeys_empty_ledger(self, ledger_con):
        assert ledger.known_citekeys(ledger_con) == set()

    def test_known_citekeys_reflects_inserts(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a_2024"))
        ledger.upsert_reference(ledger_con, make_reference(citekey="b_2024"))
        assert ledger.known_citekeys(ledger_con) == {"a_2024", "b_2024"}

    def test_all_items_ordered_by_citekey(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="zeta_2024"))
        ledger.upsert_reference(ledger_con, make_reference(citekey="alpha_2024"))
        rows = ledger.all_items(ledger_con)
        assert [r["citekey"] for r in rows] == ["alpha_2024", "zeta_2024"]

    def test_all_items_row_supports_column_access(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a_2024", title="Title A"))
        rows = ledger.all_items(ledger_con)
        assert rows[0]["title"] == "Title A"

    def test_all_items_leaves_the_callers_own_row_factory_alone(self, ledger_con):
        def mine(cursor, row):
            return {"mine": row[0]}

        ledger_con.row_factory = mine
        ledger.upsert_reference(ledger_con, make_reference(citekey="a_2024"))
        ledger.all_items(ledger_con)
        assert ledger_con.row_factory is mine
        assert ledger_con.execute("SELECT citekey FROM items").fetchone() == {"mine": "a_2024"}

    def test_a_raising_query_does_not_leave_the_connection_in_row_mode(self, ledger_con):
        ledger_con.row_factory = None
        ledger_con.execute("DROP TABLE items")
        with pytest.raises(sqlite3.OperationalError):
            ledger.all_items(ledger_con)
        assert ledger_con.row_factory is None


class TestFindStale:
    def test_finds_citekey_no_longer_in_bib(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))
        ledger.upsert_reference(ledger_con, make_reference(citekey="orphaned_key"))

        stale = ledger.find_stale(ledger_con, seen_citekeys={"kept_key"})

        assert [k for k, _ in stale] == ["orphaned_key"]
        assert ledger.known_citekeys(ledger_con) == {"kept_key", "orphaned_key"}

    def test_no_stale_citekeys_is_empty(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))

        assert ledger.find_stale(ledger_con, seen_citekeys={"kept_key"}) == []

    def test_never_raises_even_when_seen_citekeys_is_empty(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))

        stale = ledger.find_stale(ledger_con, seen_citekeys=set())

        assert [k for k, _ in stale] == ["kept_key"]
        assert ledger.known_citekeys(ledger_con) == {"kept_key"}


class TestPruneMissing:
    def test_removes_citekeys_no_longer_in_bib(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))
        ledger.upsert_reference(ledger_con, make_reference(citekey="orphaned_key"))

        removed = ledger.prune_missing(ledger_con, seen_citekeys={"kept_key"})

        assert [k for k, _ in removed] == ["orphaned_key"]
        assert ledger.known_citekeys(ledger_con) == {"kept_key"}

    def test_no_orphans_is_a_no_op(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))

        removed = ledger.prune_missing(ledger_con, seen_citekeys={"kept_key"})

        assert removed == []
        assert ledger.known_citekeys(ledger_con) == {"kept_key"}

    def test_pruned_citekey_is_no_longer_known(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))
        ledger.upsert_reference(ledger_con, make_reference(citekey="removed_from_bib"))
        ledger.prune_missing(ledger_con, seen_citekeys={"kept_key"})

        assert "removed_from_bib" not in ledger.known_citekeys(ledger_con)

    def test_returns_parsed_path_for_caller_cleanup(self, ledger_con, tmp_path):
        parsed_path = parsed_file("orphaned_key")
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))
        ref = make_reference(citekey="orphaned_key")
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parsed(ledger_con, "orphaned_key", parsed_path)

        removed = ledger.prune_missing(ledger_con, seen_citekeys={"kept_key"})

        assert removed == [("orphaned_key", parsed_path.name)]

    def test_refuses_to_prune_everything_when_bib_yields_nothing(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="kept_key"))

        with pytest.raises(RuntimeError, match="Refusing to prune"):
            ledger.prune_missing(ledger_con, seen_citekeys=set())

        assert ledger.known_citekeys(ledger_con) == {"kept_key"}

    def test_empty_ledger_with_empty_seen_citekeys_is_still_a_no_op(self, ledger_con):
        assert ledger.prune_missing(ledger_con, seen_citekeys=set()) == []


class TestFailedParseIsRetried:
    def test_a_transient_parse_failure_is_retried_while_the_pdf_is_unchanged(
        self, isolated_config, ledger_con, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))

        assert ledger.upsert_reference(ledger_con, ref) is True
        ledger.mark_parse_failed(ledger_con, ref.citekey, "worker died", transient=True)

        assert ledger.upsert_reference(ledger_con, ref) is True

    def test_a_successful_parse_is_still_not_redone(self, isolated_config, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))

        ledger.upsert_reference(ledger_con, ref)
        (parsed_file("out")).write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_file("out"))

        assert ledger.upsert_reference(ledger_con, ref) is False

    def test_retrying_resets_the_status_so_it_is_not_reported_as_failed(
        self, isolated_config, ledger_con, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(ledger_con, ref)
        ledger.mark_parse_failed(ledger_con, ref.citekey, "worker died", transient=True)

        ledger.upsert_reference(ledger_con, ref)
        row = ledger_con.execute(
            "SELECT status FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row[0] == "discovered"


class TestDiscoveredIsRescheduled:
    def test_a_discovered_row_with_an_unchanged_pdf_is_parsed_next_run(
        self, isolated_config, ledger_con, tmp_path
    ):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))

        assert ledger.upsert_reference(ledger_con, ref) is True

        assert ledger.upsert_reference(ledger_con, ref) is True

    def test_a_discovered_row_without_a_pdf_is_not_parsed(self, isolated_config, ledger_con):
        ref = make_reference(pdf_path=None)
        ledger.upsert_reference(ledger_con, ref)
        assert ledger.upsert_reference(ledger_con, ref) is False


class TestFailureKind:
    def _failed(self, con, tmp_path, *, transient):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(con, ref)
        ledger.mark_parse_failed(con, ref.citekey, "boom", transient=transient)
        return ref

    def test_a_transient_failure_is_retried(self, isolated_config, ledger_con, tmp_path):
        ref = self._failed(ledger_con, tmp_path, transient=True)
        assert ledger.upsert_reference(ledger_con, ref) is True

    def test_a_deterministic_failure_is_not_retried(self, isolated_config, ledger_con, tmp_path):
        ref = self._failed(ledger_con, tmp_path, transient=False)
        assert ledger.upsert_reference(ledger_con, ref) is False

    def test_a_deterministic_failure_keeps_its_status_so_it_stays_reported(
        self, isolated_config, ledger_con, tmp_path
    ):
        ref = self._failed(ledger_con, tmp_path, transient=False)
        ledger.upsert_reference(ledger_con, ref)
        row = ledger_con.execute(
            "SELECT status FROM items WHERE citekey = ?", (ref.citekey,)
        ).fetchone()
        assert row[0] == "parse_failed"

    def test_changed_pdf_bytes_retry_a_deterministic_failure(
        self, isolated_config, ledger_con, tmp_path
    ):
        ref = self._failed(ledger_con, tmp_path, transient=False)
        Path(ref.pdf_path).write_bytes(b"%PDF-1.4 different content entirely")
        assert ledger.upsert_reference(ledger_con, ref) is True

    def test_force_retries_a_deterministic_failure(self, isolated_config, ledger_con, tmp_path):
        ref = self._failed(ledger_con, tmp_path, transient=False)
        assert ledger.upsert_reference(ledger_con, ref, force=True) is True

    def test_force_reparses_an_already_parsed_document(self, isolated_config, ledger_con, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(con=ledger_con, ref=ref)
        (parsed_file("out")).write_text("parsed text")
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_file("out"))

        assert ledger.upsert_reference(ledger_con, ref) is False
        assert ledger.upsert_reference(ledger_con, ref, force=True) is True

    def test_force_does_not_invent_work_for_a_document_with_no_pdf(
        self, isolated_config, ledger_con
    ):
        ref = make_reference(pdf_path=None)
        assert ledger.upsert_reference(ledger_con, ref, force=True) is False

    def test_counts_split_transient_from_deterministic(self, isolated_config, ledger_con, tmp_path):
        for i, transient in enumerate([True, True, False]):
            pdf = tmp_path / f"p{i}.pdf"
            pdf.write_bytes(b"%PDF" + bytes([i]))
            ref = make_reference(citekey=f"k{i}", pdf_path=str(pdf))
            ledger.upsert_reference(ledger_con, ref)
            ledger.mark_parse_failed(ledger_con, ref.citekey, "boom", transient=transient)
        assert ledger.failure_counts(ledger_con) == {"transient": 2, "deterministic": 1}

    def test_an_old_ledger_without_the_column_is_migrated(self, isolated_config, tmp_path):
        con = ledger.connect()
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        ref = make_reference(pdf_path=str(pdf))
        ledger.upsert_reference(con, ref)
        con.execute(
            "UPDATE items SET status='parse_failed', failure_kind=NULL WHERE citekey=?",
            (ref.citekey,),
        )
        con.commit()
        assert ledger.upsert_reference(con, ref) is True
        con.close()


class TestUpsertBatching:
    def test_commit_false_leaves_the_transaction_open(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a_2024"), commit=False)
        assert ledger_con.in_transaction
        ledger_con.commit()
        assert not ledger_con.in_transaction
        assert ledger.known_citekeys(ledger_con) == {"a_2024"}

    def test_the_default_still_commits(self, ledger_con):
        ledger.upsert_reference(ledger_con, make_reference(citekey="a_2024"))
        assert not ledger_con.in_transaction

    def test_sync_commits_once_for_the_whole_reference_list(self, ledger_con):
        from chitragupta import sync_decide

        class CountingConnection:
            def __init__(self, wrapped):
                self._wrapped = wrapped
                self.commits = 0

            def commit(self):
                self.commits += 1
                self._wrapped.commit()

            def __getattr__(self, name):
                return getattr(self._wrapped, name)

        counted = CountingConnection(ledger_con)
        tally = types.SimpleNamespace(
            no_pdf=0,
            no_pdf_reasons=collections.Counter(),
            skipped=0,
            backend_unavailable=0,
        )
        refs = [make_reference(citekey=f"k{n}_2024") for n in range(5)]
        sync_decide._to_parse(counted, refs, False, True, tally)
        assert counted.commits == 1
        assert ledger.known_citekeys(ledger_con) == {f"k{n}_2024" for n in range(5)}


class TestBatchingKeepsFinishedRowsOnACrash:
    def test_a_raise_mid_loop_still_commits_what_finished(self, ledger_con, monkeypatch):
        from chitragupta import ledger_upsert, sync_decide

        real = ledger_upsert.upsert_reference

        def explode_on_the_third(con, ref, force=False, commit=True, on_missing_pdf=None):
            if ref.citekey == "k2_2024":
                raise OSError("the PDF moved mid-sync")
            return real(con, ref, force=force, commit=commit, on_missing_pdf=on_missing_pdf)

        monkeypatch.setattr(ledger, "upsert_reference", explode_on_the_third)
        tally = types.SimpleNamespace(
            no_pdf=0,
            no_pdf_reasons=collections.Counter(),
            skipped=0,
            backend_unavailable=0,
        )
        refs = [make_reference(citekey=f"k{n}_2024") for n in range(5)]
        with pytest.raises(OSError):
            sync_decide._to_parse(ledger_con, refs, False, True, tally)
        assert ledger.known_citekeys(ledger_con) == {"k0_2024", "k1_2024"}
