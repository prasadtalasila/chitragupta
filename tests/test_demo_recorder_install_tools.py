"""The demo-recorder skill's `install_tools.sh --check`.

The check is what decides what the install half fetches, and what a
session runs first to learn whether it can record at all. It runs here
for real, in bash, against a PATH holding fakes or nothing and a HOME
with or without a cached Chrome. The install half needs apt, sudo and
the network, so it was verified in a fresh Ubuntu container instead
(PR description).
"""

import shutil
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT, fake

BASH = shutil.which("bash")
SCRIPT = REPO_ROOT / ".claude" / "skills" / "demo-recorder" / "scripts" / "install_tools.sh"

pytestmark = pytest.mark.skipif(
    BASH is None or sys.platform == "win32", reason="a bash script for Ubuntu"
)

TOOLS = ("asciinema", "ffmpeg", "agg", "svg-term", "node", "npm")


def everything(tmp_path, asciinema="asciinema 2.4.0"):
    """A PATH and HOME holding every tool, as their real versions answer."""
    bin_dir, npm_root, home = tmp_path / "bin", tmp_path / "npm", tmp_path / "home"
    for d in (bin_dir, npm_root / "puppeteer-core", home):
        d.mkdir(parents=True)
    for name in ("ffmpeg", "agg", "svg-term", "node"):
        fake(bin_dir, name, "exit 0")
    fake(bin_dir, "asciinema", f'echo "{asciinema}"')
    fake(bin_dir, "npm", f'[ "$1 $2" = "root -g" ] && echo "{npm_root}"')
    chrome_dir = home / ".cache/puppeteer/chrome/linux-1/chrome-linux64"
    chrome_dir.mkdir(parents=True)
    fake(chrome_dir, "chrome", "exit 0")
    return bin_dir, home


def check(path, home, **env):
    return subprocess.run(
        [BASH, str(SCRIPT), "--check"],
        env={"PATH": str(path), "HOME": str(home), **env},
        capture_output=True,
        text=True,
        check=False,
    )


def test_everything_present_passes_and_names_the_chrome(tmp_path):
    bin_dir, home = everything(tmp_path)
    result = check(bin_dir, home)
    assert result.returncode == 0, result.stdout + result.stderr
    chrome = home / ".cache/puppeteer/chrome/linux-1/chrome-linux64/chrome"
    assert result.stdout.splitlines()[-1] == f"CHROME_PATH={chrome}"


def test_nothing_present_names_every_tool_and_installs_nothing(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "home").mkdir()
    result = check(tmp_path / "bin", tmp_path / "home")
    assert result.returncode == 1
    for name in (*TOOLS[:4], "node/npm", "puppeteer-core", "chrome"):
        assert f"{name}: missing" in result.stdout, name
    assert list((tmp_path / "home").iterdir()) == []


def test_asciinema_3_is_not_enough(tmp_path):
    """3.x changed the flags the skill's record step uses and its
    default `.cast` format, which retime_cast.py does not read."""
    bin_dir, home = everything(tmp_path, asciinema="asciinema 3.0.0")
    result = check(bin_dir, home)
    assert result.returncode == 1
    assert "asciinema: missing, or not 2.x (asciinema 3.0.0)" in result.stdout


def test_chrome_path_wins_over_the_cache(tmp_path):
    bin_dir, home = everything(tmp_path)
    mine = fake(tmp_path, "my-chrome", "exit 0")
    result = check(bin_dir, home, CHROME_PATH=str(mine))
    assert result.stdout.splitlines()[-1] == f"CHROME_PATH={mine}"


def test_a_chrome_missing_a_library_does_not_count(tmp_path):
    """The cached Puppeteer Chrome on Ubuntu 26.04 lacked libcups.so.2:
    present and executable, and still unable to start."""
    bin_dir, home = everything(tmp_path)
    fake(bin_dir, "ldd", 'echo "\tlibcups.so.2 => not found"')
    result = check(bin_dir, home)
    assert result.returncode == 1
    assert "chrome: missing" in result.stdout
