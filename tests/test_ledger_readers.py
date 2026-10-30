"""Every reader of the ledger, with no ledger to read (issue #843).

Each used to open it through `ledger.connect()`, the writer, and so
*created* it: a genre skill's first `search()` before any sync left an
empty `content/ledger.sqlite` behind, and `corpus ledger` then reported
"Ledger ... is empty" instead of "No ledger", which is the distinction
the skills refuse on. Now every reader goes through
`ledger.read_connection`, which refuses by name and creates nothing.

Two absent-ledger behaviours are deliberately kept rather than turned
into refusals, and are pinned here: the gate still runs (failing closed,
and passing a citation-free draft, which the session-start hook's probe
relies on), and a draft with nothing to cite still renders.
"""

import json
import sqlite3
import sys

import pytest

from chitragupta import (
    citation_gate,
    config,
    dossier,
    draft,
    ledger,
    ledger_cli,
    overlap_index_ledger,
    references,
    render_output,
    retrieval,
    retrieval_cli,
)
from chitragupta.discover import _data as discover_data
from chitragupta.enrich import __main__ as enrich_script
from chitragupta.review import __main__ as review_main

from tests.conftest import content_draft
from tests.ledger_faults import damage_past_the_header, leave_hot_journal


@pytest.fixture
def stale_ledger(isolated_config):
    """A ledger at schema version 0: the original table, no migrations."""
    isolated_config.CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    raw = sqlite3.connect(isolated_config.LEDGER_PATH)
    raw.execute(
        "CREATE TABLE items (citekey TEXT PRIMARY KEY, title TEXT, status TEXT, "
        "parsed_path TEXT, last_synced TEXT NOT NULL)"
    )
    raw.commit()
    raw.close()


class TestLibraryReaders:
    def test_search_refuses_and_leaves_no_ledger_for_corpus_ledger_to_find(
        self, isolated_config, capsys
    ):
        with pytest.raises(ledger.NoLedger):
            retrieval.search("digital twin")
        assert not isolated_config.LEDGER_PATH.exists()
        # The skills' refusal trigger survives the search.
        assert ledger_cli.main([]) == 0
        assert "No ledger at" in capsys.readouterr().out

    def test_corpus_rows_is_none_for_a_ledger_needing_sync(self, stale_ledger):
        assert dossier._corpus_rows() is None

    def test_corpus_rows_is_none_for_a_current_ledger_it_cannot_query(self, isolated_config):
        # Opens (the version is current) but the read itself fails -- the
        # same "no readable ledger" answer a busy or damaged one gets.
        isolated_config.CONTENT_DIR.mkdir(parents=True)
        raw = sqlite3.connect(isolated_config.LEDGER_PATH)
        raw.execute(f"PRAGMA user_version = {len(ledger._MIGRATIONS)}")
        raw.close()
        assert dossier._corpus_rows() is None

    def test_a_file_that_is_not_a_database_is_no_readable_ledger(
        self, isolated_config, monkeypatch
    ):
        isolated_config.CONTENT_DIR.mkdir(parents=True)
        isolated_config.LEDGER_PATH.write_bytes(b"not a database, just bytes" * 40)
        opened = []
        real = sqlite3.connect

        def tracked(*args, **kwargs):
            opened.append(real(*args, **kwargs))
            return opened[-1]

        monkeypatch.setattr(sqlite3, "connect", tracked)
        with pytest.raises(ledger.UnreadableLedger):
            ledger.read_connection()
        # Closed on the way out, not leaked with the exception.
        with pytest.raises(sqlite3.ProgrammingError):
            opened[0].execute("SELECT 1")
        assert dossier._corpus_rows() is None

    def test_the_overlap_index_raises_a_ledger_needing_sync(self, stale_ledger):
        # Not folded into "nothing fingerprintable": that would be a
        # silent pass on the verbatim check against a corpus never read.
        with pytest.raises(ledger.StaleLedger):
            overlap_index_ledger.ledger_item("smith_2024")

    def test_discover_names_the_sync_for_a_ledger_needing_one(self, stale_ledger):
        with pytest.raises(discover_data.MissingArtefact, match="corpus sync"):
            discover_data.read_only_connection()


