import subprocess
from pathlib import Path

import pytest

from chitragupta import citation_gate, evidence_appendix, ledger, references
from chitragupta.dossier import dossier_dir

from tests.conftest import content_draft, make_reference, pandoc_available


def seed(con, *citekeys):
    for index, key in enumerate(citekeys):
        ledger.upsert_reference(
            con,
            make_reference(
                citekey=key,
                title=f"Paper {chr(ord('A') + index)}",
                year="2024",
                fields={"author": "Doe, Jane", "journal": "J. Things"},
            ),
        )


def write_dossier(draft: Path, evidence: str, sections: str | None = None) -> Path:
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
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            (
                "## `doe_a_2024`\n\n"
                "relevance: bears on the sub-theme\n"
                "claim: the source establishes a thing\n"
                "quote: models drift apart without synchronisation\n"
            ),
        )

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert '> "models drift apart without synchronisation"' in out
        assert 'J. Doe, "Paper A," *J. Things*, 2024.' in out
        assert "`doe_a_2024`" in out

    def test_a_block_with_no_quote_produces_no_stanza(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            (
                "## `doe_a_2024`\n\n"
                "relevance: bears on the sub-theme\n"
                "claim: the source establishes a thing\n"
            ),
        )

        assert (
            evidence_appendix.build(
                draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
            )
            is None
        )

    def test_a_legacy_support_only_block_contributes_nothing(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            (
                "## `doe_a_2024`\n\n"
                "relevance: bears on the sub-theme\n"
                "support: a six-hundred-character raw window of the source\n"
            ),
        )

        assert (
            evidence_appendix.build(
                draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
            )
            is None
        )

    def test_claim_is_never_printed(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            (
                "## `doe_a_2024`\n\n"
                "claim: a restatement in the drafter's own words\n"
                "quote: the verbatim span\n"
            ),
        )

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert "the verbatim span" in out
        assert "restatement in the drafter" not in out

    def test_a_citekey_the_draft_does_not_cite_is_dropped(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            (
                "## `doe_a_2024`\n\nquote: the cited span\n\n"
                "## `roe_b_2024`\n\nquote: the uncited span\n"
            ),
        )

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert "the cited span" in out
        assert "the uncited span" not in out
        assert "roe_b_2024" not in out

    def test_no_dossier_at_all_returns_none(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")

        assert (
            evidence_appendix.build(
                draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
            )
            is None
        )

    def test_a_draft_citing_nothing_returns_none(self, isolated_config, ledger_con):
        draft = content_draft(isolated_config, "drafts/topic/tutorial.md")
        draft.write_text("A lesson with no citations.\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: an orphan span\n")

        assert (
            evidence_appendix.build(
                draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
            )
            is None
        )


class TestGrouping:
    def test_stanzas_are_grouped_under_their_section_in_row_order(
        self, isolated_config, ledger_con
    ):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("First [@roe_b_2024]. Then [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nquote: span B\n",
            "| Section | Citekeys |\n|---|---|\n"
            "| Synchronisation | `doe_a_2024` |\n"
            "| Fidelity | `roe_b_2024` |\n",
        )

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert "## Synchronisation" in out
        assert "## Fidelity" in out
        assert out.index("## Synchronisation") < out.index("## Fidelity")
        assert out.index("span A") < out.index("span B")

    def test_a_section_whose_citekeys_all_lack_a_quote_is_omitted(
        self, isolated_config, ledger_con
    ):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("One [@doe_a_2024]. Two [@roe_b_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nclaim: no quote here\n",
            "| Section | Citekeys |\n|---|---|\n"
            "| Synchronisation | `doe_a_2024` |\n"
            "| Fidelity | `roe_b_2024` |\n",
        )

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert "## Synchronisation" in out
        assert "Fidelity" not in out, "an empty section must not leave its heading behind"

    def test_a_cited_key_filed_under_no_section_lands_under_unassigned(
        self, isolated_config, ledger_con
    ):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("One [@doe_a_2024]. Two [@roe_b_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nquote: span B\n",
            "| Section | Citekeys |\n|---|---|\n| Synchronisation | `doe_a_2024` |\n",
        )

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert "## Unassigned" in out
        assert out.index("## Synchronisation") < out.index("## Unassigned")
        assert out.index("span B") > out.index("## Unassigned")

    def test_without_sections_md_everything_lands_under_unassigned(
        self, isolated_config, ledger_con
    ):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: span A\n")

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert "## Unassigned" in out
        assert "span A" in out


class TestContributesNoCitations:
    def test_the_gate_sees_zero_citations_in_a_sidecar(self, isolated_config, ledger_con, tmp_path):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )
        sidecar = tmp_path / "survey.evidence.md"
        sidecar.write_text(out, encoding="utf-8")

        result = citation_gate.check_document(sidecar, {"doe_a_2024"})
        assert result.total_citations == 0
        assert result.unknown == []

    def test_the_drafts_own_numbering_is_unperturbed(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024", "roe_b_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("First [@roe_b_2024]. Then [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")

        before = references.used_citekeys(draft.read_text(encoding="utf-8"))
        evidence_appendix.build(draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con)

        assert (
            references.used_citekeys(draft.read_text(encoding="utf-8"))
            == before
            == ["roe_b_2024", "doe_a_2024"]
        )


class TestQuoteFormatting:
    def test_a_multi_line_quote_becomes_one_blockquote(self, isolated_config, ledger_con):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, ("## `doe_a_2024`\n\nquote: the first line\nand the second line\n"))

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert '> "the first line' in out
        assert '> and the second line"' in out

    def test_a_quote_already_in_quotation_marks_is_not_double_quoted(
        self, isolated_config, ledger_con
    ):
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, '## `doe_a_2024`\n\nquote: "already quoted"\n')

        out = evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

        assert '> "already quoted"' in out
        assert '""' not in out

    def _built(self, isolated_config, ledger_con, evidence: str) -> str:
        seed(ledger_con, "doe_a_2024")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, evidence)
        return evidence_appendix.build(
            draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
        )

    def test_every_quote_in_a_block_is_printed_under_one_heading(self, isolated_config, ledger_con):
        out = self._built(
            isolated_config,
            ledger_con,
            "## `doe_a_2024`\n\nclaim: c\nquote: the first span\nquote: the second span\n",
        )
        assert out.count("`doe_a_2024`") == 1
        assert out.index('> "the first span"') < out.index('> "the second span"')

    def test_a_page_locator_is_not_printed(self, isolated_config, ledger_con):
        out = self._built(
            isolated_config, ledger_con, '## `doe_a_2024`\n\nquote: "the span" (p. 24)\n'
        )
        assert '> "the span"' in out
        assert "p. 24" not in out

    def test_a_quote_opening_and_closing_on_quoted_words_keeps_its_marks(
        self, isolated_config, ledger_con
    ):
        out = self._built(
            isolated_config,
            ledger_con,
            '## `doe_a_2024`\n\nquote: "Twin" is used loosely, as is "shadow"\n',
        )
        assert '> ""Twin" is used loosely, as is "shadow""' in out

    def test_a_block_with_only_empty_quotes_gives_no_sidecar(self, isolated_config, ledger_con):
        out = self._built(isolated_config, ledger_con, '## `doe_a_2024`\n\nquote: ""\n')
        assert out is None

    def test_a_citekey_missing_from_the_ledger_is_a_hard_error(self, isolated_config, ledger_con):
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@ghost_x_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `ghost_x_2024`\n\nquote: the span\n")

        with pytest.raises(KeyError, match="ghost_x_2024"):
            evidence_appendix.build(
                draft.read_text(encoding="utf-8"), dossier_dir(draft), ledger_con
            )


