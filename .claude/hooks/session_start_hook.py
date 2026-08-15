#!/usr/bin/env python3
"""SessionStart hook: report what is not yet ready, and nothing else.

Advisory class (docs/HOOKS.md): it never blocks, exits 0 whatever it
finds, and stays silent when the project is ready to draft. Three checks,
and only the first two are faults:

1. **Can each registered hook's launcher start?** A hook that fails to
   spawn cannot report that it failed to spawn -- the settings file still
   lists it, the tests still pass, and the citation gate silently stops
   enforcing CLAUDE.md's one invariant. Nothing else in the tree can
   notice that, which is the whole reason this hook exists (#197).
2. **Does `python -m src.draft gate` still refuse a fabricated citekey?**
3. **Has the corpus been synced?** -- reported as a *stage*, not a fault.

That third distinction is the design. The normal sequence is clone ->
config.toml -> `python -m src.corpus sync` -> drafting, and a user who has
not reached step three has done nothing wrong. A preflight that called an
empty ledger a failure would fire on every first session, and would teach
people to ignore the one channel meant for real faults. So an empty ledger
is reported as a position in that sequence, with the command that advances
it.

What makes the gate probe runnable that early: **a fabricated citekey is
absent from an empty ledger and a full one alike**, so the probe needs no
corpus. Measured before this was relied on -- with no ledger.sqlite present
at all, the gate exits 0 on a citation-free draft and non-zero on a
fabricated key, exactly as it does against a populated one.

Tier 1, like the checks it calls: standard library only, no third-party
import, and nothing here needs the venv.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
FABRICATED = "preflight_probe_not_a_real_citekey"


def launcher_faults() -> list[str]:
    """Registered hook commands that cannot start, read from settings.json.

    Static, because the alternative is not available: a launcher is a line
    in a config file the harness consumes, no test imports it, and CI never
    executes it. Absent or unreadable settings mean there is nothing to
    check rather than something wrong -- this hook does not own that file.
    """
    try:
        events = json.loads((REPO / ".claude" / "settings.json").read_text())["hooks"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    if not isinstance(events, dict):
        return []  # a "hooks" key of the wrong shape is unusable, not a fault
    faults = []
    for entries in events.values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                faults.extend(_launcher_fault(hook))
    return faults


def _launcher_fault(hook: dict) -> list[str]:
    """One hook entry's launcher problems, in both of the two forms.

    Exec form (`args` present) names the program in `command`; shell form
    puts it first in a command line. An unbraced `$CLAUDE_PROJECT_DIR` is
    expanded by the shell rather than substituted by the harness, and the
    shell is PowerShell on a Windows host without Git Bash -- where that
    syntax names an undefined variable and expands to nothing.
    """
    command = hook.get("command", "")
    if not command:
        return []
    program = command if "args" in hook else command.split()[0]
    text = " ".join([command, *hook.get("args", [])])
    faults = []
    if not shutil.which(program):
        faults.append(f"`{program}` is not on PATH, so a hook cannot start.")
    if "$CLAUDE_PROJECT_DIR" in text.replace("${CLAUDE_PROJECT_DIR}", ""):
        faults.append(f"`{program}` uses an unbraced $CLAUDE_PROJECT_DIR, which the "
                      "shell expands rather than the harness (docs/HOOKS.md).")
    return faults


def gate_is_live() -> bool:
    """Does `python -m src.draft gate` still refuse a fabricated citekey?

    Probed in a throwaway tree, so nothing is written under the user's
    content/ and no draft of theirs is read. The probe insists on the
    fabricated key appearing in the output, not merely on a non-zero exit:
    a gate that rejected the probe for its *location* would also exit
    non-zero, and counting that as a working gate is the false reassurance
    this check exists to prevent.
    """
    with tempfile.TemporaryDirectory() as tmp:
        content = Path(tmp) / "content"
        (content / "drafts").mkdir(parents=True)
        draft = content / "drafts" / "preflight_probe.md"
        draft.write_text(f"A claim [@{FABRICATED}].\n")
        config = Path(tmp) / "config.toml"
        config.write_text(f'[content]\ndir = "{content.as_posix()}"\n')
        result = _run("src.draft", "gate", str(draft),
                      CONFIG_PATH=str(config), CONTENT_DIR=str(content))
    return result.returncode != 0 and FABRICATED in result.stdout + result.stderr


def corpus_stage() -> str | None:
    """Where the user is in clone -> config -> sync -> draft, or None if ready."""
    result = _run("src.corpus", "ledger")
    if result.returncode != 0:
        return ("The corpus layer will not start, so no draft can be grounded. The\n"
                "usual cause is a fresh clone with no config file:\n"
                "    cp config.toml.example config.toml\n\n"
                f"{result.stderr.strip()[-400:]}")
    # Two distinct pre-sync states -- no ledger file at all, and one with no
    # rows in it -- and the corpus layer prints a different sentence for
    # each. Matching the instruction they share, rather than either
    # sentence, is what stops this reporting one of them and missing the
    # other; it also means the corpus layer stays the one deciding when a
    # sync is needed.
    if "src.corpus sync" in result.stdout:
        return ("No synced corpus yet: the ledger is absent or holds nothing. That is\n"
                "the expected state before a first sync, not a fault -- but every\n"
                "genre skill needs it, so run this before asking for a draft:\n"
                "    python -m src.corpus sync")
    return None


def _run(module: str, *args: str, **overrides: str):
    return subprocess.run(
        [sys.executable, "-m", module, *args], check=False,
        cwd=REPO, capture_output=True, text=True, env={**os.environ, **overrides},
    )


def main() -> int:
    notes = [f"BROKEN: {fault}" for fault in launcher_faults()]
    if not gate_is_live():
        notes.append("BROKEN: `python -m src.draft gate` did not refuse a fabricated "
                     "citekey. CLAUDE.md's one invariant is unenforced until that is "
                     "fixed -- do not trust a draft written in this state.")
    stage = corpus_stage()
    if stage:
        notes.append(stage)
    if notes:
        body = ("chitragupta preflight, at session start:\n\n"
                + "\n\n".join(notes)
                + "\n\nAdvisory, and measured once at startup: it will not re-run when "
                  "you fix it.")
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": body}}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException as exc:  # a broken preflight is never a broken session
        raise SystemExit(0) from exc
