"""chitragupta/review/synthesis.py: how many sources each unit of a draft
rests on, at the unit its genre binds at.

One of the six review aids. Advisory like the rest -- it exits 0 whatever
it finds, takes no lock, and blocks no draft. What these
tests hold it to is that the numbers are honest about *what* was
measured: a tutorial reporting no multi-source paragraphs has not failed,
it was never measured at paragraph scale, and the report has to say so on
its face.
"""

import json
import re
from pathlib import Path

import pytest

from chitragupta import config, review
from chitragupta.review import __main__ as review_main
from chitragupta.review import _synthesis_render, synthesis
from tests.test_review_units import draft_at, write_scope


def _render(draft: Path) -> str:
    """The Markdown report for `draft`, at whatever unit its genre binds at."""
    report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
    return _synthesis_render.render_markdown(report, "cmd", synthesis.findings(report))


def a_draft(text: str, genre: str = "survey", name: str = "survey.md") -> Path:
    draft = draft_at(name)
    draft.write_text(text, encoding="utf-8")
    write_scope(draft, genre)
    return draft


class TestRegistration:
    def test_the_aid_is_in_both_tables(self):
        """R10's machine-checked half -- review.AIDS owns the report
        suffix, __main__.AIDS owns the subcommand, and the entry point
        raises at import if they disagree."""
        assert "synthesis" in review.AIDS
        assert "synthesis" in review_main.AIDS

    def test_it_files_its_report_beside_the_others(self, isolated_config):
        draft = config.DRAFTS_DIR / "dt" / "survey.md"
        assert review.report_path(draft, "synthesis") == (
            config.REVIEW_DIR / "dt" / "survey.synthesis.md"
        )


class TestTheReportNamesWhatItMeasured:
    def test_it_records_the_genre_the_unit_and_the_source(self, isolated_config):
        draft = a_draft("Text [@A].\n", genre="textbook-chapter")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        assert (report.genre, report.kind, report.source) == (
            "textbook-chapter",
            "section",
            "scope.md",
        )

    def test_a_tutorials_report_says_the_unit_was_the_document(self, isolated_config):
        draft = a_draft("Lesson.\n\n## Where to go next\n\nSee [@A].\n", genre="tutorial")
        body = _render(draft)
        assert "document" in body
        assert "paragraph" not in body.split("## Units")[0].replace(
            "paragraphs", ""
        )  # the header must not imply a scale it never used

    def test_it_says_a_thin_corpus_legitimately_produces_single_source_units(self, isolated_config):
        draft = a_draft("Text [@A].\n")
        body = _render(draft)
        assert "thin corpus" in body
        assert "counts" in body and "does not judge" in body

    def test_it_opens_with_the_not_a_verdict_banner(self, isolated_config):
        draft = a_draft("Text [@A].\n")
        body = _render(draft)
        assert review.BANNER in body


class TestTheCounts:
    def test_units_are_split_by_how_many_sources_they_rest_on(self, isolated_config):
        draft = a_draft("None here.\n\nOne [@A].\n\nTwo [@A] and [@B].\n")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        assert (report.uncited, report.single_source, report.multi_source) == (1, 1, 1)

    def test_the_proportion_is_of_units_that_cite_at_all(self, isolated_config):
        """An uncited unit is not a failed multi-source unit -- most of a
        textbook chapter is original prose."""
        draft = a_draft("None.\n\nNone either.\n\nOne [@A].\n\nTwo [@A] and [@B].\n")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        assert report.single_source_pct == 50.0

    def test_a_draft_citing_nothing_has_no_proportion(self, isolated_config):
        draft = a_draft("Original prose only.\n")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        assert report.single_source_pct is None

    def test_declared_and_undeclared_are_counted_apart(self, isolated_config):
        draft = a_draft("One [@A].\n<!-- single-source: only A covers this -->\n\nTwo [@B].\n")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        assert (report.declared, report.undeclared) == (1, 1)


