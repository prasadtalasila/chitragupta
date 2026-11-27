"""Where a program this package launches comes from: PATH, never cwd (#974).

On Windows `CreateProcess` and `shutil.which` search the current
directory first, and a relative or empty PATH entry is cwd anywhere. A
cloned project is exactly where a `python.exe` can be planted, so a
program is resolved against PATH's absolute entries only (an activated
`.venv/bin` is fine: the rule is "no implicit or relative lookup").

Standard library only and importing no other `chitragupta` module, so
`hook_launchers.py`, which must import without a `config.toml`, can use it.
"""

import errno
import os
import shutil
import sys


def resolve_program(name: str) -> str | None:
    """The absolute path of the bare program `name`, or None.

    `shutil.which` gets the joined path, not `path=`, so Windows' implicit
    `.` never enters the search. On Windows a bare name gets `.exe`, not
    PATHEXT's first match: a `.bat` runs through cmd.exe, which re-parses
    the arguments `subprocess.run` passed as a vector.
    """
    suffix = ".exe" if sys.platform == "win32" and not os.path.splitext(name)[1] else ""
    for directory in os.environ.get("PATH", os.defpath).split(os.pathsep):
        if os.path.isabs(directory):
            found = shutil.which(os.path.join(directory, name + suffix))
            if found:
                return found
    return None


def require_program(name: str) -> str:
    """`resolve_program`, raising `FileNotFoundError` as a launch of a
    missing program does, so a caller's `except OSError` keeps its meaning.
    """
    found = resolve_program(name)
    if found is None:
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), name)
    return found