class TestTheGateStillRuns:
    def test_a_citation_free_draft_passes_with_no_ledger(self, isolated_config, capsys):
        path = content_draft(isolated_config, "drafts/plain.md")
        path.write_text("No citations here.\n", encoding="utf-8")
        assert citation_gate.run([str(path)]) == 0
        assert "No ledger at" in capsys.readouterr().err
        assert not isolated_config.LEDGER_PATH.exists()

    def test_a_cited_key_fails_closed_with_no_ledger(self, isolated_config, capsys):
        path = content_draft(isolated_config, "drafts/cited.md")
        path.write_text("Claim [@fabricated_2024].\n", encoding="utf-8")
        assert citation_gate.run([str(path)]) == 1
        captured = capsys.readouterr()
        assert "fabricated_2024" in captured.out
        assert "Every citekey will be reported as unknown" in captured.err
        assert not isolated_config.LEDGER_PATH.exists()


class TestCommandsRefuseByName:
    def test_draft_dispatch_turns_the_refusal_into_an_error_line(self, isolated_config, capsys):
        assert draft.main(["tldr", "show", "smith_2024"]) == 1
        err = capsys.readouterr().err
        assert err.startswith("[error] No ledger at")
        assert "chitragupta.corpus sync" in err
        assert not isolated_config.LEDGER_PATH.exists()

    def test_review_dispatch_turns_the_refusal_into_an_error_line(self, isolated_config, capsys):
        path = config.DRAFTS_DIR / "topic" / "survey.md"
        path.parent.mkdir(parents=True)
        path.write_text("A claim [@smith_2024].\n", encoding="utf-8")
        assert review_main.main(["provenance", str(path)]) == 1
        assert capsys.readouterr().err.startswith("[error] No ledger at")
        assert not isolated_config.LEDGER_PATH.exists()

    def test_an_agenda_recheck_refuses_rather_than_filing_a_partial_agenda(
        self, isolated_config, capsys
    ):
        # `--baseline` re-runs every aid; the refusal must stop the run,
        # not leave an agenda counted over whichever aids did not need
        # the ledger.
        path = config.DRAFTS_DIR / "topic" / "survey.md"
        path.parent.mkdir(parents=True)
        path.write_text("A claim [@smith_2024].\n", encoding="utf-8")
        baseline = isolated_config.CONTENT_DIR / "baseline.json"
        baseline.write_text(json.dumps({"aid": "agenda", "items": []}), encoding="utf-8")
        assert review_main.main(["agenda", str(path), "--baseline", str(baseline)]) == 1
        assert capsys.readouterr().err.startswith("[error] No ledger at")
        assert not isolated_config.LEDGER_PATH.exists()

    def test_references_reports_it_like_a_missing_citekey(self, isolated_config, capsys):
        path = content_draft(isolated_config, "draft.md")
        path.write_text("See [@smith_2024].\n", encoding="utf-8")
        assert references.main([str(path)]) == 1
        assert "[error] No ledger at" in capsys.readouterr().err

    def test_retrieve_refuses_a_ledger_needing_sync(self, stale_ledger, capsys):
        assert retrieval_cli.main(["search", "digital twin"]) == 1
        assert "predates this version's schema" in capsys.readouterr().err

    def test_corpus_ledger_exits_0_for_a_ledger_needing_sync(self, stale_ledger, capsys):
        # Zero, and the instruction on stdout: the session-start hook reads
        # a non-zero exit here as "the corpus layer will not start".
        assert ledger_cli.main([]) == 0
        assert "chitragupta.corpus sync" in capsys.readouterr().out

    def test_enrich_refuses_rather_than_enriching_an_empty_corpus(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling"])
        assert enrich_script.main() == 1
        assert "No ledger at" in capsys.readouterr().out
        assert not isolated_config.LEDGER_PATH.exists()


class TestRenderingNeedsALedgerOnlyToCite:
    def test_a_citation_free_draft_renders_to_markdown_with_no_ledger(self, isolated_config):
        path = content_draft(isolated_config, "drafts/plain.md")
        path.write_text("# Title\n\nNo citations here.\n", encoding="utf-8")
        assert render_output.main([str(path), "--format", "md"]) == 0
        assert not isolated_config.LEDGER_PATH.exists()

    def test_a_citing_draft_is_an_error_line_not_a_traceback(self, isolated_config, capsys):
        path = content_draft(isolated_config, "drafts/cited.md")
        path.write_text("See [@smith_2024].\n", encoding="utf-8")
        assert render_output.main([str(path), "--format", "md"]) == 1
        assert "[error] No ledger at" in capsys.readouterr().out
        assert not isolated_config.LEDGER_PATH.exists()


@pytest.fixture
def hot_ledger(isolated_config):
    """A synced ledger with an interrupted write's journal beside it (#1066)."""
    ledger.connect().close()
    return leave_hot_journal(isolated_config.LEDGER_PATH)


class TestAnUnreadableLedgerIsRefusedNotATraceback:
    """#1066's follow-up: every reader above, against a ledger SQLite will
    not read. `UnreadableLedger` is a `NoLedger`, so each command's
    existing refusal reports it -- with its cause, where it used to be a
    raw `sqlite3.OperationalError` -- and the readers that fold
    `NoLedger` into "nothing there" are each pinned to do what they
    should with a ledger that *is* there."""

    def test_the_gate_exits_3_through_the_draft_dispatch(self, hot_ledger, isolated_config, capsys):
        path = content_draft(isolated_config, "drafts/cited.md")
        path.write_text("Claim [@smith_2024].\n", encoding="utf-8")
        assert draft.main(["gate", str(path)]) == ledger.EXIT_UNREADABLE
        assert hot_ledger.name in capsys.readouterr().err

    def test_draft_dispatch_turns_it_into_an_error_line(self, hot_ledger, capsys):
        assert draft.main(["tldr", "show", "smith_2024"]) == 1
        err = capsys.readouterr().err
        assert err.startswith("[error] The ledger at")
        assert hot_ledger.name in err

    def test_review_dispatch_turns_it_into_an_error_line(self, hot_ledger, capsys):
        path = config.DRAFTS_DIR / "topic" / "survey.md"
        path.parent.mkdir(parents=True)
        path.write_text("A claim [@smith_2024].\n", encoding="utf-8")
        assert review_main.main(["provenance", str(path)]) == 1
        assert capsys.readouterr().err.startswith("[error] The ledger at")

    def test_references_reports_it(self, hot_ledger, isolated_config, capsys):
        path = content_draft(isolated_config, "draft.md")
        path.write_text("See [@smith_2024].\n", encoding="utf-8")
        assert references.main([str(path)]) == 1
        assert "[error] The ledger at" in capsys.readouterr().err

    def test_retrieve_reports_it(self, hot_ledger, capsys):
        assert retrieval_cli.main(["search", "digital twin"]) == 1
        assert hot_ledger.name in capsys.readouterr().err

    def test_render_refuses_a_citing_draft(self, hot_ledger, isolated_config, capsys):
        path = content_draft(isolated_config, "drafts/cited.md")
        path.write_text("See [@smith_2024].\n", encoding="utf-8")
        assert render_output.main([str(path), "--format", "md"]) == 1
        assert "[error] The ledger at" in capsys.readouterr().out

    def test_enrich_refuses(self, hot_ledger, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["enrich.py", "--stages", "docling"])
        assert enrich_script.main() == 1
        assert hot_ledger.name in capsys.readouterr().out

    def test_discover_names_the_cause(self, hot_ledger):
        with pytest.raises(discover_data.MissingArtefact, match=hot_ledger.name):
            discover_data.read_only_connection()

    def test_search_raises_it_to_a_library_caller(self, hot_ledger):
        with pytest.raises(ledger.UnreadableLedger):
            retrieval.search("digital twin")

    def test_corpus_ledger_exits_3_on_stderr(self, hot_ledger, capsys):
        # Not the 0 a missing or stale ledger gets: that is a position in
        # clone -> sync, this is a fault, and the session-start hook
        # reports it by this code.
        assert ledger_cli.main([]) == ledger.EXIT_UNREADABLE
        captured = capsys.readouterr()
        assert captured.out == ""
        assert hot_ledger.name in captured.err

    def test_corpus_ledger_exits_3_on_damage_its_first_read_missed(self, isolated_config, capsys):
        # The schema version reads; the summary query is what fails.
        ledger.connect().close()
        damage_past_the_header(isolated_config.LEDGER_PATH)
        assert ledger_cli.main([]) == ledger.EXIT_UNREADABLE
        assert "or it is damaged" in capsys.readouterr().err

    def test_the_overlap_index_raises_it(self, hot_ledger):
        # Not folded into "nothing fingerprintable", for the reason a
        # stale ledger is not: a silent pass on the verbatim check.
        with pytest.raises(ledger.UnreadableLedger):
            overlap_index_ledger.ledger_item("smith_2024")

    def test_the_dossier_drift_scan_is_skipped(self, hot_ledger):
        # Unchanged, and right: it already skips on any sqlite3.Error.
        assert dossier._corpus_rows() is None
