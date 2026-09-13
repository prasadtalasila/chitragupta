"""chitragupta/sync_plan.py: the resolved sync plan, recorded before any
parsing so an interrupted run can be offered back its own plan (#764).

The corpus layer, so: deterministic, no LLM call, and no citekey that did
not come out of the bib file. Every test here drives `sync.run()` against
a throwaway bibliography -- never the real corpus, which a real run takes
nearly two hours to walk.
"""

import json

import pytest

from chitragupta import config, ledger, pdf_text, runlock, sync, sync_plan
from tests.test_sync import fake_extract_text_factory, write_bib

TWO_PDF_BIB = """
@article{smith_example_2024,
  title = {An Example Paper},
  author = {Smith, Jane},
  year = {2024},
  file = {a.pdf:a.pdf:application/pdf},
}

@article{doe_other_2023,
  title = {Another Example Paper},
  author = {Doe, John},
  year = {2023},
  file = {b.pdf:b.pdf:application/pdf},
}

@misc{noon_nopdf_2021,
  title = {An Item With No Attachment},
  author = {Noon, Ada},
  year = {2021},
}
"""

THIRD_ENTRY = """
@article{roe_third_2022,
  title = {A Third Paper},
  author = {Roe, Ann},
  year = {2022},
  file = {c.pdf:c.pdf:application/pdf},
}
"""


@pytest.fixture
def two_pdf_corpus(isolated_config):
    write_bib(isolated_config.BIB_FILE_PATH, TWO_PDF_BIB)
    bib_dir = isolated_config.BIB_FILE_PATH.parent
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (bib_dir / name).write_bytes(b"%PDF-1.4 " + name.encode())
    return isolated_config


@pytest.fixture(autouse=True)
def _parser_present(monkeypatch):
    monkeypatch.setattr(pdf_text, "is_available", lambda: True)
    monkeypatch.setattr(pdf_text, "extract_text", fake_extract_text_factory())


def add_third_entry(cfg):
    """Grow the bibliography, which is what makes a recorded plan stale."""
    path = cfg.BIB_FILE_PATH
    path.write_text(path.read_text(encoding="utf-8") + THIRD_ENTRY, encoding="utf-8")


def read_plan():
    return json.loads(sync_plan.plan_path().read_text(encoding="utf-8"))


def ledger_rows():
    con = ledger.connect()
    try:
        return {r["citekey"]: r["status"] for r in ledger.all_items(con)}
    finally:
        con.close()


def interrupt_after_first(monkeypatch):
    """Parse exactly one document, then stop the way a sleeping machine
    does -- leaving the plan on disk with work still in it."""
    real = fake_extract_text_factory()
    parsed = []
    interrupted = []

    def extract_text(pdf_path, citekey):
        # Once only: every test here runs a *second* sync after the
        # interrupt, and that one has to parse for real.
        if parsed and not interrupted:
            interrupted.append(citekey)
            raise KeyboardInterrupt
        parsed.append(citekey)
        return real(pdf_path, citekey)

    monkeypatch.setattr(pdf_text, "extract_text", extract_text)
    return parsed


class TestTheRecordedPlan:
    def test_plan_is_on_disk_before_the_first_parse(self, two_pdf_corpus, monkeypatch):
        """Recorded *before* work begins, not as the run winds down --
        an interrupt is the case it exists for."""
        seen = []

        def extract_text(pdf_path, citekey):
            seen.append(read_plan()["remaining"])
            return fake_extract_text_factory()(pdf_path, citekey)

        monkeypatch.setattr(pdf_text, "extract_text", extract_text)
        sync.run()
        assert seen[0] == ["smith_example_2024", "doe_other_2023"]

    def test_a_completed_run_leaves_no_plan(self, two_pdf_corpus):
        assert sync.run() == 0
        assert not sync_plan.plan_path().exists()

    def test_a_failed_document_still_discards_the_plan(self, two_pdf_corpus, monkeypatch):
        """The plan records what was still to be *attempted*. Every item
        was attempted, so it is spent -- keeping it because one document
        failed would offer the same doomed resume on every later run."""
        monkeypatch.setattr(
            pdf_text, "extract_text", fake_extract_text_factory(fail_citekeys={"doe_other_2023"})
        )
        assert sync.run() == 1
        assert not sync_plan.plan_path().exists()

    def test_a_run_with_nothing_to_parse_records_no_plan(self, two_pdf_corpus):
        sync.run()
        assert sync.run() == 0
        assert not sync_plan.plan_path().exists()

    def test_an_interrupted_run_leaves_its_plan(self, two_pdf_corpus, monkeypatch):
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        assert read_plan()["remaining"] == ["smith_example_2024", "doe_other_2023"]


