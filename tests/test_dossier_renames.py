"""Renamed citekeys in the drafting layer: `dossier status` lists them,
`dossier apply-renames` swaps them (plans/1211-cg-collections-and-renames.md,
D9). The swap only ever puts in a key the ledger recorded as the
replacement and still holds -- never one it guessed."""

import json

import pytest

from chitragupta import config, dossier, ledger
from chitragupta.dossier import DossierError, _cli, _drift, _renames


@pytest.fixture
def draft(isolated_config):
    path = config.DRAFTS_DIR / "dt" / "survey.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "# A survey\n\n## 1. First\n\nAs [@old_2023] shows, not [@old_2023b].\n",
        encoding="utf-8",
    )
    dossier.init(path, "survey")
    target = dossier.dossier_dir(path)
    (target / "evidence.md").write_text("# Kept evidence\n\n## `old_2023`\n\nWhy.\n")
    (target / "sections.md").write_text(
        "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
        "| 1. First | `old_2023` |\n"
    )
    (target / "rejected.md").write_text(
        "# Rejected candidates\n\n| citekey | query that surfaced it | why rejected |\n"
        "|---|---|---|\n| `dropped_2020` | digital twin | off topic |\n"
    )
    return path


def _seed(parsed, renames):
    """Parsed ledger rows for `parsed`, and `renames` rows (old, new, same)."""
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    con = ledger.connect()
    try:
        for key in parsed:
            text = config.PARSED_DIR / f"{key}.txt"
            text.write_text("digital twin text")
            con.execute(
                "INSERT INTO items (citekey, title, status, parsed_path, last_synced) "
                "VALUES (?, ?, 'parsed', ?, 'x')",
                (key, key, str(text)),
            )
        con.executemany(
            "INSERT INTO renames VALUES (?, ?, 'pdf_hash', ?, '2026-11-22')",
            [(old, new, int(same)) for old, new, same in renames],
        )
        con.commit()
    finally:
        con.close()


class TestFinal:
    RENAMES = {"a": ("b", "pdf_hash", True), "b": ("c", "cg-renames", False)}

    def test_chain_resolves_to_the_final_key(self):
        assert _renames.final(self.RENAMES, "a") == ("c", False)
        assert _renames.final(self.RENAMES, "b") == ("c", False)

    def test_a_key_with_no_rename(self):
        assert _renames.final(self.RENAMES, "c") is None

    def test_cycle_is_reported_not_looped(self):
        assert _renames.final({"a": ("b", "x", True), "b": ("a", "x", True)}, "a") is None


class TestStatus:
    def test_renamed_is_listed_and_not_missing(self, draft):
        _seed(["new_2023"], [("old_2023", "new_2023", True)])
        report = _drift.drift(dossier.dossier_dir(draft))
        assert report.renamed == {
            "old_2023": {"new": "new_2023", "same_pdf": True, "sections": ["1. First"]}
        }
        assert "old_2023" not in report.missing
        assert report.clean is False
        assert report.as_dict()["renamed"] == report.renamed

    def test_a_key_cited_only_in_the_draft_is_listed(self, draft):
        (dossier.dossier_dir(draft) / "evidence.md").write_text("# Kept evidence\n")
        (dossier.dossier_dir(draft) / "sections.md").write_text("# Sections\n")
        _seed(["new_2023"], [("old_2023", "new_2023", True)])
        report = _drift.drift(dossier.dossier_dir(draft))
        assert report.renamed == {"old_2023": {"new": "new_2023", "same_pdf": True, "sections": []}}

    def test_a_rename_to_a_key_the_ledger_lacks_stays_missing(self, draft):
        _seed([], [("old_2023", "new_2023", True)])
        report = _drift.drift(dossier.dossier_dir(draft))
        assert report.renamed == {}
        assert "old_2023" in report.missing

    def test_a_cycle_stays_missing(self, draft):
        _seed([], [("old_2023", "x_2023", True), ("x_2023", "old_2023", True)])
        report = _drift.drift(dossier.dossier_dir(draft))
        assert report.renamed == {} and "old_2023" in report.missing

    def test_printed(self, draft, capsys):
        from chitragupta.dossier import _drift_report

        _seed(["new_2023"], [("old_2023", "new_2023", False)])
        _drift_report._print_drift(_drift.drift(dossier.dossier_dir(draft)))
        out = capsys.readouterr().out
        assert "1 citekey(s) renamed" in out
        assert "old_2023 -> new_2023 (different PDF)" in out
        assert "dossier apply-renames" in out


