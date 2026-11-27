import json
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta import config, dossier, style_check, style_language, style_rules
from tests.conftest import content_draft


@pytest.fixture
def draft(isolated_config):
    path = content_draft(isolated_config, "drafts/topic/survey.md")
    path.write_text("Prose that is simply wrong.\n", encoding="utf-8")
    return path


def write_scope(draft, line):
    scope_dir = dossier.dossier_dir(draft)
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / dossier.SCOPE_MD).write_text(
        f"# Scope\n\n- genre: survey\n{line}\n- created: 2026-08-14\n", encoding="utf-8"
    )


def fake_run(payload, stdout=None):
    def _run(argv, **kwargs):  # pylint: disable=unused-argument
        text = json.dumps(payload) if stdout is None else stdout
        return subprocess.CompletedProcess(argv, 0, stdout=text, stderr="")

    return _run


def finding(check="chitragupta.DefectMarkers", match="simply", line=3):
    return {
        "Check": check,
        "Match": match,
        "Line": line,
        "Message": f"'{match}' is a defect marker.",
        "Severity": "warning",
    }


class TestLanguageOf:
    def test_no_dossier_at_all_reads_as_unset(self, draft):
        assert style_language.language_of(draft) is None

    def test_a_dossier_without_a_language_line_reads_as_unset(self, draft):
        write_scope(draft, "- draft: x")
        assert style_language.language_of(draft) is None

    def test_the_shipped_not_settled_placeholder_reads_as_unset(self, draft):
        write_scope(draft, "- language: not settled -- a BCP-47 tag (`en-GB`, `en-IN`, `en-US`)")
        assert style_language.language_of(draft) is None

    def test_an_unrecognised_tag_is_still_reported_as_recorded(self, draft):
        write_scope(draft, "- language: fr-FR")
        assert style_language.language_of(draft) == "fr-FR"

    def test_an_empty_value_reads_as_unset(self, draft):
        write_scope(draft, "- language:")
        assert style_language.language_of(draft) is None

    @pytest.mark.parametrize("tag", ["en-GB", "en-US", "en-IN"])
    def test_a_recorded_tag_is_returned(self, draft, tag):
        write_scope(draft, f"- language: {tag}")
        assert style_language.language_of(draft) == tag

    def test_a_draft_outside_content_has_no_dossier_to_read(self, isolated_config, tmp_path):
        assert style_language.language_of(tmp_path / "loose.md") is None


class TestRuleFilter:
    def test_no_language_excludes_every_dialect_rule(self):
        expression = style_language.rule_filter(None)
        for rule in style_rules._ALL_DIALECT_RULES:
            assert f'.Name != "{rule}"' in expression

    def test_en_gb_keeps_only_the_gb_rule(self):
        expression = style_language.rule_filter("en-GB")
        assert "DialectGB" not in expression
        assert "DialectUS" in expression and "DialectIN" in expression

    def test_en_in_keeps_both_gb_and_in(self):
        expression = style_language.rule_filter("en-IN")
        assert "DialectGB" not in expression and "DialectIN" not in expression
        assert "DialectUS" in expression

    def test_the_filter_names_exclusions_so_a_new_rule_is_on_by_default(self):
        assert style_language.rule_filter("en-GB").count("!=") == 2


