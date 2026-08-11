"""Every `src.retrieval` CLI invocation named in `.claude/` must carry `--log`.

`--log` is what turns a drafting run's retrieval cost from an estimate
(docs/TOKENS.md) into something `python -m src.dossier status` can total.
A skill or subagent protocol that names the CLI without it is a silent gap
in that measurement -- found once already (peer-reviewer.md's
domain-accuracy fallback had none), and cheap to lose again the next time
a skill file is edited by hand. This is a text-scan over `.claude/`, not
an exercise of the retrieval or dossier code -- both already have their
own tests for the flag's actual effect.

Deliberately does not flag `search(query, k, snippet_chars)` /
`src.enrich.embed_index.search()` mentions: those name the Python API,
which has no `--log` parameter to check for (a real, separate gap -- see
docs/TOKENS.md's coverage note -- not a doc typo this test can catch).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_DIR = REPO_ROOT / ".claude"

# `python -m src.retrieval search "..."` / `... evidence "..." --citekey ...`
# -- the CLI form, which is the only one `--log` exists on.
_INVOCATION = re.compile(r"python -m src\.retrieval (search|evidence)\b")

# How far past the start of a matched invocation to look for its `--log`.
# Generous enough to span a `\`-continued line (draft-reviser's `evidence`
# call wraps once) without reaching into an unrelated, later sentence in
# these files -- checked by hand against every file this test scans.
_LOOKAHEAD_CHARS = 220


def _skill_and_agent_files():
    # Every Markdown file under .claude/, not just SKILL.md and agent
    # files: `deep-research/reference.md` is a real, separate protocol
    # doc that a retrieval invocation could land in just as easily, and
    # nothing about this project's layout rules out another one like it
    # appearing alongside a future skill.
    return sorted(CLAUDE_DIR.glob("**/*.md"))


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
