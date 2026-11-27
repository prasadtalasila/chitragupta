import pytest

from chitragupta import config, ledger, ledger_cli
from tests.conftest import (
    WRITE_LOCK_HOLD,
    make_reference,
    parsed_text,
    read_under_a_held_write_lock,
    run_python,
)


def _run(args=(), cwd=None):
    return run_python("-m", "chitragupta.corpus", "ledger", *args, cwd=cwd)


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
            ledger.mark_parsed(ledger_con, ref.citekey, parsed_text(ref.citekey, "text"))
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
        ledger.mark_parsed(ledger_con, ref.citekey, parsed_text(ref.citekey, "text"))
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
        result = _run(["--help"])
        assert result.returncode == 0, result.stderr
        assert "--status" in result.stdout

    def test_it_takes_no_lock_so_it_works_during_a_sync(self, isolated_config, tmp_path):
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
        assert ledger_cli.main([]) == 0
        out = capsys.readouterr().out
        assert "empty" in out.lower()
        assert "chitragupta.corpus sync" in out

    def test_transient_failures_are_reported_as_self_healing(
        self, isolated_config, ledger_con, tmp_path, capsys
    ):
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
        before = config.LEDGER_PATH.stat().st_mtime_ns
        assert ledger_cli.main([]) == 0
        assert config.LEDGER_PATH.stat().st_mtime_ns == before

    def test_it_waits_out_a_writers_commit_window(self, corpus):
        code, waited = read_under_a_held_write_lock(lambda: ledger_cli.main([]))

        assert code == 0
        assert waited >= WRITE_LOCK_HOLD / 2

    def test_a_pre_failure_kind_ledger_still_summarises(
        self, isolated_config, ledger_con, tmp_path, capsys
    ):
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")
        ledger.upsert_reference(ledger_con, make_reference(pdf_path=str(pdf)))
        ledger_con.execute("ALTER TABLE items RENAME COLUMN failure_kind TO fk_old")
        ledger_con.commit()

        assert ledger_cli.main([]) == 0
        assert "1  found, not yet parsed" in capsys.readouterr().out
