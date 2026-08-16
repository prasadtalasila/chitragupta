"""`.claude/hooks/draft_target.py`: the one decision both PostToolUse hooks
share, and therefore the one place a disagreement between them could start.

These cases were the citation gate's own tests until the helper was
extracted. They are here rather than there because both hooks now depend on
them, and because the failure this file guards against is not "the gate
broke" but "the two hooks stopped covering the same writes" -- which no
test of either hook alone can see.

Every case below is a *negative* one bar two, and that is the shape of the
problem: a helper that says "yes, a draft" too readily makes the advisory
hook noisy, and one that says "no" too readily makes the gate silently stop
enforcing CLAUDE.md's one invariant. The second failure is invisible, which
is why the containment and suffix cases are pinned this hard.
"""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = REPO_ROOT / ".claude" / "hooks"


@pytest.fixture
def dt():
    """A fresh module, so a monkeypatched REPO_ROOT cannot leak between tests."""
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location("draft_target",
                                                  HOOKS / "draft_target.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def root(tmp_path):
    (tmp_path / "content" / "drafts").mkdir(parents=True)
    return tmp_path


def stdin_of(payload) -> io.StringIO:
    return io.StringIO(payload if isinstance(payload, str) else json.dumps(payload))


class TestMalformedStdinFailsOpen:
    """Three shapes, all of which have been hit in production. Each means
    "no file path was given", and a helper that raises on one is a hook
    that stops reporting -- for the gate, that is enforcement lost."""

    @pytest.mark.parametrize("payload,why", [
        ("{not json", "invalid JSON syntax"),
        ("", "empty stdin"),
        ("[]", "valid JSON that is not an object"),
        ('"a string"', "valid JSON that is a bare scalar"),
        ('{"tool_input": []}', "tool_input of the wrong shape"),
        ('{"tool_input": null}', "tool_input explicitly null"),
        ('{}', "no tool_input at all"),
        ('{"tool_input": {}}', "no file_path at all"),
        ('{"tool_input": {"file_path": ""}}', "an empty file_path"),
        ('{"tool_input": {"file_path": 7}}', "a file_path that is not a string"),
    ])
    def test_returns_none(self, dt, payload, why):
        assert dt.from_stdin(stdin_of(payload)) is None, why


class TestContainment:
    """`is_relative_to` on resolved paths, not a substring match."""

    def test_a_draft_under_content_drafts_is_the_target(self, dt, root):
        draft = root / "content" / "drafts" / "survey.md"
        assert dt.target(str(draft), root) == draft.resolve()

    def test_a_nested_draft_is_the_target(self, dt, root):
        """Book chapters live in subdirectories, so containment is not a
        parent check."""
        nested = root / "content" / "drafts" / "books" / "ch01.md"
        nested.parent.mkdir(parents=True)
        assert dt.target(str(nested), root) == nested.resolve()

    @pytest.mark.parametrize("relative,why", [
        ("notes.md", "the repo root itself"),
        ("content/notes.md", "content/ but not drafts/"),
        ("content/rendered/survey.md", "a sibling of drafts/"),
        ("content/drafts/../../notes.md", "escaping via .."),
        ("content/draftsy/survey.md", "a directory whose name merely starts the same"),
    ])
    def test_a_write_elsewhere_is_not_a_draft(self, dt, root, relative, why):
        assert dt.target(relative, root) is None, why

    def test_a_substring_match_would_have_passed_the_escape(self, dt, root):
        """The case that makes this `is_relative_to` and not `in`: the raw
        string contains the drafts directory and the resolved path does not.

        The needle is built with `os.sep` rather than written as
        "/content/drafts/", because the separator is "\\" on Windows and a
        literal would make this test assert something true only on POSIX --
        which is what it did until CI's Windows leg said so.
        """
        escape = "content/drafts/../../outside.md"
        needle = f"{os.sep}content{os.sep}drafts{os.sep}"
        assert needle in str(root / escape)
        assert dt.target(escape, root) is None


class TestSuffixes:
    @pytest.mark.parametrize("name", ["survey.md", "chapter.tex"])
    def test_the_two_this_pipeline_writes(self, dt, root, name):
        assert dt.target(f"content/drafts/{name}", root) is not None

    @pytest.mark.parametrize("name", [
        "notes.txt", "data.json", "scope.md.bak", "noextension", "draft.MD",
    ])
    def test_anything_else_is_ignored(self, dt, root, name):
        """Including `.MD`: the suffix check is exact, and a case-insensitive
        one would be a guess about a filesystem rather than about this
        pipeline, which only ever writes lowercase."""
        assert dt.target(f"content/drafts/{name}", root) is None


class TestPathsTheFilesystemRefuses:
    """Found by an OpenCodeReview pass, and the more serious of the two it
    found: `citation_gate_hook.main()` runs straight off
    `raise SystemExit(main())` with no catch-all, so an exception raised in
    here exits non-zero *without* the blocking decision -- and the write
    lands ungated. A hook that crashes on a malformed payload is a gate
    that has stopped being one."""

    def test_an_embedded_null_byte_is_not_a_draft(self, dt, root):
        assert dt.target("content/drafts/a\0b.md", root) is None

    def test_a_null_byte_through_the_stdin_path_is_not_a_draft(self, dt, root,
                                                               monkeypatch):
        monkeypatch.setattr(dt, "REPO_ROOT", root)
        assert dt.from_stdin(
            stdin_of({"tool_input": {"file_path": "content/drafts/a\0b.md"}})) is None

    def test_a_very_long_path_is_judged_on_its_location_like_any_other(
            self, dt, root):
        """Not an error case, and worth pinning as such: `resolve()` does
        not stat, so a path past the OS length limit raises nothing here.
        `OSError` stays in the guard for the platforms where it would."""
        assert dt.target("content/drafts/" + "x" * 5000 + ".md", root) is not None


class TestPathResolution:
    def test_a_relative_path_resolves_against_the_repo_root(self, dt, root):
        """The near-miss `citation_gate_hook.py`'s docstring records: a
        substring match on "/content/drafts/" silently skips a relative
        path, because there is no leading slash to match."""
        draft = root / "content" / "drafts" / "rel.md"
        assert dt.target("content/drafts/rel.md", root) == draft.resolve()

    def test_the_root_is_not_taken_from_the_working_directory(
            self, dt, root, tmp_path, monkeypatch):
        """A hook runs from wherever the harness happens to be."""
        elsewhere = tmp_path / "cwd"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        assert dt.target("content/drafts/rel.md", root) is not None

    def test_the_default_root_is_this_checkout(self, dt):
        """With no root passed, the helper uses its own on-disk location --
        which is what production does, and the reason both hooks agree."""
        assert dt.REPO_ROOT == REPO_ROOT
        assert dt.target("content/drafts/anything.md") is not None

    def test_a_patched_root_is_read_at_call_time(self, dt, root, monkeypatch):
        """Both hooks read `REPO_ROOT` through the module rather than
        copying it at import, which is what lets one patch relocate both."""
        monkeypatch.setattr(dt, "REPO_ROOT", root)
        assert dt.target("content/drafts/rel.md") == (
            root / "content" / "drafts" / "rel.md").resolve()


class TestFromStdin:
    def test_a_draft_payload_yields_its_path(self, dt, root, monkeypatch):
        monkeypatch.setattr(dt, "REPO_ROOT", root)
        draft = root / "content" / "drafts" / "survey.md"
        assert dt.from_stdin(stdin_of({"tool_input": {"file_path": str(draft)}})) \
            == draft.resolve()

    def test_a_non_draft_payload_yields_none(self, dt, root, monkeypatch):
        monkeypatch.setattr(dt, "REPO_ROOT", root)
        assert dt.from_stdin(
            stdin_of({"tool_input": {"file_path": str(root / "notes.md")}})) is None
