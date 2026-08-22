"""chitragupta/evidence_appendix.py: the evidence sidecar rendered beside a
draft -- attributed, quoted spans drawn only from a dossier's `quote:`
fields, never from a legacy `support:` window.

See plans/a4-evidence-appendix.md. The tests that must never be relaxed
are the ones asserting a `support:`-only block contributes nothing (a
legacy `support:` holds a raw 600-character retrieval window) and that a
sidecar contributes zero citations to the gate.
"""

from pathlib import Path

import pytest

from chitragupta import citation_gate, evidence_appendix, ledger, references
from chitragupta.dossier import dossier_dir

from tests.conftest import content_draft, make_reference


def seed(con, *citekeys):
    """One ledger row per citekey, enough for an IEEE attribution line.

    Titles are letters only: `references._md_escape` neutralises Markdown
    emphasis, so a title echoing a citekey would come back as
    `Paper doe\\_a\\_2024` and make an assertion about the attribution
    line read like a bug in the escaping rather than a fixture choice.
    """
    for index, key in enumerate(citekeys):
        ledger.upsert_reference(con, make_reference(
            citekey=key, title=f"Paper {chr(ord('A') + index)}", year="2024",
            fields={"author": "Doe, Jane", "journal": "J. Things"},
        ))


def write_dossier(draft: Path, evidence: str, sections: str | None = None) -> Path:
    """`evidence.md` (and optionally `sections.md`) for `draft`'s dossier."""
    target = dossier_dir(draft)
    target.mkdir(parents=True, exist_ok=True)
    (target / "evidence.md").write_text(evidence, encoding="utf-8")
    if sections is not None:
        (target / "sections.md").write_text(sections, encoding="utf-8")
    return target


class TestBuild:
    def test_a_quote_reaches_the_sidecar_quoted_and_attributed(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, (
            "## `doe_a_2024`\n\n"
            "relevance: bears on the sub-theme\n"
            "claim: the source establishes a thing\n"
            "quote: models drift apart without synchronisation\n"
        ))

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert '> "models drift apart without synchronisation"' in out
        # Attributed: the IEEE entry references.format_entry builds, and
        # the citekey in a code span so it can never read as a citation.
        assert 'J. Doe, "Paper A," *J. Things*, 2024.' in out
        assert "`doe_a_2024`" in out

    def test_a_block_with_no_quote_produces_no_stanza(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, (
            "## `doe_a_2024`\n\n"
            "relevance: bears on the sub-theme\n"
            "claim: the source establishes a thing\n"
        ))

        assert evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con) is None

    def test_a_legacy_support_only_block_contributes_nothing(self, isolated_config, ledger_con):
        # THE copyright guard, and the test that must never be relaxed. A
        # skill reads a legacy `support:` as `quote:` (the conservative
        # reading for deciding whether it MAY quote). A builder that will
        # PRINT the field must not: `support:` holds a raw 600-character
        # retrieval window, and printing one as an attributed quotation
        # publishes source wording this project exists to keep out.
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, (
            "## `doe_a_2024`\n\n"
            "relevance: bears on the sub-theme\n"
            "support: a six-hundred-character raw window of the source\n"
        ))

        assert evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con) is None

    def test_claim_is_never_printed(self, isolated_config, ledger_con):
        # `claim:` is the drafter's own words. Quoting it back would
        # attribute this project's prose to the source.
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, (
            "## `doe_a_2024`\n\n"
            "claim: a restatement in the drafter's own words\n"
            "quote: the verbatim span\n"
        ))

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert "the verbatim span" in out
        assert "restatement in the drafter" not in out

    def test_a_citekey_the_draft_does_not_cite_is_dropped(self, isolated_config, ledger_con):
        # references.py's rule, inherited: the sidecar can never introduce
        # a citekey that has not already passed the gate on the draft.
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, (
            "## `doe_a_2024`\n\nquote: the cited span\n\n"
            "## `roe_b_2024`\n\nquote: the uncited span\n"
        ))

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert "the cited span" in out
        assert "the uncited span" not in out
        assert "roe_b_2024" not in out

    def test_no_dossier_at_all_returns_none(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")

        assert evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con) is None

    def test_a_draft_citing_nothing_returns_none(self, isolated_config, ledger_con):
        draft = content_draft(isolated_config, "drafts/topic/tutorial.md")
        draft.write_text("A lesson with no citations.\n")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: an orphan span\n")

        assert evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con) is None


