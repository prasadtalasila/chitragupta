import json
import os
import re
import shutil
import subprocess

import pytest

from chitragupta import bib_reader, citation_gate, config, dossier, ledger, references, sync
from chitragupta import render_output

from tests.conftest import (
    _IS_COVERAGE_BOOTSTRAP,
    content_draft,
    make_reference,
    real_bibliography_path,
    run_python,
)

pandoc_available = shutil.which("pandoc") is not None
pdflatex_available = shutil.which("pdflatex") is not None
pdftotext_available = shutil.which("pdftotext") is not None


def make_real_pdf(md_path, pdf_path, body):
    md_path.write_text(body)
    subprocess.run(
        ["pandoc", str(md_path), "-o", str(pdf_path), "--pdf-engine=pdflatex"],
        check=True,
        capture_output=True,
    )


@pytest.mark.skipif(
    not (pandoc_available and pdflatex_available and pdftotext_available),
    reason="pandoc/pdflatex/pdftotext not installed",
)
class TestFullPipelineNoMocks:
    def test_full_chain_with_real_binaries(self, isolated_config, tmp_path):
        pdf_md = tmp_path / "source.md"
        pdf_path = tmp_path / "paper.pdf"
        make_real_pdf(
            pdf_md,
            pdf_path,
            "# A Paper\n\nThis paper discusses distinctive digital twin content.\n",
        )

        isolated_config.BIB_FILE_PATH.write_text(
            "@article{smith_realpaper_2024,\n"
            "  title = {A Real Paper About Digital Twins},\n"
            "  author = {Smith, Jane},\n"
            "  year = {2024},\n"
            "  file = {paper.pdf:paper.pdf:application/pdf},\n"
            "}\n"
        )

        rc = sync.run()
        assert rc == 0

        con = ledger.connect()
        try:
            row = {r["citekey"]: r for r in ledger.all_items(con)}["smith_realpaper_2024"]
        finally:
            con.close()
        assert row["status"] == "parsed"
        assert (
            "distinctive digital twin content"
            in (config.PARSED_DIR / "smith_realpaper_2024.txt").read_text()
        )

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "# Chapter\n\nAs shown by prior work [@smith_realpaper_2024], digital twins matter.\n"
        )

        gate_rc = citation_gate.run([str(draft)])
        assert gate_rc == 0

        result = references.apply(draft)
        assert "wrote References section" in result
        assert "smith_realpaper_2024" in draft.read_text()

        out_path = render_output.render(str(draft), output_format="tex")
        assert out_path.exists()
        assert out_path.read_text().strip()

    def test_fabricated_citation_is_blocked_before_render(self, isolated_config, tmp_path):
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{real_key_2024,\n  title = {Real},\n  author = {A, B},\n  year = {2024},\n}\n"
        )
        assert sync.run() == 0

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text(
            "Citing a real source [@real_key_2024] and a fabricated one [@invented_2024].\n"
        )

        rc = citation_gate.run([str(draft)])
        assert rc == 1  # must fail -- @invented_2024 was never synced from the bib file

        with pytest.raises(KeyError, match="invented_2024"):
            references.apply(draft)


real_bib_available = real_bibliography_path().exists()