class TestRunVale:
    def test_missing_binary_is_reported_not_raised_past_the_cli(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: None)
        with pytest.raises(style_check.MissingBinary, match="advisory"):
            style_check.run_vale(draft, None)

    def test_findings_are_flattened_out_of_vales_per_file_payload(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({str(draft): [finding()]}))
        assert style_check.run_vale(draft, "en-GB")[0]["Match"] == "simply"

    def test_the_launch_goes_through_the_modules_own_seam(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({str(draft): [finding()]}))
        assert style_check.run_vale(draft, None)[0]["Match"] == "simply"

    def test_a_clean_run_produces_no_findings(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({}, stdout=""))
        assert style_check.run_vale(draft, None) == []

    def test_unreadable_output_blames_the_config_not_the_draft(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run(None, stdout="not json"))
        with pytest.raises(style_check.MissingBinary, match="could not read"):
            style_check.run_vale(draft, None)

    def test_the_filter_and_config_reach_the_command_line(self, draft):
        argv = style_check._vale_argv("/usr/bin/vale", draft, "en-US")
        assert argv[0] == "/usr/bin/vale"
        assert f"--config={config.VALE_CONFIG_PATH}" in argv
        assert any(a.startswith("--filter=") and "DialectGB" in a for a in argv)
        assert "--no-exit" in argv

    def test_a_latex_draft_reaches_vale_on_stdin_with_its_quotes_rewritten(
        self, tmp_path, monkeypatch
    ):
        draft = tmp_path / "c.tex"
        draft.write_text("They wrote ``a quote''.\n", encoding="utf-8")
        calls = []

        def _run(argv, **kwargs):
            calls.append((argv, kwargs.get("input"), kwargs.get("encoding")))
            return subprocess.CompletedProcess(argv, 0, stdout="{}", stderr="")

        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", _run)
        style_check.run_vale(draft, None)
        ((argv, stdin, encoding),) = calls
        assert "--ext=.tex" in argv and str(draft.resolve()) not in argv
        assert stdin == "They wrote \"\"a quote''.\n"
        assert encoding == "utf-8", "the locale's codec would refuse a non-ASCII draft"

    def test_the_draft_path_is_resolved_not_passed_as_typed(self, draft, monkeypatch):
        monkeypatch.chdir(draft.parent)
        argv = style_check._vale_argv("/usr/bin/vale", Path(draft.name), None)
        assert argv[-1] == str(draft.resolve())

    def test_a_nonzero_exit_with_empty_stdout_is_reported_not_swallowed(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")

        def _run(argv, **kwargs):  # pylint: disable=unused-argument
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="Fatal: bad filter")

        monkeypatch.setattr(style_check, "_run", _run)
        with pytest.raises(style_check.MissingBinary, match="Fatal: bad filter"):
            style_check.run_vale(draft, None)

    def test_a_nonzero_exit_with_findings_on_stdout_is_not_treated_as_an_error(
        self, draft, monkeypatch
    ):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        payload = {str(draft): [finding()]}

        def _run(argv, **kwargs):  # pylint: disable=unused-argument
            return subprocess.CompletedProcess(argv, 1, stdout=json.dumps(payload), stderr="")

        monkeypatch.setattr(style_check, "_run", _run)
        assert style_check.run_vale(draft, None)[0]["Match"] == "simply"


class TestCollapse:
    def test_repeats_of_one_token_become_one_finding_with_a_count(self):
        collapsed = style_check.collapse([finding(match="AI", line=n) for n in (5, 9, 20)])
        assert len(collapsed) == 1
        assert collapsed[0]["count"] == 3
        assert collapsed[0]["line"] == 5  # the first, so a reader starts there

    def test_different_tokens_stay_separate(self):
        collapsed = style_check.collapse([finding(match="simply"), finding(match="clearly")])
        assert {f["match"] for f in collapsed} == {"simply", "clearly"}

    def test_the_same_token_under_two_rules_stays_separate(self):
        collapsed = style_check.collapse(
            [
                finding(check="chitragupta.DefectMarkers", match="just"),
                finding(check="chitragupta.Just", match="just"),
            ]
        )
        assert len(collapsed) == 2

    def test_the_most_repeated_finding_sorts_first(self):
        collapsed = style_check.collapse(
            [finding(match="once", line=1)] + [finding(match="often", line=2)] * 4
        )
        assert collapsed[0]["match"] == "often"

    def test_a_finding_missing_every_optional_key_does_not_crash(self):
        assert style_check.collapse([{}])[0]["count"] == 1