class TestFindings:
    def test_a_single_source_unit_is_a_finding(self, isolated_config):
        draft = a_draft("One [@A].\n")
        findings = synthesis.findings(
            synthesis.build_report(draft, *synthesis.resolve(draft, None))
        )
        assert [f["kind"] for f in findings] == ["single_source"]

    def test_a_multi_source_unit_is_not(self, isolated_config):
        draft = a_draft("Two [@A] and [@B].\n")
        assert (
            synthesis.findings(synthesis.build_report(draft, *synthesis.resolve(draft, None))) == []
        )

    def test_an_uncited_unit_is_counted_but_is_never_a_finding(self, isolated_config):
        """Making original prose a finding would bury the one thing this
        report is for."""
        draft = a_draft("Original prose, no citation at all.\n")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        assert report.uncited == 1
        assert synthesis.findings(report) == []

    def test_undeclared_findings_come_first(self, isolated_config):
        draft = a_draft("One [@A].\n<!-- single-source: stated -->\n\nTwo [@B].\n\nThree [@C].\n")
        findings = synthesis.findings(
            synthesis.build_report(draft, *synthesis.resolve(draft, None))
        )
        assert [f["declared"] for f in findings] == [None, None, "stated"]

    def test_a_long_single_key_run_is_a_finding_in_a_section(self, isolated_config):
        draft = a_draft(
            "## S\n\nOne [@A].\n\nTwo [@A].\n\nThree [@A].\n\nFour [@B].\n",
            genre="textbook-chapter",
        )
        findings = synthesis.findings(
            synthesis.build_report(draft, *synthesis.resolve(draft, None))
        )
        assert [f["kind"] for f in findings] == ["single_key_run"]
        assert findings[0]["longest_run"] == 3

    def test_a_single_source_section_raises_one_finding_not_two(self, isolated_config):
        """Its run is as long as it has paragraphs, by construction --
        reporting that beside the spread says nothing twice."""
        draft = a_draft("## S\n\nOne [@A].\n\nTwo [@A].\n\nThree [@A].\n", genre="textbook-chapter")
        findings = synthesis.findings(
            synthesis.build_report(draft, *synthesis.resolve(draft, None))
        )
        assert [f["kind"] for f in findings] == ["single_source"]

    def test_the_interleaved_counterpart_is_not_a_finding(self, isolated_config):
        draft = a_draft(
            "## S\n\nOne [@A].\n\nTwo [@B].\n\nThree [@A].\n\nFour [@B].\n",
            genre="textbook-chapter",
        )
        assert (
            synthesis.findings(synthesis.build_report(draft, *synthesis.resolve(draft, None))) == []
        )

    def test_spread_alone_cannot_tell_the_two_apart(self, isolated_config):
        """The point of measuring the run: both sections below span two
        sources, and only one of them fuses anything."""
        blocked = a_draft(
            "## S\n\n[@A] one.\n\n[@A] two.\n\n[@A] three.\n\n[@B] four.\n",
            genre="textbook-chapter",
            name="blocked.md",
        )
        fused = a_draft(
            "## S\n\n[@A] one.\n\n[@B] two.\n\n[@A] three.\n\n[@B] four.\n",
            genre="textbook-chapter",
            name="fused.md",
        )
        reports = [synthesis.build_report(d, *synthesis.resolve(d, None)) for d in (blocked, fused)]
        assert {len(r.units[0].citekeys) for r in reports} == {2}
        assert [r.units[0].longest_run for r in reports] == [3, 1]


class TestFindingIdentity:
    def test_is_stable_across_runs(self, isolated_config):
        draft = a_draft("One [@A].\n")
        first, second = (
            synthesis.findings(synthesis.build_report(draft, *synthesis.resolve(draft, None)))
            for _ in range(2)
        )
        assert [f["id"] for f in first] == [f["id"] for f in second]

    def test_is_unchanged_by_declaring_the_unit(self, isolated_config):
        """Otherwise the declared/undeclared split renames every finding
        the moment someone explains one -- which is what R2 forbids."""
        plain = a_draft("One [@A].\n", name="plain.md")
        declared = a_draft("One [@A].\n<!-- single-source: because -->\n", name="declared.md")
        ids = [
            synthesis.findings(synthesis.build_report(d, *synthesis.resolve(d, None)))[0]["id"]
            for d in (plain, declared)
        ]
        assert ids[0] == ids[1]

    def test_is_unchanged_by_an_edit_above_it(self, isolated_config):
        """Position-free, for the reason
        citation_provenance/_citation_provenance_render.finding_id is: a
        line-based identity renames every finding below an edit."""
        before = a_draft("One [@A].\n", name="before.md")
        after = a_draft("A new opening paragraph [@X] and [@Y].\n\nOne [@A].\n", name="after.md")
        ids = [
            {
                f["id"]
                for f in synthesis.findings(synthesis.build_report(d, *synthesis.resolve(d, None)))
            }
            for d in (before, after)
        ]
        assert ids[0] <= ids[1]


