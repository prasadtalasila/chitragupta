"""Renamed citekeys: detected during sync, recorded before any prune,
reported beside the stale line (plans/1211-cg-collections-and-renames.md,
D6, D7). Nothing here edits a draft -- that is the drafting layer's job."""

import pytest

from chitragupta import config, ledger, ledger_tables, pdf_text, sync, sync_renames
from chitragupta.sync_renames import Rename


def _row(con, citekey, pdf_hash):
    con.execute(
        "INSERT INTO items (citekey, pdf_hash, status, last_synced) VALUES (?, ?, 'parsed', 'x')",
        (citekey, pdf_hash),
    )


class TestDetect:
    def test_same_hash_new_key_is_a_rename(self, ledger_con):
        _row(ledger_con, "old_2023", "h1")
        _row(ledger_con, "new_2023", "h1")
        renames, shared = sync_renames.detect(ledger_con, ["old_2023"], {"new_2023"}, {})
        assert renames == [Rename("old_2023", "new_2023", "pdf_hash", True)]
        assert shared == {}

    def test_declared_rename_wins_and_flags_a_different_pdf(self, ledger_con):
        _row(ledger_con, "old_2023", "h1")
        _row(ledger_con, "other_2023", "h1")
        _row(ledger_con, "new_2023", "h2")
        renames, _shared = sync_renames.detect(
            ledger_con, ["old_2023"], {"new_2023", "other_2023"}, {"old_2023": "new_2023"}
        )
        assert renames == [Rename("old_2023", "new_2023", "cg-renames", False)]

    def test_declared_rename_to_a_key_not_in_the_bib_falls_back_to_the_hash(self, ledger_con):
        _row(ledger_con, "old_2023", "h1")
        _row(ledger_con, "new_2023", "h1")
        renames, _shared = sync_renames.detect(
            ledger_con, ["old_2023"], {"new_2023"}, {"old_2023": "gone_2023"}
        )
        assert renames == [Rename("old_2023", "new_2023", "pdf_hash", True)]

    def test_declared_rename_with_no_hashes_is_not_same_pdf(self, ledger_con):
        _row(ledger_con, "old_2023", None)
        renames, _shared = sync_renames.detect(
            ledger_con, ["old_2023"], {"new_2023"}, {"old_2023": "new_2023"}
        )
        assert renames == [Rename("old_2023", "new_2023", "cg-renames", False)]

    def test_a_shared_hash_is_reported_not_renamed(self, ledger_con):
        _row(ledger_con, "old_2023", "h1")
        _row(ledger_con, "book_2023", "h1")
        _row(ledger_con, "chapter_2023", "h1")
        renames, shared = sync_renames.detect(
            ledger_con, ["old_2023"], {"book_2023", "chapter_2023"}, {}
        )
        assert renames == []
        assert shared == {"old_2023": ["book_2023", "chapter_2023"]}

    def test_a_stale_key_without_a_hash_is_plain_stale(self, ledger_con):
        _row(ledger_con, "old_2023", None)
        _row(ledger_con, "new_2023", None)
        assert sync_renames.detect(ledger_con, ["old_2023"], {"new_2023"}, {}) == ([], {})

    def test_a_hash_only_another_stale_key_has_is_no_rename(self, ledger_con):
        _row(ledger_con, "old_2023", "h1")
        _row(ledger_con, "older_2023", "h1")
        assert sync_renames.detect(ledger_con, ["old_2023", "older_2023"], set(), {}) == ([], {})


class TestRecord:
    def test_record_and_read_back(self, ledger_con):
        sync_renames.record(ledger_con, [Rename("a_2023", "b_2023", "pdf_hash", True)], set())
        assert ledger_tables.renames(ledger_con) == {"a_2023": ("b_2023", "pdf_hash", True)}

    def test_a_changed_mapping_replaces_the_row(self, ledger_con):
        sync_renames.record(ledger_con, [Rename("a_2023", "b_2023", "pdf_hash", True)], set())
        sync_renames.record(ledger_con, [Rename("a_2023", "c_2023", "cg-renames", False)], set())
        assert ledger_tables.renames(ledger_con) == {"a_2023": ("c_2023", "cg-renames", False)}

    def test_an_undone_rename_is_deleted(self, ledger_con):
        sync_renames.record(ledger_con, [Rename("a_2023", "b_2023", "pdf_hash", True)], set())
        sync_renames.record(ledger_con, [], {"a_2023", "b_2023"})
        assert ledger_tables.renames(ledger_con) == {}