class TestTheOffer:
    def test_an_incomplete_plan_is_detected_and_offered(self, two_pdf_corpus, monkeypatch, capsys):
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        capsys.readouterr()

        sync.run()
        out = capsys.readouterr().out
        assert "interrupted sync run left a plan" in out
        assert "--resume" in out

    def test_the_offer_is_not_taken_without_the_flag(self, two_pdf_corpus, monkeypatch, capsys):
        """Offered, never forced: a plain run re-derives, which is what
        every existing caller and cron line already expects."""
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        capsys.readouterr()

        sync.run()
        assert "resuming the recorded sync plan" not in capsys.readouterr().out

    def test_resume_takes_the_recorded_plan(self, two_pdf_corpus, monkeypatch, capsys):
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        capsys.readouterr()

        assert sync.run(resume=True) == 0
        assert "resuming the recorded sync plan" in capsys.readouterr().out

    def test_resume_does_not_re_derive_the_whole_bibliography(
        self, two_pdf_corpus, monkeypatch, capsys
    ):
        """The saving the issue is about: an interrupted run re-derives
        what to do -- hashing every attachment in the bibliography again.
        A resumed one asks the ledger only about the documents its own
        plan still names, so the entry that needed no work at plan time
        is never revisited."""
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        capsys.readouterr()

        asked = []
        real_upsert = ledger.upsert_reference

        def upsert_reference(con, ref, **kwargs):
            asked.append(ref.citekey)
            return real_upsert(con, ref, **kwargs)

        monkeypatch.setattr(ledger, "upsert_reference", upsert_reference)
        sync.run(resume=True)
        assert asked == ["smith_example_2024", "doe_other_2023"]
        assert "noon_nopdf_2021" not in asked

    def test_resume_with_no_plan_says_so_and_carries_on(self, two_pdf_corpus, capsys):
        assert sync.run(resume=True) == 0
        out = capsys.readouterr().out
        assert "no incomplete sync plan" in out
        assert "parsed  smith_example_2024" in out

    def test_an_unreadable_plan_reads_as_no_plan(self, two_pdf_corpus, capsys):
        sync_plan.plan_path().parent.mkdir(parents=True, exist_ok=True)
        sync_plan.plan_path().write_text("{not json", encoding="utf-8")
        assert sync.run(resume=True) == 0
        assert "no incomplete sync plan" in capsys.readouterr().out

    def test_a_plan_from_a_future_schema_reads_as_no_plan(
        self, two_pdf_corpus, monkeypatch, capsys
    ):
        """Forward compatibility in the only direction that matters: a
        plan this release cannot read costs the saving, never
        correctness, because the run derives its own instead."""
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        plan = read_plan()
        plan["schema"] = sync_plan._SCHEMA + 1
        sync_plan.plan_path().write_text(json.dumps(plan), encoding="utf-8")
        capsys.readouterr()

        assert sync.run(resume=True) == 0
        out = capsys.readouterr().out
        assert "no incomplete sync plan" in out
        assert "parsed  doe_other_2023" in out


class TestStalePlans:
    def test_a_changed_bibliography_rejects_the_plan(self, two_pdf_corpus, monkeypatch, capsys):
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        add_third_entry(two_pdf_corpus)
        capsys.readouterr()

        assert sync.run(resume=True) == 0
        out = capsys.readouterr().out
        assert "stale" in out
        assert "resuming the recorded sync plan" not in out
        # Rejected, not resumed -- so the entry the plan never knew about
        # is parsed, which a resumed run would have skipped.
        assert "parsed  roe_third_2022" in out

    def test_a_stale_plan_is_reported_without_the_flag_too(
        self, two_pdf_corpus, monkeypatch, capsys
    ):
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        add_third_entry(two_pdf_corpus)
        capsys.readouterr()

        sync.run()
        out = capsys.readouterr().out
        assert "stale" in out
        assert "interrupted sync run left a plan" not in out


class TestResumeEqualsAnUninterruptedRun:
    def test_same_ledger_and_same_parsed_text(self, two_pdf_corpus, monkeypatch, capsys):
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        sync.run(resume=True)
        resumed_rows = ledger_rows()
        resumed_text = sorted(p.name for p in config.PARSED_DIR.glob("*.txt"))
        summary = [line for line in capsys.readouterr().out.splitlines() if "Sync complete" in line]

        # Same bibliography, same host, from scratch.
        for path in config.PARSED_DIR.glob("*.txt"):
            path.unlink()
        config.LEDGER_PATH.unlink()
        assert sync.run() == 0
        straight_summary = [
            line for line in capsys.readouterr().out.splitlines() if "Sync complete" in line
        ]

        assert resumed_rows == ledger_rows()
        assert resumed_text == sorted(p.name for p in config.PARSED_DIR.glob("*.txt"))
        # The summaries are *not* identical, and must not be: the
        # document parsed before the interrupt is genuinely unchanged by
        # the time the resumed run looks at it, so it reports as such.
        # What has to match is the accounting -- every item in the
        # bibliography is in exactly one bucket, including the one the
        # resumed run's own decide phase never saw.
        assert "1 parsed, 1 unchanged, 1 without a PDF attachment, 0 failed" in summary[-1]
        assert "2 parsed, 0 unchanged, 1 without a PDF attachment, 0 failed" in straight_summary[-1]


class TestRunlockIsUnchanged:
    def test_a_second_writer_exits_2_and_leaves_the_plan_alone(
        self, two_pdf_corpus, monkeypatch, capsys
    ):
        interrupt_after_first(monkeypatch)
        with pytest.raises(KeyboardInterrupt):
            sync.run()
        before = sync_plan.plan_path().read_bytes()

        with runlock.pipeline_lock():
            assert sync.main(["--resume"]) == runlock.EXIT_ALREADY_RUNNING
        assert sync_plan.plan_path().read_bytes() == before


class TestTheFlag:
    def test_resume_reaches_run_from_the_command_line(self, two_pdf_corpus, monkeypatch):
        seen = {}
        monkeypatch.setattr(sync, "run", lambda **kwargs: seen.update(kwargs) or 0)
        assert sync.main(["--resume"]) == 0
        assert seen["resume"] is True

    def test_resume_is_off_by_default(self, two_pdf_corpus, monkeypatch):
        seen = {}
        monkeypatch.setattr(sync, "run", lambda **kwargs: seen.update(kwargs) or 0)
        assert sync.main([]) == 0
        assert seen["resume"] is False
