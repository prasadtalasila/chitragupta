#!/usr/bin/env python3
"""PostToolUse hook: report a draft's prose findings, and never block.

`python -m chitragupta.draft style` has existed since 5.13.0 and nothing called
it. docs/ARCHITECTURE.md's "Grounding is enforced, not requested" is the
argument for why that is not enough -- the citation gate runs twice on
every draft and neither run is the skill's own good intentions -- and
#183 is that argument applied to prose. This hook is the enforced
invocation. **Only the invocation:** what the findings mean, and whether
any of them is a defect, stays a judgement, and nothing here acts on one.

**Advisory class, and everything follows from that** (docs/HOOKS.md):

- It never emits `{"decision": "block"}`. The gate is measured against
  the ledger, which is ground truth; this is measured against a line
  someone typed into `scope.md`, which can be wrong, stale or
  deliberately overridden. Blocking on the second kind refuses a
  *correct* draft on a *bad target*.
- It exits 0 whatever happens, including its own crash. A broken prose
  checker must not be able to stop a write, and it shares a matcher with
  the gate.
- It says nothing when there is nothing to say: no findings, no `vale`
  binary, not a draft.

Two behaviours here are not guesses about `chitragupta.draft style` but measured
facts about it, and both would be bugs if assumed the other way:

- **It exits 0 whatever it finds**, so the return code carries no
  information and `--json` is the only signal.
- **A path that does not exist reports zero findings**, because the
  checker never inspects Vale's return code. So this hook stats the file
  itself; without that, a draft deleted or renamed between the write and
  the check comes back as a clean bill of health, which is the one
  outcome an advisory check must never fake.
"""

import json
import subprocess
import sys

import draft_target

# What the report leads with, so the agent reads the caveat before the
# list. The check sees §9's decidable rules and nothing else, and a
# quoted "simply" is indistinguishable to it from the draft's own voice.
PREAMBLE = (
    "Prose findings from `python -m chitragupta.draft style` (WRITING-STANDARDS.md "
    "§9's decidable rules only -- it is silent on whether a paragraph leads "
    "with its point, and it cannot tell a quotation from the draft's own "
    "voice). A review aid, not a gate: nothing here blocks, and a finding is "
    "a place to look rather than a defect."
)


def main() -> int:
    draft = draft_target.from_stdin(sys.stdin)
    if draft is None or not draft.is_file():
        return 0  # not a draft, or gone between the write and this check

    payload = _findings(draft)
    if payload:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": payload,
                    }
                }
            )
        )
    return 0


def _findings(draft) -> str:
    """The report for one draft, or "" when there is nothing worth saying.

    A missing `vale` is deliberately silent rather than a warning on every
    write: it is the ordinary state of a checkout that has not run the
    `os-deps` install stage, and a hook that says so on each write teaches
    the reader to skip the channel this one shares with the citation gate.
    """
    result = subprocess.run(
        [sys.executable, "-m", "chitragupta.draft", "style", "--json", str(draft)],
        check=False,
        cwd=draft_target.REPO_ROOT,
        capture_output=True,
        text=True,
    )
    try:
        report = json.loads(result.stdout)
        drafts = report["drafts"]
    except (ValueError, TypeError, KeyError):
        return ""  # the checker failed or changed shape -- say nothing, block nothing
    lines = []
    for entry in drafts:
        lines.extend(_entry_lines(entry))
    return f"{PREAMBLE}\n\n" + "\n".join(lines) if lines else ""


def _entry_lines(entry) -> list[str]:
    """One draft's findings, or nothing at all when it has none.

    **Silence on zero findings is deliberate, and it costs something.**
    With no `language:` line in `scope.md` no dialect rule runs, so an
    empty list there means "not checked" rather than "clean" -- exactly
    the trap the verbatim scan's caveat exists to prevent. Reporting that
    here would mean a message on every write of every draft whose dossier
    predates 5.12.0, which is most of them, and a channel that speaks on
    every write is one the reader learns to skip. It is shared with the
    citation gate, so that cost is not this hook's alone to spend.

    The unrecorded dialect is therefore reported two ways instead: as a
    caveat *above the findings* when there are any, and once per draft by
    the skill step, which speaks to the human at presentation rather than
    to the agent on every write. docs/GENRE.md records that split.
    """
    if not isinstance(entry, dict):
        return []
    findings = [f for f in (entry.get("findings") or []) if isinstance(f, dict)]
    if not findings:
        return []
    lines = []
    if not entry.get("language"):
        lines.append(
            "  dialect: not checked -- no `language:` in scope.md, so no "
            "dialect rule ran. This list is not the whole picture."
        )
    for finding in findings:
        # `count` is an int in every payload this checker emits, so a
        # comparison would do -- but the whole reason this hook parses
        # `--json` defensively is that it is reading another command's
        # output, and `None > 1` raises. That exception would be caught at
        # the module tail and cost the *entire* report, not one line.
        count = finding.get("count")
        times = f" (x{count})" if isinstance(count, int) and count > 1 else ""
        lines.append(
            f"  line {finding.get('line', 0)}  "
            f"{finding.get('rule', '?')}: {finding.get('message', '')}{times}"
        )
    return lines


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    # Exception, not BaseException: a broken prose checker must not break a
    # write, but SystemExit and KeyboardInterrupt are not breakage. This
    # hook shares a matcher with the citation gate, so anything it does to
    # the turn is done to the gate's turn too.
    except Exception as exc:
        raise SystemExit(0) from exc
