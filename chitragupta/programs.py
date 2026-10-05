"""Where a program this package launches comes from: PATH, never cwd (#974).

`subprocess.run(["pdftotext", ...])` hands the lookup to the OS, and on
Windows `CreateProcess` searches the current directory before PATH.
`shutil.which` does the same there (it prepends `.` unless
`NoDefaultCurrentDirectoryInExePath` is set), and on any host a relative
or empty PATH entry is the current directory by another name. The
current directory is the one place this process does not choose: a
cloned or shared project is exactly where a `python.exe` or a
`pdftotext.bat` can be planted, and every launch here then ran it with
the user's privileges.

So a program is resolved here, against the absolute entries of PATH and
nothing else, and the launch is handed the absolute path that comes
back. An absolute entry is the user's own choice, which a directory this
process walked into cannot make for them -- including one inside the
project, such as an activated `.venv/bin`, which is why the rule is "no
implicit or relative lookup" rather than "nothing under cwd".

Standard library only and importing no other `chitragupta` module, so
`chitragupta/hook_launchers.py`, which must import without a
`config.toml`, can use it.
"""

import errno
import os
import shutil
import sys


def resolve_program(name: str) -> str | None:
    """The absolute path of the bare program `name`, or None.

    Each absolute PATH entry is searched by handing `shutil.which` the
    joined path rather than `path=`: with a directory in the name it
    looks only there, so Windows' implicit `.` never enters the search.

    On Windows a name with no extension gets `.exe`, which is what
    `CreateProcess` itself appends, rather than whatever PATHEXT finds
    first. PATHEXT would let a `.bat` or `.cmd` earlier on PATH win, and
    a batch file runs through cmd.exe, which re-parses the arguments
    (corpus paths among them) that `subprocess.run` passed as a vector.
    """
    suffix = ".exe" if sys.platform == "win32" and not os.path.splitext(name)[1] else ""
    for directory in os.environ.get("PATH", os.defpath).split(os.pathsep):
        if os.path.isabs(directory):
            found = shutil.which(os.path.join(directory, name + suffix))
            if found:
                return found
    return None


def require_program(name: str) -> str:
    """`resolve_program`, raising what a launch of a missing program raises.

    `FileNotFoundError`, as `subprocess.run([name, ...])` raised before
    this existed, so a caller's `except OSError` keeps its meaning.
    """
    found = resolve_program(name)
    if found is None:
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), name)
    return found