class TestApply:
    def test_swaps_bounded_matches_in_four_files(self, draft):
        (dossier.dossier_dir(draft) / "rejected.md").write_text("| `old_2023` | q | off |\n")
        _seed(["new_2023"], [("old_2023", "new_2023", True)])
        applied = _renames.apply_renames(draft)
        assert [(a.old, a.new, a.same_pdf) for a in applied] == [("old_2023", "new_2023", True)]
        target = dossier.dossier_dir(draft)
        assert "[@new_2023] shows, not [@old_2023b]" in draft.read_text()
        for name in ("evidence.md", "sections.md", "rejected.md"):
            text = (target / name).read_text()
            assert "new_2023" in text and "old_2023" not in text
        assert sorted(applied[0].files) == sorted(
            [str(draft), *(str(target / n) for n in ("evidence.md", "rejected.md", "sections.md"))]
        )

    def test_logs_a_revision(self, draft):
        _seed(["new_2023"], [("old_2023", "new_2023", True)])
        _renames.apply_renames(draft)
        log = (dossier.dossier_dir(draft) / "revisions.md").read_text()
        assert "apply-renames: old_2023 -> new_2023" in log
        assert "Sections: 1. First" in log

    def test_refuses_a_target_absent_from_the_ledger_and_writes_nothing(self, draft):
        _seed([], [("old_2023", "new_2023", True)])
        before = draft.read_text()
        with pytest.raises(DossierError, match="new_2023 is not in the ledger"):
            _renames.apply_renames(draft)
        assert draft.read_text() == before

    def test_refuses_a_cycle(self, draft):
        _seed([], [("old_2023", "x_2023", True), ("x_2023", "old_2023", True)])
        with pytest.raises(DossierError, match="cycle"):
            _renames.apply_renames(draft)

    def test_nothing_to_apply(self, draft):
        _seed(["other_2023"], [])
        assert _renames.apply_renames(draft) == []
        assert "apply-renames" not in (dossier.dossier_dir(draft) / "revisions.md").read_text()

    def test_a_draft_only_citation_logs_no_sections_line(self, draft):
        target = dossier.dossier_dir(draft)
        (target / "evidence.md").write_text("# Kept evidence\n")
        (target / "sections.md").write_text("# Sections\n")
        _seed(["new_2023"], [("old_2023", "new_2023", True)])
        _renames.apply_renames(draft)
        log = (target / "revisions.md").read_text()
        assert "Sections:" not in log.split("apply-renames: old_2023 -> new_2023")[1]

    def test_corpus_renames_read_as_none_without_a_ledger(self, isolated_config):
        assert _drift.Corpus([]).renames == {}

    def test_without_a_ledger(self, draft):
        with pytest.raises(DossierError, match="sync"):
            _renames.apply_renames(draft)


class TestCli:
    def test_prints_each_swap_and_the_quote_recheck(self, draft, capsys):
        _seed(["new_2023"], [("old_2023", "new_2023", False)])
        assert _cli.main(["apply-renames", str(draft)]) == 0
        out = capsys.readouterr().out
        assert "renamed old_2023 -> new_2023 in 3 file(s)" in out
        assert "python -m chitragupta.review quotation" in out

    def test_json(self, draft, capsys):
        _seed(["new_2023"], [("old_2023", "new_2023", True)])
        assert _cli.main(["apply-renames", str(draft), "--json"]) == 0
        (row,) = json.loads(capsys.readouterr().out)["applied"]
        assert row["old"] == "old_2023" and row["same_pdf"] is True

    def test_nothing_to_apply_says_so(self, draft, capsys):
        _seed([], [])
        assert _cli.main(["apply-renames", str(draft)]) == 0
        assert "No recorded rename applies to this draft." in capsys.readouterr().out

    def test_a_refusal_exits_1(self, draft, capsys):
        _seed([], [("old_2023", "new_2023", True)])
        assert _cli.main(["apply-renames", str(draft)]) == 1
        assert "not in the ledger" in capsys.readouterr().err
