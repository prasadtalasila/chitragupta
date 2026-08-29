"""chitragupta/review/citation_coverage.py: how much of retrieval's candidates actually
made it into a draft's citations. Informational only, not a gate."""

import json
from pathlib import Path

from chitragupta import config, ledger
from chitragupta.review import _citation_coverage_render, citation_coverage

from tests.conftest import make_reference


class TestCitedCitekeys:
    def test_extracts_pandoc_and_latex_citations(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("Digital twins [@smith_2024] enable X. \\citep{jones_2023}\n")
        assert citation_coverage.cited_citekeys(draft) == {"smith_2024", "jones_2023"}

    def test_empty_draft_has_no_citations(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("No citations here.\n")
        assert citation_coverage.cited_citekeys(draft) == set()


class TestComputeCoverage:
    def test_full_coverage_when_every_candidate_cited(self, ledger_con, tmp_path):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = tmp_path / "draft.md"
        draft.write_text("Composable twins [@a2024] are useful.\n")

        result = citation_coverage.compute_coverage(draft, ["digital twin composability"])

        assert result.candidates == {"a2024": "Digital Twin Composability"}
        assert result.cited_candidates == {"a2024"}
        assert result.uncited_candidates == set()
        assert result.coverage_pct == 100.0

    def test_partial_coverage_lists_uncited_candidates(self, ledger_con, tmp_path):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="b2024", title="Digital Twin Simulation")
        )
        draft = tmp_path / "draft.md"
        draft.write_text("Composable twins [@a2024] are useful.\n")

        result = citation_coverage.compute_coverage(draft, ["digital twin"])

        assert result.cited_candidates == {"a2024"}
        assert result.uncited_candidates == {"b2024"}
        assert result.coverage_pct == 50.0

    def test_no_candidates_gives_none_coverage(self, ledger_con, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("Nothing relevant [@a2024].\n")

        result = citation_coverage.compute_coverage(draft, ["completely unrelated nonsense query"])

        assert result.candidates == {}
        assert result.coverage_pct is None
        # still reports the citation even though no candidate surfaced it
        assert result.cited_outside_candidates == {"a2024"}

    def test_cited_outside_candidates_tracked_separately(self, ledger_con, tmp_path):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = tmp_path / "draft.md"
        draft.write_text("[@a2024] and also [@never_retrieved_2024].\n")

        result = citation_coverage.compute_coverage(draft, ["digital twin composability"])

        assert result.cited_outside_candidates == {"never_retrieved_2024"}
        assert result.uncited_candidates == set()


class TestFormatReport:
    def test_reports_coverage_percentage_and_gaps(self, ledger_con, tmp_path):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="b2024", title="Digital Twin Simulation")
        )
        draft = tmp_path / "draft.md"
        draft.write_text("Composable twins [@a2024] are useful.\n")

        result = citation_coverage.compute_coverage(draft, ["digital twin"])
        report = _citation_coverage_render.format_report(draft, ["digital twin"], result)

        assert "Coverage: 50%" in report
        assert "b2024: Digital Twin Simulation" in report

    def test_reports_citations_outside_candidates(self, ledger_con, tmp_path):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = tmp_path / "draft.md"
        draft.write_text("[@a2024] and also [@never_retrieved_2024].\n")

        result = citation_coverage.compute_coverage(draft, ["digital twin composability"])
        report = _citation_coverage_render.format_report(
            draft, ["digital twin composability"], result
        )

        assert "Cited but not surfaced by these queries" in report
        assert "never_retrieved_2024" in report

    def test_reports_no_candidates_message(self, tmp_path):
        draft = tmp_path / "draft.md"
        draft.write_text("Nothing here.\n")
        result = citation_coverage.CoverageResult()
        report = _citation_coverage_render.format_report(draft, ["x"], result)
        assert "No candidates found" in report


def _draft(text: str = "Composable twins [@a2024] are useful.\n", name: str = "draft.md") -> Path:
    """A draft where the review layer will accept one: under content/drafts/."""
    path = config.DRAFTS_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class TestMain:
    def test_main_prints_report_and_returns_zero(self, ledger_con, isolated_config, capsys):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()

        rc = citation_coverage.main([str(draft), "--query", "digital twin composability"])

        assert rc == 0
        out = capsys.readouterr().out
        assert "Coverage: 100%" in out

    def test_main_supports_repeated_query_and_custom_k(self, ledger_con, isolated_config, capsys):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft("[@a2024]\n")

        rc = citation_coverage.main(
            [
                str(draft),
                "--query",
                "digital twin",
                "--query",
                "composability",
                "--k",
                "1",
            ]
        )

        assert rc == 0


