#!/usr/bin/env python3
"""PostToolUse hook: report a C1/C2 crossing at the edit that causes it.

`tests/test_code_standards_scan.py` already catches every crossing, and
this hook adds no detection whatever. What it adds is *timing*. The
ratchet catches a function that crossed 25 statements at the next full
test run, which may be a session later -- by which point splitting it is
separate work against code whose reasons have left the context that
wrote it. At the edit it is an adjustment to the change in hand.

That is the same argument `style_check_hook.py` makes for prose, and
issue 431 is it pointed at this repository's own code: until this hook
existed, every row of `docs/HOOKS.md`'s registry was keyed on a write
under `content/drafts/`, and nothing hooked a change to `chitragupta/`.

**Advisory class, and everything follows from it** (docs/HOOKS.md's rule
that decides everything):

- It never emits `{"decision": "block"}`. C1/C2 is a ratchet, not ground
  truth: `docs/CODE-STANDARDS.md`'s own failure message says to add an
  entry to the register when a split is genuinely wrong, and #405 took
  that path. `docs/TECHNICAL-DEBT.md` is equally emphatic that nothing
  goes red for an unpaid debt. The citation gate stays the only hook
  allowed to block, and SOUL.md has why there is exactly one.
- It exits 0 whatever happens, including its own crash.
- It says nothing when there is nothing to say.

**Adapter only.** The scan is `scripts/code_standards.py`, runnable by
hand and by CI; this file reads a `PostToolUse` payload on stdin and
writes one JSON document. `docs/HOOKS.md`'s layer rule -- an adapter
contains no logic anyone could want to run by hand -- is what puts the
scan there rather than here, and that module's docstring says why
`scripts/` rather than `chitragupta/`.

**Inert, not broken, in a scaffolded project.** `chitragupta/init.py`'s
`COPY_VERBATIM` begins `".claude"`, so this hook and its settings entry
are copied into every `chitragupta init` directory -- which deliberately
has no `chitragupta/`, `scripts/` or `tests/` tree
(docs/PACKAGING.md). Nothing there is ever under a watched root, so
`source_target` returns None on every write; and if a path somehow were,
a missing scanner is silence rather than a fault. That is the same
distinction `session_start_hook.py` draws when it reports an unsynced
corpus as a stage rather than a failure.

**It does not share `draft_target.py`.** That module answers "was this
write a draft?" and its docstring is explicit that what must be shared
between hooks is the *definition of a draft*. This one needs the
opposite question, so it holds its own -- a sibling helper is right when
a second developer-side hook appears, not before.
"""

import json
import subprocess
import sys
from pathlib import Path

# This file's own location, never the target path and never the working
# directory: a hook is run from wherever the harness happens to be. The
# same rule `draft_target.py` records, learned the same way.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCANNER = REPO_ROOT / "scripts" / "code_standards.py"

# The intersection of C1's roots and C2's. C1 also covers `tests/` and C2
# does not, and hooking the difference would report on the test file
# someone is writing at the moment they are writing it, for a rule that
# has one registered test offender and is therefore silent there anyway.
# The intersection is the only line neither rule argues with.
WATCHED_ROOTS = ("chitragupta", "scripts")

PREAMBLE = (
    "Size findings from `python3 scripts/code_standards.py` "
    "(docs/CODE-STANDARDS.md's C1 and C2). Reported at the edit rather "
    "than at the next test run, because that is when the split is still "
    "part of the change in hand. Advisory: nothing here blocks, and "
    "adding an entry to code-standards-register.toml is a documented "
    "move when a split is genuinely wrong."
)


def source_target(stdin) -> "Path | None":
    """The written file when it is one this hook checks, else None.

    Malformed stdin fails open in all three shapes that have been hit --
    invalid JSON, valid JSON that is not an object, and a `tool_input`
    that is not a dict. Each means "no file path was given", and a hook
    that raises cannot report that it raised.

    A relative `file_path` is resolved rather than ignored: Claude Code
    documents it as absolute and it has always been so, but a substring
    match would silently skip a relative one -- no leading slash to
    match, no error, just an unchecked write. Containment is
    `is_relative_to` on resolved paths, so `chitragupta/../../etc/passwd`
    cannot pass for a source file.
    """
    try:
        payload = json.load(stdin)
        raw = payload["tool_input"]["file_path"]
    except (ValueError, TypeError, KeyError):
        return None
    path = Path(raw)
    resolved = (path if path.is_absolute() else REPO_ROOT / path).resolve()
    if resolved.suffix != ".py":
        return None
    if not any(resolved.is_relative_to(REPO_ROOT / root) for root in WATCHED_ROOTS):
        return None
    return resolved


def _findings(path: Path) -> list:
    """What the scanner says about `path`, or nothing at all.

    Every failure mode is silence, deliberately: an absent scanner (the
    scaffolded-project case in the module docstring), a non-zero exit, or
    output this cannot parse. The hook is reading another command's
    stdout, which is exactly where `style_check_hook.py` records the same
    posture -- a checker that failed or changed shape must cost the
    reader nothing.
    """
    if not SCANNER.is_file():
        return []
    result = subprocess.run(
        [sys.executable, str(SCANNER), str(path), "--json"],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout)["findings"]
    except (ValueError, TypeError, KeyError):
        return []


def _report(found: list) -> str:
    lines = []
    for finding in found:
        noun = "statements" if finding.get("rule") == "C1" else "code lines"
        lines.append(
            f"  {finding.get('rule', '?')}  {finding.get('name', '?')}  "
            f"{finding.get('count', '?')} {noun} "
            f"(limit {finding.get('limit', '?')})"
        )
    return f"{PREAMBLE}\n\n" + "\n".join(lines)


def main() -> int:
    path = source_target(sys.stdin)
    if path is None:
        return 0
    found = _findings(path)
    if found:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": _report(found),
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    # Exception, not BaseException: a broken size check must not break a
    # write. This hook shares a matcher with the citation gate, so
    # anything it does to the turn is done to the gate's turn too.
    except Exception as exc:
        raise SystemExit(0) from exc
