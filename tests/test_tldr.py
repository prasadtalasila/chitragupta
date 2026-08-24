"""chitragupta/tldr.py: per-citekey TL;DR, cached beside a fingerprint of
the citekey's parsed text.

The invariants that matter most: a re-parse marks a summary stale
without rewriting it (`write` is never called on `show`'s behalf), a
missing summary is not an error, an unknown citekey is refused rather
than minting one, and nothing here ever touches `content/ledger.sqlite`.
"""

import io
import json
import subprocess
from pathlib import Path

import pytest

from chitragupta import config, ledger, tldr

REPO_ROOT = Path(__file__).resolve().parent.parent


def _add_item(citekey, parsed_text=None, title="T"):
    """A ledger row, optionally with parsed text on disk -- mirrors
    tests/test_passages.py's own helper for the same shape of fixture."""
    parsed_path = None
    if parsed_text is not None:
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        parsed_path = config.PARSED_DIR / f"{citekey}.txt"
        parsed_path.write_text(parsed_text, encoding="utf-8")
        parsed_path = str(parsed_path)
    con = ledger.connect()
    try:
        con.execute(
            "INSERT OR REPLACE INTO items (citekey, title, status, parsed_path, last_synced)"
            " VALUES (?, ?, 'parsed', ?, '2026-01-01')",
            (citekey, title, parsed_path),
        )
        con.commit()
    finally:
        con.close()