@pytest.mark.skipif(
    not real_bib_available,
    reason="papers/bibliography.bib is gitignored, per-host data (AGENTS.md) -- "
    "absent on a fresh clone/CI checkout until someone exports their own",
)
class TestRealBibliographySmoke:
    def test_real_bib_file_parses_without_error(self, isolated_config, monkeypatch):
        real_bib = real_bibliography_path()
        monkeypatch.setattr(config, "BIB_FILE_PATH", real_bib)

        refs = bib_reader.read_library().references

        raw = real_bib.read_text(encoding="utf-8")
        blocks = re.split(r"^@", raw, flags=re.M)[1:]
        with_fields = [b for b in blocks if "=" in b]
        assert len(refs) == len(with_fields), (
            f"{len(with_fields)} bibliography entries carry fields but "
            f"{len(refs)} parsed -- bibtexparser skipped one it could not "
            "parse, without raising, so that paper is silently out of the "
            "corpus. Find the citekey missing from the parse and fix the "
            "braces or quotes in its entry."
        )

        citekeys = {r.citekey for r in refs}
        assert len(citekeys) == len(refs), "citekeys must be unique"

        assert "noauthor_digital_nodate" in citekeys
        assert "zech_digital-twins-as--service_2024" in citekeys

    def test_real_bib_citekeys_all_pass_citation_gate(self, isolated_config, monkeypatch):
        real_bib = real_bibliography_path()
        monkeypatch.setattr(config, "BIB_FILE_PATH", real_bib)

        refs = bib_reader.read_library().references
        con = ledger.connect()
        try:
            for ref in refs:
                ledger.upsert_reference(con, ref)
        finally:
            con.close()

        draft = isolated_config.CONTENT_DIR / "all_citekeys.md"
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text("\n".join(f"[@{r.citekey}]" for r in refs))

        con = ledger.connect()
        try:
            known = ledger.known_citekeys(con)
        finally:
            con.close()
        result = citation_gate.check_document(draft, known)
        assert result.ok, result.unknown[:10]
        assert result.total_citations == len(refs)


@pytest.mark.skipif(
    not (pandoc_available and pdflatex_available and pdftotext_available),
    reason="pandoc/pdflatex/pdftotext not installed",
)
class TestReparseReproducibility:
    def _rows(self):
        con = ledger.connect()
        try:
            return {r["citekey"]: dict(r) for r in ledger.all_items(con)}
        finally:
            con.close()

    def test_reparse_changes_only_last_synced(self, isolated_config, tmp_path):
        pdf_md = tmp_path / "source.md"
        pdf_path = tmp_path / "stable.pdf"
        make_real_pdf(
            pdf_md, pdf_path, "# Stable\n\nText that must survive a re-parse unchanged.\n"
        )
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{roe_stable_2024,\n"
            "  title = {A Stable Paper},\n"
            "  author = {Roe, Jan},\n"
            "  year = {2024},\n"
            f"  file = {{stable.pdf:{pdf_path}:application/pdf}},\n"
            "}\n"
        )

        assert sync.run() == 0
        first = self._rows()
        first_text = (config.PARSED_DIR / "roe_stable_2024.txt").read_bytes()

        assert sync.run(reparse=True) == 0
        second = self._rows()
        second_text = (config.PARSED_DIR / "roe_stable_2024.txt").read_bytes()

        assert first_text == second_text, "pdftotext output is not byte-identical"
        assert set(first) == set(second)
        row_a, row_b = first["roe_stable_2024"], second["roe_stable_2024"]
        assert row_a["last_synced"] != row_b["last_synced"], (
            "last_synced must change -- it is wall-clock, and the contract "
            "names it as the one column that does"
        )
        unstable = {k for k in row_a if row_a[k] != row_b[k]}
        assert unstable == {"last_synced"}, (
            f"columns changed across a re-parse of unchanged input: {sorted(unstable)}"
        )


def _add_paper(citekey, title, body):
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    parsed = config.PARSED_DIR / f"{citekey}.txt"
    parsed.write_text(body, encoding="utf-8")
    con = ledger.connect()
    try:
        con.execute(
            "INSERT INTO items (citekey, title, parsed_path, status, last_synced) "
            "VALUES (?, ?, ?, 'parsed', '2026-01-01')",
            (citekey, title, str(parsed)),
        )
        con.commit()
    finally:
        con.close()


def _drop_paper(citekey):
    con = ledger.connect()
    try:
        con.execute("DELETE FROM items WHERE citekey = ?", (citekey,))
        con.commit()
    finally:
        con.close()
    (config.PARSED_DIR / f"{citekey}.txt").unlink()


