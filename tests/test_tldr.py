import io
import json
import subprocess
from pathlib import Path

import pytest

from chitragupta import config, tldr
from tests.conftest import add_item, run_python


class TestRoundTrip:
    def test_a_written_summary_reads_back_fresh(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        path = tldr.write(ledger_con, "smith2024", "A one-paragraph summary.")

        assert path == tldr.sidecar_path("smith2024")
        result = tldr.read(ledger_con, "smith2024")
        assert result["citekey"] == "smith2024"
        assert result["summary"] == "A one-paragraph summary."
        assert result["stale"] is False

    def test_the_summary_is_stripped(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "  padded summary  \n")
        assert tldr.read(ledger_con, "smith2024")["summary"] == "padded summary"

    def test_writing_twice_overwrites(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "first")
        tldr.write(ledger_con, "smith2024", "second")
        assert tldr.read(ledger_con, "smith2024")["summary"] == "second"


class TestStaleness:
    def test_a_reparse_marks_it_stale_rather_than_rewriting_it(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        before = tldr.sidecar_path("smith2024").read_bytes()

        config.PARSED_DIR.joinpath("smith2024.txt").write_text(
            "Completely different parsed text.", encoding="utf-8"
        )

        result = tldr.read(ledger_con, "smith2024")
        assert result["stale"] is True
        assert result["summary"] == "A summary."
        assert tldr.sidecar_path("smith2024").read_bytes() == before

    def test_a_reparse_producing_identical_text_stays_fresh(self, ledger_con):
        add_item("smith2024", "Unchanged text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        config.PARSED_DIR.joinpath("smith2024.txt").write_text("Unchanged text.", encoding="utf-8")
        assert tldr.read(ledger_con, "smith2024")["stale"] is False

    def test_reading_twice_does_not_write(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        before = tldr.sidecar_path("smith2024").read_bytes()
        tldr.read(ledger_con, "smith2024")
        tldr.read(ledger_con, "smith2024")
        assert tldr.sidecar_path("smith2024").read_bytes() == before

    def test_a_citekey_pruned_from_the_ledger_reads_as_stale(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        ledger_con.execute("DELETE FROM items WHERE citekey = ?", ("smith2024",))
        ledger_con.commit()
        assert tldr.read(ledger_con, "smith2024")["stale"] is True

    def test_a_sidecar_whose_fingerprint_is_null_also_reads_as_stale(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        path = tldr.sidecar_path("smith2024")
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["fingerprint"] = None
        path.write_text(json.dumps(payload), encoding="utf-8")
        ledger_con.execute("DELETE FROM items WHERE citekey = ?", ("smith2024",))
        ledger_con.commit()
        assert tldr.read(ledger_con, "smith2024")["stale"] is True


class TestMissingSummaryIsNotAnError:
    def test_no_sidecar_at_all(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        assert tldr.read(ledger_con, "smith2024") is None

    def test_a_corrupted_sidecar_reads_as_missing(self, ledger_con):
        config.TLDR_DIR.mkdir(parents=True, exist_ok=True)
        config.TLDR_DIR.joinpath("smith2024.json").write_text("not json", encoding="utf-8")
        assert tldr.read(ledger_con, "smith2024") is None

    def test_a_sidecar_with_no_summary_field_reads_as_missing(self, ledger_con):
        config.TLDR_DIR.mkdir(parents=True, exist_ok=True)
        config.TLDR_DIR.joinpath("smith2024.json").write_text(
            json.dumps({"citekey": "smith2024"}), encoding="utf-8"
        )
        assert tldr.read(ledger_con, "smith2024") is None


def _passage_sidecar(citekey, records):
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    config.PARSED_DIR.joinpath(f"{citekey}.passages.json").write_text(
        json.dumps([{"text": t, "label": lbl, "page": 1} for t, lbl in records]),
        encoding="utf-8",
    )


ABSTRACT_BODY = " ".join(f"word{i}" for i in range(60))


class TestResolveFallsBackToTheAuthorsAbstract:
    def test_a_hand_written_summary_wins_over_an_abstract(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_BODY, "text")])
        tldr.write(ledger_con, "smith2024", "A hand-written summary.")

        result = tldr.resolve(ledger_con, "smith2024")
        assert result["source"] == "human"
        assert result["summary"] == "A hand-written summary."

    def test_with_no_summary_the_abstract_stands_in(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_BODY, "text")])

        result = tldr.resolve(ledger_con, "smith2024")
        assert result["source"] == "abstract"
        assert result["summary"] == ABSTRACT_BODY

    def test_an_extracted_abstract_is_never_stale(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_BODY, "text")])
        config.PARSED_DIR.joinpath("smith2024.txt").write_text("Re-parsed.", encoding="utf-8")

        assert tldr.resolve(ledger_con, "smith2024")["stale"] is False

    def test_it_writes_no_sidecar(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_BODY, "text")])
        tldr.resolve(ledger_con, "smith2024")
        assert not tldr.sidecar_path("smith2024").exists()

    def test_a_paper_with_no_abstract_says_so(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar(
            "smith2024", [("1 Introduction", "section_header"), (ABSTRACT_BODY, "text")]
        )

        result = tldr.resolve(ledger_con, "smith2024")
        assert result["source"] == "none"
        assert result["summary"] is None

    def test_no_structural_sidecar_is_a_separate_answer(self, ledger_con):
        add_item("smith2024", "Original parsed text.")

        result = tldr.resolve(ledger_con, "smith2024")
        assert result["source"] == "unknown"
        assert result["summary"] is None

    def test_a_corrupted_tldr_sidecar_falls_through_to_the_abstract(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_BODY, "text")])
        config.TLDR_DIR.mkdir(parents=True, exist_ok=True)
        config.TLDR_DIR.joinpath("smith2024.json").write_text("not json", encoding="utf-8")

        assert tldr.resolve(ledger_con, "smith2024")["source"] == "abstract"


