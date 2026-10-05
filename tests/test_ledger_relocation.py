"""#966: a ledger survives its project moving.

Moved directory, renamed content dir, a container path then the host
path: all the same case. The stored paths must not name the host, so
the second sync re-parses nothing and refuses nothing. The schema scan
is the class test: every `*_path` column, including one added later.
"""

import os
import shutil
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

from chitragupta import config, ledger, pdf_text, sync
from tests.conftest import run_python

BIB = """
@article{smith_example_2024,
  title = {An Example Paper},
  author = {Smith, Jane},
  year = {2024},
  file = {paper.pdf:paper.pdf:application/pdf},
}
"""


def point_at(monkeypatch, root: Path, content: str = "content") -> None:
    """Every path sync reads or writes, under `root`."""
    monkeypatch.setattr(config, "CONTENT_DIR", root / content)
    monkeypatch.setattr(config, "PARSED_DIR", root / content / "parsed")
    monkeypatch.setattr(config, "LEDGER_PATH", root / content / "ledger.sqlite")
    monkeypatch.setattr(config, "BIB_FILE_PATH", root / "papers" / "bibliography.bib")


@pytest.fixture
def parses(isolated_config, monkeypatch):
    """The citekeys sync actually parsed, in order."""
    seen = []
    monkeypatch.setattr(pdf_text, "is_available", lambda: True)

    def fake_extract_text(pdf_path, citekey):
        seen.append(citekey)
        config.PARSED_DIR.mkdir(parents=True, exist_ok=True)
        out = config.PARSED_DIR / f"{citekey}.txt"
        out.write_text(f"text of {citekey}", encoding="utf-8")
        return out

    monkeypatch.setattr(pdf_text, "extract_text", fake_extract_text)
    return seen


def make_project(root: Path) -> None:
    (root / "papers").mkdir(parents=True)
    (root / "papers" / "bibliography.bib").write_text(BIB, encoding="utf-8")
    (root / "papers" / "paper.pdf").write_bytes(b"%PDF-1.4 content")


def absolute_path_values(con) -> list:
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    scanned = [
        (table, row[1])
        for table in tables
        for row in con.execute(f'PRAGMA table_info("{table}")')
        if row[1].endswith("_path")
    ]
    assert {"parsed_path", "pdf_path"} <= {column for _, column in scanned}
    return [
        (f"{table}.{column}", value)
        for table, column in scanned
        for (value,) in con.execute(
            f'SELECT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'
        )
        if PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
    ]


def move_project(tmp: Path, mp) -> None:
    shutil.move(tmp / "a", tmp / "b")
    point_at(mp, tmp / "b")


def rename_content(tmp: Path, mp) -> None:
    (tmp / "a" / "content").rename(tmp / "a" / "corpus")
    point_at(mp, tmp / "a", "corpus")


@pytest.mark.parametrize(
    "relocate",
    [pytest.param(move_project, id="moved"), pytest.param(rename_content, id="content-renamed")],
)
def test_a_relocated_project_reparses_nothing(tmp_path, monkeypatch, parses, capsys, relocate):
    make_project(tmp_path / "a")
    point_at(monkeypatch, tmp_path / "a")
    assert sync.run() == 0
    assert parses == ["smith_example_2024"]

    relocate(tmp_path, monkeypatch)
    parses.clear()
    capsys.readouterr()
    assert sync.run() == 0
    out = capsys.readouterr()
    assert parses == []
    assert "WARNING refusing" not in out.err + out.out


def test_a_legacy_absolute_ledger_survives_upgrade_and_move(tmp_path, monkeypatch, parses, capsys):
    """An older release wrote host-absolute paths. Upgrade and move in
    one step, and the next sync must still re-parse nothing."""
    make_project(tmp_path / "a")
    point_at(monkeypatch, tmp_path / "a")
    sync.run()
    with ledger.connection() as con:
        con.execute(
            "UPDATE items SET parsed_path = ?, pdf_path = ?",
            (
                str(config.PARSED_DIR / "smith_example_2024.txt"),
                str(tmp_path / "a" / "papers" / "paper.pdf"),
            ),
        )
        con.commit()

    shutil.move(tmp_path / "a", tmp_path / "b")
    point_at(monkeypatch, tmp_path / "b")
    parses.clear()
    capsys.readouterr()
    assert sync.run() == 0
    assert parses == []
    out = capsys.readouterr()
    assert "WARNING refusing" not in out.err + out.out
    with ledger.connection() as con:
        assert absolute_path_values(con) == []


def test_no_ledger_column_stores_an_absolute_path(tmp_path, monkeypatch, parses):
    make_project(tmp_path / "a")
    point_at(monkeypatch, tmp_path / "a")
    sync.run()
    with ledger.connection() as con:
        assert absolute_path_values(con) == []


def test_parsed_paths_follow_the_configured_content_dir(tmp_path):
    """The stored `<citekey>.txt` is read from `parsed/` under whatever
    `[content].dir` names, not from a fixed `content/parsed/`. Checked
    through a real `config.toml` in a child process, because `point_at`
    above sets the derived paths directly and never reads the setting."""
    project = tmp_path / "project"
    project.mkdir()
    example = (Path(__file__).resolve().parent.parent / "config.toml.example").read_text(
        encoding="utf-8"
    )
    (project / config.PROJECT_MARKER).write_text(
        example.replace('dir = "content"', 'dir = "mycorpus"', 1), encoding="utf-8"
    )
    result = run_python(
        "-c",
        "from chitragupta import config, ledger_paths\n"
        "config.PARSED_DIR.mkdir(parents=True)\n"
        "(config.PARSED_DIR / 'smith_example_2024.txt').write_text('x')\n"
        "print(config.PARSED_DIR)\n"
        "print(ledger_paths.parsed_file('smith_example_2024.txt'))",
        cwd=project,
        env={
            **{k: v for k, v in os.environ.items() if k not in ("CONTENT_DIR", "CONFIG_PATH")},
            "CHITRAGUPTA_PROJECT": str(project),
        },
        check=True,
    )
    parsed_dir, resolved = result.stdout.strip().splitlines()
    assert Path(parsed_dir) == project.resolve() / "mycorpus" / "parsed"
    assert Path(resolved) == project.resolve() / "mycorpus" / "parsed" / "smith_example_2024.txt"