class TestReGroundingAfterTheCorpusMoves:
    @pytest.fixture
    def grounded(self, isolated_config):
        _add_paper(
            "kept_paper_2024",
            "Digital twin architectures",
            "Digital twin architectures for engineering systems.",
        )
        _add_paper(
            "turned_down_2023",
            "Digital twin adoption economics",
            "Digital twin adoption economics and cost recovery.",
        )

        draft = config.DRAFTS_DIR / "dt-for-engineers" / "survey.md"
        draft.parent.mkdir(parents=True)
        draft.write_text(
            "# A survey\n\n## 1. First\n\n"
            "Twins are structured this way [@kept_paper_2024].\n\n"
            "## 2. Second\n\nmore\n"
        )

        dossier.init(draft, "survey")
        target = dossier.dossier_dir(draft)
        (target / "evidence.md").write_text(
            "# Kept evidence\n\n## `kept_paper_2024`\n\nHow twins are structured.\n"
        )
        (target / "rejected.md").write_text(
            "# Rejected candidates\n\n| citekey | query that surfaced it | why rejected |\n"
            "|---|---|---|\n"
            "| `turned_down_2023` | digital twin | out of scope: adoption economics |\n"
        )
        (target / "sections.md").write_text(
            "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
            "| 1. First | `kept_paper_2024` |\n"
        )
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 2400)

        assert citation_gate.run([str(draft)]) == 0, "the draft starts sound"
        return draft

    def test_a_moved_corpus_produces_the_three_findings_and_a_failing_gate(self, grounded):
        _drop_paper("kept_paper_2024")
        _add_paper(
            "fresh_twin_2026",
            "Digital twin fidelity",
            "Digital twin fidelity metrics for engineering models.",
        )

        report = dossier.drift(dossier.dossier_dir(grounded))

        assert report.missing == {"kept_paper_2024": ["1. First"]}
        assert citation_gate.run([str(grounded)]) == 1, (
            "the gate is the exit criterion, and it must already disagree "
            "with a draft the drift report calls broken"
        )

        assert [c.citekey for c in report.candidates] == ["fresh_twin_2026"]

        assert [r.citekey for r in report.reconsider] == ["turned_down_2023"]
        assert report.reconsider[0].reason == "out of scope: adoption economics"

        assert report.drifted, "the recorded fingerprint no longer matches"

    def test_the_json_the_skill_reads_carries_all_three(self, grounded, capsys):
        _drop_paper("kept_paper_2024")
        _add_paper(
            "fresh_twin_2026",
            "Digital twin fidelity",
            "Digital twin fidelity metrics for engineering models.",
        )

        assert dossier.main(["status", str(grounded), "--json"]) == 0
        (entry,) = __import__("json").loads(capsys.readouterr().out)["dossiers"]

        assert entry["corpus_available"] is True
        assert entry["missing"] == {"kept_paper_2024": ["1. First"]}
        assert [c["citekey"] for c in entry["candidates"]] == ["fresh_twin_2026"]
        assert entry["reconsider"][0]["reason"] == "out of scope: adoption economics"
        assert entry["current"] is not None, "the values a re-stamp writes back"

    def test_a_scoped_re_grounding_clears_the_defect_and_passes_the_gate(self, grounded):
        _drop_paper("kept_paper_2024")
        _add_paper(
            "fresh_twin_2026",
            "Digital twin fidelity",
            "Digital twin fidelity metrics for engineering models.",
        )
        target = dossier.dossier_dir(grounded)
        before = dossier.recorded_corpus(target)

        grounded.write_text(grounded.read_text().replace("@kept_paper_2024", "@fresh_twin_2026"))
        (target / "evidence.md").write_text(
            "# Kept evidence\n\n## `fresh_twin_2026`\n\nHow twins are structured.\n"
        )
        (target / "sections.md").write_text(
            "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
            "| 1. First | `fresh_twin_2026` |\n"
        )

        report = dossier.drift(target)
        assert not report.missing, "the defect is gone"
        assert "fresh_twin_2026" not in [c.citekey for c in report.candidates], (
            "an accepted candidate leaves the list by being recorded in evidence.md"
        )
        assert citation_gate.run([str(grounded)]) == 0

        assert dossier.recorded_corpus(target) == before, (
            "clearing the defect needs no fingerprint re-stamp -- the "
            "re-stamp is bookkeeping the skill does afterwards, not the "
            "mechanism"
        )

    def test_re_stamping_the_fingerprint_clears_drifted_and_still_parses(self, grounded):
        _drop_paper("kept_paper_2024")
        _add_paper(
            "fresh_twin_2026",
            "Digital twin fidelity",
            "Digital twin fidelity metrics for engineering models.",
        )
        target = dossier.dossier_dir(grounded)
        scope = target / "scope.md"

        (count, digest) = dossier.drift(target).current
        old = dossier.recorded_corpus(target)
        scope.write_text(
            scope.read_text().replace(
                f"- corpus: {old[0]} citekeys, digest `{old[1]}`",
                f"- corpus: {count} citekeys, digest `{digest}`",
            )
        )

        assert dossier.recorded_corpus(target) == (count, digest), (
            "the re-stamped line must still match what `init` wrote"
        )
        assert not dossier.drift(target).drifted

    def test_an_unpursued_candidate_keeps_the_dossier_unclean(self, grounded):
        _drop_paper("kept_paper_2024")
        _add_paper(
            "fresh_twin_2026",
            "Digital twin fidelity",
            "Digital twin fidelity metrics for engineering models.",
        )
        _add_paper(
            "other_twin_2026",
            "Digital twin calibration",
            "Digital twin calibration under drift in engineering use.",
        )
        target = dossier.dossier_dir(grounded)

        grounded.write_text(grounded.read_text().replace("@kept_paper_2024", "@fresh_twin_2026"))
        (target / "evidence.md").write_text(
            "# Kept evidence\n\n## `fresh_twin_2026`\n\nHow twins are structured.\n"
        )
        (target / "sections.md").write_text(
            "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
            "| 1. First | `fresh_twin_2026` |\n"
        )

        report = dossier.drift(target)
        assert not report.missing
        assert [c.citekey for c in report.candidates] == ["other_twin_2026"]
        assert not report.clean, (
            "an unweighed candidate is still a decision the sweep should surface"
        )


