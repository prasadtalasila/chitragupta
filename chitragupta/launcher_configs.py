"""Which launcher configs a project carries, one per harness (#812).

Every `{"hooks": {...}}` document (`.claude/settings.json`,
`.codex/hooks.json`), so a dead launcher is reported on every harness.
OpenCode's plugin refuses writes itself when the gate cannot start.
Reads a launcher config, never a payload: docs/HOOKS.md's one layer-1
exception.
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
