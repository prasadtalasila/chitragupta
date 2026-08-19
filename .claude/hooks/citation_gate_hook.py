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
"""

import json
import subprocess
import sys

import draft_target


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
        check=False, cwd=draft_target.REPO_ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
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
