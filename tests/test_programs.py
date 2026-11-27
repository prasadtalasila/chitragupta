import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

from chitragupta import programs


_PLANTED = ("python", "python.exe", "python.bat", "python.cmd")


def _executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def planted(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    for name in _PLANTED:
        _executable(project / name)
    monkeypatch.chdir(project)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", os.environ.get("PATH", "")]))
    return project


class TestResolveProgram:
    def test_a_program_planted_in_cwd_is_never_the_answer(self, planted):
        found = programs.resolve_program("python")
        assert found is None or not Path(found).resolve().is_relative_to(planted)

    def test_the_planted_shape_is_what_shutil_which_returns(self, planted):
        assert Path(shutil.which("python")).resolve().is_relative_to(planted)

    def test_an_absolute_path_entry_is_searched(self, tmp_path, monkeypatch):
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        tool = _executable(bin_dir / ("tool.exe" if sys.platform == "win32" else "tool"))
        monkeypatch.setenv("PATH", str(bin_dir))
        found = programs.resolve_program("tool")
        assert found is not None
        assert Path(found) == tool
        assert Path(found).is_absolute()

    def test_windows_looks_for_the_exe_createprocess_would_run(self, monkeypatch):
        monkeypatch.setattr(programs.sys, "platform", "win32")
        monkeypatch.setenv("PATH", os.path.abspath(os.sep))
        searched = []
        monkeypatch.setattr(programs.shutil, "which", searched.append)
        programs.resolve_program("pdftotext")
        programs.resolve_program("python3.12")
        root = os.path.abspath(os.sep)
        assert searched == [
            os.path.join(root, "pdftotext.exe"),
            os.path.join(root, "python3.12"),
        ]

    def test_a_relative_entry_naming_another_directory_is_skipped(self, tmp_path, monkeypatch):
        (tmp_path / "bin").mkdir()
        _executable(tmp_path / "bin" / "tool")
        _executable(tmp_path / "bin" / "tool.bat")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PATH", "bin")
        assert programs.resolve_program("tool") is None

    def test_a_program_on_no_path_entry_is_none(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PATH", str(tmp_path))
        assert programs.resolve_program("no-such-program-anywhere") is None

    def test_an_unset_path_falls_back_to_the_default(self, monkeypatch):
        monkeypatch.delenv("PATH", raising=False)
        searched = []
        monkeypatch.setattr(programs.shutil, "which", searched.append)
        programs.resolve_program("tool")
        expected = [d for d in os.defpath.split(os.pathsep) if os.path.isabs(d)]
        suffix = ".exe" if sys.platform == "win32" else ""
        assert searched == [os.path.join(d, "tool" + suffix) for d in expected]


class TestRequireProgram:
    def test_a_found_program_is_its_absolute_path(self, monkeypatch):
        monkeypatch.setattr(programs, "resolve_program", lambda name: f"/usr/bin/{name}")
        assert programs.require_program("pdftotext") == "/usr/bin/pdftotext"

    def test_a_missing_program_raises_what_subprocess_would_have(self, monkeypatch):
        monkeypatch.setattr(programs, "resolve_program", lambda name: None)
        with pytest.raises(FileNotFoundError, match="pdftotext"):
            programs.require_program("pdftotext")