class TestSuffix:
    @pytest.mark.parametrize(
        "renames,shared,expected",
        [
            ([Rename("a", "b", "pdf_hash", True)], {}, "; renamed to b, same PDF"),
            ([Rename("a", "b", "cg-renames", False)], {}, "; renamed to b, different PDF"),
            ([], {"a": ["b", "c"]}, "; same PDF as b, c"),
            ([], {}, ""),
        ],
    )
    def test_suffix(self, renames, shared, expected):
        assert sync_renames.suffixes(renames, shared).get("a", "") == expected


def _bib(entries):
    return "".join(
        f"@article{{{key},\n  title = {{T}},\n  author = {{Doe, J}},\n  year = {{2023}},\n"
        f"  file = {{{pdf}:{pdf}:application/pdf}},\n}}\n"
        for key, pdf in entries
    )


@pytest.fixture
def renamed_corpus(isolated_config, monkeypatch):
    monkeypatch.setattr(pdf_text, "is_available", lambda: True)

    def fake_extract_text(pdf_path, citekey):
        out = config.PARSED_DIR / f"{citekey}.txt"
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(f"text of {citekey}")
        return out

    monkeypatch.setattr(pdf_text, "extract_text", fake_extract_text)
    bib_dir = isolated_config.BIB_FILE_PATH.parent
    bib_dir.mkdir(parents=True, exist_ok=True)
    (bib_dir / "a.pdf").write_bytes(b"%PDF-1.4 the same paper")
    (bib_dir / "b.pdf").write_bytes(b"%PDF-1.4 the same paper")
    isolated_config.BIB_FILE_PATH.write_text(_bib([("lehner_pattern_2023-1", "a.pdf")]))
    assert sync.run() == 0
    isolated_config.BIB_FILE_PATH.write_text(_bib([("lehner_pattern_2023", "b.pdf")]))
    return isolated_config


class TestSyncRun:
    def test_the_stale_line_names_the_new_key(self, renamed_corpus, capsys):
        capsys.readouterr()
        sync.run()
        out = capsys.readouterr().out
        assert (
            "stale   lehner_pattern_2023-1 (no longer in bibliography.bib; "
            "renamed to lehner_pattern_2023, same PDF)" in out
        )

    def test_rename_is_recorded_before_the_prune(self, renamed_corpus, capsys):
        sync.run(remove_stale=True)
        assert "renamed to lehner_pattern_2023" in capsys.readouterr().out
        con = ledger.connect()
        try:
            assert ledger_tables.renames(con) == {
                "lehner_pattern_2023-1": ("lehner_pattern_2023", "pdf_hash", True)
            }
            assert "lehner_pattern_2023-1" not in ledger.known_citekeys(con)
        finally:
            con.close()

    def test_stale_keys_are_recorded_for_the_drafting_layer(self, renamed_corpus, capsys):
        sync.run()
        con = ledger.connect()
        try:
            assert ledger_tables.stale(con) == {"lehner_pattern_2023-1"}
        finally:
            con.close()
        sync.run(remove_stale=True)
        sync.run()
        con = ledger.connect()
        try:
            assert ledger_tables.stale(con) == set()
        finally:
            con.close()

    def test_the_report_points_at_dossier_status(self, renamed_corpus, capsys):
        capsys.readouterr()
        sync.run()
        assert "chitragupta draft dossier status --all" in capsys.readouterr().out

    def test_a_lossy_read_records_nothing(self, renamed_corpus, capsys):
        text = renamed_corpus.BIB_FILE_PATH.read_text()
        renamed_corpus.BIB_FILE_PATH.write_text(text + "@article{broken,\n  title = {T\n")
        sync.run()
        con = ledger.connect()
        try:
            assert ledger_tables.renames(con) == {}
        finally:
            con.close()
