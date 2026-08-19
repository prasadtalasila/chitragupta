"""What `--help` should call this command, given how it was started.

Every layer's parser hardcoded `prog="python -m chitragupta.<layer>"`
because that was the only way to reach it. There are two ways now -- the
console script this package installs, and the module form the hooks and
skills keep using (docs/PACKAGING.md says why both survive) -- and a
usage line that names the wrong one is worse than no usage line: it tells
a reader to type something that may not exist on their PATH.

Deliberately derived from `sys.argv[0]` rather than from an environment
variable or a flag threaded down from the dispatcher. The dispatcher is
not the only caller: a layer's `main()` is invoked directly by tests and
by `python -m chitragupta.<layer>`, and anything that had to be passed in
would be absent on exactly those paths and default to a lie.

Standard library only, and it imports no other module in this package --
including `config`, which raises without a `config.toml`. Computing a
usage string must never be the thing that stops `--help` printing.
"""

import os
import sys

# The two names `[tool.poetry.scripts]` installs. Matched exactly rather
# than by prefix: a script called `chitragupta-old` on someone's PATH is
# not this one, and `cg` is short enough that a substring test would
# match half the executables on a system.
CONSOLE_SCRIPTS = ("chitragupta", "cg")


def prog_for(layer: str) -> str:
    """`chitragupta <layer>` when started as the console script, else the
    module form.

    `.exe` is stripped because that is what Windows appends to a console
    script, and `chitragupta.exe draft` is not what anybody types.
    """
    invoked = os.path.basename(sys.argv[0])
    root, ext = os.path.splitext(invoked)
    if ext.lower() == ".exe":
        invoked = root
    if invoked in CONSOLE_SCRIPTS:
        return f"{invoked} {layer}" if layer else invoked
    return f"python -m chitragupta.{layer}" if layer else "python -m chitragupta"