class TestSidecarPath:
    def test_the_suffix_sits_between_the_stem_and_the_format(self, tmp_path):
        draft = tmp_path / "survey.md"
        assert (
            evidence_appendix.sidecar_path(draft, tmp_path, "pdf")
            == tmp_path / "survey.evidence.pdf"
        )

    def test_it_defaults_to_markdown(self, tmp_path):
        assert (
            evidence_appendix.sidecar_path(tmp_path / "survey.md", tmp_path)
            == tmp_path / "survey.evidence.md"
        )


class TestWrite:
    def test_it_writes_the_sidecar_and_leaves_the_draft_alone(self, isolated_config, tmp_path):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        original = "Body [@doe_a_2024].\n"
        draft.write_text(original, encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")
        out_dir = isolated_config.CONTENT_DIR / "rendered" / "topic"

        out_path = evidence_appendix.write(draft, out_dir)

        assert out_path == out_dir / "survey.evidence.md"
        assert '> "the span"' in out_path.read_text(encoding="utf-8")
        assert draft.read_text(encoding="utf-8") == original, (
            "the gated source must not be rewritten"
        )

    def test_a_private_use_character_in_a_quote_is_written_as_a_marker(
        self, isolated_config, capsys
    ):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the \uf02d span\n")

        out_path = evidence_appendix.write(draft, isolated_config.CONTENT_DIR / "rendered")

        assert '> "the [U+F02D] span"' in out_path.read_text(encoding="utf-8")
        assert "shown as [U+F02D]" in capsys.readouterr().err

    def test_nothing_to_show_writes_no_file(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/tutorial.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nclaim: no quote was captured\n")
        out_dir = isolated_config.CONTENT_DIR / "rendered" / "topic"

        assert evidence_appendix.write(draft, out_dir) is None
        assert not out_dir.exists(), "an empty sidecar must not even make its directory"

    def test_a_commented_out_tex_citation_gets_no_stanza(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024", "roe_b_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/thesis.tex")
        draft.write_text(
            "Body \\citep{doe_a_2024}.\n% Cut: \\citep{roe_b_2024}\n", encoding="utf-8"
        )
        write_dossier(
            draft, "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nquote: span B\n"
        )
        out_dir = isolated_config.CONTENT_DIR / "rendered" / "topic"

        sidecar = evidence_appendix.write(draft, out_dir).read_text(encoding="utf-8")

        assert "span A" in sidecar
        assert "span B" not in sidecar

    def test_a_text_override_is_used_instead_of_the_file_on_disk(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024", "roe_b_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@roe_b_2024].\n", encoding="utf-8")
        write_dossier(
            draft, "## `doe_a_2024`\n\nquote: span A\n\n## `roe_b_2024`\n\nquote: span B\n"
        )
        out_dir = isolated_config.CONTENT_DIR / "rendered" / "topic"

        out_path = evidence_appendix.write(draft, out_dir, draft_text="Body [@doe_a_2024].\n")

        assert "span A" in out_path.read_text(encoding="utf-8")
        assert "span B" not in out_path.read_text(encoding="utf-8")


class TestEmit:
    def test_markdown_lands_in_the_mirrored_rendered_directory(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")

        out_path = evidence_appendix.emit(draft)

        assert out_path == isolated_config.RENDERED_DIR / "topic" / "survey.evidence.md"
        assert out_path.is_file()

    def test_an_output_dir_overrides_the_mirror(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")
        elsewhere = isolated_config.CONTENT_DIR / "somewhere"

        assert evidence_appendix.emit(draft, out_dir=elsewhere) == elsewhere / "survey.evidence.md"

    def test_nothing_to_show_returns_none_in_any_format(self, isolated_config):
        draft = content_draft(isolated_config, "drafts/topic/tutorial.md")
        draft.write_text("A lesson with no citations.\n", encoding="utf-8")

        assert evidence_appendix.emit(draft, "pdf") is None

    def test_a_draft_outside_the_content_directory_is_refused(self, isolated_config, tmp_path):
        outside = tmp_path / "elsewhere" / "survey.md"
        outside.parent.mkdir(parents=True)
        outside.write_text("Body [@doe_a_2024].\n", encoding="utf-8")

        with pytest.raises(evidence_appendix.config.OutsideContentDir):
            evidence_appendix.emit(outside)

    def test_an_output_dir_outside_the_content_directory_is_refused(
        self, isolated_config, tmp_path
    ):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")
        elsewhere = tmp_path / "outside-content"

        with pytest.raises(evidence_appendix.config.OutsideContentDir):
            evidence_appendix.emit(draft, out_dir=elsewhere)
        assert not elsewhere.exists()  # refused before anything was written


class TestMain:
    def test_it_prints_the_written_path_and_returns_0(self, isolated_config, capsys):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")

        assert evidence_appendix.main([str(draft)]) == 0
        assert "survey.evidence.md" in capsys.readouterr().out

    def test_nothing_to_show_says_so_and_still_returns_0(self, isolated_config, capsys):
        draft = content_draft(isolated_config, "drafts/topic/tutorial.md")
        draft.write_text("A lesson with no citations.\n", encoding="utf-8")

        assert evidence_appendix.main([str(draft)]) == 0
        assert "no quoted evidence recorded" in capsys.readouterr().out

    def test_a_citekey_missing_from_the_ledger_prints_an_error_and_returns_1(
        self, isolated_config, ledger_con, capsys
    ):
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@ghost_x_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `ghost_x_2024`\n\nquote: the span\n")

        assert evidence_appendix.main([str(draft)]) == 1
        assert "ghost_x_2024" in capsys.readouterr().err

    def test_a_draft_outside_the_content_directory_prints_an_error_and_returns_1(
        self, isolated_config, tmp_path, capsys
    ):
        outside = tmp_path / "elsewhere" / "survey.md"
        outside.parent.mkdir(parents=True)
        outside.write_text("Body [@doe_a_2024].\n", encoding="utf-8")

        assert evidence_appendix.main([str(outside)]) == 1
        assert "[error]" in capsys.readouterr().err

    def test_a_comma_list_format_is_a_usage_error(self, isolated_config, tmp_path, capsys):
        draft = tmp_path / "survey.md"
        draft.write_text("Body.\n", encoding="utf-8")

        with pytest.raises(SystemExit) as exc:
            evidence_appendix.main([str(draft), "--format", "md,tex,pdf"])
        assert exc.value.code == 2
        assert "md,tex,pdf" in capsys.readouterr().err


class TestTheSidecarIsNeverCommitted:
    @pytest.mark.parametrize("output_format", ["md", "tex", "pdf"])
    def test_git_ignores_the_path_the_module_actually_chooses(self, output_format):
        repo = Path(__file__).resolve().parent.parent
        rendered = repo / "content" / "rendered" / "digital-twins-for-software-engineers"
        candidate = evidence_appendix.sidecar_path(rendered / "survey.md", rendered, output_format)

        result = subprocess.run(
            ["git", "check-ignore", "-q", str(candidate)],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"{candidate.relative_to(repo)} is NOT ignored by git. An evidence "
            "sidecar holds verbatim quoted spans from copyrighted sources; "
            "publishing one is the failure chitragupta/evidence_appendix.py "
            "exists to prevent. Fix .gitignore's content/rendered/**/*.evidence.* "
            "rule to match evidence_appendix.SUFFIX."
        )

    def test_the_ordinary_render_beside_it_is_still_tracked(self):
        repo = Path(__file__).resolve().parent.parent
        ordinary = (
            repo / "content" / "rendered" / "digital-twins-for-software-engineers" / "survey.pdf"
        )

        result = subprocess.run(
            ["git", "check-ignore", "-q", str(ordinary)],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 1, "the shipped example renders must stay tracked"


@pytest.mark.skipif(not pandoc_available, reason="pandoc not installed")
class TestNonMarkdownFormats:
    def test_a_tex_sidecar_is_a_standalone_document(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text("", encoding="utf-8")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the quoted span\n")

        out_path = evidence_appendix.emit(draft, "tex")

        assert out_path == isolated_config.RENDERED_DIR / "topic" / "survey.evidence.tex"
        body = out_path.read_text(encoding="utf-8")
        assert "\\documentclass" in body, "a sidecar must stand on its own"
        assert "the quoted span" in body

    def test_a_thesis_tex_fragment_gets_a_sidecar_from_its_citep_markers(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text("", encoding="utf-8")
        draft = content_draft(isolated_config, "drafts/topic/chapter.tex")
        draft.write_text("Body \\citep{doe_a_2024}.\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the quoted span\n")

        out_path = evidence_appendix.emit(draft, "tex")

        assert out_path.name == "chapter.evidence.tex"
        assert "the quoted span" in out_path.read_text(encoding="utf-8")

    def test_the_sidecar_needs_no_bibliography_machinery(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        isolated_config.BIB_FILE_PATH.write_text("", encoding="utf-8")
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the quoted span\n")

        body = evidence_appendix.emit(draft, "tex").read_text(encoding="utf-8")

        assert "\\bibliography" not in body
        assert "biblatex" not in body


class TestRenderFailuresAreReportedNotRaised:
    def _quoted_draft(self, isolated_config):
        con = ledger.connect()
        seed(con, "doe_a_2024")
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@doe_a_2024].\n", encoding="utf-8")
        write_dossier(draft, "## `doe_a_2024`\n\nquote: the span\n")
        return draft

    def test_a_missing_pandoc_is_reported_not_raised(self, isolated_config, monkeypatch, capsys):
        from chitragupta.render_output._errors import MissingBinary

        draft = self._quoted_draft(isolated_config)
        monkeypatch.setattr(
            "chitragupta.render_output.render",
            lambda *a, **k: (_ for _ in ()).throw(MissingBinary("pandoc not found")),
        )

        assert evidence_appendix.main([str(draft), "--format", "pdf"]) == 1
        assert "[missing-binary]" in capsys.readouterr().err

    def test_a_pandoc_failure_is_reported_not_raised(self, isolated_config, monkeypatch, capsys):
        draft = self._quoted_draft(isolated_config)

        def boom(*_args, **_kwargs):
            raise subprocess.CalledProcessError(1, ["pandoc"], stderr="pandoc said no")

        monkeypatch.setattr("chitragupta.render_output.render", boom)

        assert evidence_appendix.main([str(draft), "--format", "pdf"]) == 1
        assert "pandoc said no" in capsys.readouterr().err

    def test_the_markdown_sidecar_survives_a_failed_pdf_render(
        self, isolated_config, monkeypatch, capsys
    ):
        draft = self._quoted_draft(isolated_config)

        def boom(*_args, **_kwargs):
            raise subprocess.CalledProcessError(1, ["pandoc"], stderr="pandoc said no")

        monkeypatch.setattr("chitragupta.render_output.render", boom)
        evidence_appendix.main([str(draft), "--format", "pdf"])

        sidecar = isolated_config.RENDERED_DIR / "topic" / "survey.evidence.md"
        assert sidecar.is_file()
        assert '> "the span"' in sidecar.read_text(encoding="utf-8")


class TestNonAsciiSourceWording:
    def test_a_quote_with_non_ascii_characters_survives_the_round_trip(self, isolated_config):
        con = ledger.connect()
        ledger.upsert_reference(
            con,
            make_reference(
                citekey="mueller_a_2024",
                title="Zwillinge und Modelle",
                year="2024",
                fields={"author": "Müller, Jürgen", "journal": "Zeitschrift für Dinge"},
            ),
        )
        con.close()
        draft = content_draft(isolated_config, "drafts/topic/survey.md")
        draft.write_text("Body [@mueller_a_2024].\n", encoding="utf-8")
        write_dossier(
            draft,
            (
                "## `mueller_a_2024`\n\n"
                "quote: the model’s fidelity — judged 1–9 — is a claim about purpose\n"
            ),
        )
        out_dir = isolated_config.CONTENT_DIR / "rendered" / "topic"

        out_path = evidence_appendix.write(draft, out_dir)
        written = out_path.read_text(encoding="utf-8")

        assert "the model’s fidelity — judged 1–9 — is a claim about purpose" in written
        assert "Müller" in written, "an accented author name must survive attribution"