class TestWrite:
    """`--write` puts the report in content/review/, mirroring the draft's
    path, so it sits beside the same draft's provenance and verbatim
    reports rather than only in a terminal that gets closed."""

    def test_off_by_default(self, ledger_con, isolated_config, capsys):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()

        citation_coverage.main([str(draft), "--query", "digital twin composability"])

        assert not config.REVIEW_DIR.exists()

    def test_write_lands_in_the_mirrored_review_dir(self, ledger_con, isolated_config, capsys):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft(name="dt/survey.md")

        rc = citation_coverage.main(
            [
                str(draft),
                "--query",
                "digital twin composability",
                "--write",
                "--formats",
                "md",
            ]
        )

        assert rc == 0
        report = config.REVIEW_DIR / "dt" / "survey.coverage.md"
        assert report.is_file()

    def test_the_report_records_its_queries(self, ledger_con, isolated_config, capsys):
        """A coverage figure is meaningless without the queries it was
        measured against, so the header carries the whole invocation."""
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()

        citation_coverage.main(
            [
                str(draft),
                "--query",
                "digital twin",
                "--query",
                "composability",
                "--k",
                "3",
                "--write",
                "--formats",
                "md",
            ]
        )

        text = (config.REVIEW_DIR / "draft.coverage.md").read_text()
        assert "Review aid, not a gate" in text
        # shlex-quoted, so a multi-word query is re-runnable as printed.
        assert "--query 'digital twin' --query composability" in text
        assert "--k 3" in text

    def test_no_candidates_says_so_rather_than_reporting_zero_percent(
        self, ledger_con, isolated_config, capsys
    ):
        """An empty ledger means nothing was retrieved, which is not the
        same finding as "0% of what was retrieved is cited" -- the report
        must not let those read alike."""
        draft = _draft("[@a2024]\n")

        citation_coverage.main(
            [str(draft), "--query", "nothing matches this", "--write", "--formats", "md"]
        )

        text = (config.REVIEW_DIR / "draft.coverage.md").read_text()
        assert "No candidates found for any query" in text
        assert "%" not in text.split("## Coverage")[1]

    def test_uncited_candidates_are_listed_with_their_titles(
        self, ledger_con, isolated_config, capsys
    ):
        """The whole point of the report: a source retrieval surfaced and
        the draft never cited. A bare citekey would make the reader look
        each one up."""
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft("Cites nothing from the corpus.\n")

        citation_coverage.main(
            [str(draft), "--query", "digital twin composability", "--write", "--formats", "md"]
        )

        text = (config.REVIEW_DIR / "draft.coverage.md").read_text()
        assert "### Retrieved but not cited" in text
        assert "`a2024` -- Digital Twin Composability" in text

    def test_a_citekey_cited_but_not_surfaced_is_listed_as_not_a_gap(
        self, ledger_con, isolated_config, capsys
    ):
        """Listed so the report cannot be misread as a complete picture
        of the draft's sources -- and labelled so it is not misread as a
        finding either."""
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="b2023", title="Unrelated Runtime Verification")
        )
        draft = _draft("Cites both [@a2024] [@b2023].\n")

        citation_coverage.main(
            [
                str(draft),
                "--query",
                "digital twin composability",
                "--k",
                "1",
                "--write",
                "--formats",
                "md",
            ]
        )

        text = (config.REVIEW_DIR / "draft.coverage.md").read_text()
        assert "### Cited but not surfaced by these queries" in text
        assert "Not necessarily a problem" in text
        assert "`b2023`" in text

    def test_the_recorded_command_regenerates_the_file(self, ledger_con, isolated_config, capsys):
        """The header records the invocation so a reader can re-run it.
        Without `--write` the recorded command prints to stdout and writes
        nothing -- it reproduces the *findings* but not the file, which is
        the one thing someone holding the file wants."""
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()

        citation_coverage.main(
            [str(draft), "--query", "digital twin", "--write", "--formats", "md"]
        )

        text = (config.REVIEW_DIR / "draft.coverage.md").read_text()
        assert "--write" in text

    def test_two_runs_over_unchanged_input_are_byte_identical(
        self, ledger_con, isolated_config, capsys
    ):
        """No wall-clock timestamp anywhere in a report: the point of
        writing one is that it diffs cleanly against the next revision's."""
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()
        argv = [str(draft), "--query", "digital twin", "--write", "--formats", "md"]

        citation_coverage.main(argv)
        first = (config.REVIEW_DIR / "draft.coverage.md").read_bytes()
        citation_coverage.main(argv)
        second = (config.REVIEW_DIR / "draft.coverage.md").read_bytes()

        assert first == second


