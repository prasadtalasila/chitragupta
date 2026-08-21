"""Every `chitragupta.draft retrieve` CLI invocation named in `.claude/` must carry `--log`.

`--log` is what turns a drafting run's retrieval cost from an estimate
(docs/TOKENS.md) into something `python -m chitragupta.draft dossier status` can total.
A skill or subagent protocol that names the CLI without it is a silent gap
in that measurement -- found once already (peer-reviewer.md's
domain-accuracy fallback had none), and cheap to lose again the next time
a skill file is edited by hand. This is a text-scan over `.claude/`, not
an exercise of the retrieval or dossier code -- both already have their
own tests for the flag's actual effect.

Deliberately does not flag `search(query, k, snippet_chars)` /
`chitragupta.enrich.embed_index.search()` mentions: those name the Python API,
which has no `--log` parameter to check for (a real, separate gap -- see
docs/TOKENS.md's coverage note -- not a doc typo this test can catch).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR = REPO_ROOT / ".claude"

# `python -m chitragupta.draft retrieve search "..."` / `... evidence "..." --citekey ...`
# -- the CLI form, which is the only one `--log` exists on.
_INVOCATION = re.compile(r"python -m chitragupta\.draft retrieve (search|evidence)\b")

# How far past the start of a matched invocation to look for its `--log`.
# Generous enough to span a `\`-continued line (draft-reviser's `evidence`
# call wraps once) without reaching into an unrelated, later sentence in
# these files -- checked by hand against every file this test scans.
_LOOKAHEAD_CHARS = 220


# Claude Code checks a whole second copy of this repository out at
# `.claude/worktrees/<name>/`, which drags every `.md` file in the tree
# under the glob below -- `docs/RETRIEVAL.md`, `docs/CONFIG.md` and
# `docs/ZOTERO.md` among them. Those are user documentation, correctly
# outside this scan at their real paths, and they are held here to a rule
# written for drafting-protocol files. The finding is not about the docs
# and not about old code: a glob scoped to `.claude/` simply cannot tell
# a skill file from a nested checkout of everything -- the same
# worktree-scan bug `tests/test_removed_command_scan.py` excludes for,
# fixed in #236.
_WORKTREES = "worktrees"


def _skill_and_agent_files(claude_dir=CLAUDE_DIR):
    # Every Markdown file under .claude/, not just SKILL.md and agent
    # files: `deep-research/reference.md` is a real, separate protocol
    # doc that a retrieval invocation could land in just as easily, and
    # nothing about this project's layout rules out another one like it
    # appearing alongside a future skill.
    #
    # `claude_dir` is a parameter so the worktree exclusion can be proved
    # against a fixture rather than by writing one into the live
    # `.claude/worktrees/`, which on this host holds 26 real checkouts.
    excluded = claude_dir / _WORKTREES
    return sorted(
        path for path in claude_dir.glob("**/*.md")
        if excluded not in path.parents
    )


def _invocations_missing_log(text: str):
    missing = []
    for match in _INVOCATION.finditer(text):
        window = text[match.start(): match.start() + _LOOKAHEAD_CHARS]
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
    # A regression guard on the test itself: if every skill file were
    # rewritten to use the Python API exclusively, the assertion above
    # would pass vacuously and stop meaning anything. >= 1 rather than a
    # specific count -- a higher threshold would make this brittle to a
    # future reorganization that consolidates skill files without
    # actually losing coverage.
    total = sum(
        len(_INVOCATION.findall(path.read_text(encoding="utf-8")))
        for path in _skill_and_agent_files()
    )
    assert total >= 1


def _worktree_fixture(claude_dir):
    """A skill file that passes, beside a nested checkout of a doc that
    would fail -- the shape that bug actually reported, in miniature."""
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
    """Proved against a fixture, because nothing on CI can catch a
    regression here: `actions/checkout` never creates a worktree, so this
    exclusion only ever matters on a developer's own machine, where a
    scan that quietly stopped excluding would read as unrelated doc rot.
    """
    nested_doc = _worktree_fixture(tmp_path)
    scanned = _skill_and_agent_files(tmp_path)

    assert nested_doc.exists(), "fixture should contain the file being excluded"
    assert nested_doc not in scanned
    assert [p.name for p in scanned] == ["SKILL.md"]


def test_the_fixture_would_otherwise_be_reported(tmp_path):
    """The other half: without the exclusion the nested doc is a genuine
    offender, so the test above is not passing because the fixture is
    harmless."""
    nested_doc = _worktree_fixture(tmp_path)
    assert _invocations_missing_log(nested_doc.read_text(encoding="utf-8"))
