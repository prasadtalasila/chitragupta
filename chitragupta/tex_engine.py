"""How this codebase starts a TeX engine on draft text (#823, #1037).

Two callers, the pdf render (`render_output/_pandoc.py`) and the
figure-layout probe (`review/figure_layout/_probe.py`), and one rule for
both: the draft may not make TeX read a file outside it.

That rule used to be kpathsea's `openin_any=p` alone. TeX Live 2024
changed `p` to restrict absolute paths to `TEXMFOUTPUT`, and `luaotfload`
opens `ScriptExtensions.txt` by absolute path from texmf-dist on every
LuaLaTeX run, so under `p` every render on a current distribution failed
before TeX printed a line; TeX Live 2026 drops the read check altogether.
pandoc sets `TEXMFOUTPUT` itself, so no prefix variable reaches the
engine either (measured; plans/823-tex-read-hardening.md has the
addendum). The fence is therefore a LuaTeX `find_read_file` callback,
`assets/latex/chitragupta-read-fence.lua`, which refuses an absolute,
`..` or dot-leading name after the main file and logs the refusal, and
`openin_any=r` keeps kpathsea's own dot-file refusal underneath it.
"""

import os

from chitragupta import config

READ_FENCE = config.shipped("assets", "latex", "chitragupta-read-fence.lua")

# TeX wraps its log at `max_print_line` (~79 columns), which breaks a
# one-line `\typeout` parse (#496); kpathsea reads a same-named
# environment variable, and LuaTeX honours it. 1000 is past any real
# line this codebase writes.
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
