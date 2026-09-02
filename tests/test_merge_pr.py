"""`scripts/merge_pr.py`: the commit body a person no longer has to remember
at merge time (#357).

DEVELOPER-AGENTS.md's "Merging" section already established that no
`squash_merge_commit_message` value can turn a PR description into a commit
body -- none of `PR_BODY`/`COMMIT_MESSAGES`/`BLANK` transforms text, so the
body has to be *supplied* at merge time. This is that supply step, made a
command instead of a paragraph a session has to still be holding at the end
of a long run.

The composed body is pulled from the PR's own `## Description` section
rather than the branch's raw commits, because `## Description` is where
this repository's own PRs already carry a well-formed bulleted list (see
e.g. #366's body) -- concatenating raw commit subjects is the same
low-quality mechanism the old `COMMIT_MESSAGES` default used, just rebuilt
by hand. The section is not itself always bullets-only (the template's own
prompt asks for "why this change", so a prose lead-in before the bullets is
the common shape, not an edge case) -- so extraction pulls just the bullet
block out of the surrounding prose, rather than requiring the whole section
to already be in the target shape.
"""

import importlib.util
import subprocess
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def merge_pr():
    spec = importlib.util.spec_from_file_location("merge_pr", REPO_ROOT / "scripts" / "merge_pr.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSections:
    def test_it_splits_into_heading_content_pairs_in_order(self, merge_pr):
        body = "## Type of Change\n\n- [x] Bug fix\n\n## Description\n\nSome why.\n"
        assert merge_pr._sections(body) == [
            ("Type of Change", "\n\n- [x] Bug fix\n\n"),
            ("Description", "\n\nSome why.\n"),
        ]

    def test_a_body_with_no_headings_yields_nothing(self, merge_pr):
        assert merge_pr._sections("just some text, no ## headings\n") == []

    def test_it_does_not_assume_the_templates_exact_heading_names(self, merge_pr):
        """#365 used `## Summary` where the template says `## Description`
        -- splitting on every heading rather than looking for one named
        section is what survives that."""
        body = "## Summary\n\n- A real bullet.\n"
        assert merge_pr._sections(body) == [("Summary", "\n\n- A real bullet.\n")]


class TestBulletsIn:
    def test_a_prose_only_section_has_no_bullets(self, merge_pr):
        assert merge_pr._bullets_in("Just an explanation, no list here.") == []

    def test_bullets_after_a_prose_lead_in_are_found(self, merge_pr):
        text = (
            "Closes #360. This PR pays those four:\n\n"
            "- First change, concrete.\n"
            "- Second change, concrete.\n"
        )
        assert merge_pr._bullets_in(text) == [
            "First change, concrete.",
            "Second change, concrete.",
        ]

    def test_a_wrapped_continuation_line_joins_the_bullet_above(self, merge_pr):
        text = (
            "- `chitragupta/dossier/_cli.py::main` (54 statements): one\n"
            "  `_add_*_parser(sub)` function per subcommand.\n"
        )
        assert merge_pr._bullets_in(text) == [
            "`chitragupta/dossier/_cli.py::main` (54 statements): one "
            "`_add_*_parser(sub)` function per subcommand."
        ]

    def test_a_trailing_prose_paragraph_after_the_bullets_is_dropped(self, merge_pr):
        text = (
            "- First change.\n"
            "- Second change.\n\n"
            "**The remaining three are out of scope**, for stated reasons.\n"
        )
        assert merge_pr._bullets_in(text) == ["First change.", "Second change."]

    def test_dash_lines_inside_a_fenced_block_are_not_bullets(self, merge_pr):
        # A Description quoting a YAML/Markdown snippet carries dash lines
        # that are code, not content; scraping them lands the snippet
        # verbatim in main's permanent commit history -- the exact
        # non-conforming body this script exists to prevent.
        text = (
            "- Real change, concrete.\n\n"
            "```yaml\n"
            "- not: a bullet\n"
            "- also: code\n"
            "```\n\n"
            "- Second real change.\n"
        )
        assert merge_pr._bullets_in(text) == [
            "Real change, concrete.",
            "Second real change.",
        ]

    def test_tilde_fences_are_respected_too(self, merge_pr):
        text = "~~~\n- code line\n~~~\n\n- Real change.\n"
        assert merge_pr._bullets_in(text) == ["Real change."]

    def test_an_unclosed_fence_swallows_the_rest_of_the_section(self, merge_pr):
        # CommonMark runs an unclosed fence to the end of the block; a
        # dash line after one is still code.
        text = "- Real change.\n\n```\n- code line\n"
        assert merge_pr._bullets_in(text) == ["Real change."]

    def test_a_wrapped_bullet_mentioning_a_fence_is_not_truncated(self, merge_pr):
        # Seen live on PR 518's dry run: a bullet wrapping onto an
        # indented continuation line that *begins* with ~~~ read as an
        # unclosed fence opener, truncating the bullet and swallowing the
        # rest of the section. Only a column-0 marker toggles: an indented
        # dash line never matched _BULLET_RE in the first place, so
        # nested-in-bullet fences need no stripping here.
        text = "- Anchored per CommonMark (both ``` and\n  ~~~), so nothing shifts.\n"
        assert merge_pr._bullets_in(text) == [
            "Anchored per CommonMark (both ``` and ~~~), so nothing shifts."
        ]

    def test_a_checkbox_bullet_is_never_content(self, merge_pr):
        # The heading exclusion catches the template's three checklist
        # sections by name; a checkbox under any *other* heading (a
        # hand-added "Reviewer checklist") is still a checkbox, not a
        # commit-body bullet.
        text = "- [x] Ticked a box.\n- [ ] Unticked box.\n- Real change.\n"
        assert merge_pr._bullets_in(text) == ["Real change."]

    def test_a_star_marker_is_normalized_like_a_dash(self, merge_pr):
        assert merge_pr._bullets_in("* Fix the thing.\n") == ["Fix the thing."]

    def test_two_separate_bullet_blocks_both_contribute(self, merge_pr):
        text = "- First.\n\nsome connecting prose\n\n- Second.\n"
        assert merge_pr._bullets_in(text) == ["First.", "Second."]


class TestBulletsFromDescription:
    def test_checkbox_lines_under_type_of_change_are_not_content(self, merge_pr):
        body = "## Type of Change\n\n- [x] Bug fix\n\n## Description\n\nJust prose.\n"
        assert merge_pr.bullets_from_description(body) == []

    def test_checkbox_lines_under_test_plan_are_not_content(self, merge_pr):
        body = "## Description\n\n- Fix the thing.\n\n## Test plan\n\n- [x] Full suite passes\n"
        assert merge_pr.bullets_from_description(body) == ["Fix the thing."]

    def test_it_falls_through_to_a_differently_named_section(self, merge_pr):
        """`## Summary` in place of the template's `## Description`
        (#365's actual shape) still contributes its bullets."""
        body = "## Type of Change\n\n- [x] Docs\n\n## Summary\n\n- Fix the thing.\n"
        assert merge_pr.bullets_from_description(body) == ["Fix the thing."]

    def test_bullets_from_two_content_sections_are_both_kept_in_order(self, merge_pr):
        body = (
            "## Description\n\n- First.\n\n"
            "## What changed, from the user's point of view\n\n- Second.\n"
        )
        assert merge_pr.bullets_from_description(body) == ["First.", "Second."]


class TestBulletsFromCommits:
    def test_each_subject_becomes_one_bullet(self, merge_pr):
        assert merge_pr.bullets_from_commits(["Fix the thing", "Add the other thing"]) == [
            "Fix the thing",
            "Add the other thing",
        ]

    def test_duplicate_subjects_are_not_repeated(self, merge_pr):
        assert merge_pr.bullets_from_commits(["Fix it", "Fix it"]) == ["Fix it"]

    def test_order_is_preserved(self, merge_pr):
        assert merge_pr.bullets_from_commits(["b", "a", "b", "c"]) == ["b", "a", "c"]

    def test_blank_subjects_are_dropped(self, merge_pr):
        assert merge_pr.bullets_from_commits(["Fix it", "  ", ""]) == ["Fix it"]


class TestComposeBody:
    PR_BODY = (
        "## Description\n\n"
        "Closes #1. Some rationale.\n\n"
        "- Fix the first thing.\n"
        "- Fix the second thing.\n\n"
        "## Impact\n\nnone\n"
    )

    def test_it_prefers_the_description_bullets(self, merge_pr):
        text, source = merge_pr.compose_body(self.PR_BODY, ["irrelevant commit subject"])
        assert text == "- Fix the first thing.\n- Fix the second thing."
        assert source == "description"

    def test_it_falls_back_to_commits_when_the_description_has_no_bullets(self, merge_pr):
        body = "## Description\n\nJust prose, no list.\n\n## Impact\n\nnone\n"
        text, source = merge_pr.compose_body(body, ["Fix the reconcile drift", "Fix it"])
        assert text == "- Fix the reconcile drift\n- Fix it"
        assert source == "commits"

    def test_a_missing_description_section_also_falls_back(self, merge_pr):
        text, source = merge_pr.compose_body("## Impact\n\nnone\n", ["Fix it"])
        assert text == "- Fix it"
        assert source == "commits"

    def test_a_single_commit_branch_still_prefers_the_bulleted_description(self, merge_pr):
        """The regression this design exists to avoid: a single-commit
        branch's raw subject is one bullet restating the (sometimes
        truncated) commit title, almost the `* <title>` preamble the
        issue exists to kill. A real PR body's bullets must win over it
        even though there is only one commit to fall back to."""
        body = (
            "## Type of Change\n\n- [x] Documentation update\n\n"
            "## Description\n\nCloses #1. Some rationale:\n\n"
            "- Fix the first thing.\n- Fix the second thing.\n\n"
            "## Test plan\n\n- [x] Full suite passes\n"
        )
        text, source = merge_pr.compose_body(
            body, ["State OCR's Markdown boundary, add the reachability test it lacked, p…"]
        )
        assert text == "- Fix the first thing.\n- Fix the second thing."
        assert source == "description"


class TestGh:
    def test_it_runs_gh_and_returns_stdout(self, merge_pr, monkeypatch):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(cmd, 0, stdout="output\n", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert merge_pr._gh("pr", "view", "1") == "output\n"
        assert captured["cmd"] == ["gh", "pr", "view", "1"]

    def test_it_passes_input_text_to_stdin(self, merge_pr, monkeypatch):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["kwargs"] = kwargs
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        merge_pr._gh("pr", "merge", "1", input_text="body text")
        assert captured["kwargs"]["input"] == "body text"

    def test_output_is_decoded_as_utf8_not_the_host_locale(self, merge_pr):
        """The same reasoning `check_version_bump.py::_git` documents: this
        reads PR titles and descriptions, which are not guaranteed ASCII,
        and CI's Windows leg decodes cp1252 by default without this."""
        import inspect

        source = inspect.getsource(merge_pr._gh)
        assert 'encoding="utf-8"' in source


class TestPrData:
    def test_pr_body_reads_the_body_field(self, merge_pr, monkeypatch):
        monkeypatch.setattr(merge_pr, "_gh", lambda *a, **k: "the body\n")
        assert merge_pr._pr_body(42) == "the body\n"

    def test_pr_commit_subjects_splits_on_newlines(self, merge_pr, monkeypatch):
        monkeypatch.setattr(merge_pr, "_gh", lambda *a, **k: "Fix a\nFix b\n")
        assert merge_pr._pr_commit_subjects(42) == ["Fix a", "Fix b"]

    def test_pr_commit_subjects_handles_no_output(self, merge_pr, monkeypatch):
        monkeypatch.setattr(merge_pr, "_gh", lambda *a, **k: "")
        assert merge_pr._pr_commit_subjects(42) == []


class TestMerge:
    def test_it_calls_gh_pr_merge_squash_with_the_body_on_stdin(self, merge_pr, monkeypatch):
        calls = []
        monkeypatch.setattr(merge_pr, "_gh", lambda *a, **k: calls.append((a, k)) or "")
        merge_pr._merge(42, "- a change")
        ((args, kwargs),) = calls
        assert args == ("pr", "merge", "42", "--squash", "--body-file", "-")
        assert kwargs == {"input_text": "- a change"}

    def test_a_cosmetic_worktree_error_is_swallowed_when_the_pr_actually_merged(
        self, merge_pr, monkeypatch, capsys
    ):
        """Seen on this host: `gh pr merge` reports a worktree-cleanup error
        even though the remote merge succeeded. Re-running it is wrong --
        the merge already happened -- so this checks the PR's real state
        before deciding the command failed."""

        def fake_gh(*args, **kwargs):
            if args[:2] == ("pr", "merge"):
                raise subprocess.CalledProcessError(1, ["gh", *args])
            assert args == ("pr", "view", "42", "--json", "state", "--jq", ".state")
            return "MERGED\n"

        monkeypatch.setattr(merge_pr, "_gh", fake_gh)
        merge_pr._merge(42, "- a change")
        assert "cosmetic" in capsys.readouterr().out.lower()

    def test_a_real_merge_failure_still_raises(self, merge_pr, monkeypatch):
        def fake_gh(*args, **kwargs):
            if args[:2] == ("pr", "merge"):
                raise subprocess.CalledProcessError(1, ["gh", *args])
            return "OPEN\n"

        monkeypatch.setattr(merge_pr, "_gh", fake_gh)
        with pytest.raises(subprocess.CalledProcessError):
            merge_pr._merge(42, "- a change")


class TestInertClosingKeywords:
    """GitHub does not parse a closing keyword inside a code span, and the
    failure is silent: the PR merges, the issue stays open, and nothing
    says so. Seen on #430, whose body carried `Closes #421.` in backticks
    -- copied from `plans/f3-agenda-reviser.md`, which *quotes* the line
    PR 1 should carry. Reported at `--dry-run`, which is when it can
    still be fixed."""

    def test_a_backticked_keyword_is_reported(self, merge_pr):
        assert merge_pr.inert_closing_keywords("`Closes #421.`") == ["Closes #421"]

    def test_a_bare_keyword_is_not_reported(self, merge_pr):
        assert merge_pr.inert_closing_keywords("Closes #421.") == []

    def test_every_keyword_github_accepts_is_recognised(self, merge_pr):
        for word in ("Closes", "Fixes", "Resolves", "close", "fixed", "resolved"):
            assert merge_pr.inert_closing_keywords(f"`{word} #7`") == [f"{word} #7"]

    def test_a_keyword_in_a_fenced_block_is_reported_too(self, merge_pr):
        """A fence is the other span GitHub does not parse, and quoting a
        PR template in one is exactly how the mistake propagates."""
        body = "Example:\n\n```text\nCloses #9\n```\n"
        assert merge_pr.inert_closing_keywords(body) == ["Closes #9"]

    def test_a_bare_keyword_beside_a_backticked_one_still_reports_only_the_dead_one(self, merge_pr):
        assert merge_pr.inert_closing_keywords("Closes #1. See `Fixes #2`.") == ["Fixes #2"]

    def test_prose_mentioning_an_issue_is_not_a_keyword(self, merge_pr):
        assert merge_pr.inert_closing_keywords("`See #421 for the argument.`") == []

    def test_several_are_all_reported(self, merge_pr):
        assert merge_pr.inert_closing_keywords("`Closes #1` and `Fixes #2`") == [
            "Closes #1",
            "Fixes #2",
        ]


class TestVersionRules:
    def test_it_loads_the_real_check_by_path(self, merge_pr):
        """The rules are reused, not restated: this has to be the same
        module `ci.yml` runs, or the merge-time check can drift from the
        pull-request-time one. Loaded by path because the two ways
        `merge_pr.py` runs put different directories on `sys.path`."""
        rules = merge_pr._version_rules()
        assert callable(rules.blocks_a_merge)
        assert callable(rules.problems)
        assert rules.parse("6.10.0") > rules.parse("6.9.0")  # the real module, not a stub

    def test_loading_it_does_not_touch_sys_path(self, merge_pr):
        """The reason the load is by path rather than by a `sys.path`
        insert: a stray entry shadowing the stdlib has cost this
        repository once already."""
        import sys

        before = list(sys.path)
        merge_pr._version_rules()
        assert sys.path == before


class TestMain:
    def _stub(self, merge_pr, monkeypatch, body, subjects, blocks=False):
        monkeypatch.setattr(merge_pr, "_pr_body", lambda n: body)
        monkeypatch.setattr(merge_pr, "_pr_commit_subjects", lambda n: subjects)
        # Stubbed for every test here, not only the ones about it:
        # unstubbed, the merge-time version check runs a real `git
        # fetch` and reads this worktree, so a body-composition test
        # would depend on the state of the checkout it runs in.
        monkeypatch.setattr(
            merge_pr, "_version_rules", lambda: types.SimpleNamespace(blocks_a_merge=lambda: blocks)
        )
        calls = []
        monkeypatch.setattr(merge_pr, "_merge", lambda n, text: calls.append((n, text)))
        return calls

    def test_dry_run_prints_and_does_not_merge(self, merge_pr, monkeypatch, capsys):
        calls = self._stub(
            merge_pr,
            monkeypatch,
            "## Description\n\n- Fix it.\n\n## Impact\n\nnone\n",
            ["Fix it"],
        )
        assert merge_pr.main(["42", "--dry-run"]) == 0
        assert calls == []
        assert "- Fix it." in capsys.readouterr().out

    def test_without_dry_run_it_merges_with_the_composed_body(self, merge_pr, monkeypatch, capsys):
        calls = self._stub(
            merge_pr,
            monkeypatch,
            "## Description\n\n- Fix it.\n\n## Impact\n\nnone\n",
            ["Fix it"],
        )
        assert merge_pr.main(["42"]) == 0
        assert calls == [(42, "- Fix it.")]

    def test_it_says_which_source_the_body_came_from(self, merge_pr, monkeypatch, capsys):
        self._stub(merge_pr, monkeypatch, "## Description\n\nJust prose.\n", ["Fix it"])
        merge_pr.main(["42", "--dry-run"])
        assert "commits" in capsys.readouterr().out.lower()

    def test_an_inert_closing_keyword_is_warned_about(self, merge_pr, monkeypatch, capsys):
        self._stub(
            merge_pr,
            monkeypatch,
            "`Closes #421.`\n\n## Description\n\n- Fix it.\n",
            ["Fix it"],
        )
        merge_pr.main(["42", "--dry-run"])
        out = capsys.readouterr().out
        assert "Closes #421" in out
        assert "backtick" in out.lower() or "code span" in out.lower()

    def test_a_working_keyword_produces_no_warning(self, merge_pr, monkeypatch, capsys):
        self._stub(
            merge_pr,
            monkeypatch,
            "Closes #421.\n\n## Description\n\n- Fix it.\n",
            ["Fix it"],
        )
        merge_pr.main(["42", "--dry-run"])
        assert "will not close" not in capsys.readouterr().out

    def test_a_lost_version_bump_refuses_instead_of_merging(self, merge_pr, monkeypatch, capsys):
        """The #560 failure, at the point it is still preventable: the
        composed body is printed, and then the merge does not happen."""
        calls = self._stub(
            merge_pr, monkeypatch, "## Description\n\n- Fix it.\n", ["Fix it"], blocks=True
        )
        assert merge_pr.main(["42"]) == 1
        assert calls == []
        assert "- Fix it." in capsys.readouterr().out

    def test_dry_run_reports_the_same_refusal(self, merge_pr, monkeypatch):
        """`--dry-run` is where a person looks first, so it must report
        what a real run would do rather than a body that would not have
        been merged."""
        self._stub(merge_pr, monkeypatch, "## Description\n\n- Fix it.\n", ["Fix it"], blocks=True)
        assert merge_pr.main(["42", "--dry-run"]) == 1

    def test_the_check_runs_after_the_body_is_composed(self, merge_pr, monkeypatch, capsys):
        """Ordering that matters for readability rather than
        correctness: the body first, so a refusal is read against the
        change it refused."""
        order = []
        monkeypatch.setattr(merge_pr, "_pr_body", lambda n: "## Description\n\n- Fix it.\n")
        monkeypatch.setattr(merge_pr, "_pr_commit_subjects", lambda n: ["Fix it"])
        monkeypatch.setattr(merge_pr, "_merge", lambda n, text: order.append("merge"))
        monkeypatch.setattr(
            merge_pr,
            "_version_rules",
            lambda: types.SimpleNamespace(blocks_a_merge=lambda: order.append("check") or False),
        )
        merge_pr.main(["42"])
        assert order == ["check", "merge"]
        assert "- Fix it." in capsys.readouterr().out

    def test_the_warning_does_not_stop_the_merge(self, merge_pr, monkeypatch, capsys):
        """Advisory, like every other check this project added to a
        developer path: it reports, and a person decides. Blocking would
        make a deliberately-quoted keyword unmergeable."""
        calls = self._stub(
            merge_pr,
            monkeypatch,
            "`Closes #421.`\n\n## Description\n\n- Fix it.\n",
            ["Fix it"],
        )
        assert merge_pr.main(["42"]) == 0
        assert calls == [(42, "- Fix it.")]
