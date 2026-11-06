"""`install_full_pipeline.sh os-deps` installs what a book's index needs
(#1168), and says so loudly if it did not.

`upmendex` ships in texlive-binaries and `imakeidx.sty` in
texlive-latex-extra, both already on the stage's apt line for other
reasons. They arrive by accident unless something checks: a later trim
of that line would break every book index silently. So the stage ends by
checking for them by name, and these tests run that check for real, in
bash, against a PATH holding fakes or nothing.
"""

import re
import shutil
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

BASH = shutil.which("bash")
SCRIPT = (REPO_ROOT / "scripts" / "install_full_pipeline.sh").read_text(encoding="utf-8")


def test_the_apt_line_names_both_packages():
    install = SCRIPT[SCRIPT.index("install_os_deps() {") :]
    apt = install[install.index("apt-get install") : install.index("libgl1")]
    assert "texlive-binaries" in apt
    assert "texlive-latex-extra" in apt


def test_the_stage_runs_the_check():
    stage = SCRIPT[
        SCRIPT.index("install_os_deps() {") : SCRIPT.index(
            "\n}\n", SCRIPT.index("install_os_deps() {")
        )
    ]
    assert "check_book_index_tools" in stage


def _function() -> str:
    return re.search(r"check_book_index_tools\(\) \{.*?\n\}\n", SCRIPT, re.S).group(0)


def _run(tmp_path, tools):
    fake = tmp_path / "bin"
    fake.mkdir()
    for name, body in tools.items():
        path = fake / name
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o755)
    return subprocess.run(
        [BASH, "-c", _function() + "check_book_index_tools"],
        env={"PATH": str(fake)},
        capture_output=True,
        text=True,
        check=False,
    )


needs_bash = pytest.mark.skipif(
    BASH is None or sys.platform == "win32", reason="runs the POSIX install script's check"
)


@needs_bash
def test_both_present_passes(tmp_path):
    result = _run(tmp_path, {"upmendex": "exit 0", "kpsewhich": "echo /x/imakeidx.sty"})
    assert result.returncode == 0, result.stderr


@needs_bash
def test_nothing_present_names_both(tmp_path):
    result = _run(tmp_path, {})
    assert result.returncode == 1
    assert "upmendex (texlive-binaries)" in result.stderr
    assert "imakeidx.sty (texlive-latex-extra)" in result.stderr


@needs_bash
def test_kpsewhich_that_cannot_find_imakeidx_names_it(tmp_path):
    result = _run(tmp_path, {"upmendex": "exit 0", "kpsewhich": "exit 1"})
    assert result.returncode == 1
    assert "imakeidx.sty" in result.stderr and "upmendex (" not in result.stderr
