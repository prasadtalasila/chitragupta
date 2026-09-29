"""Which launcher configs a project carries, one per harness (#812).

`hook_launchers.faults` reads one `{"hooks": {...}}` document -- the shape
Claude Code's `.claude/settings.json` and Codex's `.codex/hooks.json`
share -- and says what would stop a hook from starting. This is the list
of those documents, so the session preflight, the gate and `doctor`
report a dead launcher on every harness a project is set up for, not
only on Claude Code. OpenCode's launcher is a plugin rather than a
config; its own failure to start the gate refuses the write
(`.opencode/chitragupta/gate.js`).

Standard library only, and it reads a launcher config, never a payload:
the one layer-1 exception docs/HOOKS.md names, kept to one place.
"""

from pathlib import Path

from chitragupta import hook_launchers

CONFIGS = (".claude/settings.json", ".codex/hooks.json")


def present(root: Path) -> list[Path]:
    """The launcher configs that exist under `root`, in `CONFIGS` order."""
    return [root / rel for rel in CONFIGS if (root / rel).is_file()]


def faults(root: Path) -> list[str]:
    """Every present config's launcher faults, each prefixed with its config."""
    found = [
        f"{path.relative_to(root).as_posix()}: {fault}"
        for path in present(root)
        for fault in hook_launchers.faults(path)
    ]
    return list(dict.fromkeys(found))
