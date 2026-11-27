import os
import types
from pathlib import Path

import pytest

from tests import content_guard
from tests.conftest import run_python


def tracked_tree(root):
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
        tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        (tmp_path / "parsed").mkdir()
        assert "created parsed/" in content_guard.changes(before, content_guard.snapshot(tmp_path))

    def test_content_created_from_nothing_is_named(self, tmp_path):
        root = tmp_path / "content"
        before = content_guard.snapshot(root)
        assert before == {}
        root.mkdir()
        (root / "ledger.sqlite").write_bytes(b"x" * 12)
        assert content_guard.changes(before, content_guard.snapshot(root)) == [
            "created ledger.sqlite"
        ]

    @pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")
    def test_a_dangling_symlink_is_an_entry_not_a_crash(self, tmp_path):
        tracked_tree(tmp_path)
        before = content_guard.snapshot(tmp_path)
        (tmp_path / "parsed").symlink_to(tmp_path / "moved-away")
        assert content_guard.changes(before, content_guard.snapshot(tmp_path)) == ["created parsed"]

    def test_a_file_that_vanishes_mid_walk_is_skipped(self, tmp_path, monkeypatch):
        tracked_tree(tmp_path)
        journal = tmp_path / "ledger.sqlite-journal"
        journal.write_bytes(b"")
        real_lstat = os.lstat

        def vanish(path, *args, **kwargs):
            if Path(path) == journal:
                raise FileNotFoundError(path)
            return real_lstat(path, *args, **kwargs)

        monkeypatch.setattr(os, "lstat", vanish)
        assert "ledger.sqlite-journal" not in content_guard.snapshot(tmp_path)


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
        reporter = FakeReporter()
        session = fake_session(reporter, exitstatus=pytest.ExitCode.INTERRUPTED)
        content_guard.record(session, tmp_path)
        (tmp_path / "pipeline.lock.db").write_bytes(b"")

        content_guard.verify(session)

        assert session.exitstatus == pytest.ExitCode.INTERRUPTED
        assert any("created pipeline.lock.db" in line for line in reporter.lines)

    def test_no_baseline_adds_no_second_traceback(self):
        reporter = FakeReporter()
        session = fake_session(reporter, exitstatus=pytest.ExitCode.INTERNAL_ERROR)

        content_guard.verify(session)

        assert session.exitstatus == pytest.ExitCode.INTERNAL_ERROR
        assert reporter.lines == []


def test_conftest_wires_the_guard_to_the_real_content_dir():
    source = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    assert "content_guard.record(session, config.CONTENT_DIR)" in source
    assert "content_guard.verify(session)" in source


class TestTheRealHooksEndToEnd:
    def _run(self, tmp_path, body: str):
        content = tmp_path / "content"
        content.mkdir()
        probe = tmp_path / "test_probe.py"
        probe.write_text(
            f"from chitragupta import config\n\n\ndef test_probe():\n    {body}\n",
            encoding="utf-8",
        )
        args = ["-m", "pytest", "-p", "no:cacheprovider", "-p", "tests.conftest", "-q"]
        return run_python(
            *args, str(probe), env={**os.environ, "CONTENT_DIR": str(content)}, check=False
        )

    def test_a_passing_run_that_wrote_content_exits_one_naming_the_path(self, tmp_path):
        done = self._run(tmp_path, '(config.CONTENT_DIR / "leak.txt").write_text("x")')
        assert done.returncode == pytest.ExitCode.TESTS_FAILED, done.stdout + done.stderr
        assert "1 passed" in done.stdout
        assert "created leak.txt" in done.stdout

    def test_a_run_that_wrote_nothing_exits_zero(self, tmp_path):
        done = self._run(tmp_path, "assert config.CONTENT_DIR")
        assert done.returncode == pytest.ExitCode.OK, done.stdout + done.stderr
        assert "(#862)" not in done.stdout
