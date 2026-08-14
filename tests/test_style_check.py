"""`python -m src.draft style`: which rules apply, and what it reports.

What Vale itself matches is Vale's business and is not re-tested here --
that is what `assets/vale/` and the bench entry are for. What *is* tested
is everything this repository decides: which dialect rule a draft gets,
what happens when nobody chose one, how repeated findings collapse, and
that the command exits 0 whatever it finds. The last one is the load-bearing
test: docs/ARCHITECTURE.md's "Layer 4" and DEVELOPER-AGENTS.md both turn on
this check never becoming a gate, and an exit code is how that would slip.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src import config, dossier, style_check
from tests.conftest import content_draft


@pytest.fixture
def draft(isolated_config):
    path = content_draft(isolated_config, "drafts/topic/survey.md")
    path.write_text("Prose that is simply wrong.\n", encoding="utf-8")
    return path


def write_scope(draft, line):
    """Put one `- language:` line into this draft's dossier scope.md."""
    scope_dir = dossier.dossier_dir(draft)
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / dossier.SCOPE_MD).write_text(
        f"# Scope\n\n- genre: survey\n{line}\n- created: 2026-08-14\n", encoding="utf-8"
    )


def fake_run(payload, stdout=None):
    """A `subprocess.run` returning `payload` as Vale's JSON on stdout."""
    def _run(argv, **kwargs):  # pylint: disable=unused-argument
        text = json.dumps(payload) if stdout is None else stdout
        return subprocess.CompletedProcess(argv, 0, stdout=text, stderr="")
    return _run


def finding(check="chitragupta.DefectMarkers", match="simply", line=3):
    return {"Check": check, "Match": match, "Line": line,
            "Message": f"'{match}' is a defect marker.", "Severity": "warning"}


class TestLanguageOf:
    def test_no_dossier_at_all_reads_as_unset(self, draft):
        assert style_check.language_of(draft) is None

    def test_a_dossier_without_a_language_line_reads_as_unset(self, draft):
        """Every dossier written before 5.12.0 is this case, including the
        fifteen restored with the example book -- so it is the common one,
        not an edge."""
        write_scope(draft, "- draft: x")
        assert style_check.language_of(draft) is None

    def test_the_shipped_not_settled_placeholder_reads_as_unset(self, draft):
        """The placeholder *contains* real tags, to tell a human what shape
        to write. Taking the first word is what stops "not settled -- a
        BCP-47 tag (`en-GB`, ...)" being read as en-GB."""
        write_scope(draft, "- language: not settled -- a BCP-47 tag (`en-GB`, `en-IN`, `en-US`)")
        assert style_check.language_of(draft) is None

    def test_an_unrecognised_tag_reads_as_unset(self, draft):
        write_scope(draft, "- language: fr-FR")
        assert style_check.language_of(draft) is None

    def test_an_empty_value_reads_as_unset(self, draft):
        write_scope(draft, "- language:")
        assert style_check.language_of(draft) is None

    @pytest.mark.parametrize("tag", ["en-GB", "en-US", "en-IN"])
    def test_a_recorded_tag_is_returned(self, draft, tag):
        write_scope(draft, f"- language: {tag}")
        assert style_check.language_of(draft) == tag

    def test_a_draft_outside_content_has_no_dossier_to_read(self, isolated_config, tmp_path):
        """dossier_dir refuses a path outside content/. That is a fine
        reason to skip the dialect rules and no reason to crash: the rest
        of the check still applies to the prose."""
        assert style_check.language_of(tmp_path / "loose.md") is None


class TestRuleFilter:
    def test_no_language_excludes_every_dialect_rule(self):
        expression = style_check.rule_filter(None)
        for rule in style_check._ALL_DIALECT_RULES:
            assert f'.Name != "{rule}"' in expression

    def test_en_gb_keeps_only_the_gb_rule(self):
        expression = style_check.rule_filter("en-GB")
        assert "DialectGB" not in expression
        assert 'DialectUS' in expression and 'DialectIN' in expression

    def test_en_in_keeps_both_gb_and_in(self):
        """en-IN is en-GB plus the -ize check, not an alias for either:
        British English accepts Oxford -ize and Indian English does not."""
        expression = style_check.rule_filter("en-IN")
        assert "DialectGB" not in expression and "DialectIN" not in expression
        assert "DialectUS" in expression

    def test_the_filter_names_exclusions_so_a_new_rule_is_on_by_default(self):
        """A rule added to assets/vale/ later must be enabled without
        touching this module. An inclusion list would silently disable it,
        and a report of zero findings is where that hides."""
        assert style_check.rule_filter("en-GB").count("!=") == 2