class TestJsonPayload:
    """`--json`, widening #127's plumbing from `verbatim scan` to the rest
    of the review layer (#309). Mirrors `verbatim scan`'s own contract:
    printing stays the default, `--json` prints the payload instead, and
    `--write` files it beside the Markdown whether or not `--json` was
    also given."""

    def test_json_flag_prints_the_payload_instead_of_text(
        self, ledger_con, isolated_config, capsys
    ):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()

        rc = citation_coverage.main([str(draft), "--query", "digital twin composability", "--json"])

        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["aid"] == "coverage"
        assert payload["coverage_pct"] == 100.0

    def test_json_flag_alone_does_not_write_a_file(self, ledger_con, isolated_config, capsys):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()

        citation_coverage.main([str(draft), "--query", "digital twin composability", "--json"])

        assert not config.REVIEW_DIR.exists()

    def test_findings_match_the_printed_report_one_for_one(
        self, ledger_con, isolated_config, capsys
    ):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="b2024", title="Digital Twin Simulation")
        )
        draft = _draft()

        citation_coverage.main([str(draft), "--query", "digital twin", "--json"])
        payload = json.loads(capsys.readouterr().out)

        result = citation_coverage.compute_coverage(draft, ["digital twin"])
        statuses = {f["citekey"]: f["status"] for f in payload["findings"]}
        assert statuses == {
            **{key: "uncited_candidates" for key in result.uncited_candidates},
            **{key: "cited_outside_candidates" for key in result.cited_outside_candidates},
        }

    def test_uncited_candidates_carry_their_title(self, ledger_con, isolated_config, capsys):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="b2024", title="Digital Twin Simulation")
        )
        draft = _draft()

        citation_coverage.main([str(draft), "--query", "digital twin", "--json"])
        payload = json.loads(capsys.readouterr().out)

        by_key = {f["citekey"]: f for f in payload["findings"]}
        assert by_key["b2024"]["title"] == "Digital Twin Simulation"

    def test_a_citekey_outside_the_candidates_is_still_a_finding_with_no_candidates_at_all(
        self, ledger_con, isolated_config, capsys
    ):
        """The printed report only shows `coverage_pct` when there are
        candidates, but a citation outside the (empty) candidate set is
        still worth reporting -- pin that the payload doesn't inherit the
        printed form's conditional."""
        draft = _draft("Nothing relevant [@a2024].\n")

        citation_coverage.main(
            [str(draft), "--query", "completely unrelated nonsense query", "--json"]
        )
        payload = json.loads(capsys.readouterr().out)

        assert payload["coverage_pct"] is None
        assert {f["citekey"] for f in payload["findings"]} == {"a2024"}

    def test_finding_ids_are_stable_across_runs_and_distinct_from_each_other(
        self, ledger_con, isolated_config, capsys
    ):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="b2024", title="Digital Twin Simulation")
        )
        draft = _draft()
        argv = [str(draft), "--query", "digital twin", "--json"]

        citation_coverage.main(argv)
        first_ids = [f["id"] for f in json.loads(capsys.readouterr().out)["findings"]]
        citation_coverage.main(argv)
        second_ids = [f["id"] for f in json.loads(capsys.readouterr().out)["findings"]]

        assert first_ids == second_ids
        assert len(set(first_ids)) == len(first_ids)

    def test_write_files_the_json_sibling_regardless_of_the_json_flag(
        self, ledger_con, isolated_config, capsys
    ):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft(name="dt/survey.md")

        rc = citation_coverage.main(
            [
                str(draft),
                "--query",
                "digital twin composability",
                "--write",
                "--formats",
                "md",
            ]
        )

        assert rc == 0
        assert (config.REVIEW_DIR / "dt" / "survey.coverage.json").is_file()

    def test_two_runs_over_unchanged_input_write_byte_identical_json(
        self, ledger_con, isolated_config, capsys
    ):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()
        argv = [str(draft), "--query", "digital twin", "--write", "--formats", "md"]

        citation_coverage.main(argv)
        first = (config.REVIEW_DIR / "draft.coverage.json").read_bytes()
        citation_coverage.main(argv)
        second = (config.REVIEW_DIR / "draft.coverage.json").read_bytes()

        assert first == second

    def test_json_flag_moves_the_written_summary_to_stderr(
        self, ledger_con, isolated_config, capsys
    ):
        ledger.upsert_reference(
            ledger_con, make_reference(citekey="a2024", title="Digital Twin Composability")
        )
        draft = _draft()

        citation_coverage.main(
            [
                str(draft),
                "--query",
                "digital twin composability",
                "--write",
                "--formats",
                "md",
                "--json",
            ]
        )
        out, err = capsys.readouterr()

        json.loads(out)
        assert "coverage.md" in err
        assert "coverage.json" in err


class TestInputIsConfinedToContent:
    def test_a_draft_outside_the_content_dir_is_refused(
        self, ledger_con, isolated_config, tmp_path, capsys
    ):
        """The tier-1 rule 3.17.0 set for the gate chain, which the three
        review aids did not follow until 4.0.0."""
        outside = tmp_path / "outside.md"
        outside.write_text("[@a2024]\n")

        rc = citation_coverage.main([str(outside), "--query", "x"])

        assert rc == 1
        assert "outside the content directory" in capsys.readouterr().err

    def test_a_missing_draft_is_refused(self, ledger_con, isolated_config, capsys):
        missing = config.DRAFTS_DIR / "nope.md"

        rc = citation_coverage.main([str(missing), "--query", "x"])

        assert rc == 1
        assert "No such draft" in capsys.readouterr().err