SCAN_RUN_CITED = (
    "the composable architecture of a digital twin separates its "
    "simulation core from its data ingestion layer"
)
SCAN_RUN_UNCITED = (
    "elastic provisioning of virtual machines allows a workload to "
    "acquire capacity on demand and release it afterwards"
)
SCAN_RUN_CONNECTIVE = (
    "recalibration must be triggered whenever the residual between "
    "measured and predicted behaviour exceeds a fixed threshold"
)
SCAN_RUN_AFTER_RESYNC = (
    "the revised architecture note now describes a scheduler that "
    "batches ingestion jobs by priority"
)

SCAN_PARAPHRASE_IN_SOURCE = (
    "the validation of a digital twin requires continuous comparison "
    "against measurements taken from the physical asset"
)
SCAN_PARAPHRASE_IN_DRAFT = (
    "the validation of one digital twin requires constant comparison "
    "against measurements drawn from the physical plant"
)


def _scan_source_text(page_one, page_two):
    return f"{page_one}\n\f{page_two}\n"


def _add_scan_paper(citekey, text, pdf_bytes=b"%PDF-1.4 fixture"):
    config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
    pdf = config.CONTENT_DIR / f"{citekey}.pdf"
    pdf.write_bytes(pdf_bytes)
    parsed = config.PARSED_DIR / f"{citekey}.txt"
    parsed.write_text(text, encoding="utf-8")
    con = ledger.connect()
    try:
        ledger.upsert_reference(con, make_reference(citekey=citekey, pdf_path=str(pdf)))
        ledger.mark_parsed(con, citekey, parsed)
    finally:
        con.close()
    return parsed


_FINDING_RE = re.compile(
    r"\s+\[(?P<span>\d+) words(?:, (?P<matched>\d+) matched)?, "
    r"pdf p\.(?P<page>\d+)(?:, draft (?P<position>[^\]]+))?\] "
    r"(?P<citekey>\S+) \(tier=(?P<tier>[\w-]+)\)(?P<flags>.*)"
)


