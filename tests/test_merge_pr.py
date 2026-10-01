"""`scripts/merge_pr.py`: the squash body is written by the author, in the
documented format, and checked -- not assembled from the description (#827).

The script used to scrape every non-checkbox bullet out of the PR
description, which landed review notes, duplicated bullets and anything
hostile a bullet carried (a trailer, a live closing keyword, an escape
sequence) in `main`'s history. Now the body is the one fenced block under
`## Commit message`, accepted byte for byte or refused with the line that
broke the format. `plans/827-commit-message-format.md` has the design.
"""

import importlib.util
import re
import subprocess
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

GOOD = "- Fix the first thing.\n- Add the second thing, which wraps onto\n  a continuation line."


@pytest.fixture(scope="module")
def merge_pr():
    spec = importlib.util.spec_from_file_location("merge_pr", REPO_ROOT / "scripts" / "merge_pr.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pr(message: str, *, before: str = "", after: str = "") -> str:
    """A PR body whose `## Commit message` section fences `message`."""
    return (
        "## Description\n\nWhy this change.\n\n"
        f"## Commit message\n\n{before}```text\n{message}\n```\n{after}\n"
        "## Test plan\n\n- [x] Full suite\n"
    )


def _documented_example() -> str:
    """The body of DEVELOPER-AGENTS.md's commit-message example, read from
    the file so the example cannot drift out of the format it shows."""
    text = (REPO_ROOT / "DEVELOPER-AGENTS.md").read_text(encoding="utf-8")
    section = text.split("## 💬 Commit messages", 1)[1]
    example = re.search(r"```text\n(.*?)\n```", section, re.DOTALL).group(1)
    return example.split("\n\n", 1)[1]


class TestCommitBodyAccepts:
    def test_the_documented_example_is_accepted_and_kept_byte_for_byte(self, merge_pr):
        example = _documented_example()
        assert str(merge_pr.CommitBody(example)) == example

    def test_a_wrapped_bullet_keeps_its_wrapping(self, merge_pr):
        """The old scraper joined continuation lines with a space; the
        whole point now is that what the author previews is what lands."""
        assert str(merge_pr.CommitBody(GOOD)) == GOOD

    def test_a_line_of_exactly_the_limit_is_accepted(self, merge_pr):
        line = "- Fix " + "x" * (merge_pr.MAX_LINE - len("- Fix "))
        assert len(line) == merge_pr.MAX_LINE
        merge_pr.CommitBody(line)

    def test_a_bare_issue_reference_is_only_a_cross_reference(self, merge_pr):
        merge_pr.CommitBody("- Fix the drift reported in #421.")

    def test_git_finds_no_trailer_in_anything_accepted(self, merge_pr):
        """git's own trailer parser, not a reimplementation of it: a body
        this class accepts can never carry a `Co-authored-by:` or
        `Signed-off-by:` that git (and GitHub after it) would honour --
        not even one hidden on a continuation line."""
        bodies = [
            GOOD,
            _documented_example(),
            "- Fix the thing.\n  Co-authored-by: Mallory <m@evil.example>",
            "- Fix the thing.\n  Signed-off-by: Mallory <m@evil.example>",
        ]
        for body in bodies:
            parsed = subprocess.run(
                ["git", "interpret-trailers", "--parse"],
                input=f"Title\n\n{merge_pr.CommitBody(body)}\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            assert parsed.stdout == "", body


class TestCommitBodyRefuses:
    """Each probe from issue 827, and each shape the grammar rules out, is
    refused with the line number, the reason and the line itself."""

    def _refusal(self, merge_pr, text):
        with pytest.raises(merge_pr.FormatError) as caught:
            merge_pr.CommitBody(text)
        return str(caught.value)

    @pytest.mark.parametrize(
        "bad",
        [
            "- Fix the thing \x1b[31mred\x1b[0m",  # ANSI escape
            "- Fix the thing ‮evil",  # right-to-left override
            "- Fix the​thing",  # zero-width space
            "- Fix the thing ⁦isolated⁩",  # bidi isolate
            "- Fix the thing",  # no-break space
            "- Fix the thing\x7f",  # DEL
            "- Fix the\tthing",  # tab
            "- Fix the thing\r",  # a lone carriage return
        ],
    )
    def test_an_invisible_or_control_character_is_refused(self, merge_pr, bad):
        message = self._refusal(merge_pr, f"- Add a first line.\n{bad}")
        assert "line 2" in message
        assert "invisible" in message
        assert repr(bad) in message  # shown escaped, so it can be seen

    @pytest.mark.parametrize(
        "trailer",
        [
            "- Co-authored-by: Mallory <m@evil.example>",
            "- Signed-off-by: Mallory <m@evil.example>",
            "- Closes: the thing",
            "- Note: something",
        ],
    )
    def test_a_trailer_shaped_bullet_is_refused(self, merge_pr, trailer):
        message = self._refusal(merge_pr, trailer)
        assert "line 1" in message
        assert "verb" in message

    @pytest.mark.parametrize(
        "keyword",
        [
            "- Closes #12",
            "- Fix #12's crash on an empty ledger",
            "- Add the guard; resolves #12",
            "- Add the guard, which fixes: #12",
            "- Add the guard. Closes prasadtalasila/chitragupta#12",
            "- Add the guard. Closes https://github.com/o/r/issues/12",
            "- Add the guard and\n  closes #12",
        ],
    )
    def test_a_closing_keyword_anywhere_is_refused(self, merge_pr, keyword):
        """GitHub closes an issue named this way in a commit landing on the
        default branch -- whichever issue it names, linked or not. The PR
        description is where a PR closes its issue."""
        message = self._refusal(merge_pr, keyword)
        assert "closing keyword" in message
        assert f"line {keyword.count(chr(10)) + 1}" in message

    def test_a_keyword_split_across_two_lines_is_refused_too(self, merge_pr):
        message = self._refusal(merge_pr, "- Add the guard that closes\n  #12 for good")
        assert "closing keyword" in message
        assert "line 1" in message

    def test_a_line_over_the_limit_is_refused(self, merge_pr):
        line = "- Fix " + "x" * (merge_pr.MAX_LINE + 1 - len("- Fix "))
        message = self._refusal(merge_pr, f"- Fix one.\n  {line[2:]}")
        assert "line 2" in message
        assert str(merge_pr.MAX_LINE) in message

    @pytest.mark.parametrize(
        ("text", "line"),
        [
            ("- Fix one.\n\n- Fix two.", 2),  # blank line between bullets
            ("* Fix one.", 1),  # a star marker
            ("- fix one.", 1),  # lower-case verb
            ("- ", 1),  # no verb at all
            ("-Fix one.", 1),  # no space after the dash
            ("- Fix one.\n three", 2),  # one space of indent
            ("- Fix one.\n   three", 2),  # three spaces of indent
            ("  Fix one.", 1),  # a continuation with nothing to continue
            ("Fix one.", 1),  # prose, not a bullet
            ("- Fix one.\n```", 2),  # a stray fence
        ],
    )
    def test_a_line_outside_the_grammar_is_refused(self, merge_pr, text, line):
        assert f"line {line}" in self._refusal(merge_pr, text)

    def test_an_empty_body_is_refused(self, merge_pr):
        assert "empty" in self._refusal(merge_pr, "")

    def test_the_first_offending_line_is_the_one_reported(self, merge_pr):
        message = self._refusal(merge_pr, "- Fix one.\n- bad two.\n- bad three.")
        assert "line 2" in message
        assert "line 3" not in message


class TestCommitBodyFromPr:
    def test_the_fenced_block_is_the_body(self, merge_pr):
        assert str(merge_pr.commit_body(_pr(GOOD))) == GOOD

    def test_bullets_elsewhere_in_the_description_are_ignored(self, merge_pr):
        """The regression pin for #910, #912 and #913, whose squash bodies
        carry every change twice: once from `## Description` and once from
        `## What changed`."""
        body = (
            "## Description\n\n- Fix the thing.\n\n"
            "## What changed, from the user's point of view\n\n- The thing works.\n\n"
            + _pr("- Fix the thing.")
        )
        assert str(merge_pr.commit_body(body)) == "- Fix the thing."

    def test_the_heading_is_matched_case_insensitively(self, merge_pr):
        body = _pr(GOOD).replace("## Commit message", "## Commit Message")
        assert str(merge_pr.commit_body(body)) == GOOD

    def test_crlf_line_endings_are_read_as_line_endings(self, merge_pr):
        """A description edited in GitHub's web editor can come back from
        the API with CRLF line endings; the CR is a line ending there, not
        content, and the body lands with plain newlines."""
        assert str(merge_pr.commit_body(_pr(GOOD).replace("\n", "\r\n"))) == GOOD

    def test_a_missing_section_is_refused_with_a_skeleton_to_paste(self, merge_pr):
        with pytest.raises(merge_pr.FormatError) as caught:
            merge_pr.commit_body("## Description\n\n- Fix the thing.\n")
        message = str(caught.value)
        assert "## Commit message" in message
        assert "```text" in message

    @pytest.mark.parametrize(
        ("body", "reason"),
        [
            ("## Commit message\n\n- Fix it.\n", "fence"),
            (_pr(GOOD, before="Some prose.\n\n"), "fence"),
            (_pr(GOOD, after="\nSome prose.\n"), "fence"),
            ("## Commit message\n\n```\n- Fix it.\n```\n", "fence"),
            ("## Commit message\n\n~~~text\n- Fix it.\n~~~\n", "fence"),
            ("## Commit message\n\n```text\n- Fix it.\n```\n\n```text\n- Fix it.\n```\n", "fence"),
            (_pr(GOOD) + _pr(GOOD), "more than one"),
        ],
    )
    def test_a_section_that_is_not_exactly_one_text_fence_is_refused(self, merge_pr, body, reason):
        with pytest.raises(merge_pr.FormatError) as caught:
            merge_pr.commit_body(body)
        assert reason in str(caught.value)

    def test_the_fence_content_is_checked_against_the_grammar(self, merge_pr):
        with pytest.raises(merge_pr.FormatError, match="line 1"):
            merge_pr.commit_body(_pr("- Co-authored-by: Mallory <m@evil.example>"))


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


class TestPrBody:
    def test_it_reads_the_body_field(self, merge_pr, monkeypatch):
        monkeypatch.setattr(merge_pr, "_gh", lambda *a, **k: "the body\n")
        assert merge_pr._pr_body(42) == "the body\n"


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
    def _stub(self, merge_pr, monkeypatch, body, blocks=False):
        monkeypatch.setattr(merge_pr, "_pr_body", lambda n: body)
        # Stubbed for every test here, not only the ones about it:
        # unstubbed, the merge-time version check runs a real `git
        # fetch` and reads this worktree, so a body test would depend on
        # the state of the checkout it runs in.
        order = []
        monkeypatch.setattr(
            merge_pr,
            "_version_rules",
            lambda: types.SimpleNamespace(blocks_a_merge=lambda: order.append("check") or blocks),
        )
        monkeypatch.setattr(merge_pr, "_merge", lambda n, text: order.append((n, text)))
        return order

    def test_dry_run_prints_and_does_not_merge(self, merge_pr, monkeypatch, capsys):
        order = self._stub(merge_pr, monkeypatch, _pr(GOOD))
        assert merge_pr.main(["42", "--dry-run"]) == 0
        assert order == ["check"]
        assert GOOD in capsys.readouterr().out

    def test_without_dry_run_it_merges_with_the_fenced_body(self, merge_pr, monkeypatch):
        order = self._stub(merge_pr, monkeypatch, _pr(GOOD))
        assert merge_pr.main(["42"]) == 0
        assert order == ["check", (42, GOOD)]

    @pytest.mark.parametrize("flags", [["42"], ["42", "--dry-run"]])
    def test_a_malformed_body_refuses_before_the_version_check(
        self, merge_pr, monkeypatch, capsys, flags
    ):
        """Nothing to merge, so nothing to check the version of: the
        refusal names the line and stops."""
        order = self._stub(merge_pr, monkeypatch, _pr("- Signed-off-by: Mallory <m@evil.example>"))
        assert merge_pr.main(flags) == 1
        assert order == []
        assert "line 1" in capsys.readouterr().err

    def test_a_missing_section_refuses(self, merge_pr, monkeypatch, capsys):
        order = self._stub(merge_pr, monkeypatch, "## Description\n\n- Fix it.\n")
        assert merge_pr.main(["42"]) == 1
        assert order == []
        assert "## Commit message" in capsys.readouterr().err

    def test_an_inert_closing_keyword_is_warned_about(self, merge_pr, monkeypatch, capsys):
        self._stub(merge_pr, monkeypatch, "`Closes #421.`\n\n" + _pr(GOOD))
        merge_pr.main(["42", "--dry-run"])
        out = capsys.readouterr().out
        assert "Closes #421" in out
        assert "code span" in out.lower()

    def test_a_working_keyword_produces_no_warning(self, merge_pr, monkeypatch, capsys):
        self._stub(merge_pr, monkeypatch, "Closes #421.\n\n" + _pr(GOOD))
        merge_pr.main(["42", "--dry-run"])
        assert "will not close" not in capsys.readouterr().out

    def test_the_warning_does_not_stop_the_merge(self, merge_pr, monkeypatch):
        """Advisory, like every other check this project added to a
        developer path: it reports, and a person decides. Blocking would
        make a deliberately-quoted keyword unmergeable."""
        order = self._stub(merge_pr, monkeypatch, "`Closes #421.`\n\n" + _pr(GOOD))
        assert merge_pr.main(["42"]) == 0
        assert order == ["check", (42, GOOD)]

    def test_a_lost_version_bump_refuses_instead_of_merging(self, merge_pr, monkeypatch, capsys):
        """The #560 failure, at the point it is still preventable: the
        body is printed, and then the merge does not happen."""
        order = self._stub(merge_pr, monkeypatch, _pr(GOOD), blocks=True)
        assert merge_pr.main(["42"]) == 1
        assert order == ["check"]
        assert GOOD in capsys.readouterr().out

    def test_dry_run_reports_the_same_refusal(self, merge_pr, monkeypatch):
        """`--dry-run` is where a person looks first, so it must report
        what a real run would do rather than a body that would not have
        been merged."""
        self._stub(merge_pr, monkeypatch, _pr(GOOD), blocks=True)
        assert merge_pr.main(["42", "--dry-run"]) == 1


class TestCheck:
    """`--check` is the pull-request-time half: `commit-message.yml` pipes
    the description in on stdin. No `gh`, no version check, no merge."""

    def _stdin(self, monkeypatch, text):
        import io
        import sys

        stream = types.SimpleNamespace(buffer=io.BytesIO(text.encode("utf-8")))
        monkeypatch.setattr(sys, "stdin", stream)

    def _forbid_the_rest(self, merge_pr, monkeypatch):
        def boom(*args, **kwargs):
            raise AssertionError("--check must not reach this")

        for name in ("_gh", "_pr_body", "_version_rules", "_merge"):
            monkeypatch.setattr(merge_pr, name, boom)

    def test_a_conforming_body_passes(self, merge_pr, monkeypatch, capsys):
        self._forbid_the_rest(merge_pr, monkeypatch)
        self._stdin(monkeypatch, _pr(GOOD))
        assert merge_pr.main(["--check"]) == 0
        assert GOOD in capsys.readouterr().out

    def test_a_malformed_body_fails_naming_the_line(self, merge_pr, monkeypatch, capsys):
        self._forbid_the_rest(merge_pr, monkeypatch)
        self._stdin(monkeypatch, _pr("- Fix it.\n- Closes #9"))
        assert merge_pr.main(["--check"]) == 1
        assert "line 2" in capsys.readouterr().err

    def test_stdin_is_decoded_as_utf8(self, merge_pr, monkeypatch, capsys):
        """A description is not guaranteed ASCII, and a runner's locale is
        not guaranteed UTF-8 -- the same reasoning as `_gh`."""
        self._forbid_the_rest(merge_pr, monkeypatch)
        self._stdin(monkeypatch, _pr("- Fix the café's naïve résumé."))
        assert merge_pr.main(["--check"]) == 0

    def test_it_takes_no_pr_number(self, merge_pr):
        with pytest.raises(SystemExit):
            merge_pr.main(["42", "--check"])

    def test_a_merge_needs_a_pr_number(self, merge_pr):
        with pytest.raises(SystemExit):
            merge_pr.main([])

    def test_check_and_dry_run_do_not_combine(self, merge_pr):
        with pytest.raises(SystemExit):
            merge_pr.main(["--check", "--dry-run"])


class TestWorkflow:
    """The pull-request-time check, as configured. The body is
    attacker-controlled text, so it must reach the script through `env:`
    and never be interpolated into the shell line."""

    WORKFLOW = REPO_ROOT / ".github" / "workflows" / "commit-message.yml"

    def test_it_runs_when_the_description_is_edited(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        assert re.search(r"types:\s*\[[^\]]*\bedited\b", text)

    def test_the_body_is_never_interpolated_into_a_run_line(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        run_lines = [line for line in text.splitlines() if "pull_request.body" in line]
        assert run_lines, "the workflow must read the PR body"
        for line in run_lines:
            assert re.match(r"\s*BODY:\s", line), line

    def test_it_runs_the_check_mode(self):
        text = self.WORKFLOW.read_text(encoding="utf-8")
        assert "python scripts/merge_pr.py --check" in text


class TestTemplate:
    def test_the_pr_template_carries_the_section_and_an_empty_fence(self, merge_pr):
        """A PR opened from the template fails the check until its author
        writes the body -- an empty fence, never a pre-filled one."""
        text = (REPO_ROOT / ".github" / "pull_request_template.md").read_text(encoding="utf-8")
        assert "## Commit message" in text
        with pytest.raises(merge_pr.FormatError, match="empty"):
            merge_pr.commit_body(text)
