"""chitragupta/review/uncited_prose.py: which sentences of a draft carry
no citation at all.

The fifth review aid, and the one whose whole difficulty is in what it
declines to report. `citation_coverage` answers the corpus-side question
-- which surfaced candidates got cited -- and nothing before this asked
the prose-side one. Measured on the four real drafts, the naive reading
flags four fifths of a survey, so these tests hold the aid to its
exclusions as tightly as to its findings: a report nobody opens twice
has failed, whatever it got right.

Advisory like the other five -- exit 0 whatever it finds, no lock, and
no draft blocked by any of it.
"""

import json
from pathlib import Path

import pytest

from chitragupta import config, dossier, review
from chitragupta.review import __main__ as review_main
from chitragupta.review import _uncited_render, _units, uncited_prose
from tests.test_review_units import draft_at, write_scope


def a_draft(text: str, genre: str = "survey", name: str = "survey.md") -> Path:
    draft = draft_at(name)
    draft.write_text(text, encoding="utf-8")
    write_scope(draft, genre)
    return draft


def report_for(draft: Path, genre: str | None = None) -> uncited_prose.Report:
    return uncited_prose.build_report(draft, *uncited_prose.resolve(draft, genre))


def found_text(draft: Path, genre: str | None = None) -> list[str]:
    """The sentence of every finding this draft raises."""
    return [f["sentence"] for f in uncited_prose.findings(report_for(draft, genre))]