class TestTheCommandLine:
    def test_it_prints_by_default_and_exits_zero(self, isolated_config, capsys):
        draft = a_draft("One [@A].\n")
        assert review_main.main(["synthesis", str(draft)]) == 0
        assert "Multi-source synthesis" in capsys.readouterr().out

    def test_it_exits_zero_when_every_unit_is_single_source(self, isolated_config):
        draft = a_draft("One [@A].\n\nTwo [@B].\n\nThree [@C].\n")
        assert review_main.main(["synthesis", str(draft)]) == 0

    def test_a_missing_draft_is_refused(self, isolated_config, capsys):
        missing = config.DRAFTS_DIR / "nope.md"
        assert review_main.main(["synthesis", str(missing)]) == 1
        assert "No such draft" in capsys.readouterr().err

    def test_a_draft_outside_content_is_refused(self, isolated_config, tmp_path, capsys):
        outside = tmp_path / "loose.md"
        outside.write_text("Text [@A].\n", encoding="utf-8")
        assert review_main.main(["synthesis", str(outside)]) == 1
        assert capsys.readouterr().err

    def test_the_unit_flag_overrides_the_dossier(self, isolated_config, capsys):
        draft = a_draft("One [@A].\n", genre="tutorial")
        assert review_main.main(["synthesis", str(draft), "--unit", "paragraph"]) == 0
        assert "--unit" in capsys.readouterr().out

    def test_json_prints_the_payload(self, isolated_config, capsys):
        draft = a_draft("One [@A].\n")
        assert review_main.main(["synthesis", str(draft), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["aid"] == "synthesis"
        assert payload["unit"] == "paragraph"
        assert payload["findings"][0]["kind"] == "single_source"

    def test_the_json_carries_the_not_a_verdict_notice(self, isolated_config, capsys):
        draft = a_draft("One [@A].\n")
        review_main.main(["synthesis", str(draft), "--json"])
        assert "not a gate" in json.loads(capsys.readouterr().out)["notice"]

    def test_write_files_the_report_and_its_json_sibling(self, isolated_config, capsys):
        draft = a_draft("One [@A].\n")
        assert review_main.main(["synthesis", str(draft), "--write", "--formats", "md"]) == 0
        assert review.report_path(draft, "synthesis").is_file()
        assert review.report_path(draft, "synthesis", "json").is_file()
        assert "synthesis.md" in capsys.readouterr().out

    def test_write_under_json_puts_the_summary_on_stderr(self, isolated_config, capsys):
        draft = a_draft("One [@A].\n")
        review_main.main(["synthesis", str(draft), "--write", "--json", "--formats", "md"])
        captured = capsys.readouterr()
        json.loads(captured.out)
        assert "synthesis.md" in captured.err

    def test_it_has_a_standalone_parser_too(self, isolated_config):
        """build_parser(None) is the path `python -m chitragupta.review
        synthesis` does not take, and the other aids all keep it."""
        args = synthesis.build_parser().parse_args(["draft.md"])
        assert args.draft == "draft.md"


class TestRepeatability:
    def test_two_runs_produce_byte_identical_markdown(self, isolated_config):
        draft = a_draft("One [@A].\n\nTwo [@A] and [@B].\n")
        bodies = [_render(draft) for _ in range(2)]
        assert bodies[0] == bodies[1]

    def test_two_runs_produce_byte_identical_json(self, isolated_config):
        draft = a_draft("One [@A].\n\nTwo [@A] and [@B].\n")
        payloads = [
            json.dumps(
                synthesis.synthesis_payload(
                    synthesis.build_report(draft, *synthesis.resolve(draft, None)), "cmd"
                )
            )
            for _ in range(2)
        ]
        assert payloads[0] == payloads[1]

    def test_the_report_carries_no_date(self, isolated_config):
        """A wall-clock line defeats the diff across revisions, which is
        the reason to write a report to disk at all.

        Matched as a date rather than as the digits of a year: the header
        quotes the draft's own path, and under pytest that path contains
        a run number which is sometimes '20'.
        """
        draft = a_draft("One [@A].\n")
        assert re.search(r"\b\d{4}-\d{2}-\d{2}\b", _render(draft)) is None


class TestTheRenderedReport:
    def test_it_itemises_each_finding_with_its_line(self, isolated_config):
        draft = a_draft("One [@A].\n")
        body = _render(draft)
        assert "line 1" in body
        assert "`A`" in body

    def test_it_shows_a_declared_units_stated_reason(self, isolated_config):
        draft = a_draft("One [@A].\n<!-- single-source: only A covers this -->\n")
        body = _render(draft)
        assert "only A covers this" in body

    def test_it_reports_a_clean_draft_as_clean(self, isolated_config):
        draft = a_draft("Two [@A] and [@B].\n")
        body = _render(draft)
        assert "Every unit that cites at all cites more than one source." in body

    def test_it_names_the_run_in_a_section_report(self, isolated_config):
        draft = a_draft(
            "## S\n\n[@A] one.\n\n[@A] two.\n\n[@A] three.\n\n[@B] four.\n",
            genre="textbook-chapter",
        )
        body = _render(draft)
        assert "consecutive paragraphs" in body

    def test_a_paragraph_report_does_not_mention_runs(self, isolated_config):
        draft = a_draft("One [@A].\n")
        body = _render(draft)
        assert "consecutive paragraphs" not in body

    def test_an_uncited_draft_says_so(self, isolated_config):
        draft = a_draft("Original prose only.\n")
        body = _render(draft)
        assert "cites nothing" in body


class TestTheTextReport:
    """stdout's form, which is what the default invocation prints."""

    def test_an_uncited_draft_says_so(self, isolated_config):
        draft = a_draft("Original prose only.\n")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        text = _synthesis_render.format_report(report, synthesis.findings(report))
        assert "cites nothing" in text

    def test_a_declared_finding_is_marked(self, isolated_config):
        draft = a_draft("One [@A].\n<!-- single-source: stated -->\n")
        report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
        text = _synthesis_render.format_report(report, synthesis.findings(report))
        assert "[declared]" in text


class TestTheStandaloneEntryPoint:
    def test_main_parses_its_own_argv(self, isolated_config, capsys):
        """`synthesis.main` is the path `python -m chitragupta.review
        synthesis` does not take, and the other aids all keep it."""
        draft = a_draft("One [@A].\n")
        assert synthesis.main([str(draft)]) == 0
        assert "Multi-source synthesis" in capsys.readouterr().out

    def test_the_recorded_command_carries_the_unit_flag(self, isolated_config, capsys):
        """A single-source count means something different on a draft
        measured at a unit its genre did not choose, so the report has to
        record the flag that chose it."""
        draft = a_draft("One [@A].\n", genre="tutorial")
        review_main.main(["synthesis", str(draft), "--unit", "paragraph", "--json"])
        assert "--unit paragraph" in json.loads(capsys.readouterr().out)["command"]


class TestResolve:
    def test_it_returns_the_kind_its_source_and_the_genre(self, isolated_config):
        draft = a_draft("Text [@A].\n", genre="tutorial")
        assert synthesis.resolve(draft, None) == ("document", "scope.md", "tutorial")

    def test_an_override_reports_no_genre_source(self, isolated_config):
        draft = a_draft("Text [@A].\n", genre="tutorial")
        assert synthesis.resolve(draft, "section") == ("section", "--unit", "tutorial")


@pytest.mark.parametrize(
    "genre,kind",
    [
        ("survey", "paragraph"),
        ("thesis-chapter", "paragraph"),
        ("deep-research", "paragraph"),
        ("textbook-chapter", "section"),
        ("tutorial", "document"),
    ],
)
def test_each_genre_is_measured_at_its_own_unit(isolated_config, genre, kind):
    draft = a_draft("## S\n\nText [@A].\n", genre=genre, name=f"{genre}.md")
    report = synthesis.build_report(draft, *synthesis.resolve(draft, None))
    assert report.kind == kind
