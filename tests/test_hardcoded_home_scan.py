import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