class TestRunVale:
    def test_missing_binary_is_reported_not_raised_past_the_cli(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.shutil, "which", lambda _: None)
        with pytest.raises(style_check.MissingBinary, match="advisory"):
            style_check.run_vale(draft, None)

    def test_findings_are_flattened_out_of_vales_per_file_payload(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(subprocess, "run", fake_run({str(draft): [finding()]}))
        assert style_check.run_vale(draft, "en-GB")[0]["Match"] == "simply"

    def test_a_clean_run_produces_no_findings(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(subprocess, "run", fake_run({}, stdout=""))
        assert style_check.run_vale(draft, None) == []

    def test_unreadable_output_blames_the_config_not_the_draft(self, draft, monkeypatch):
        """A parse failure means the vendored style is broken. Swallowing
        it would report zero findings, which reads as a clean draft."""
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(subprocess, "run", fake_run(None, stdout="not json"))
        with pytest.raises(style_check.MissingBinary, match="could not read"):
            style_check.run_vale(draft, None)

    def test_the_filter_and_config_reach_the_command_line(self, draft):
        argv = style_check._vale_argv(draft, "en-US")
        assert argv[0] == "vale"
        assert f"--config={config.VALE_CONFIG_PATH}" in argv
        assert any(a.startswith("--filter=") and "DialectGB" in a for a in argv)
        assert "--no-exit" in argv


class TestCollapse:
    def test_repeats_of_one_token_become_one_finding_with_a_count(self):
        """Measured: a chapter that never expands "AI" produced 45
        identical findings. That is one thing to fix, not 45."""
        collapsed = style_check.collapse([finding(match="AI", line=n) for n in (5, 9, 20)])
        assert len(collapsed) == 1
        assert collapsed[0]["count"] == 3
        assert collapsed[0]["line"] == 5  # the first, so a reader starts there

    def test_different_tokens_stay_separate(self):
        collapsed = style_check.collapse([finding(match="simply"), finding(match="clearly")])
        assert {f["match"] for f in collapsed} == {"simply", "clearly"}

    def test_the_same_token_under_two_rules_stays_separate(self):
        collapsed = style_check.collapse([
            finding(check="chitragupta.DefectMarkers", match="just"),
            finding(check="chitragupta.Just", match="just"),
        ])
        assert len(collapsed) == 2

    def test_the_most_repeated_finding_sorts_first(self):
        collapsed = style_check.collapse(
            [finding(match="once", line=1)] + [finding(match="often", line=2)] * 4
        )
        assert collapsed[0]["match"] == "often"

    def test_a_finding_missing_every_optional_key_does_not_crash(self):
        """Vale's JSON is a contract this repo does not own. A key that
        moves in a later release should degrade, not raise."""
        assert style_check.collapse([{}])[0]["count"] == 1


class TestReport:
    def test_an_unset_dialect_is_stated_not_silently_skipped(self, draft):
        """A report that omits dialect findings because nobody set a
        target looks exactly like a draft that has none."""
        lines = style_check.report(draft, None, [])
        assert any("not checked" in line for line in lines)

    def test_a_recorded_dialect_is_named(self, draft):
        assert any("en-GB" in line for line in style_check.report(draft, "en-GB", []))

    def test_a_clean_draft_says_so(self, draft):
        assert any("no findings" in line for line in style_check.report(draft, "en-GB", []))

    def test_a_repeated_finding_shows_its_count(self, draft):
        collapsed = style_check.collapse([finding(), finding()])
        assert any("(x2)" in line for line in style_check.report(draft, "en-GB", collapsed))

    def test_a_single_finding_shows_no_count(self, draft):
        collapsed = style_check.collapse([finding()])
        assert not any("(x" in line for line in style_check.report(draft, "en-GB", collapsed))

    def test_the_report_says_it_is_not_a_gate(self, draft):
        collapsed = style_check.collapse([finding()])
        assert any("not a gate" in line for line in style_check.report(draft, None, collapsed))


class TestMain:
    def test_it_exits_zero_with_findings(self, draft, monkeypatch, capsys):
        """The single most important assertion in this file. SOUL.md and
        DEVELOPER-AGENTS.md both turn on this check never gating, and a
        non-zero exit is exactly how it would become one."""
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(subprocess, "run", fake_run({str(draft): [finding()] * 3}))
        assert style_check.main([str(draft)]) == 0
        assert "not a gate" in capsys.readouterr().out

    def test_it_exits_zero_with_no_findings(self, draft, monkeypatch, capsys):
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(subprocess, "run", fake_run({}))
        assert style_check.main([str(draft)]) == 0
        assert "no findings" in capsys.readouterr().out

    def test_a_missing_binary_warns_and_still_exits_zero(self, draft, monkeypatch, capsys):
        """render_output's bargain: an absent optional tool costs you this
        report and nothing else."""
        monkeypatch.setattr(style_check.shutil, "which", lambda _: None)
        assert style_check.main([str(draft)]) == 0
        assert "WARNING" in capsys.readouterr().out

    def test_a_missing_binary_stops_after_the_first_draft(self, draft, monkeypatch, capsys):
        """It will not appear between two drafts, so repeating the same
        warning once per draft is noise."""
        monkeypatch.setattr(style_check.shutil, "which", lambda _: None)
        style_check.main([str(draft), str(draft)])
        assert capsys.readouterr().out.count("WARNING") == 1

    def test_an_unreadable_draft_warns_and_still_exits_zero(self, isolated_config,
                                                            monkeypatch, capsys):
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")

        def _raise(*_args, **_kwargs):
            raise OSError("no such file")
        monkeypatch.setattr(subprocess, "run", _raise)
        assert style_check.main(["content/drafts/gone.md"]) == 0
        assert "WARNING" in capsys.readouterr().out

    def test_json_carries_the_findings_and_the_not_a_verdict_notice(self, draft,
                                                                    monkeypatch, capsys):
        """The hook and docs/AUTO-IMPROVEMENT.md's agenda both read this
        rather than the printed form."""
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(subprocess, "run", fake_run({str(draft): [finding()]}))
        assert style_check.main([str(draft), "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert "not a gate" in payload["notice"]
        assert payload["drafts"][0]["findings"][0]["match"] == "simply"

    def test_json_reports_a_missing_binary_as_a_warning_not_an_empty_result(
            self, draft, monkeypatch, capsys):
        monkeypatch.setattr(style_check.shutil, "which", lambda _: None)
        style_check.main([str(draft), "--json"])
        assert json.loads(capsys.readouterr().out)["warnings"]

    def test_check_returns_the_language_it_used(self, draft, monkeypatch):
        monkeypatch.setattr(style_check.shutil, "which", lambda _: "/usr/bin/vale")
        monkeypatch.setattr(subprocess, "run", fake_run({}))
        write_scope(draft, "- language: en-IN")
        assert style_check.check(draft)["language"] == "en-IN"


vale_available = shutil.which("vale") is not None


@pytest.mark.skipif(not vale_available, reason="vale not installed")
class TestAgainstRealVale:
    """The only place the vendored style is exercised by the real binary.

    Skipped where Vale is absent, exactly as tests/test_render_output.py
    skips where pandoc is -- and the same reason CI's Windows leg holds a
    95 coverage floor rather than the full 100. CI's lint job runs the
    same fixtures through the same command.
    """

    FIXTURES = Path(__file__).resolve().parent / "fixtures" / "style"

    @pytest.mark.parametrize("name", ["exemptions.md", "exemptions.tex"])
    def test_every_marker_inside_an_exemption_is_ignored(self, name):
        """Both fixtures are wall-to-wall defect markers and en-US
        spellings, every one inside a code fence, an inline span, a block
        quote, a references section or a LaTeX verbatim block. A finding
        here is an exemption that has broken."""
        assert style_check.check(self.FIXTURES / name)["findings"] == []

    def test_prose_outside_an_exemption_is_still_reported(self, tmp_path):
        """The complement of the test above, and the one that stops it
        passing for the wrong reason: a config that exempted everything
        would satisfy the fixtures too."""
        draft = tmp_path / "loose.md"
        draft.write_text("This is simply wrong.\n", encoding="utf-8")
        matches = [f["match"] for f in style_check.check(draft)["findings"]]
        assert "simply" in matches
