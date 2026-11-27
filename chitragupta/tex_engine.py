"""How this codebase starts a TeX engine on draft text (#823, #1037).

Used by the pdf render and the figure-layout probe, under one rule: the
draft may not make TeX read a file outside it. kpathsea's `openin_any=p`
alone no longer works (TeX Live 2024 made it refuse luaotfload's own
absolute reads; plans/823-tex-read-hardening.md), so the fence is the
LuaTeX callback `assets/latex/chitragupta-read-fence.lua`, with
`openin_any=r` underneath it.
"""

import os

from chitragupta import config

READ_FENCE = config.shipped("assets", "latex", "chitragupta-read-fence.lua")

# TeX wraps its log at `max_print_line`, breaking a one-line `\typeout`
# parse (#496); 1000 is past any line this codebase writes.
_MAX_PRINT_LINE = "1000"


def engine_opts() -> list[str]:
    """The engine's own flags: no `\\write18` at all, and the read fence."""
    return ["-no-shell-escape", f"--lua={READ_FENCE}"]


def engine_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """The host's environment, `extra` on top, and the read rules last,
    so neither the host nor a caller can loosen them."""
    return {
        **os.environ,
        **(extra or {}),
        "max_print_line": _MAX_PRINT_LINE,
        "openin_any": "r",
    }
