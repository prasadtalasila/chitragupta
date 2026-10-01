"""The session guard that keeps the suite out of the checkout's real content/ (#862).

`isolated_config` points every path constant at a tmp_path tree, but
nothing made a test use it: two groups wrote `retrieval_index.json`, the
pipeline lock and its holder record into the real `content/`, and the
existing scan (`test_unversioned_data_scan.py`) only sees *reads* of
config.toml and the .bib. These pin the detector on the exact shapes it
was blind to, and the hook wiring that turns a finding into a red run.
"""

import os
import types
from pathlib import Path

import pytest

from tests import content_guard


def tracked_tree(root):
    """A content/ shaped like a fresh checkout's: tracked sample files,
    nothing generated."""
    draft = root / "drafts" / "digital-twins-for-software-engineers" / "survey.md"
    draft.parent.mkdir(parents=True)
    draft.write_text("# survey\n", encoding="utf-8")
    return draft


class TestChanges:
    def test_an_untouched_tree_reports_nothing(self, tmp_path):
        tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        assert content_guard.changes(before, content_guard.snapshot(tmp_path)) == []

    def test_the_retrieval_index_a_test_wrote_is_named(self, tmp_path):
        tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        (tmp_path / "retrieval_index.json").write_text('{"version": 4, "items": {}}')
        assert content_guard.changes(before, content_guard.snapshot(tmp_path)) == [
            "created retrieval_index.json"
        ]

    def test_the_lock_and_its_holder_record_are_both_named(self, tmp_path):
        tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        (tmp_path / "pipeline.lock.db").write_bytes(b"")
        (tmp_path / "pipeline.lock.db.holder").write_text("{}")
        assert content_guard.changes(before, content_guard.snapshot(tmp_path)) == [
            "created pipeline.lock.db",
            "created pipeline.lock.db.holder",
        ]

    def test_an_overwrite_of_the_same_size_is_still_a_write(self, tmp_path):
        """The real index is overwritten, not created, on a checkout that
        has one -- and a same-length payload changes only the mtime."""
        draft = tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        stat = draft.stat()
        os.utime(draft, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        assert content_guard.changes(before, content_guard.snapshot(tmp_path)) == [
            "modified drafts/digital-twins-for-software-engineers/survey.md"
        ]

    def test_a_deleted_file_is_named(self, tmp_path):
        draft = tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        draft.unlink()
        changed = content_guard.changes(before, content_guard.snapshot(tmp_path))
        assert "deleted drafts/digital-twins-for-software-engineers/survey.md" in changed

    def test_an_empty_directory_left_behind_is_named(self, tmp_path):
        """`mkdir(parents=True)` ahead of a write that never happened
        still leaves a directory in the user's tree."""
        tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        (tmp_path / "parsed").mkdir()
        assert "created parsed/" in content_guard.changes(
            before, content_guard.snapshot(tmp_path)
        )

    def test_content_created_from_nothing_is_named(self, tmp_path):
        """CI's checkout has tracked files under content/, but a project
        made by `chitragupta init` may have none until a test writes."""
        root = tmp_path / "content"
        before = content_guard.snapshot(root)
        assert before == {}
        root.mkdir()
        (root / "ledger.sqlite").write_bytes(b"x" * 12)
        assert content_guard.changes(before, content_guard.snapshot(root)) == [
            "created ledger.sqlite"
        ]


class FakeReporter:
    def __init__(self):
        self.lines = []

    def write_line(self, line, **_markup):
        self.lines.append(line)


def fake_session(reporter, exitstatus=pytest.ExitCode.OK):
    plugins = types.SimpleNamespace(get_plugin=lambda name: reporter)
    return types.SimpleNamespace(
        stash=pytest.Stash(),
        exitstatus=exitstatus,
        config=types.SimpleNamespace(pluginmanager=plugins),
    )


class TestSessionHooks:
    def test_a_write_during_the_session_fails_it_and_names_the_path(self, tmp_path):
        tracked_tree(tmp_path)
        reporter = FakeReporter()
        session = fake_session(reporter)
        content_guard.record(session, tmp_path)
        (tmp_path / "retrieval_index.json").write_text("{}")

        content_guard.verify(session)

        assert session.exitstatus == pytest.ExitCode.TESTS_FAILED
        report = "\n".join(reporter.lines)
        assert str(tmp_path) in report
        assert "created retrieval_index.json" in report
        assert "isolated_config" in report  # the fix, not only the finding

    def test_a_clean_session_is_left_alone(self, tmp_path):
        tracked_tree(tmp_path)
        reporter = FakeReporter()
        session = fake_session(reporter)
        content_guard.record(session, tmp_path)

        content_guard.verify(session)

        assert session.exitstatus == pytest.ExitCode.OK
        assert reporter.lines == []

    def test_an_interrupted_session_keeps_its_own_exit_code(self, tmp_path):
        """Ctrl-C mid-run leaves whatever the interrupted test wrote, and
        reporting that as a test failure would hide the interruption."""
        reporter = FakeReporter()
        session = fake_session(reporter, exitstatus=pytest.ExitCode.INTERRUPTED)
        content_guard.record(session, tmp_path)
        (tmp_path / "pipeline.lock.db").write_bytes(b"")

        content_guard.verify(session)

        assert session.exitstatus == pytest.ExitCode.INTERRUPTED
        assert any("created pipeline.lock.db" in line for line in reporter.lines)


def test_conftest_wires_the_guard_to_the_real_content_dir():
    """The hooks only work if conftest calls them; a guard that is
    defined and never registered fails open, silently."""
    source = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    assert "content_guard.record(session, config.CONTENT_DIR)" in source
    assert "content_guard.verify(session)" in source
