#!/usr/bin/env python3
"""SessionStart hook: report what is not yet ready, and nothing else.

Advisory class (docs/HOOKS.md): it never blocks, exits 0 whatever it
finds, and stays silent when the project is ready to draft. Three checks,
and only the first two are faults:

1. **Can each registered hook's launcher start, and can it import
   `chitragupta` once it has?** A hook that fails to spawn cannot report
   that it failed to spawn -- the settings file still lists it, the tests
   still pass, and the citation gate silently stops enforcing CLAUDE.md's
   one invariant. Noticing that is the whole reason this hook exists
   (#197). Since the package can now live in a venv the harness may not
   be using, a launcher that resolves on `PATH` is no longer enough on
   its own -- an `init`-ed project can have a `python` that starts and
   then cannot `import chitragupta`, which fails exactly as silently. It
   is not, on its own, enough either way: **this hook is launched by the
   same interpreter name it vets**, so the one host where the gate's
   launcher is missing or broken is a host where this report never
   arrives either. `chitragupta/hook_launchers.py` holds both checks for
   that reason, and `python -m chitragupta.draft gate` makes them too.
2. **Does `python -m chitragupta.draft gate` still refuse a fabricated citekey?**
3. **Has the corpus been synced?** -- reported as a *stage*, not a fault.

That third distinction is the design. The normal sequence is clone ->
config.toml -> `python -m chitragupta.corpus sync` -> drafting, and a user who has
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
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

# Not at the top, because the path this import needs is the line above it:
# the hook is run as a script by the harness, from a directory that is not
# the repository, so `chitragupta` is only importable once the root it derived from
# its own location is on the path. Module level rather than inside the
# function on purpose -- a local `try: ... except ImportError: return []`
# would turn a genuine breakage into the exact silence this hook exists to
# notice, and a crashed advisory hook (which can never block) is the safer
# half of that trade. `scripts/release.py` ships every git-tracked path bar
# tests/, .github/ and bench/, so `chitragupta/` and `.claude/hooks/` always travel
# together in a release bundle.
#
# Appended rather than prepended: nothing else supplies a `chitragupta` package in
# a real run, so the position costs nothing there, while prepending would
# let a repo root shadow anything already importable -- including, in this
# repository's own tests, the stub `chitragupta/` a test plants to simulate a dead
# gate for the hook's *children*.
sys.path.append(str(REPO))
from chitragupta import hook_launchers  # noqa: E402  pylint: disable=wrong-import-position

FABRICATED = "preflight_probe_not_a_real_citekey"


def launcher_faults() -> list[str]:
    """Registered hook commands that cannot start, read from settings.json.

    The check itself is `chitragupta/hook_launchers.py`, shared with
    `python -m chitragupta.draft gate` -- see this module's docstring for why one
    reporter is not enough. The settings path is passed rather than looked
    up there so that this hook keeps deriving the repository root from its
    own on-disk location, which is what lets a test point it at a
    throwaway tree.
    """
    return hook_launchers.faults(REPO / ".claude" / "settings.json")


def gate_is_live() -> bool:
    """Does `python -m chitragupta.draft gate` still refuse a fabricated citekey?

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
        result = _run(
            "chitragupta.draft",
            "gate",
            str(draft),
            CONFIG_PATH=str(config),
            CONTENT_DIR=str(content),
        )
    return result.returncode != 0 and FABRICATED in result.stdout + result.stderr


def corpus_stage() -> str | None:
    """Where the user is in clone -> config -> sync -> draft, or None if ready."""
    result = _run("chitragupta.corpus", "ledger")
    if result.returncode != 0:
        return (
            "The corpus layer will not start, so no draft can be grounded. The\n"
            "usual cause is a fresh clone with no config file:\n"
            "    cp config.toml.example config.toml\n\n"
            f"{result.stderr.strip()[-400:]}"
        )
    # Two distinct pre-sync states -- no ledger file at all, and one with no
    # rows in it -- and the corpus layer prints a different sentence for
    # each. Matching the instruction they share, rather than either
    # sentence, is what stops this reporting one of them and missing the
    # other; it also means the corpus layer stays the one deciding when a
    # sync is needed.
    if "chitragupta.corpus sync" in result.stdout:
        return (
            "No synced corpus yet: the ledger is absent or holds nothing. That is\n"
            "the expected state before a first sync, not a fault -- but every\n"
            "genre skill needs it, so run this before asking for a draft:\n"
            "    python -m chitragupta.corpus sync"
        )
    return None


def _run(module: str, *args: str, **overrides: str):
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        check=False,
        cwd=REPO,
        capture_output=True,
        text=True,
        env={**os.environ, **overrides},
    )


def main() -> int:
    notes = [f"BROKEN: {fault}" for fault in launcher_faults()]
    if not gate_is_live():
        notes.append(
            "BROKEN: `python -m chitragupta.draft gate` did not refuse a fabricated "
            "citekey. CLAUDE.md's one invariant is unenforced until that is "
            "fixed -- do not trust a draft written in this state."
        )
    stage = corpus_stage()
    if stage:
        notes.append(stage)
    if notes:
        body = (
            "chitragupta preflight, at session start:\n\n"
            + "\n\n".join(notes)
            + "\n\nAdvisory, and measured once at startup: it will not re-run when "
            "you fix it."
        )
        print(
            json.dumps(
                {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": body}}
            )
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    # Exception, not BaseException: a broken preflight is never a broken
    # session, but SystemExit and KeyboardInterrupt are not breakage.
    # Catching those too would swallow this hook's own exit status and an
    # operator's Ctrl-C alike, and would need a re-raising SystemExit
    # clause above to undo half of itself.
    except Exception as exc:
        raise SystemExit(0) from exc
