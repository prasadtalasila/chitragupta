import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_INVOCATION = re.compile(
    r"""-m["']?      # the flag, and the quote closing it in a list
                             [\s,]*       # whitespace and/or the comma between elements
                             ["']?        # the quote opening the module string
                             chitragupta\.sync\b""",
    re.VERBOSE,
)

_ALLOWED = {
    Path("chitragupta/sync.py"),
    Path("tests/test_corpus_entrypoint.py"),
    Path("tests/test_removed_command_scan.py"),
}


_EXCLUDED_DIRS = (
    Path(".claude") / "worktrees",
    Path("bench") / "results",
)


def _scanned_files(root=REPO_ROOT):
    patterns = ("*.py", "*.md", "*.sh", "*.toml", "*.yml", "*.yaml", "*.cfg")
    roots = ("chitragupta", "tests", "bench", "scripts", "docs", ".claude", ".github", "docker")
    found = set()
    for sub in roots:
        for pattern in patterns:
            found.update((root / sub).glob(f"**/{pattern}"))
    for pattern in patterns:
        found.update(root.glob(pattern))
    found.add(root / "config.toml.example")
    found.add(root / "docker" / "Dockerfile")
    found.add(root / "docker" / "Dockerfile.claude")
    found.add(root / "docker" / ".env.example")
    excluded = [root / d for d in _EXCLUDED_DIRS]
    return sorted(
        path for path in found if path.is_file() and not any(d in path.parents for d in excluded)
    )


def _offenders(root=REPO_ROOT):
    out = []
    for path in _scanned_files(root):
        relative = path.relative_to(root)
        if relative in _ALLOWED:
            continue
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
        for match in _INVOCATION.finditer(text):
            out.append((relative.as_posix(), match.group(0)))
    return out


class TestNothingInvokesTheRemovedCommand:
    def test_the_tree_is_clean(self):
        offenders = _offenders()
        assert not offenders, (
            "`python -m chitragupta.sync` was removed in 5.2.0 and now refuses. Use "
            "`python -m chitragupta.corpus sync`:\n"
            + "\n".join(f"  {path}: {text!r}" for path, text in offenders)
        )

    @pytest.mark.parametrize(
        "path",
        [
            "bench/repro_check.py",
            "bench/sweep_sync.py",
            "docker/Dockerfile",
            "docker/Dockerfile.claude",
            "docker/.env.example",
            "config.toml.example",
            "scripts/install_full_pipeline.sh",
        ],
    )
    def test_the_files_that_matter_are_in_scope(self, path):
        scanned = {p.relative_to(REPO_ROOT).as_posix() for p in _scanned_files()}
        assert path in scanned


class TestANestedWorktreeIsNotScanned:
    @staticmethod
    def _tree(root):
        for name in ("chitragupta", "tests", "bench", "scripts", "docs", ".github", "docker"):
            (root / name).mkdir(parents=True)
        (root / "docker" / "Dockerfile").write_text("FROM python\n", encoding="utf-8")
        (root / "config.toml.example").write_text("# example\n", encoding="utf-8")
        (root / "docs" / "OLD.md").write_text(
            "run python -m chitragupta.sync nightly\n", encoding="utf-8"
        )
        (root / ".claude" / "skills").mkdir(parents=True)
        (root / ".claude" / "skills" / "SKILL.md").write_text(
            "use python -m chitragupta.corpus sync\n", encoding="utf-8"
        )
        nested = root / ".claude" / "worktrees" / "issue-999"
        (nested / "docs").mkdir(parents=True)
        (nested / "chitragupta").mkdir(parents=True)
        (nested / "docs" / "OLD.md").write_text(
            "run python -m chitragupta.sync nightly\n", encoding="utf-8"
        )
        (nested / "chitragupta" / "sync.py").write_text(
            'subprocess.run([python, "-m", "chitragupta.sync"])\n', encoding="utf-8"
        )

    def test_the_nested_checkout_is_not_reported(self, tmp_path):
        self._tree(tmp_path)
        reported = {path for path, _ in _offenders(tmp_path)}
        assert reported == {"docs/OLD.md"}

    def test_the_nested_checkouts_files_are_not_even_walked(self, tmp_path):
        self._tree(tmp_path)
        scanned = {p.relative_to(tmp_path).as_posix() for p in _scanned_files(tmp_path)}
        assert "docs/OLD.md" in scanned
        assert not any(name.startswith(".claude/worktrees/") for name in scanned)

    def test_the_rest_of_claude_is_still_walked(self, tmp_path):
        self._tree(tmp_path)
        scanned = {p.relative_to(tmp_path).as_posix() for p in _scanned_files(tmp_path)}
        assert ".claude/skills/SKILL.md" in scanned


class TestThePatternCatchesBothSpellings:
    def test_it_catches_the_prose_form(self):
        assert _INVOCATION.search("run python -m chitragupta.sync nightly")

    def test_it_catches_the_list_form(self):
        assert _INVOCATION.search('subprocess.run([python, "-m", "chitragupta.sync"])')

    def test_it_catches_the_unspaced_list_form(self):
        assert _INVOCATION.search("[python,'-m','chitragupta.sync']")

    def test_it_ignores_the_logger_name(self):
        assert not _INVOCATION.search("sync logs as chitragupta.sync whatever the")

    def test_it_ignores_the_file_path(self):
        assert not _INVOCATION.search("chitragupta/sync.py's parse loop is serial")

    def test_it_ignores_the_replacement(self):
        assert not _INVOCATION.search("python -m chitragupta.corpus sync --reparse")