class TestResolveLanguage:
    def test_the_flag_wins_over_everything(self, draft, monkeypatch):
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "en-US")
        write_scope(draft, "- language: en-IN")
        assert style_language.resolve_language(draft, "en-GB") == ("en-GB", "--language")

    def test_the_draft_wins_over_the_host_default(self, draft, monkeypatch):
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "en-US")
        write_scope(draft, "- language: en-GB")
        assert style_language.resolve_language(draft) == ("en-GB", "scope.md")

    def test_the_host_default_applies_when_the_draft_records_nothing(self, draft, monkeypatch):
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "en-GB")
        assert style_language.resolve_language(draft) == ("en-GB", "config.toml")

    def test_nothing_anywhere_is_reported_as_nothing(self, draft, monkeypatch):
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "")
        assert style_language.resolve_language(draft) == (None, "nothing")


class TestProposeLanguage:
    def _counts(self, monkeypatch, gb, us):
        def _run(draft, language):  # pylint: disable=unused-argument
            n = gb if language == "en-GB" else us
            return [finding(check="chitragupta.DialectGB")] * n

        monkeypatch.setattr(style_check, "run_vale", _run)

    def test_the_dialect_with_fewer_findings_is_proposed(self, draft, monkeypatch):
        self._counts(monkeypatch, gb=0, us=13)
        assert style_check.propose_language(draft)[0] == "en-GB"

    def test_a_tie_proposes_nothing(self, draft, monkeypatch):
        self._counts(monkeypatch, gb=0, us=0)
        assert style_check.propose_language(draft) is None

    def test_only_dialect_findings_are_counted(self, draft, monkeypatch):
        def _run(draft_, language):  # pylint: disable=unused-argument
            noise = [finding(check="chitragupta.Acronyms", match="ISO")] * 18
            return noise + (
                [] if language == "en-GB" else [finding(check="chitragupta.DialectUS")] * 13
            )

        monkeypatch.setattr(style_check, "run_vale", _run)
        best, counts = style_check.propose_language(draft)
        assert (best, counts) == ("en-GB", {"en-GB": 0, "en-US": 13})


class TestReport:
    def _payload(self, draft, language=None, source="nothing", findings=(), proposal=None):
        return {
            "draft": str(draft),
            "language": language,
            "language_source": source,
            "findings": list(findings),
            "proposed_language": proposal,
        }

    def test_an_unset_dialect_is_stated_not_silently_skipped(self, draft):
        lines = style_check.report(draft, self._payload(draft))
        assert any("not checked" in line for line in lines)

    def test_a_recorded_dialect_names_where_it_came_from(self, draft):
        lines = style_check.report(draft, self._payload(draft, "en-GB", "config.toml"))
        assert any("en-GB (from config.toml)" in line for line in lines)

    def test_a_tag_with_no_rules_says_nothing_was_checked(self, draft):
        lines = style_check.report(draft, self._payload(draft, "fr-FR", "scope.md"))
        assert any("no rules for that tag" in line for line in lines)

    def test_a_proposal_prints_the_command_that_records_it(self, draft):
        proposal = {"language": "en-GB", "findings_by_language": {"en-GB": 0, "en-US": 13}}
        lines = style_check.report(draft, self._payload(draft, proposal=proposal))
        assert any("dossier set-language en-GB" in line for line in lines)
        assert any("en-US: 13" in line for line in lines)

    def test_a_clean_draft_says_so(self, draft):
        lines = style_check.report(draft, self._payload(draft, "en-GB", "scope.md"))
        assert any("no findings" in line for line in lines)

    def test_a_repeated_finding_shows_its_count(self, draft):
        collapsed = style_check.collapse([finding(), finding()])
        lines = style_check.report(draft, self._payload(draft, "en-GB", "scope.md", collapsed))
        assert any("(x2)" in line for line in lines)

    def test_a_single_finding_shows_no_count(self, draft):
        collapsed = style_check.collapse([finding()])
        lines = style_check.report(draft, self._payload(draft, "en-GB", "scope.md", collapsed))
        assert not any("(x" in line for line in lines)

    def test_the_report_says_it_is_not_a_gate(self, draft):
        collapsed = style_check.collapse([finding()])
        lines = style_check.report(draft, self._payload(draft, "en-GB", "scope.md", collapsed))
        assert any("not a gate" in line for line in lines)


