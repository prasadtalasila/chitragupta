"""Feature tests: the actual chains a user runs, exercised with real
binaries (pdftotext/pandoc/pdflatex) and no mocking of the seams between
modules -- as distinct from the unit tests elsewhere, which mock those
seams deliberately for speed/determinism. These are slower but catch
integration regressions the unit tests structurally can't (e.g. sync's
real handoff to pdf_text, or a regression in the real bibliography.bib
export itself)."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from src import bib_reader, citation_gate, config, dossier, ledger, references, sync
from src import render_output

from tests.conftest import content_draft, make_reference

pandoc_available = shutil.which("pandoc") is not None
pdflatex_available = shutil.which("pdflatex") is not None
pdftotext_available = shutil.which("pdftotext") is not None


def make_real_pdf(md_path, pdf_path, body):
    md_path.write_text(body)
    subprocess.run(
        ["pandoc", str(md_path), "-o", str(pdf_path), "--pdf-engine=pdflatex"],
        check=True, capture_output=True,
    )


@pytest.mark.skipif(
    not (pandoc_available and pdflatex_available and pdftotext_available),
    reason="pandoc/pdflatex/pdftotext not installed",
)
class TestFullPipelineNoMocks:
    """bib -> sync (real pdftotext) -> draft -> citation_gate -> references
    -> render_output.render, with nothing mocked -- the real workflow
    AGENTS.md describes, end to end."""

    def test_full_chain_with_real_binaries(self, isolated_config, tmp_path):
        pdf_md = tmp_path / "source.md"
        pdf_path = tmp_path / "paper.pdf"
        make_real_pdf(pdf_md, pdf_path, "# A Paper\n\nThis paper discusses distinctive digital twin content.\n")

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
        assert "distinctive digital twin content" in (config.PARSED_DIR / "smith_realpaper_2024.txt").read_text()

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
        """The hard invariant (AGENTS.md): a citekey not in the ledger
        must fail the gate, not silently make it to a rendered draft."""
        isolated_config.BIB_FILE_PATH.write_text(
            "@article{real_key_2024,\n  title = {Real},\n  author = {A, B},\n  year = {2024},\n}\n"
        )
        assert sync.run() == 0

        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("Citing a real source [@real_key_2024] and a fabricated one [@invented_2024].\n")

        rc = citation_gate.run([str(draft)])
        assert rc == 1  # must fail -- @invented_2024 was never synced from the bib file

        # references.apply would itself hard-error on the fabricated key,
        # which is the second line of defense if the gate is skipped.
        with pytest.raises(KeyError, match="invented_2024"):
            references.apply(draft)


real_bib_available = (config.REPO_ROOT / "papers" / "bibliography.bib").exists()


@pytest.mark.skipif(
    not real_bib_available,
    reason="papers/bibliography.bib is gitignored, per-host data (AGENTS.md) -- "
           "absent on a fresh clone/CI checkout until someone exports their own",
)
class TestRealBibliographySmoke:
    """Parses this repo's actual bibliography.bib (read-only) -- catches
    a regression against real export data that a synthetic 1-3 entry
    fixture can't, which is exactly the failure class AGENTS.md's hard
    invariant exists to prevent."""

    def test_real_bib_file_parses_without_error(self, isolated_config, monkeypatch):
        real_bib = config.REPO_ROOT / "papers" / "bibliography.bib"
        monkeypatch.setattr(config, "BIB_FILE_PATH", real_bib)

        refs = bib_reader.read_library()
        assert len(refs) == 646

        citekeys = {r.citekey for r in refs}
        assert len(citekeys) == len(refs), "citekeys must be unique"

        # Known awkward real entries this pipeline's design explicitly
        # accounts for: a no-author webpage export, and a citekey
        # containing "--" (render_output.py's alias workaround exists
        # because of exactly this key).
        assert "noauthor_digital_nodate" in citekeys
        assert "zech_digital-twins-as--service_2024" in citekeys

    def test_real_bib_citekeys_all_pass_citation_gate(self, isolated_config, monkeypatch):
        """Every real citekey, cited in Pandoc form, must be recognized
        as known once synced -- the gate's regex must not choke on any
        real citekey shape (hyphens, underscores, digits, "--")."""
        real_bib = config.REPO_ROOT / "papers" / "bibliography.bib"
        monkeypatch.setattr(config, "BIB_FILE_PATH", real_bib)

        refs = bib_reader.read_library()
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
    """The ledger half of the reproducibility contract, pinned.

    docs/ARCHITECTURE.md's "What is reproducible, and what is not" makes
    two claims about a re-parse of unchanged input: every ledger column
    comes back byte-identical *except* `last_synced`, and `pdftotext`
    output is byte-identical. Both are the kind of promise that rots
    silently -- a new column defaulting to a timestamp, or a backend flag
    that reorders output, would break it with nothing failing.

    Real `pdftotext` on a real PDF rather than a mocked extractor,
    because a fake that returns a constant string would pass this test
    while proving nothing about the backend the claim is actually about.

    `last_synced` is asserted to **change** rather than quietly excluded.
    Excluding it would leave a test that passes whatever the contract
    says; asserting it encodes the exception as part of the promise.
    """

    def _rows(self):
        con = ledger.connect()
        try:
            return {r["citekey"]: dict(r) for r in ledger.all_items(con)}
        finally:
            con.close()

    def test_reparse_changes_only_last_synced(self, isolated_config, tmp_path):
        pdf_md = tmp_path / "source.md"
        pdf_path = tmp_path / "stable.pdf"
        make_real_pdf(pdf_md, pdf_path, "# Stable\n\nText that must survive a re-parse unchanged.\n")
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

        # --reparse, not a plain re-run: a second sync would skip the
        # document on its unchanged hash and compare the parse against
        # itself, which tests the skip logic rather than the parser.
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
        # Every other column, whatever the schema grows to. Written as a
        # difference rather than a fixed list so a column added later is
        # covered by this test on the day it lands, not the day someone
        # remembers to add it here.
        unstable = {k for k in row_a if row_a[k] != row_b[k]}
        assert unstable == {"last_synced"}, (
            f"columns changed across a re-parse of unchanged input: {sorted(unstable)}"
        )


def _add_paper(citekey, title, body):
    """One parsed paper in the ledger, with the text a query ranks against.

    Raw SQL for the same reason `tests/test_dossier.py` uses it:
    `upsert_reference` takes a `bib_reader.Reference` and would drag
    bibtexparser into a chain that is otherwise stdlib-only.
    """
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
    """What `sync --remove-stale` does to a paper dropped from the bib."""
    con = ledger.connect()
    try:
        con.execute("DELETE FROM items WHERE citekey = ?", (citekey,))
        con.commit()
    finally:
        con.close()
    (config.PARSED_DIR / f"{citekey}.txt").unlink()


class TestReGroundingAfterTheCorpusMoves:
    """The chain `draft-reviser`'s re-grounding mode runs: a corpus that
    moved -> `dossier status --json` -> a scoped edit -> `citation_gate`.

    Characterisation rather than test-first: the mode itself lives in
    `.claude/skills/draft-reviser/SKILL.md`, which no test can assert on.
    What these pin is the composition underneath it -- the three findings
    the skill branches on, and the fact that acting on them needs no new
    machinery. A change in `src/` that broke the mode would otherwise
    break nothing that fails.

    No binaries: the seams here are dossier <-> ledger <-> citation_gate,
    all pure Python, so this runs everywhere rather than skipping wherever
    pandoc is absent.
    """

    @pytest.fixture
    def grounded(self, isolated_config):
        """A draft that cites one paper, turned another down, and logged
        the query that found both -- written against the corpus as it
        stood at the time, so `scope.md` records that fingerprint."""
        _add_paper("kept_paper_2024", "Digital twin architectures",
                   "Digital twin architectures for engineering systems.")
        _add_paper("turned_down_2023", "Digital twin adoption economics",
                   "Digital twin adoption economics and cost recovery.")

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
            "|---|---|---|\n| `turned_down_2023` | digital twin | out of scope: adoption economics |\n"
        )
        (target / "sections.md").write_text(
            "# Sections and their citekeys\n\n| section | citekeys |\n|---|---|\n"
            "| 1. First | `kept_paper_2024` |\n"
        )
        dossier.log_retrieval(draft, "search", "digital twin", 15, 15, 2400)

        assert citation_gate.run([str(draft)]) == 0, "the draft starts sound"
        return draft

    def test_a_moved_corpus_produces_the_three_findings_and_a_failing_gate(self, grounded):
        """`missing` is a defect the gate agrees with; `candidates` are new;
        a paper already turned down is held back in `reconsider`."""
        _drop_paper("kept_paper_2024")
        _add_paper("fresh_twin_2026", "Digital twin fidelity",
                   "Digital twin fidelity metrics for engineering models.")

        report = dossier.drift(dossier.dossier_dir(grounded))

        # A defect: the draft stands on a paper the corpus no longer has,
        # carried with the section that cites it so the edit stays scoped.
        assert report.missing == {"kept_paper_2024": ["1. First"]}
        assert citation_gate.run([str(grounded)]) == 1, (
            "the gate is the exit criterion, and it must already disagree "
            "with a draft the drift report calls broken"
        )

        # An opportunity, and a separate kind of thing.
        assert [c.citekey for c in report.candidates] == ["fresh_twin_2026"]

        # Already judged once. `rejected.md` was subtracted from
        # `candidates`, and the reason is carried so the skill can weigh
        # it without re-retrieving and re-judging the paper.
        assert [r.citekey for r in report.reconsider] == ["turned_down_2023"]
        assert report.reconsider[0].reason == "out of scope: adoption economics"

        assert report.drifted, "the recorded fingerprint no longer matches"

    def test_the_json_the_skill_reads_carries_all_three(self, grounded, capsys):
        """One envelope, one element, exit 0 -- the contract #85 added for
        this mode. The skill branches on the payload, never the code."""
        _drop_paper("kept_paper_2024")
        _add_paper("fresh_twin_2026", "Digital twin fidelity",
                   "Digital twin fidelity metrics for engineering models.")

        assert dossier.main(["status", str(grounded), "--json"]) == 0
        (entry,) = __import__("json").loads(capsys.readouterr().out)["dossiers"]

        assert entry["corpus_available"] is True
        assert entry["missing"] == {"kept_paper_2024": ["1. First"]}
        assert [c["citekey"] for c in entry["candidates"]] == ["fresh_twin_2026"]
        assert entry["reconsider"][0]["reason"] == "out of scope: adoption economics"
        assert entry["current"] is not None, "the values a re-stamp writes back"

    def test_a_scoped_re_grounding_clears_the_defect_and_passes_the_gate(self, grounded):
        """Swapping the citation and recording the swap drives `missing`
        empty and the gate back to OK -- with nothing in `src/` beyond the
        files the skill already writes, and no fingerprint change."""
        _drop_paper("kept_paper_2024")
        _add_paper("fresh_twin_2026", "Digital twin fidelity",
                   "Digital twin fidelity metrics for engineering models.")
        target = dossier.dossier_dir(grounded)
        before = dossier.recorded_corpus(target)

        # Exactly what the skill does: edit inside the one section the
        # report named, then write the dossier back.
        grounded.write_text(
            grounded.read_text().replace("@kept_paper_2024", "@fresh_twin_2026")
        )
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
        """The one step of the mode with a silent failure mode.

        `scope.md`'s corpus line is written once by `init` and rewritten
        only here. Reshaping it rather than rewriting it makes
        `recorded_corpus()` return `None`, and the dossier downgrades to
        "records no corpus fingerprint" instead of erroring -- so the
        skill is told to rewrite the line in place, and this is what says
        that the line it writes is one the parser accepts.
        """
        _drop_paper("kept_paper_2024")
        _add_paper("fresh_twin_2026", "Digital twin fidelity",
                   "Digital twin fidelity metrics for engineering models.")
        target = dossier.dossier_dir(grounded)
        scope = target / "scope.md"

        (count, digest) = dossier.drift(target).current
        old = dossier.recorded_corpus(target)
        scope.write_text(scope.read_text().replace(
            f"- corpus: {old[0]} citekeys, digest `{old[1]}`",
            f"- corpus: {count} citekeys, digest `{digest}`",
        ))

        assert dossier.recorded_corpus(target) == (count, digest), (
            "the re-stamped line must still match what `init` wrote"
        )
        assert not dossier.drift(target).drifted

    def test_an_unpursued_candidate_keeps_the_dossier_unclean(self, grounded):
        """The limit of the claim above, pinned deliberately.

        `Drift.clean` is `not missing and not candidates`, so a dossier
        with any candidate left unpursued still shows in the sweep -- and
        on a real corpus that is the normal outcome, since a query returns
        fifteen hits and a revision accepts one or two. Driving `clean`
        true would mean writing the rest into `rejected.md` on nothing but
        a title, which is the judgment `docs/REJECTION.md` refuses to make
        cheaply. Re-grounding therefore promises `missing`, not `clean`.
        """
        _drop_paper("kept_paper_2024")
        _add_paper("fresh_twin_2026", "Digital twin fidelity",
                   "Digital twin fidelity metrics for engineering models.")
        _add_paper("other_twin_2026", "Digital twin calibration",
                   "Digital twin calibration under drift in engineering use.")
        target = dossier.dossier_dir(grounded)

        grounded.write_text(
            grounded.read_text().replace("@kept_paper_2024", "@fresh_twin_2026")
        )
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


# --- The whole-draft x whole-corpus verbatim scan, end to end -------------
#
# tests/test_verbatim_check.py drives `cmd_scan()` in process, with capsys
# and a hand-built index, and covers the finding logic. These drive the
# command a reviewer actually types -- a child process, over a real
# mini-ledger with real pdf_hash values and real form-feed page breaks --
# and assert on what the user sees. Four things that reaches which the
# unit tests structurally cannot: the CONTENT_DIR override the command is
# configured through, the index artifacts appearing on disk, their reuse
# on a second run, and invalidation after the corpus moves underneath.

# Planted verbatim runs. Each is well above the n=8 index floor, so a
# finding is unambiguous rather than borderline.
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
# What the corpus says after a re-sync replaces the first source's text.
SCAN_RUN_AFTER_RESYNC = (
    "the revised architecture note now describes a scheduler that "
    "batches ingestion jobs by priority"
)

# The negative control. The draft form swaps a synonym at exactly every
# fourth word of the source form -- see the test that uses it for why
# that spacing is the point rather than an arbitrary choice.
SCAN_PARAPHRASE_IN_SOURCE = (
    "the validation of a digital twin requires continuous comparison "
    "against measurements taken from the physical asset"
)
SCAN_PARAPHRASE_IN_DRAFT = (
    "the validation of one digital twin requires constant comparison "
    "against measurements drawn from the physical plant"
)


def _scan_source_text(page_one, page_two):
    """Parsed text with a real form-feed page break in it.

    `overlap_index` splits source text on form feeds to number pages, so
    putting every planted run on page two is what lets these tests assert
    a literal `pdf p.2` instead of settling for "some plausible page".
    """
    return f"{page_one}\n\f{page_two}\n"


def _add_scan_paper(citekey, text, pdf_bytes=b"%PDF-1.4 fixture"):
    """One parsed ledger row, left the way `sync` leaves one.

    Both calls matter. `upsert_reference` hashes the PDF bytes for real,
    and that hash is half of the key the corpus index caches per
    document; `mark_parsed` is what moves the row to `status='parsed'`,
    which is the only status `overlap_index._ledger_items()` selects.
    """
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
    r"pdf p\.(?P<page>\d+)\] (?P<citekey>\S+) \(tier=(?P<tier>\w+)\)(?P<flags>.*)"
)


def _findings(stdout):
    """`scan`'s three-lines-per-finding output, parsed back into dicts.

    Asserting through the printed form rather than around it is
    deliberate: the printed line *is* the product here, and a change that
    dropped the page number or the UNCITED SOURCE flag would leave every
    in-process assertion on the findings list passing.
    """
    lines = stdout.splitlines()
    parsed = []
    for i, line in enumerate(lines):
        match = _FINDING_RE.fullmatch(line)
        if match:
            parsed.append({
                "span": int(match["span"]),
                "page": int(match["page"]),
                "citekey": match["citekey"],
                "tier": match["tier"],
                "flags": match["flags"].strip(),
                "fragment": lines[i + 1].strip(),
            })
    return parsed


def _run_scan(draft, *args):
    """`scan`, in a child process, against this test's throwaway corpus.

    The coverage variables are stripped rather than inherited. Under the
    pinned pytest-cov 6.x a .pth file auto-instruments every spawned
    child, and a child that inherits the parent's coverage settings
    without the config those settings assume can fail at the *combine*
    step -- long after every test has passed, with a message
    (`Can't combine statement coverage data with branch data`) that names
    nothing connected to the test that caused it. That happened for real
    on PR #114. `src/review/verbatim_check.py` is covered in process by
    tests/test_verbatim_check.py, so nothing is lost by not measuring
    these children.
    """
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith("COV_CORE_")
        and key not in {"COVERAGE_PROCESS_START", "COVERAGE_FILE", "COVERAGE_RCFILE"}
    }
    env["CONTENT_DIR"] = str(config.CONTENT_DIR)
    return subprocess.run(
        [sys.executable, "-m", "src.review", "verbatim", "scan", str(draft), *args],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True, text=True, env=env,
    )


class TestVerbatimScanEndToEnd:
    """`python3 -m src.review verbatim scan <draft>` over a real
    mini-ledger: index build -> disk cache -> findings, through the entry
    point README's step 7 and the seven skills now point at.

    No `skipif`. The whole scan path is stdlib-only and never opens the
    PDF -- only its bytes' hash reaches the index -- so unlike the
    render-chain tests above there is no binary to be missing, and
    `TestReGroundingAfterTheCorpusMoves`'s reasoning applies: run
    everywhere rather than skip wherever pandoc is absent.
    """

    @pytest.fixture
    def corpus(self, isolated_config):
        """Three parsed sources, each with its planted run on page 2."""
        _add_scan_paper("dt_arch_2024", _scan_source_text(
            "This opening page reviews how twins are checked before release. "
            + SCAN_PARAPHRASE_IN_SOURCE + ".",
            SCAN_RUN_CITED + ". A later remark on module boundaries follows it.",
        ))
        _add_scan_paper("cloud_infra_2023", _scan_source_text(
            "An opening page about billing models for rented hardware.",
            SCAN_RUN_UNCITED + ". Costs are then compared across three vendors.",
        ))
        _add_scan_paper("calib_2025", _scan_source_text(
            "An opening page about sensor drift in long-lived deployments.",
            SCAN_RUN_CONNECTIVE + ". Two thresholds are then derived empirically.",
        ))
        return isolated_config

    @pytest.fixture
    def planted_draft(self, corpus):
        """A draft carrying all four planted cases at once.

        Written as one plausible document rather than four minimal ones,
        because three of the four only exist relative to their
        surroundings: whether a run's paragraph cites the source it
        borrowed from is the thing under test.
        """
        draft = content_draft(corpus, "drafts/scan-e2e.md")
        draft.write_text(
            "# Architecture of digital twins\n\n"
            "## 1. Structure\n\n"
            # (a) verbatim, in a paragraph that does cite this source.
            f"Recent work sets out the shape of these systems: {SCAN_RUN_CITED} "
            "[@dt_arch_2024].\n\n"
            "## 2. Deployment\n\n"
            # (b) verbatim from a source this paragraph never cites --
            # it cites a different one, which is what makes the borrowed
            # wording invisible to a per-citekey `overlap` run.
            "Most twins are deployed on rented infrastructure [@dt_arch_2024]. "
            f"{SCAN_RUN_UNCITED}.\n\n"
            "## 3. Keeping a twin honest\n\n"
            # (c) verbatim, in connective prose that cites nothing at all,
            # so no `overlap` invocation would ever examine it.
            f"{SCAN_RUN_CONNECTIVE}. That question is taken up below.\n\n"
            "## 4. Validation\n\n"
            # (d) the negative control.
            f"{SCAN_PARAPHRASE_IN_DRAFT}, which is by now a familiar demand.\n",
            encoding="utf-8",
        )
        return draft

    def test_planted_runs_from_cited_uncited_and_connective_prose_all_report(
        self, planted_draft
    ):
        """The three cases the scan exists for, through the real CLI.

        The `UNCITED SOURCE` flag is the discriminator a reviewer acts
        on, so each case is asserted on the flag and not merely on having
        produced some finding.
        """
        result = _run_scan(planted_draft)

        assert result.returncode == 0, result.stderr
        findings = {f["citekey"]: f for f in _findings(result.stdout)}
        assert set(findings) == {"dt_arch_2024", "cloud_infra_2023", "calib_2025"}

        # (a) The paragraph cites the source it borrowed from: reported,
        # with the page it came from, and deliberately not flagged.
        cited = findings["dt_arch_2024"]
        assert cited["fragment"] == SCAN_RUN_CITED
        assert cited["page"] == 2, "the run was planted on the source's second page"
        assert cited["tier"] == "exact"
        assert "UNCITED SOURCE" not in cited["flags"]

        # (b) Borrowed from a source the paragraph never names.
        uncited = findings["cloud_infra_2023"]
        assert uncited["fragment"] == SCAN_RUN_UNCITED
        assert uncited["page"] == 2
        assert "UNCITED SOURCE" in uncited["flags"]

        # (c) Borrowed into prose that cites nothing whatsoever.
        connective = findings["calib_2025"]
        assert connective["fragment"] == SCAN_RUN_CONNECTIVE
        assert connective["page"] == 2
        assert "UNCITED SOURCE" in connective["flags"]

    def test_lightly_paraphrased_run_is_not_reported_by_the_exact_tier(
        self, planted_draft
    ):
        """A deliberate negative control, not a coverage gap.

        `SCAN_PARAPHRASE_IN_DRAFT` is `SCAN_PARAPHRASE_IN_SOURCE` with a
        synonym swapped at every fourth word -- the signature of an LLM
        paraphrasing a passage it has drifted too close to. The spacing
        is the whole construction: swapping every fourth word leaves no
        unbroken run longer than three words, so no 8-gram survives and
        the exact tier cannot fire. Swap every tenth word instead and an
        8-gram does survive, this test fails, and it fails for a reason
        that has nothing to do with the behaviour being pinned.

        This is not a duplicate of
        `test_clean_paraphrase_does_not_flag` in
        tests/test_verbatim_check.py: that fixture is a clean rewrite,
        which nobody expects an n-gram index to catch. This one is
        near-verbatim and still missed, which is the documented boundary
        of the exact tier and the reason README, docs/CLI.md and all
        seven skills say a clean scan is not a clean bill of health.

        When the deterministic skip-gram tier lands (discussion #115),
        this is the fixture that must flip from missed to caught. Invert
        the assertion then -- don't delete it.
        """
        result = _run_scan(planted_draft)

        assert result.returncode == 0, result.stderr
        assert not [
            f for f in _findings(result.stdout)
            if f["citekey"] == "dt_arch_2024" and f["page"] == 1
        ], "the exact tier reported the paraphrased passage on the source's first page"
        assert "validation" not in result.stdout

    def test_clean_draft_reports_nothing_and_still_exits_zero(self, corpus):
        """A review aid, so "found nothing" is a successful run."""
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

    def test_first_scan_builds_the_index_on_disk(self, planted_draft):
        """The command builds the real index, not a stand-in for one.

        Asserting the artifacts exist is what makes the rest of this
        class a test of the cached index path rather than of whatever a
        mock would have returned.
        """
        assert not config.OVERLAP_DIR.exists(), "the fixture starts with no cache"

        assert _run_scan(planted_draft).returncode == 0

        assert (config.OVERLAP_DIR / "index.bin").is_file()
        assert (config.OVERLAP_DIR / "index.json").is_file()
        for citekey in ("dt_arch_2024", "cloud_infra_2023", "calib_2025"):
            assert (config.OVERLAP_DIR / "docs" / f"{citekey}.fpr").is_file()

    def test_rescanning_an_unchanged_corpus_reuses_the_merged_index(
        self, planted_draft
    ):
        """The "re-scans are near-instant" contract docs/CLI.md states.

        `index.bin` is the artifact to watch, and the `.fpr` files are
        not: on a cache hit `build_corpus_index` returns from
        `_load_corpus_index` before it ever reaches `fingerprint_document`,
        so "the .fpr files were not rewritten" would be trivially true and
        would pass even if the merged index were rebuilt from scratch
        every run.
        """
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
        """The user-visible command never serves a stale index.

        What this proves is the workflow-level half: `scan` re-fingerprints
        and re-merges when the corpus moves under it. It does *not*
        isolate `pdf_hash` from the `(size, mtime_ns)` half of
        `_fingerprint_key` -- rewriting a source's text moves both at once,
        which is exactly what a real re-sync does.
        tests/test_overlap_index.py pins each half separately.
        """
        draft = content_draft(corpus, "drafts/scan-resync.md")
        draft.write_text(
            f"One claim [@dt_arch_2024]. {SCAN_RUN_CITED}.\n\n"
            f"Another claim [@dt_arch_2024]. {SCAN_RUN_AFTER_RESYNC}.\n",
            encoding="utf-8",
        )
        before = _run_scan(draft)
        assert [f["fragment"] for f in _findings(before.stdout)] == [SCAN_RUN_CITED]
        key_before = json.loads((config.OVERLAP_DIR / "index.json").read_text())["key"]

        # What `sync` does to a paper whose PDF was replaced: new bytes,
        # so a new pdf_hash, and new parsed text alongside it.
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
        assert [f["fragment"] for f in _findings(after.stdout)] == [
            SCAN_RUN_AFTER_RESYNC
        ], "the scan served fingerprints of text the corpus no longer holds"
        assert (
            json.loads((config.OVERLAP_DIR / "index.json").read_text())["key"]
            != key_before
        )

    def test_scan_runs_on_the_bare_system_interpreter(
        self, planted_draft, system_python
    ):
        """docs/CLI.md files `scan` in interpreter tier 1 -- bare
        `python3`, stdlib only, no venv. Everything above runs it on
        `sys.executable`, which is the venv's interpreter and so cannot
        tell that claim from a false one. This is the same check
        `citation_gate`/`references`/`render_output` already get, applied
        to the command this change is adding to that list.
        """
        env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("COV_CORE_")
            and key not in {"COVERAGE_PROCESS_START", "COVERAGE_FILE", "COVERAGE_RCFILE"}
        }
        env["CONTENT_DIR"] = str(config.CONTENT_DIR)

        result = subprocess.run(
            [system_python, "-m", "src.review", "verbatim", "scan", str(planted_draft)],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True, text=True, env=env,
        )

        assert result.returncode == 0, result.stderr
        assert {f["citekey"] for f in _findings(result.stdout)} == {
            "dt_arch_2024", "cloud_infra_2023", "calib_2025"
        }


class TestOneDraftsReviewArtefactsLandTogether:
    """The property #121 exists to provide: a draft, and the evidence
    behind it, findable from the draft's own path.

    Every other test in the review layer checks one command. This checks
    the thing none of them can -- that all three, run independently and
    knowing nothing about each other, converge on one directory. Getting
    that wrong is not a crash; it is three reports scattered across two
    directories with nothing complaining, which is exactly what the layer
    was introduced to stop.

    No `skipif`: the `.md` half of every report is stdlib-only, and the
    formats are pinned to `md` so a host without pandoc runs the same
    assertions as one with it.
    """

    def _draft(self, isolated_config):
        _add_scan_paper("dt_arch_2024", _scan_source_text(
            "Front matter and abstract.",
            "A digital twin architecture couples a physical asset to its model.",
        ))
        draft = content_draft(isolated_config, "drafts/dt/survey.md")
        draft.write_text(
            "# Survey\n\n"
            "A digital twin architecture couples a physical asset to its "
            "model [@dt_arch_2024].\n"
        )
        return draft

    def test_all_three_reports_share_one_mirrored_directory(self, isolated_config, capsys):
        from src.review import verbatim_check as vc
        from src.review import citation_coverage, citation_provenance

        draft = self._draft(isolated_config)

        citation_provenance.write_report(draft, ["md"])
        vc.cmd_scan(str(draft), write=True, formats=["md"])
        citation_coverage.main([str(draft), "--query", "digital twin", "--write",
                                "--formats", "md"])

        review_dir = config.REVIEW_DIR / "dt"
        assert sorted(p.name for p in review_dir.iterdir()) == [
            "survey.coverage.md", "survey.provenance.md", "survey.verbatim.md"
        ]

    def test_nothing_lands_in_the_drafting_layers_output(self, isolated_config, capsys):
        """A review artefact in `content/rendered/` is the layer smear
        this issue removed -- 3.19.2 rendered a report's `.tex`/`.pdf`
        there, because `render()` had no way to be told otherwise."""
        from src.review import citation_provenance

        draft = self._draft(isolated_config)
        citation_provenance.write_report(draft, ["md"])

        assert not list(config.RENDERED_DIR.rglob("*provenance*")), (
            "a review artefact reached content/rendered/"
        )

    def test_every_report_says_it_is_not_a_verdict(self, isolated_config, capsys):
        """The banner has to be in the file, not only in the docs: a
        report found on disk months later is the case the docs can't
        reach."""
        from src.review import verbatim_check as vc
        from src.review import citation_coverage, citation_provenance

        draft = self._draft(isolated_config)
        citation_provenance.write_report(draft, ["md"])
        vc.cmd_scan(str(draft), write=True, formats=["md"])
        citation_coverage.main([str(draft), "--query", "digital twin", "--write",
                                "--formats", "md"])

        for report in (config.REVIEW_DIR / "dt").iterdir():
            assert "Review aid, not a gate" in report.read_text(), report.name

    def test_the_bundle_carries_them_and_restores_them(self, isolated_config, tmp_path, capsys):
        """`dossier export` is the tool the findability property is *for*
        -- #114's own rationale for confining everything to `content/`."""
        from src.review import verbatim_check as vc
        from src.review import citation_provenance

        draft = self._draft(isolated_config)
        dossier.init(draft, "survey")
        citation_provenance.write_report(draft, ["md"])
        vc.cmd_scan(str(draft), write=True, formats=["md"])

        out, _ = dossier.export([], tmp_path / "bundle.tar.gz")
        shutil.rmtree(config.REVIEW_DIR)

        plan = dossier.restore(out, force=True)

        assert plan.performed
        assert sorted(p.name for p in (config.REVIEW_DIR / "dt").iterdir()) == [
            "survey.provenance.md", "survey.verbatim.md"
        ]
