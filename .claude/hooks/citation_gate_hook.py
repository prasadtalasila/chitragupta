#!/usr/bin/env python3
"""PostToolUse hook: enforce the citekey gate on genre-skill drafts.

AGENTS.md calls python -m chitragupta.draft gate "a gate, not a lint
suggestion" and every genre skill's prose instructs the agent to run it
before presenting a draft -- but until this hook existed, nothing
mechanically enforced that instruction; an agent could just skip the
step. This makes it enforced by the harness: every Write/Edit under
content/drafts/ (.md from survey-writer/textbook-chapter-writer/
tutorial-writer/deep-research,
.tex from thesis-chapter-writer -- see each SKILL.md's "Save the
draft/fragment as content/drafts/<slug>.{md,tex}" step) is gated
automatically, and a failure is surfaced back to Claude as blocking
feedback (not a silent/advisory warning).

**The gate class, and the only member of it.** This is the one hook in
this repository permitted to block, because it is the only one measured
against ground truth: a citekey is in the ledger or it is not, and no
state of the world makes an absent one legitimately present.
docs/HOOKS.md has the axis that decides which checks may block, and
SOUL.md has why there is exactly one.

Deciding whether a write was a draft at all now lives in
`draft_target.py`, shared with the advisory hook beside it. The
subtleties it holds -- a relative `file_path`, the repo root taken from
the hook's own location, `is_relative_to` containment rather than a
substring match, the two suffixes this pipeline writes -- are recorded
there, each learned from a real near-miss. What is left in this file is
the gate and nothing else.

**A non-zero gate exit means two different things, and only one of them
is a citekey problem.** #563: in an `init`-ed project whose harness
started from a shell that never activated the venv, `sys.executable` is
some `python` that resolves on `PATH` but cannot `import chitragupta` --
`python -m chitragupta.draft gate` then exits non-zero with a
`ModuleNotFoundError`, and the block reason used to say "Fix the
offending citekey(s)" over that traceback. The gate still has to fail
closed -- nothing should land ungated just because the environment is
broken -- but blaming a citekey that was never checked wastes the one
message this hook gets. `_environment_is_broken` probes the same
interpreter directly (`-c "import chitragupta"`) rather than matching
`ModuleNotFoundError` in the gate's stderr, per DEVELOPER-AGENTS.md's
"classify a failure by cause, not by message" convention. It does not
reuse `chitragupta/hook_launchers.py`'s own `_import_fault`: that would
mean importing `chitragupta` from *this* process to reach the probe,
which is exactly the operation being tested for -- the same trap
`session_start_hook.py`'s docstring names, and worse here, since this is
the one hook required to fail closed rather than merely go silent.
"""

import json
import subprocess
import sys

import draft_target

IMPORT_PROBE_TIMEOUT = 5.0


def _environment_is_broken() -> bool:
    """Can `sys.executable` import `chitragupta` at all?

    Run only after the gate itself has already failed -- this is an extra
    subprocess, paid on the rare non-zero path, not on every draft write.

    `cwd=draft_target.REPO_ROOT`, matching the gate call above: `python -c`
    also puts an empty-string cwd entry on `sys.path`, so in a checkout
    (which relies on exactly that to find `chitragupta/`, no PYTHONPATH
    needed) a probe launched from wherever *this hook process* happened to
    start would say the environment is broken even when the gate call --
    which does set this cwd -- imported the package just fine.
    """
    try:
        probe = subprocess.run(
            [sys.executable, "-c", "import chitragupta"],
            check=False,
            cwd=draft_target.REPO_ROOT,
            capture_output=True,
            timeout=IMPORT_PROBE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return True  # a hung probe never proved the interpreter works either
    return probe.returncode != 0


def main() -> int:
    file_path = draft_target.from_stdin(sys.stdin)
    if file_path is None:
        return 0  # not a genre-skill draft -- nothing to gate

    # sys.executable, not a bare "python"/"python3". This hook is
    # the gate's only automatic enforcement point, and an interpreter name
    # that does not resolve raises FileNotFoundError here -- which exits
    # non-zero *without* the block, so the draft lands ungated. A hard
    # gate that degrades to advisory depending on whether a host has
    # `python` as well as `python3` is the worst of the available failure
    # modes. The interpreter already running this hook is known to exist
    # and is the one settings.json chose.
    result = subprocess.run(
        [sys.executable, "-m", "chitragupta.draft", "gate", str(file_path)],
        check=False,
        cwd=draft_target.REPO_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0 and _environment_is_broken():
        reason = (
            "The citation gate could not run -- this is an environment fault, "
            "not a bad citekey (nothing was actually checked). "
            f"`{sys.executable}` cannot `import chitragupta`. The usual cause "
            "is a shell that never activated the project's venv -- activate "
            "it (or start this session from a shell where it is already "
            "activated) and this file will be re-checked automatically on your next write to "
            "it. Blocking until then, since a citekey cannot be verified "
            "either way.\n\n"
            f"{result.stdout}{result.stderr}"
        )
        print(json.dumps({"decision": "block", "reason": reason}))
    elif result.returncode != 0:
        reason = (
            "Citation gate FAILED for this draft (AGENTS.md: a hard gate, not "
            "advisory). Fix the offending citekey(s) -- correct the key or "
            "remove the claim -- then this file will be re-checked "
            "automatically on your next write to it.\n\n"
            f"{result.stdout}{result.stderr}"
        )
        print(json.dumps({"decision": "block", "reason": reason}))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