class TestGrouping:
    def test_stanzas_are_grouped_under_their_section_in_row_order(
            self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("First [@roe_b_2024]. Then [@doe_a_2024].\n")
        write_dossier(
            draft,
            "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nquote: span B\n",
            # Row order is the order the run itself chose, not the
            # draft's citation order -- so Synchronisation comes first
            # here even though roe_b_2024 is cited first.
            "| Section | Citekeys |\n|---|---|\n"
            "| Synchronisation | `doe_a_2024` |\n"
            "| Fidelity | `roe_b_2024` |\n",
        )

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert "## Synchronisation" in out
        assert "## Fidelity" in out
        assert out.index("## Synchronisation") < out.index("## Fidelity")
        assert out.index("span A") < out.index("span B")

    def test_a_section_whose_citekeys_all_lack_a_quote_is_omitted(
            self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("One [@doe_a_2024]. Two [@roe_b_2024].\n")
        write_dossier(
            draft,
            "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nclaim: no quote here\n",
            "| Section | Citekeys |\n|---|---|\n"
            "| Synchronisation | `doe_a_2024` |\n"
            "| Fidelity | `roe_b_2024` |\n",
        )

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert "## Synchronisation" in out
        assert "Fidelity" not in out, "an empty section must not leave its heading behind"

    def test_a_cited_key_filed_under_no_section_lands_under_unassigned(
            self, isolated_config, ledger_con):
        # Mirrors `dossier sections --citekeys`, which reports an unfiled
        # key rather than putting it under a section that does not
        # contain it.
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("One [@doe_a_2024]. Two [@roe_b_2024].\n")
        write_dossier(
            draft,
            "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nquote: span B\n",
            "| Section | Citekeys |\n|---|---|\n| Synchronisation | `doe_a_2024` |\n",
        )

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert "## Unassigned" in out
        assert out.index("## Synchronisation") < out.index("## Unassigned")
        assert out.index("span B") > out.index("## Unassigned")

    def test_without_sections_md_everything_lands_under_unassigned(
            self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: span A\n")

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert "## Unassigned" in out
        assert "span A" in out


class TestContributesNoCitations:
    def test_the_gate_sees_zero_citations_in_a_sidecar(
            self, isolated_config, ledger_con, tmp_path):
        # The issue's acceptance criterion, met as a shape rather than a
        # check: citekeys appear only in code spans, which
        # citation_gate._blank_code blanks before extraction.
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)
        sidecar = tmp_path / "survey.evidence.md"
        sidecar.write_text(out, encoding="utf-8")

        result = citation_gate.check_document(sidecar, {"doe_a_2024"})
        assert result.total_citations == 0
        assert result.unknown == []

    def test_the_drafts_own_numbering_is_unperturbed(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("First [@roe_b_2024]. Then [@doe_a_2024].\n")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")

        before = references.used_citekeys(draft.read_text())
        evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert references.used_citekeys(draft.read_text()) == before == \
            ["roe_b_2024", "doe_a_2024"]


class TestQuoteFormatting:
    def test_a_multi_line_quote_becomes_one_blockquote(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, (
            "## `doe_a_2024`\n\nquote: the first line\nand the second line\n"
        ))

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert "> \"the first line" in out
        assert "> and the second line\"" in out

    def test_a_quote_already_in_quotation_marks_is_not_double_quoted(
            self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n")
        write_dossier(draft, '## `doe_a_2024`\n\nquote: "already quoted"\n')

        out = evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)

        assert '> "already quoted"' in out
        assert '""' not in out

    def test_a_citekey_missing_from_the_ledger_is_a_hard_error(
            self, isolated_config, ledger_con):
        # AGENTS.md's citekey invariant: a cited key with no ledger row is
        # never silently dropped. Same contract as references.build_section.
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@ghost_x_2024].\n")
        write_dossier(draft, "## `ghost_x_2024`\n\nquote: the span\n")

        with pytest.raises(KeyError, match="ghost_x_2024"):
            evidence_appendix.build(draft.read_text(), dossier_dir(draft), ledger_con)