def _findings(stdout):
    lines = stdout.splitlines()
    parsed = []
    for i, line in enumerate(lines):
        match = _FINDING_RE.fullmatch(line)
        if match:
            parsed.append(
                {
                    "span": int(match["span"]),
                    "page": int(match["page"]),
                    "citekey": match["citekey"],
                    "tier": match["tier"],
                    "flags": match["flags"].strip(),
                    "position": (match["position"] or "").strip(),
                    "fragment": lines[i + 1].strip().removeprefix("draft:").strip(),
                }
            )
    return parsed


def _run_scan(draft, *args):
    return _run_verbatim("scan", str(draft), *args)


def _run_verbatim(mode, *args):
    env = {k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)}
    env["CONTENT_DIR"] = str(config.CONTENT_DIR)
    return run_python("-m", "chitragupta.review", "verbatim", mode, *args, env=env)


class TestVerbatimScanEndToEnd:
    @pytest.fixture
    def corpus(self, isolated_config):
        _add_scan_paper(
            "dt_arch_2024",
            _scan_source_text(
                "This opening page reviews how twins are checked before release. "
                + SCAN_PARAPHRASE_IN_SOURCE
                + ".",
                SCAN_RUN_CITED + ". A later remark on module boundaries follows it.",
            ),
        )
        _add_scan_paper(
            "cloud_infra_2023",
            _scan_source_text(
                "An opening page about billing models for rented hardware.",
                SCAN_RUN_UNCITED + ". Costs are then compared across three vendors.",
            ),
        )
        _add_scan_paper(
            "calib_2025",
            _scan_source_text(
                "An opening page about sensor drift in long-lived deployments.",
                SCAN_RUN_CONNECTIVE + ". Two thresholds are then derived empirically.",
            ),
        )
        return isolated_config

    @pytest.fixture
    def planted_draft(self, corpus):
        draft = content_draft(corpus, "drafts/scan-e2e.md")
        draft.write_text(
            "# Architecture of digital twins\n\n"
            "## 1. Structure\n\n"
            f"Recent work sets out the shape of these systems: {SCAN_RUN_CITED} "
            "[@dt_arch_2024].\n\n"
            "## 2. Deployment\n\n"
            "Most twins are deployed on rented infrastructure [@dt_arch_2024]. "
            f"{SCAN_RUN_UNCITED}.\n\n"
            "## 3. Keeping a twin honest\n\n"
            f"{SCAN_RUN_CONNECTIVE}. That question is taken up below.\n\n"
            "## 4. Validation\n\n"
            f"{SCAN_PARAPHRASE_IN_DRAFT}, which is by now a familiar demand.\n",
            encoding="utf-8",
        )
        return draft

    def test_planted_runs_from_cited_uncited_and_connective_prose_all_report(self, planted_draft):
        result = _run_scan(planted_draft)

        assert result.returncode == 0, result.stderr
        findings = {(f["citekey"], f["page"]): f for f in _findings(result.stdout)}
        assert {citekey for citekey, _page in findings} == {
            "dt_arch_2024",
            "cloud_infra_2023",
            "calib_2025",
        }

        cited = findings["dt_arch_2024", 2]
        assert cited["fragment"] == SCAN_RUN_CITED
        assert cited["page"] == 2, "the run was planted on the source's second page"
        assert cited["tier"] == "exact"
        assert "UNCITED SOURCE" not in cited["flags"]

        uncited = findings["cloud_infra_2023", 2]
        assert uncited["fragment"] == SCAN_RUN_UNCITED
        assert uncited["page"] == 2
        assert "UNCITED SOURCE" in uncited["flags"]

        connective = findings["calib_2025", 2]
        assert connective["fragment"] == SCAN_RUN_CONNECTIVE
        assert connective["page"] == 2
        assert "UNCITED SOURCE" in connective["flags"]

    def test_lightly_paraphrased_run_is_missed_by_the_exact_tier_alone(self, planted_draft):
        result = _run_scan(planted_draft)

        assert result.returncode == 0, result.stderr
        assert not [
            f
            for f in _findings(result.stdout)
            if f["citekey"] == "dt_arch_2024" and f["page"] == 1 and f["tier"] == "exact"
        ], "the exact tier reported the paraphrased passage on the source's first page"

    def test_lightly_paraphrased_run_is_reported_by_the_skipgram_tier(self, planted_draft):
        result = _run_scan(planted_draft)

        assert result.returncode == 0, result.stderr
        skipgram_findings = [
            f for f in _findings(result.stdout) if f["citekey"] == "dt_arch_2024" and f["page"] == 1
        ]
        assert skipgram_findings, "the skip-gram tier did not report the paraphrased passage"
        assert all(f["tier"] == "skip-gram" for f in skipgram_findings)
        assert "validation" in result.stdout

    def test_clean_draft_reports_nothing_and_still_exits_zero(self, corpus):
        draft = content_draft(corpus, "drafts/scan-clean.md")
        draft.write_text(
            "# A clean chapter\n\n"
            "Everything here was written from scratch for this chapter, and "
            "no sentence in it was taken from anywhere else [@dt_arch_2024].\n",
            encoding="utf-8",
        )

        result = _run_scan(draft)

        assert result.returncode == 0, result.stderr
        assert "no verbatim run" in result.stdout
        assert _findings(result.stdout) == []

    def test_the_embedding_tier_says_it_did_not_run_rather_than_going_quiet(self, planted_draft):
        result = _run_scan(planted_draft, "--json")

        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        not_run = payload["tiers_not_run"]
        assert [entry["tier"] for entry in not_run] == ["embedding"]
        assert not_run[0]["reason"], "a tier that did not run must say why"

    def test_every_finding_carries_the_score_field_even_where_it_is_null(self, planted_draft):
        result = _run_scan(planted_draft, "--json")

        assert result.returncode == 0, result.stderr
        findings = json.loads(result.stdout)["findings"]
        assert findings, "expected the planted runs to be found"
        assert all("score" in f for f in findings)
        assert all(f["score"] is None for f in findings if f["tier"] != "embedding")

    def test_first_scan_builds_the_index_on_disk(self, planted_draft):
        assert not config.OVERLAP_DIR.exists(), "the fixture starts with no cache"

        assert _run_scan(planted_draft).returncode == 0

        assert (config.OVERLAP_DIR / "index.bin").is_file()
        assert (config.OVERLAP_DIR / "index.json").is_file()
        for citekey in ("dt_arch_2024", "cloud_infra_2023", "calib_2025"):
            assert (config.OVERLAP_DIR / "docs" / f"{citekey}.fpr").is_file()

    def test_rescanning_an_unchanged_corpus_reuses_the_merged_index(self, planted_draft):
        first = _run_scan(planted_draft)
        assert first.returncode == 0, first.stderr
        index_bin = config.OVERLAP_DIR / "index.bin"
        stamp = index_bin.stat().st_mtime_ns
        key = json.loads((config.OVERLAP_DIR / "index.json").read_text())["key"]

        second = _run_scan(planted_draft)

        assert second.returncode == 0, second.stderr
        assert index_bin.stat().st_mtime_ns == stamp, "the merged index was rebuilt"
        assert json.loads((config.OVERLAP_DIR / "index.json").read_text())["key"] == key
        assert second.stdout == first.stdout, "a cache hit changed the findings"

    def test_a_resynced_source_is_refingerprinted_before_the_next_scan(self, corpus):
        draft = content_draft(corpus, "drafts/scan-resync.md")
        draft.write_text(
            f"One claim [@dt_arch_2024]. {SCAN_RUN_CITED}.\n\n"
            f"Another claim [@dt_arch_2024]. {SCAN_RUN_AFTER_RESYNC}.\n",
            encoding="utf-8",
        )
        before = _run_scan(draft)
        assert [f["fragment"] for f in _findings(before.stdout)] == [SCAN_RUN_CITED]
        key_before = json.loads((config.OVERLAP_DIR / "index.json").read_text())["key"]

        _add_scan_paper(
            "dt_arch_2024",
            _scan_source_text(
                "A rewritten opening page.",
                SCAN_RUN_AFTER_RESYNC + ". The scheduler section then continues.",
            ),
            pdf_bytes=b"%PDF-1.4 fixture, revised",
        )

        after = _run_scan(draft)

        assert after.returncode == 0, after.stderr
        assert [f["fragment"] for f in _findings(after.stdout)] == [SCAN_RUN_AFTER_RESYNC], (
            "the scan served fingerprints of text the corpus no longer holds"
        )
        assert json.loads((config.OVERLAP_DIR / "index.json").read_text())["key"] != key_before

    def test_scan_runs_on_the_bare_system_interpreter(self, planted_draft, system_python):
        env = {k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)}
        env["CONTENT_DIR"] = str(config.CONTENT_DIR)

        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "scan",
            str(planted_draft),
            python=system_python,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        assert {f["citekey"] for f in _findings(result.stdout)} == {
            "dt_arch_2024",
            "cloud_infra_2023",
            "calib_2025",
        }