class TestMain:
    def test_it_exits_zero_with_findings(self, draft, monkeypatch, capsys):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({str(draft): [finding()] * 3}))
        assert style_check.main([str(draft)]) == 0
        assert "not a gate" in capsys.readouterr().out

    def test_it_exits_zero_with_no_findings(self, draft, monkeypatch, capsys):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({}))
        assert style_check.main([str(draft)]) == 0
        assert "no findings" in capsys.readouterr().out

    def test_a_missing_binary_warns_and_still_exits_zero(self, draft, monkeypatch, capsys):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: None)
        assert style_check.main([str(draft)]) == 0
        assert "WARNING" in capsys.readouterr().out

    def test_a_missing_binary_stops_after_the_first_draft(self, draft, monkeypatch, capsys):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: None)
        style_check.main([str(draft), str(draft)])
        assert capsys.readouterr().out.count("WARNING") == 1

    def test_an_unreadable_draft_warns_and_still_exits_zero(
        self, isolated_config, monkeypatch, capsys
    ):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")

        def _raise(*_args, **_kwargs):
            raise OSError("no such file")

        monkeypatch.setattr(style_check, "_run", _raise)
        assert style_check.main(["content/drafts/gone.md"]) == 0
        assert "WARNING" in capsys.readouterr().out

    def test_a_broken_exceptions_file_is_a_usage_error_not_a_finding(
        self, draft, monkeypatch, capsys
    ):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({}))

        def _broken(*_args, **_kwargs):
            raise ValueError("style_exceptions.toml: malformed TOML")

        monkeypatch.setattr(style_check, "check", _broken)
        assert style_check.main([str(draft)]) == 2
        captured = capsys.readouterr()
        assert "style_exceptions.toml" in captured.err
        assert captured.out == ""

    def test_json_carries_the_findings_and_the_not_a_verdict_notice(
        self, draft, monkeypatch, capsys
    ):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({str(draft): [finding()]}))
        assert style_check.main([str(draft), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "not a gate" in payload["notice"]
        assert payload["drafts"][0]["findings"][0]["match"] == "simply"

    def test_json_reports_a_missing_binary_as_a_warning_not_an_empty_result(
        self, draft, monkeypatch, capsys
    ):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: None)
        style_check.main([str(draft), "--json"])
        assert json.loads(capsys.readouterr().out)["warnings"]

    def test_check_returns_the_language_it_used(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.programs, "resolve_program", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(style_check, "_run", fake_run({}))
        write_scope(draft, "- language: en-IN")
        assert style_check.check(draft)["language"] == "en-IN"


vale_available = shutil.which("vale") is not None


@pytest.mark.skipif(not vale_available, reason="vale not installed")
class TestAgainstRealVale:
    FIXTURES = Path(__file__).resolve().parent / "fixtures" / "style"

    @pytest.mark.parametrize("name", ["exemptions.md", "exemptions.tex"])
    def test_every_marker_inside_an_exemption_is_ignored(self, name):
        assert style_check.check(self.FIXTURES / name)["findings"] == []

    def test_prose_outside_an_exemption_is_still_reported(self, tmp_path):
        draft = tmp_path / "loose.md"
        draft.write_text("This is simply wrong.\n", encoding="utf-8")
        matches = [f["match"] for f in style_check.check(draft)["findings"]]
        assert "simply" in matches

    def _matches(self, tmp_path, name, text):
        draft = tmp_path / name
        draft.write_text(text, encoding="utf-8")
        found = style_check.check(draft, override="en-GB")["findings"]
        return [f["match"] for f in found]

    @staticmethod
    def _empty_vocabulary(tmp_path, monkeypatch, body=""):
        vocab = tmp_path / "acronyms.toml"
        vocab.write_text(body, encoding="utf-8")
        monkeypatch.setattr(config, "ACRONYMS_PATH", vocab)

    def test_latex_command_names_are_not_prose(self, tmp_path):
        text = "\\begin{center}\n\\centering\nInside, this is simply the center.\n\\end{center}\n"
        assert self._matches(tmp_path, "c.tex", text) == ["simply", "center"]

    def test_emph_argument_is_still_prose(self, tmp_path):
        assert "obviously" in self._matches(tmp_path, "e.tex", "\\emph{obviously} so.\n")

    def test_exercise_grade_is_not_a_marker(self, tmp_path):
        text = "**Exercise 1 (Objective 2, easy).** Classify.\n"
        assert self._matches(tmp_path, "x.md", text) == []

    def test_other_words_in_a_bold_exercise_heading_are_still_prose(self, tmp_path):
        text = "**Exercise 3: why this is obviously wrong**\n"
        assert "obviously" in self._matches(tmp_path, "z.md", text)

    def test_easy_in_prose_is_still_a_marker(self, tmp_path):
        assert "easy" in self._matches(tmp_path, "y.md", "This is easy to see.\n")

    def test_lower_case_expansion_counts_as_expanded(self, tmp_path, monkeypatch):
        self._empty_vocabulary(tmp_path, monkeypatch)
        text = "We use supervisory control and data acquisition (SCADA). SCADA again.\n"
        draft = tmp_path / "s.md"
        draft.write_text(text, encoding="utf-8")
        found = style_check.check(draft, override="en-GB")["findings"]
        assert not [f for f in found if f["rule"] == "chitragupta.Acronyms"]

    def test_unexpanded_acronym_is_still_reported(self, tmp_path, monkeypatch):
        self._empty_vocabulary(tmp_path, monkeypatch)
        draft = tmp_path / "f.md"
        draft.write_text("FOOB is unexpanded.\n", encoding="utf-8")
        found = style_check.check(draft, override="en-GB")["findings"]
        assert [f for f in found if f["rule"] == "chitragupta.Acronyms"]

    def test_declared_term_is_exempt_under_en_gb(self, tmp_path, monkeypatch):
        self._empty_vocabulary(tmp_path, monkeypatch, 'UML = "Unified Modeling Language"\n')
        text = "The Unified Modeling Language is used.\n"
        assert self._matches(tmp_path, "t.md", text) == []
        assert "Modeling" in self._matches(tmp_path, "u.md", "Modeling is used.\n")


class TestSetLanguageRoundTrip:
    def test_setting_a_language_makes_style_check_read_it(self, draft):
        dossier.init(draft, "survey")
        dossier.set_language(draft, "en-IN")
        assert style_language.language_of(draft) == "en-IN"

    def test_it_replaces_the_shipped_placeholder_rather_than_adding_a_line(self, draft):
        dossier.init(draft, "survey")
        dossier.set_language(draft, "en-GB")
        scope = (dossier.dossier_dir(draft) / dossier.SCOPE_MD).read_text(encoding="utf-8")
        assert scope.count("- language:") == 1

    def test_it_inserts_the_line_into_a_dossier_that_predates_it(self, draft):
        write_scope(draft, "- draft: x")
        dossier.set_language(draft, "en-GB")
        assert style_language.language_of(draft) == "en-GB"

    def test_it_refuses_something_that_is_not_a_language_tag(self, draft):
        dossier.init(draft, "survey")
        with pytest.raises(ValueError, match="BCP-47"):
            dossier.set_language(draft, "british")

    def test_it_refuses_a_draft_with_no_dossier(self, draft):
        with pytest.raises(FileNotFoundError, match="dossier init"):
            dossier.set_language(draft, "en-GB")

    def test_the_cli_reports_what_it_wrote(self, draft, capsys):
        dossier.init(draft, "survey")
        assert dossier.main(["set-language", str(draft), "en-GB"]) == 0
        assert "en-GB" in capsys.readouterr().out

    def test_the_cli_exits_one_on_a_bad_tag_without_a_traceback(self, draft, capsys):
        dossier.init(draft, "survey")
        assert dossier.main(["set-language", str(draft), "nonsense!"]) == 1
        assert "BCP-47" in capsys.readouterr().err


class TestTheRuleRegistry:
    def test_every_style_module_with_findings_is_registered(self):
        package = Path(style_check.__file__).parent
        modules = sorted(
            f"chitragupta.{path.stem}"
            for path in package.glob("style_*.py")
            if "\ndef findings(" in path.read_text(encoding="utf-8")
        )
        assert modules, "the scan found no style rule modules"
        registered = sorted(check.__module__ for check in style_rules.PYTHON_CHECKS)
        assert registered == modules

    def test_check_runs_whatever_the_registry_holds(self, draft, monkeypatch):
        mine = {"rule": "demo", "match": "x", "line": 1, "repair": "review"}
        monkeypatch.setattr(style_check, "PYTHON_CHECKS", (lambda path: [mine],))
        monkeypatch.setattr(style_check, "run_vale", lambda d, lang: [])
        assert style_check.check(draft, propose=False)["findings"] == [mine]


class TestCheckWiring:
    def test_an_unset_draft_gets_a_proposal(self, draft, monkeypatch):
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "")
        monkeypatch.setattr(
            style_check,
            "run_vale",
            lambda d, lang: (
                [] if lang in (None, "en-GB") else [finding(check="chitragupta.DialectUS")]
            ),
        )
        assert style_check.check(draft)["proposed_language"]["language"] == "en-GB"

    def test_a_draft_with_a_dialect_gets_no_proposal(self, draft, monkeypatch):
        write_scope(draft, "- language: en-GB")
        monkeypatch.setattr(style_check, "run_vale", lambda d, lang: [])
        assert style_check.check(draft)["proposed_language"] is None

    def test_an_inconclusive_draft_gets_no_proposal(self, draft, monkeypatch):
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "")
        monkeypatch.setattr(style_check, "run_vale", lambda d, lang: [])
        assert style_check.check(draft)["proposed_language"] is None

    def test_propose_false_skips_the_extra_vale_runs_even_when_unset(self, draft, monkeypatch):
        monkeypatch.setattr(config, "STYLE_LANGUAGE", "")
        calls = []

        def _run(d, lang):  # pylint: disable=unused-argument
            calls.append(lang)
            return []

        monkeypatch.setattr(style_check, "run_vale", _run)
        result = style_check.check(draft, propose=False)
        assert result["proposed_language"] is None
        assert calls == [None]  # only the main check's run, no en-GB/en-US probes

    def test_findings_include_acronym_drift_alongside_vales_own(self, draft, monkeypatch):
        write_scope(draft, "- language: en-GB")
        monkeypatch.setattr(style_check, "run_vale", lambda d, lang: [finding()])

        def drift(_draft):
            return [
                {
                    "rule": "chitragupta.AcronymDrift",
                    "match": "DT",
                    "line": 0,
                    "message": "drifted",
                    "severity": "suggestion",
                    "count": 1,
                }
            ]

        monkeypatch.setattr(style_check, "PYTHON_CHECKS", (drift, *style_rules.PYTHON_CHECKS[1:]))
        findings = style_check.check(draft)["findings"]
        assert {f["rule"] for f in findings} == {
            "chitragupta.DefectMarkers",
            "chitragupta.AcronymDrift",
        }