class TestRefusals:
    def test_an_unknown_citekey_is_refused(self, ledger_con):
        with pytest.raises(tldr.TldrError, match="not in the ledger"):
            tldr.write(ledger_con, "bogus2099", "A summary.")

    def test_a_citekey_with_no_parsed_text_is_refused(self, ledger_con):
        add_item("smith2024", parsed_text=None)
        with pytest.raises(tldr.TldrError, match="no parsed text yet"):
            tldr.write(ledger_con, "smith2024", "A summary.")

    def test_a_citekey_whose_parsed_file_is_gone_is_refused(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        config.PARSED_DIR.joinpath("smith2024.txt").unlink()
        with pytest.raises(tldr.TldrError, match="no parsed text yet"):
            tldr.write(ledger_con, "smith2024", "A summary.")

    def test_an_empty_summary_is_refused(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        with pytest.raises(tldr.TldrError, match="cannot be empty"):
            tldr.write(ledger_con, "smith2024", "   \n  ")

    def test_a_path_shaped_citekey_is_refused_before_it_becomes_a_path(self, ledger_con):
        with pytest.raises(tldr.TldrError, match="cannot name a file"):
            tldr.sidecar_path("../outside")

    def test_a_refusal_writes_no_sidecar(self, ledger_con):
        with pytest.raises(tldr.TldrError):
            tldr.write(ledger_con, "bogus2099", "A summary.")
        assert not tldr.sidecar_path("bogus2099").exists()


class TestNothingIsWrittenToTheLedger:
    def test_write_leaves_the_ledger_byte_identical(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        ledger_con.commit()
        before = config.LEDGER_PATH.read_bytes()

        tldr.write(ledger_con, "smith2024", "A summary.")

        assert config.LEDGER_PATH.read_bytes() == before

    def test_read_leaves_the_ledger_byte_identical(self, ledger_con):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        ledger_con.commit()
        before = config.LEDGER_PATH.read_bytes()

        tldr.read(ledger_con, "smith2024")

        assert config.LEDGER_PATH.read_bytes() == before


class TestCLI:
    def test_show_refuses_a_citekey_that_climbs_out_of_the_tldr_directory(self, ledger_con, capsys):
        outside = config.TLDR_DIR.parent / "outside.json"
        outside.write_text(json.dumps({"summary": "SECRET"}), encoding="utf-8")
        assert tldr.main(["show", "../outside"]) == 1
        captured = capsys.readouterr()
        assert "SECRET" not in captured.out + captured.err
        assert "cannot name a file" in captured.err

    def test_write_reads_stdin_and_reports_the_path(self, ledger_con, monkeypatch, capsys):
        add_item("smith2024", "Original parsed text.")
        monkeypatch.setattr("sys.stdin", io.StringIO("A summary from stdin.\n"))
        assert tldr.main(["write", "smith2024"]) == 0
        assert "wrote" in capsys.readouterr().out
        assert tldr.read(ledger_con, "smith2024")["summary"] == "A summary from stdin."

    def test_show_prints_the_summary(self, ledger_con, capsys):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        assert tldr.main(["show", "smith2024"]) == 0
        assert "A summary." in capsys.readouterr().out

    def test_show_flags_a_stale_summary_in_the_human_output(self, ledger_con, capsys):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        config.PARSED_DIR.joinpath("smith2024.txt").write_text("New text.", encoding="utf-8")
        assert tldr.main(["show", "smith2024"]) == 0
        assert "STALE" in capsys.readouterr().out

    def test_show_json_includes_the_stale_flag(self, ledger_con, capsys):
        add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        assert tldr.main(["show", "smith2024", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["stale"] is False
        assert payload["source"] == "human"

    def test_show_with_no_sidecar_of_either_kind_exits_zero(self, ledger_con, capsys):
        add_item("smith2024", "Original parsed text.")
        assert tldr.main(["show", "smith2024"]) == 0
        out = capsys.readouterr().out
        assert "cannot tell" in out and "docling" in out

    def test_show_names_the_paper_with_no_abstract(self, ledger_con, capsys):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar(
            "smith2024", [("1 Introduction", "section_header"), (ABSTRACT_BODY, "text")]
        )
        assert tldr.main(["show", "smith2024"]) == 0
        assert "abstract not available" in capsys.readouterr().out

    def test_show_marks_an_extracted_abstract_as_the_authors_words(self, ledger_con, capsys):
        add_item("smith2024", "Original parsed text.")
        _passage_sidecar("smith2024", [("Abstract", "section_header"), (ABSTRACT_BODY, "text")])
        assert tldr.main(["show", "smith2024"]) == 0
        out = capsys.readouterr().out
        assert "authors' own abstract" in out and ABSTRACT_BODY in out

    def test_show_json_carries_the_source_in_every_case(self, ledger_con, capsys):
        add_item("smith2024", "Original parsed text.")
        assert tldr.main(["show", "smith2024", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["source"] == "unknown"

    def test_write_of_an_unknown_citekey_is_a_refusal_not_a_traceback(
        self, ledger_con, monkeypatch, capsys
    ):
        monkeypatch.setattr("sys.stdin", io.StringIO("A summary.\n"))
        assert tldr.main(["write", "bogus2099"]) == 1
        assert "[error]" in capsys.readouterr().err

    def test_no_subcommand_is_a_usage_error(self, ledger_con):
        with pytest.raises(SystemExit) as exc:
            tldr.main([])
        assert exc.value.code == 2


class TestRunsWithBareSystemPython3:
    def test_write_and_show(self, system_python, isolated_config):
        add_item("smith2024", "Original parsed text.")
        env = {"PATH": "/usr/bin:/bin", "CONTENT_DIR": str(isolated_config.CONTENT_DIR)}

        written = run_python(
            "-m",
            "chitragupta.draft",
            "tldr",
            "write",
            "smith2024",
            python=system_python,
            input="A summary written under the bare interpreter.",
            env=env,
        )
        assert written.returncode == 0, written.stderr

        shown = run_python(
            "-m", "chitragupta.draft", "tldr", "show", "smith2024", python=system_python, env=env
        )
        assert shown.returncode == 0, shown.stderr
        assert "A summary written under the bare interpreter." in shown.stdout


class TestTheSidecarIsGitignored:
    def test_git_ignores_the_path_the_module_actually_chooses(self):
        repo = Path(__file__).resolve().parent.parent
        candidate = tldr.sidecar_path("some-citekey-2024")

        result = subprocess.run(
            ["git", "check-ignore", "-q", str(candidate)],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"{candidate} is NOT ignored by git -- content/tldr/ should be "
            "covered by .gitignore's blanket `content/*` rule."
        )
