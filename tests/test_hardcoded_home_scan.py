"""#988's class: a hardcoded home directory in a shipped Docker file.

`scripts/release.py`'s docker-only zip ships `docker/` and the two
`DOCKER*.md` guides, so a literal `/home/<name>` there is a path that is
wrong for every user but one. Spell it `/home/${CHITRAGUPTA_USER}`, the
path `docker-compose.yml` actually mounts, or `/home/<user>` in prose.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# A literal name straight after `/home/`. `$`, `${` and `<` are the
# three spellings of "whichever user", so they never match.
LITERAL_HOME = re.compile(r"/home/[A-Za-z0-9_]")


def _shipped_docker_files() -> list[Path]:
    return sorted([*(ROOT / "docker").rglob("*"), *ROOT.glob("DOCKER*.md")])


def test_the_scan_reads_every_shipped_docker_file():
    names = {path.name for path in _shipped_docker_files()}
    assert {"entrypoint.sh", "docker-compose.yml", "DOCKER.md"} <= names


def test_no_shipped_docker_file_names_one_users_home():
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for path in _shipped_docker_files()
        if path.is_file()
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if LITERAL_HOME.search(line)
    ]
    assert offenders == []