class TestWithRepair:
    @staticmethod
    def _repair(rule: str, source: str = "scope.md", match: str = "x") -> str:
        found = {"rule": rule, "match": match, "line": 1, "count": 1}
        return style_rules.with_repair([found], source)[0]["repair"]

    def test_just_is_left_for_a_person(self):
        assert self._repair("chitragupta.Just") == "review"

    def test_a_defect_marker_is_still_repaired_unattended(self):
        assert self._repair("chitragupta.DefectMarkers") == "edit"

    def test_a_dialect_from_config_is_left_for_a_person(self):
        assert self._repair("chitragupta.DialectGB", "config.toml") == "review"

    def test_a_dialect_the_author_declared_is_repaired_unattended(self):
        assert self._repair("chitragupta.DialectGB", "scope.md") == "edit"

    def test_a_capitalised_dialect_match_is_left_for_a_person(self):
        assert self._repair("chitragupta.DialectGB", "scope.md", "Modeling") == "review"

    def test_a_lower_case_dialect_match_is_still_repaired(self):
        assert self._repair("chitragupta.DialectGB", "scope.md", "modeling") == "edit"

    def test_capitalisation_does_not_touch_other_rules(self):
        assert self._repair("chitragupta.DefectMarkers", "scope.md", "Simply") == "edit"