class TestRegistration:
    def test_the_aid_is_in_both_tables(self):
        """R10's machine-checked half -- review.AIDS owns the report
        suffix, __main__.AIDS owns the subcommand, and the entry point
        raises at import if they disagree."""
        assert "uncited" in review.AIDS
        assert "uncited" in review_main.AIDS

    def test_it_files_its_report_beside_the_others(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        assert review.report_path(draft, "uncited") == (
            config.REVIEW_DIR / "dt" / "survey.uncited.md"
        )


class TestWhatIsAndIsNotAFinding:
    def test_a_cited_sentence_is_not_reported(self, isolated_config):
        draft = a_draft("Twins close the loop [@Kritzinger2018].\n")
        assert found_text(draft) == []

    def test_an_uncited_claim_is_reported(self, isolated_config):
        draft = a_draft("Most systems sold as digital twins are dashboards.\n")
        assert found_text(draft) == ["Most systems sold as digital twins are dashboards."]

    def test_only_the_uncited_sentence_of_a_citing_paragraph_is_reported(self, isolated_config):
        """The failure this aid exists for: a paragraph with one citation
        at the end and an unrelated assertion before it. Suppressing the
        whole paragraph because it cites *something* would be blind to
        exactly the case worth catching."""
        draft = a_draft(
            "The pump runs at 3 a.m. until the pot overflows.\n"
            "Coupling is what separates a twin from a shadow [@Kritzinger2018].\n"
        )
        assert found_text(draft) == ["The pump runs at 3 a.m. until the pot overflows."]

    def test_a_latex_citation_counts_as_a_citation(self, isolated_config):
        """Every genre skill exports .tex beside the .md, so the aid must
        read a draft in either markup."""
        draft = a_draft("Twins close the loop \\citep{Kritzinger2018}.\n", name="thesis.tex")
        assert found_text(draft) == []


class TestBlockCites:
    def test_it_is_false_when_nothing_in_the_block_cites(self, isolated_config):
        draft = a_draft("Apply that to the pot.\n")
        assert uncited_prose.findings(report_for(draft))[0]["block_cites"] is False

    def test_it_is_true_when_a_sibling_sentence_cites(self, isolated_config):
        draft = a_draft("Three failure modes recur.\nClocks are the first [@Frasheri2022].\n")
        assert uncited_prose.findings(report_for(draft))[0]["block_cites"] is True

    def test_the_counts_separate_the_two(self, isolated_config):
        draft = a_draft("A bare claim.\n\nA framed claim.\nIts evidence [@Frasheri2022].\n")
        report = report_for(draft)
        assert (len(report.uncited), len(report.bare)) == (2, 1)


class TestTheExclusions:
    """Each one measured against the four real drafts before it was
    written -- see plans/c1-uncited-prose-report.md."""

    def test_the_reference_list_is_excluded(self, isolated_config):
        """40 of survey.md's 87 naive findings. A bibliography entry is
        uncited prose by construction."""
        draft = a_draft(
            "A bare claim.\n\n"
            "## 7. References\n\n"
            '[1] W. Kritzinger et al., "Digital Twin in manufacturing," 2018.\n'
        )
        assert found_text(draft) == ["A bare claim."]

    def test_a_numbered_references_heading_still_matches(self, isolated_config):
        """The real drafts write `## 7. References`, not `## References`,
        so a pattern anchored straight after the hashes matches neither."""
        draft = a_draft("## 7. References\n\n[1] A paper.\n")
        assert found_text(draft) == []

    def test_a_latex_bibliography_heading_is_excluded(self, isolated_config):
        draft = a_draft("\\section*{Bibliography}\n\nA paper.\n", name="thesis.tex")
        assert found_text(draft) == []

    def test_headings_are_excluded(self, isolated_config):
        """A numbered heading also splits into two sentences -- `1.` and
        the title -- so leaving it in costs two findings, not one."""
        draft = a_draft("# Digital twins\n\n## 1. The connection is the twin\n")
        assert found_text(draft) == []

    def test_a_latex_heading_is_excluded(self, isolated_config):
        draft = a_draft("\\section{Architecture}\n", name="thesis.tex")
        assert found_text(draft) == []

    def test_captions_are_excluded(self, isolated_config):
        draft = a_draft(
            "![A potted plant and its twin](figures/pot.png)\n\n"
            "Figure 1. The loop closes at the pump.\n\n"
            "Table 2: Where to start.\n"
        )
        assert found_text(draft) == []

    def test_a_latex_caption_is_excluded(self, isolated_config):
        draft = a_draft("\\caption{The loop closes at the pump.}\n", name="thesis.tex")
        assert found_text(draft) == []

    def test_a_pandoc_table_caption_is_excluded(self, isolated_config):
        """WRITING-STANDARDS.md §13's caption line. Without this the aid
        reports one false finding per table in every draft written to that
        section -- on the aid whose whole design problem is alarm
        fatigue."""
        draft = a_draft(
            "| Starting point | Core idea |\n"
            "|---|---|\n"
            "| Pattern catalog | Patterns to instantiate |\n\n"
            ": Where to start when building a first twin.\n"
            "<!-- table: start-here -->\n"
        )
        assert found_text(draft) == ["Pattern catalog -- Patterns to instantiate"]

    def test_an_inline_table_reference_does_not_reach_the_report(self, isolated_config):
        """§13's reference marker sits *inside* a sentence, which the
        block-level COMMENT exclusion cannot see. Left in, a finding
        quotes pipeline markup back at the reader."""
        draft = a_draft("The platforms in <!-- tableref: start-here --> differ.\n")
        assert found_text(draft) == ["The platforms in Table differ."]

    def test_a_table_header_row_is_excluded_and_the_body_rows_are_not(self, isolated_config):
        """The column names are scaffolding. The rows are claims -- and
        survey.md's own comparison table attributes each row with a
        citekey in backticks, which the gate cannot see and neither can
        this aid, so reporting them is correct."""
        draft = a_draft(
            "| Starting point | Core idea |\n"
            "|---|---|\n"
            "| Pattern catalog | Patterns to instantiate |\n"
        )
        assert found_text(draft) == ["Pattern catalog -- Patterns to instantiate"]

    def test_a_latex_table_header_row_is_excluded_and_the_body_rows_are_not(self, isolated_config):
        """The two markups mark the header from opposite sides: markdown's
        separator follows it, booktabs' `\\toprule` precedes it. Missing
        this fired in production -- `thesis-chapter` emits `.tex` and is
        one of the three genres where uncited prose is exceptional."""
        draft = a_draft(
            "\\begin{tabular}{lll}\n"
            "\\toprule\n"
            "Approach & Core idea & Limitation \\\\\n"
            "\\midrule\n"
            "Patterns & Instantiate them & Structure only \\\\\n"
            "\\bottomrule\n"
            "\\end{tabular}\n",
            name="thesis.tex",
        )
        assert found_text(draft) == ["Patterns -- Instantiate them -- Structure only"]

    def test_an_hline_ruled_header_row_is_a_known_gap(self, isolated_config):
        """Pinned rather than fixed. `\\hline` separates every row from
        every other, so nothing in it distinguishes the header -- and the
        genre skills emit booktabs. Stated in `_claims.py` as a limit."""
        draft = a_draft(
            "\\begin{tabular}{ll}\n"
            "\\hline\n"
            "Approach & Core idea \\\\\n"
            "\\hline\n"
            "Patterns & Instantiate them \\\\\n"
            "\\end{tabular}\n",
            name="thesis.tex",
        )
        assert "Approach -- Core idea" in found_text(draft)

    def test_a_comment_only_block_is_excluded(self, isolated_config):
        """Including WRITING-STANDARDS.md §11's own single-source marker,
        which must not be read as an uncited claim about the world."""
        draft = a_draft(
            "<!-- single-source: Foo2019 is the only paper covering X -->\n\n% A LaTeX comment.\n"
        )
        assert found_text(draft) == []

    def test_a_figure_caption_is_excluded(self, isolated_config):
        """Issue 411's caption line has no self-identifying prefix, unlike
        a table's `:`-led one -- so this needs the block-membership check
        `_excluded` already has for a booktabs `\\toprule`, not the
        first-line prefix check a table's caption gets."""
        draft = a_draft("<!-- figure: figures/fig1 -->\nOne reading path.\n")
        assert found_text(draft) == []

    def test_an_inline_figure_reference_does_not_reach_the_report(self, isolated_config):
        """Mirrors `test_an_inline_table_reference_does_not_reach_the_report`:
        the marker sits *inside* a sentence, so it must be replaced by the
        word it stands for rather than left as markup."""
        draft = a_draft("The flow in <!-- figureref: fig1 --> differs.\n")
        assert found_text(draft) == ["The flow in Figure differs."]

    def test_fenced_code_is_excluded(self, isolated_config):
        draft = a_draft("```\nprint('the pot is dry')\n```\n")
        assert found_text(draft) == []

    def test_list_scaffolding_flattens_to_nothing_and_is_skipped(self, isolated_config):
        """A bare `\\item` or an environment opener carries no claim once
        its marker is stripped."""
        draft = a_draft("\\begin{itemize}\n\\item\n\\end{itemize}\n", name="thesis.tex")
        assert found_text(draft) == []

    def test_a_blockquote_is_reported_without_its_markers(self, isolated_config):
        """A blockquote repeats its `>` on every line, unlike a list item
        whose continuation lines carry no marker -- so stripping only the
        first left the rest embedded mid-sentence, and deep-research.md's
        method banner read back as "Method adapted from > hadufer/...".
        The quote is still a finding: quoted material needs attribution.
        """
        draft = a_draft("> Method adapted from\n> hadufer/claude-storm (MIT).\n")
        assert found_text(draft) == ["Method adapted from hadufer/claude-storm (MIT)."]

    def test_a_list_item_with_prose_is_still_reported(self, isolated_config):
        """The marker is scaffolding; what follows it is a claim."""
        draft = a_draft("- Most twins never close the loop.\n")
        assert found_text(draft) == ["Most twins never close the loop."]


class TestTheGenreDecidesWhetherUncitedProseIsAFinding:
    @pytest.mark.parametrize("genre", ["survey", "thesis-chapter", "deep-research"])
    def test_uncited_prose_is_exceptional_in_a_citing_genre(self, isolated_config, genre):
        draft = a_draft("A bare claim.\n", genre=genre)
        assert found_text(draft) == ["A bare claim."]

    @pytest.mark.parametrize("genre", ["textbook-chapter", "tutorial"])
    def test_uncited_prose_is_ordinary_in_an_original_prose_genre(self, isolated_config, genre):
        """WRITING-STANDARDS §11: a tutorial's body carries no citations
        by design, and a textbook chapter is mostly worked examples.
        Measured, book-chapter.md still yields 81 findings after every
        exclusion above, and not one of them is actionable."""
        draft = a_draft("A bare claim.\n", genre=genre)
        assert found_text(draft) == []

    def test_the_counts_are_reported_whatever_the_genre(self, isolated_config):
        """A textbook chapter whose background section cites nothing is
        still worth a human's eye; what changes is whether a machine is
        handed a finding about it."""
        draft = a_draft("A bare claim.\n", genre="tutorial")
        assert len(report_for(draft).uncited) == 1

    def test_an_unrecorded_genre_gets_the_strict_reading(self, isolated_config):
        """Silence reads as clean, so the fallback reports and says the
        genre was not recorded -- _units.FALLBACK_KIND's own reasoning."""
        draft = draft_at()
        draft.write_text("A bare claim.\n", encoding="utf-8")
        assert found_text(draft) == ["A bare claim."]
        assert report_for(draft).genre_source == "nothing"

    def test_a_genre_scope_md_does_not_recognise_gets_the_strict_reading(self, isolated_config):
        draft = a_draft("A bare claim.\n", genre="monograph")
        report = report_for(draft)
        assert (report.genre, report.standing) == ("monograph", "exceptional")

    def test_the_genre_override_wins(self, isolated_config):
        draft = a_draft("A bare claim.\n", genre="survey")
        report = report_for(draft, "tutorial")
        assert (report.standing, report.genre_source) == ("ordinary", "--genre")

    def test_every_genre_has_a_standing(self):
        """Pinned against dossier.GENRES so a sixth genre cannot arrive
        as a silent fallback -- the same guard tests/test_review_units.py
        puts on UNITS."""
        assert set(_units.UNCITED_PROSE) == set(dossier.GENRES)

    def test_every_standing_is_one_of_the_two(self):
        assert set(_units.UNCITED_PROSE.values()) <= set(_units.STANDINGS)

    def test_the_report_has_a_sentence_for_every_standing(self):
        """The renderer keys a dict on the standing, so a third one would
        reach a reader as a KeyError rather than as a missing paragraph.
        Same guard as the genre pin above, one layer out."""
        assert set(_uncited_render._STANDING) == set(_units.STANDINGS)


class TestFindingIdentity:
    def test_it_is_stable_across_runs(self, isolated_config):
        draft = a_draft("A bare claim.\n")
        assert found_ids(draft) == found_ids(draft)

    def test_it_survives_an_unrelated_edit(self, isolated_config):
        """R2: position-free, so "this finding is gone" stays decidable
        after a paragraph is inserted above it."""
        draft = a_draft("A bare claim.\n")
        before = found_ids(draft)
        draft.write_text("Something else entirely [@A].\n\nA bare claim.\n", encoding="utf-8")
        assert found_ids(draft) == before

    def test_it_survives_a_citation_arriving_elsewhere_in_the_block(self, isolated_config):
        """The finding is still true -- this sentence still carries no
        citation -- so it is not renamed into a new one. Only
        `block_cites` moves."""
        draft = a_draft("A bare claim.\n")
        before = found_ids(draft)
        draft.write_text("A bare claim.\nIts neighbour [@A].\n", encoding="utf-8")
        assert found_ids(draft) == before
        assert uncited_prose.findings(report_for(draft))[0]["block_cites"] is True

    def test_citing_the_sentence_itself_removes_the_finding(self, isolated_config):
        draft = a_draft("A bare claim.\n")
        assert found_ids(draft)
        draft.write_text("A bare claim [@A].\n", encoding="utf-8")
        assert found_ids(draft) == []


def found_ids(draft: Path) -> list[str]:
    return [f["id"] for f in uncited_prose.findings(report_for(draft))]


class TestTheReportIsAnArtefactThatDiffs:
    def test_two_runs_are_byte_identical(self, isolated_config):
        draft = a_draft("A bare claim.\n")
        report = report_for(draft)
        found = uncited_prose.findings(report)
        assert _uncited_render.render_markdown(
            report, "cmd", found
        ) == _uncited_render.render_markdown(report, "cmd", found)

    def test_the_markdown_carries_no_date(self, isolated_config):
        """review/__init__.py's rule: a wall-clock line defeats the diff
        the report exists to be read through."""
        draft = a_draft("A bare claim.\n")
        report = report_for(draft)
        body = _uncited_render.render_markdown(report, "cmd", [])
        assert "2026" not in body

    def test_the_report_opens_with_the_not_a_verdict_banner(self, isolated_config):
        draft = a_draft("A bare claim.\n")
        body = _uncited_render.render_markdown(report_for(draft), "cmd", [])
        assert review.BANNER in body

    def test_it_says_which_genre_and_standing_it_measured_under(self, isolated_config):
        """A textbook chapter reporting no findings has not passed a
        check -- none was applied -- and the report must say so on its
        face, the way synthesis names its unit."""
        draft = a_draft("A bare claim.\n", genre="tutorial")
        body = _uncited_render.render_markdown(report_for(draft), "cmd", [])
        assert "tutorial" in body
        assert "ordinary" in body

    def test_it_says_the_genre_was_not_recorded_when_it_was_not(self, isolated_config):
        draft = draft_at()
        draft.write_text("A bare claim.\n", encoding="utf-8")
        body = _uncited_render.render_markdown(report_for(draft), "cmd", [])
        assert "not recorded" in body

    def test_the_findings_are_listed_bare_blocks_first(self, isolated_config):
        """Volume control: the sentences resting on nothing at all are
        what a reviewer should read before the ones their paragraph
        frames."""
        draft = a_draft("A framed claim.\nIts evidence [@A].\n\nA bare claim.\n")
        assert found_text(draft) == ["A bare claim.", "A framed claim."]


class TestTheCommandLine:
    def test_it_exits_zero_with_findings(self, isolated_config):
        draft = a_draft("A bare claim.\n")
        assert uncited_prose.main([str(draft)]) == 0

    def test_it_exits_zero_without_findings(self, isolated_config):
        draft = a_draft("A cited claim [@A].\n")
        assert uncited_prose.main([str(draft)]) == 0

    def test_a_missing_draft_exits_one(self, isolated_config):
        assert uncited_prose.main([str(config.DRAFTS_DIR / "nope.md")]) == 1

    def test_a_draft_outside_the_content_directory_exits_one(self, isolated_config, tmp_path):
        outside = tmp_path / "elsewhere.md"
        outside.write_text("A bare claim.\n", encoding="utf-8")
        assert uncited_prose.main([str(outside)]) == 1

    def test_the_default_prints_text(self, isolated_config, capsys):
        draft = a_draft("A bare claim.\n")
        uncited_prose.main([str(draft)])
        assert "A bare claim." in capsys.readouterr().out

    def test_the_text_form_says_why_an_original_prose_genre_raised_nothing(
        self, isolated_config, capsys
    ):
        """stdout is where most of these reports are read, so the
        sentence that stops a tutorial's empty report reading as a pass
        has to be there too, not only in the Markdown."""
        draft = a_draft("A bare claim.\n", genre="tutorial")
        uncited_prose.main([str(draft)])
        out = capsys.readouterr().out
        assert "original by design" in out
        assert "A bare claim." not in out

    def test_the_text_form_names_an_unrecorded_genre_as_such(self, isolated_config, capsys):
        draft = draft_at()
        draft.write_text("A bare claim.\n", encoding="utf-8")
        uncited_prose.main([str(draft)])
        assert "not recorded" in capsys.readouterr().out

    def test_json_prints_the_payload(self, isolated_config, capsys):
        draft = a_draft("A bare claim.\n")
        uncited_prose.main([str(draft), "--json"])
        payload = json.loads(capsys.readouterr().out)
        assert payload["aid"] == "uncited"
        assert [f["sentence"] for f in payload["findings"]] == ["A bare claim."]

    def test_the_payload_carries_the_envelope_and_no_timestamp(self, isolated_config, capsys):
        draft = a_draft("A bare claim.\n")
        uncited_prose.main([str(draft), "--json"])
        out = capsys.readouterr().out
        assert "never a verdict" in json.loads(out)["notice"]
        assert "2026" not in out

    def test_the_recorded_command_carries_every_flag(self, isolated_config, capsys):
        """A count of uncited sentences means something different when a
        --genre override chose the standing, so the envelope records it."""
        draft = a_draft("A bare claim.\n")
        uncited_prose.main([str(draft), "--genre", "tutorial", "--json"])
        command = json.loads(capsys.readouterr().out)["command"]
        assert "--genre tutorial" in command
        assert "--json" in command

    def test_write_files_the_report_and_its_payload(self, isolated_config, capsys):
        draft = a_draft("A bare claim.\n")
        uncited_prose.main([str(draft), "--write", "--formats", "md"])
        capsys.readouterr()
        assert review.report_path(draft, "uncited").is_file()
        assert (
            json.loads(review.report_path(draft, "uncited", "json").read_text(encoding="utf-8"))[
                "aid"
            ]
            == "uncited"
        )

    def test_write_under_json_keeps_the_summary_off_stdout(self, isolated_config, capsys):
        draft = a_draft("A bare claim.\n")
        uncited_prose.main([str(draft), "--json", "--write", "--formats", "md"])
        captured = capsys.readouterr()
        json.loads(captured.out)  # stdout is the payload and nothing else
        assert "uncited.md" in captured.err

    def test_the_entry_point_dispatches_to_it(self, isolated_config, capsys):
        draft = a_draft("A bare claim.\n")
        assert review_main.main(["uncited", str(draft)]) == 0
        assert "A bare claim." in capsys.readouterr().out