class TestRoundTrip:
    def test_a_written_summary_reads_back_fresh(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        path = tldr.write(ledger_con, "smith2024", "A one-paragraph summary.")

        assert path == tldr.sidecar_path("smith2024")
        result = tldr.read(ledger_con, "smith2024")
        assert result["citekey"] == "smith2024"
        assert result["summary"] == "A one-paragraph summary."
        assert result["stale"] is False

    def test_the_summary_is_stripped(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "  padded summary  \n")
        assert tldr.read(ledger_con, "smith2024")["summary"] == "padded summary"

    def test_writing_twice_overwrites(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "first")
        tldr.write(ledger_con, "smith2024", "second")
        assert tldr.read(ledger_con, "smith2024")["summary"] == "second"


class TestStaleness:
    def test_a_reparse_marks_it_stale_rather_than_rewriting_it(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        before = tldr.sidecar_path("smith2024").read_bytes()

        # Simulate `corpus sync --reparse` changing the extracted text
        # without touching the sidecar at all.
        config.PARSED_DIR.joinpath("smith2024.txt").write_text(
            "Completely different parsed text.", encoding="utf-8"
        )

        result = tldr.read(ledger_con, "smith2024")
        assert result["stale"] is True
        assert result["summary"] == "A summary."
        # The read must not have rewritten the sidecar -- only `write`
        # may touch it, and `read` recomputes staleness fresh every call.
        assert tldr.sidecar_path("smith2024").read_bytes() == before

    def test_a_reparse_producing_identical_text_stays_fresh(self, ledger_con):
        _add_item("smith2024", "Unchanged text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        config.PARSED_DIR.joinpath("smith2024.txt").write_text("Unchanged text.", encoding="utf-8")
        assert tldr.read(ledger_con, "smith2024")["stale"] is False

    def test_reading_twice_does_not_write(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        before = tldr.sidecar_path("smith2024").read_bytes()
        tldr.read(ledger_con, "smith2024")
        tldr.read(ledger_con, "smith2024")
        assert tldr.sidecar_path("smith2024").read_bytes() == before

    def test_a_citekey_pruned_from_the_ledger_reads_as_stale(self, ledger_con):
        """The fingerprint can no longer be recomputed at all, which
        counts as stale too -- a summary that cannot be verified is not
        reported as trustworthy."""
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        ledger_con.execute("DELETE FROM items WHERE citekey = ?", ("smith2024",))
        ledger_con.commit()
        assert tldr.read(ledger_con, "smith2024")["stale"] is True


class TestMissingSummaryIsNotAnError:
    def test_no_sidecar_at_all(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
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


class TestRefusals:
    def test_an_unknown_citekey_is_refused(self, ledger_con):
        with pytest.raises(tldr.TldrError, match="not in the ledger"):
            tldr.write(ledger_con, "bogus2099", "A summary.")

    def test_a_citekey_with_no_parsed_text_is_refused(self, ledger_con):
        _add_item("smith2024", parsed_text=None)
        with pytest.raises(tldr.TldrError, match="no parsed text yet"):
            tldr.write(ledger_con, "smith2024", "A summary.")

    def test_a_citekey_whose_parsed_file_is_gone_is_refused(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        config.PARSED_DIR.joinpath("smith2024.txt").unlink()
        with pytest.raises(tldr.TldrError, match="no parsed text yet"):
            tldr.write(ledger_con, "smith2024", "A summary.")

    def test_an_empty_summary_is_refused(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        with pytest.raises(tldr.TldrError, match="cannot be empty"):
            tldr.write(ledger_con, "smith2024", "   \n  ")

    def test_a_refusal_writes_no_sidecar(self, ledger_con):
        with pytest.raises(tldr.TldrError):
            tldr.write(ledger_con, "bogus2099", "A summary.")
        assert not tldr.sidecar_path("bogus2099").exists()


class TestNothingIsWrittenToTheLedger:
    def test_write_leaves_the_ledger_byte_identical(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        ledger_con.commit()
        before = config.LEDGER_PATH.read_bytes()

        tldr.write(ledger_con, "smith2024", "A summary.")

        assert config.LEDGER_PATH.read_bytes() == before

    def test_read_leaves_the_ledger_byte_identical(self, ledger_con):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        ledger_con.commit()
        before = config.LEDGER_PATH.read_bytes()

        tldr.read(ledger_con, "smith2024")

        assert config.LEDGER_PATH.read_bytes() == before


class TestCLI:
    def test_write_reads_stdin_and_reports_the_path(self, ledger_con, monkeypatch, capsys):
        _add_item("smith2024", "Original parsed text.")
        monkeypatch.setattr("sys.stdin", io.StringIO("A summary from stdin.\n"))
        assert tldr.main(["write", "smith2024"]) == 0
        assert "wrote" in capsys.readouterr().out
        assert tldr.read(ledger_con, "smith2024")["summary"] == "A summary from stdin."

    def test_show_prints_the_summary(self, ledger_con, capsys):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        assert tldr.main(["show", "smith2024"]) == 0
        assert "A summary." in capsys.readouterr().out

    def test_show_flags_a_stale_summary_in_the_human_output(self, ledger_con, capsys):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        config.PARSED_DIR.joinpath("smith2024.txt").write_text("New text.", encoding="utf-8")
        assert tldr.main(["show", "smith2024"]) == 0
        assert "STALE" in capsys.readouterr().out

    def test_show_json_includes_the_stale_flag(self, ledger_con, capsys):
        _add_item("smith2024", "Original parsed text.")
        tldr.write(ledger_con, "smith2024", "A summary.")
        assert tldr.main(["show", "smith2024", "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["stale"] is False

    def test_show_with_no_summary_exits_zero(self, ledger_con, capsys):
        _add_item("smith2024", "Original parsed text.")
        assert tldr.main(["show", "smith2024"]) == 0
        assert "no TL;DR recorded" in capsys.readouterr().out

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
    """docs/ARCHITECTURE.md's tier-1 row claims `chitragupta.draft`'s
    commands are stdlib-only -- chitragupta/tldr.py only ever imports
    config and ledger, both stdlib, so it belongs in that tier alongside
    citation_gate.py and references.py rather than needing the venv."""

    def test_write_and_show(self, system_python, isolated_config):
        _add_item("smith2024", "Original parsed text.")
        env = {"PATH": "/usr/bin:/bin", "CONTENT_DIR": str(isolated_config.CONTENT_DIR)}

        written = subprocess.run(
            [system_python, "-m", "chitragupta.draft", "tldr", "write", "smith2024"],
            cwd=str(REPO_ROOT),
            input="A summary written under the bare interpreter.",
            capture_output=True,
            text=True,
            env=env,
        )
        assert written.returncode == 0, written.stderr

        shown = subprocess.run(
            [system_python, "-m", "chitragupta.draft", "tldr", "show", "smith2024"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env=env,
        )
        assert shown.returncode == 0, shown.stderr
        assert "A summary written under the bare interpreter." in shown.stdout


class TestTheSidecarIsGitignored:
    """Not because it carries copyrighted wording -- evidence_appendix.py
    is the module for that -- but content/* is per-host data unconditionally
    (.gitignore's own header), and a summary is generated content someone
    else authored, not something to publish by accident.
    """

    def test_git_ignores_the_path_the_module_actually_chooses(self):
        # Deliberately not run under isolated_config, so config.TLDR_DIR
        # is this checkout's real path -- the same reason
        # test_evidence_appendix.py's equivalent test resolves against
        # the real repo rather than a tmp_path fixture.
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
