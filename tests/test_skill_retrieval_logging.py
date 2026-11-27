import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR = REPO_ROOT / ".claude"

_INVOCATION = re.compile(r"python -m chitragupta\.draft retrieve (search|evidence)\b")

_LOOKAHEAD_CHARS = 220


_WORKTREES = "worktrees"


def _skill_and_agent_files(claude_dir=CLAUDE_DIR):
    excluded = claude_dir / _WORKTREES
    return sorted(path for path in claude_dir.glob("**/*.md") if excluded not in path.parents)


def _invocations_missing_log(text: str):
    missing = []
    for match in _INVOCATION.finditer(text):
        window = text[match.start() : match.start() + _LOOKAHEAD_CHARS]
        if "--log" not in window:
            line_no = text.count("\n", 0, match.start()) + 1
            missing.append((line_no, match.group(0)))
    return missing


def test_every_retrieval_cli_invocation_carries_log():
    files = _skill_and_agent_files()
    assert files, "expected to find Markdown files under .claude/"

    offenders = {}
    for path in files:
        missing = _invocations_missing_log(path.read_text(encoding="utf-8"))
        if missing:
            offenders[str(path.relative_to(REPO_ROOT))] = missing

    assert not offenders, (
        "retrieval CLI invocation(s) without --log (each row is a token-cost "
        f"measurement this run would silently skip):\n{offenders}"
    )


def test_at_least_one_invocation_is_actually_found():
    total = sum(
        len(_INVOCATION.findall(path.read_text(encoding="utf-8")))
        for path in _skill_and_agent_files()
    )
    assert total >= 1


def _worktree_fixture(claude_dir):
    (claude_dir / "skills" / "writer").mkdir(parents=True)
    (claude_dir / "skills" / "writer" / "SKILL.md").write_text(
        'python -m chitragupta.draft retrieve search "topic" --log\n', encoding="utf-8"
    )
    nested = claude_dir / _WORKTREES / "issue-999" / "docs"
    nested.mkdir(parents=True)
    (nested / "RETRIEVAL.md").write_text(
        'python -m chitragupta.draft retrieve evidence "claim"\n', encoding="utf-8"
    )
    return nested / "RETRIEVAL.md"


def test_a_nested_worktree_is_not_scanned(tmp_path):
    nested_doc = _worktree_fixture(tmp_path)
    scanned = _skill_and_agent_files(tmp_path)

    assert nested_doc.exists(), "fixture should contain the file being excluded"
    assert nested_doc not in scanned
    assert [p.name for p in scanned] == ["SKILL.md"]


def test_the_fixture_would_otherwise_be_reported(tmp_path):
    nested_doc = _worktree_fixture(tmp_path)
    assert _invocations_missing_log(nested_doc.read_text(encoding="utf-8"))