class TestOverlapRemediationEndToEnd:
    @pytest.fixture
    def corpus(self, isolated_config):
        _add_scan_paper(
            "cloud_infra_2023",
            _scan_source_text(
                "An opening page about billing models for rented hardware.",
                SCAN_RUN_UNCITED + ". Costs are then compared across three vendors.",
            ),
        )
        _add_scan_paper(
            "calib_2025",
            _scan_source_text(
                "An opening page about sensor drift in long-lived deployments.",
                SCAN_RUN_CONNECTIVE + ". Two thresholds are then derived empirically.",
            ),
        )
        return isolated_config

    @pytest.fixture
    def draft(self, corpus):
        draft = content_draft(corpus, "drafts/remediate-e2e.md")
        draft.write_text(
            "# Deployment\n\n"
            f"Most twins run on rented hardware. {SCAN_RUN_UNCITED}.\n\n"
            "## Keeping a twin honest\n\n"
            f"{SCAN_RUN_CONNECTIVE}. That question is taken up below.\n",
            encoding="utf-8",
        )
        return draft

    def _baseline(self, draft):
        result = _run_scan(draft, "--write", "--formats", "md")
        assert result.returncode == 0, result.stderr
        path = config.REVIEW_DIR / "remediate-e2e.verbatim.json"
        return path, json.loads(path.read_text(encoding="utf-8"))

    def test_a_filed_findings_draft_text_still_matches_the_draft(self, draft):
        path, payload = self._baseline(draft)

        assert path.is_file()
        text = draft.read_text(encoding="utf-8")
        for finding in payload["findings"]:
            assert finding["draft_text"] in text
            assert text[finding["char_start"] : finding["char_end"]] == finding["draft_text"]

    def test_repairing_one_finding_reports_it_resolved_and_the_other_persisting(self, draft):
        path, payload = self._baseline(draft)
        target = next(f for f in payload["findings"] if f["citekey"] == "cloud_infra_2023")
        other = next(f for f in payload["findings"] if f["citekey"] == "calib_2025")

        draft.write_text(
            draft.read_text(encoding="utf-8").replace(
                target["draft_text"],
                "we rewrote this passage in our own words, keeping the claim",
            ),
            encoding="utf-8",
        )
        result = _run_verbatim("recheck", str(draft), "--baseline", str(path), "--json")

        assert result.returncode == 0, result.stderr
        comparison = json.loads(result.stdout)
        assert [f["id"] for f in comparison["resolved"]] == [target["id"]]
        assert [f["id"] for f in comparison["persisting"]] == [other["id"]]
        assert comparison["new"] == []
        assert comparison["objective_delta"] == -1

    def test_an_untouched_draft_is_reported_as_no_progress_not_as_success(self, draft):
        path, _ = self._baseline(draft)

        result = _run_verbatim("recheck", str(draft), "--baseline", str(path), "--json")

        assert result.returncode == 0, result.stderr
        comparison = json.loads(result.stdout)
        assert comparison["resolved"] == []
        assert comparison["objective_delta"] == 0

    def test_recheck_exits_zero_on_a_draft_it_could_not_improve(self, draft):
        path, _ = self._baseline(draft)

        assert _run_verbatim("recheck", str(draft), "--baseline", str(path)).returncode == 0

    def test_recheck_runs_on_the_bare_system_interpreter(self, draft, system_python):
        path, _ = self._baseline(draft)
        env = {k: v for k, v in os.environ.items() if not _IS_COVERAGE_BOOTSTRAP(k)}
        env["CONTENT_DIR"] = str(config.CONTENT_DIR)

        result = run_python(
            "-m",
            "chitragupta.review",
            "verbatim",
            "recheck",
            str(draft),
            "--baseline",
            str(path),
            python=system_python,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        assert "objective findings (long + short): 2 -> 2" in result.stdout


class TestOneDraftsReviewArtefactsLandTogether:
    def _draft(self, isolated_config):
        _add_scan_paper(
            "dt_arch_2024",
            _scan_source_text(
                "Front matter and abstract.",
                "A digital twin architecture couples a physical asset to its model.",
            ),
        )
        draft = content_draft(isolated_config, "drafts/dt/survey.md")
        draft.write_text(
            "# Survey\n\n"
            "A digital twin architecture couples a physical asset to its "
            "model [@dt_arch_2024].\n"
        )
        return draft

    def test_all_three_reports_share_one_mirrored_directory(self, isolated_config, capsys):
        from chitragupta.review import verbatim_check as vc
        from chitragupta.review import citation_coverage, citation_provenance

        draft = self._draft(isolated_config)

        citation_provenance.write_report(draft, ["md"])
        vc.cmd_scan(str(draft), write=True, formats=["md"])
        citation_coverage.main(
            [str(draft), "--query", "digital twin", "--write", "--formats", "md"]
        )

        review_dir = config.REVIEW_DIR / "dt"
        assert sorted(p.name for p in review_dir.iterdir()) == [
            "survey.coverage.json",
            "survey.coverage.md",
            "survey.provenance.md",
            "survey.verbatim.json",
            "survey.verbatim.md",
        ]

    def test_nothing_lands_in_the_drafting_layers_output(self, isolated_config, capsys):
        from chitragupta.review import citation_provenance

        draft = self._draft(isolated_config)
        citation_provenance.write_report(draft, ["md"])

        assert not list(config.RENDERED_DIR.rglob("*provenance*")), (
            "a review artefact reached content/rendered/"
        )

    def test_every_report_says_it_is_not_a_verdict(self, isolated_config, capsys):
        from chitragupta.review import verbatim_check as vc
        from chitragupta.review import citation_coverage, citation_provenance

        draft = self._draft(isolated_config)
        citation_provenance.write_report(draft, ["md"])
        vc.cmd_scan(str(draft), write=True, formats=["md"])
        citation_coverage.main(
            [str(draft), "--query", "digital twin", "--write", "--formats", "md"]
        )

        for report in (config.REVIEW_DIR / "dt").iterdir():
            assert "Review aid, not a gate" in report.read_text(), report.name

    def test_the_bundle_carries_them_and_restores_them(self, isolated_config, tmp_path, capsys):
        from chitragupta.review import verbatim_check as vc
        from chitragupta.review import citation_provenance

        draft = self._draft(isolated_config)
        dossier.init(draft, "survey")
        citation_provenance.write_report(draft, ["md"])
        vc.cmd_scan(str(draft), write=True, formats=["md"])

        out, _ = dossier.export([], tmp_path / "bundle.tar.gz")
        shutil.rmtree(config.REVIEW_DIR)

        plan = dossier.restore(out, force=True)

        assert plan.performed
        assert sorted(p.name for p in (config.REVIEW_DIR / "dt").iterdir()) == [
            "survey.provenance.md",
            "survey.verbatim.json",
            "survey.verbatim.md",
        ]
