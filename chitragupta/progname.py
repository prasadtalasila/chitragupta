"""What `--help` should call this command, given how it was started.

Derived from `sys.argv[0]`, not passed down from the dispatcher: tests and
`python -m chitragupta.<layer>` call a layer's `main()` directly, and a
passed-in value would be absent there. Standard library only (not even
`config`, which raises without a `config.toml`), so `--help` always prints.
"""

import os
import sys

# The two `[project.scripts]` names, matched exactly: a prefix or
# substring test would match `chitragupta-old` or half a system's `cg*`.
CONSOLE_SCRIPTS = ("chitragupta", "cg")


def prog_for(layer: str) -> str:
    """`chitragupta <layer>` when started as the console script, else the
    module form. `.exe` is stripped, as Windows appends it."""
    invoked = os.path.basename(sys.argv[0])
    root, ext = os.path.splitext(invoked)
    if ext.lower() == ".exe":
        invoked = root
    if invoked in CONSOLE_SCRIPTS:
        return f"{invoked} {layer}" if layer else invoked
    return f"python -m chitragupta.{layer}" if layer else "python -m chitragupta"
