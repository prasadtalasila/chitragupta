"""The import probe `hook_launchers` runs on each bare Python launcher.

Split out of `chitragupta/hook_launchers.py` (#1025), whose other job is
reading the settings file and saying whether each launcher exists. This
one answers the next question for a launcher that does: can it import
the `chitragupta` package, which only spawning it can tell. Everything
that decides whether spawning it is safe lives here with the spawn.

Standard library only, and no `chitragupta` module but `programs`, for
the reason `hook_launchers` gives: it must import without a
`config.toml`.
"""

import os
import subprocess
from pathlib import Path, PurePath

from chitragupta import programs

# Generous on purpose: this runs once per session, not once per keystroke,
# and a launcher that is merely slow to start (a cold venv on a networked
# filesystem) must not be misreported as one that cannot import the
# package at all.
IMPORT_PROBE_TIMEOUT = 5.0


def is_bare_command(program: str) -> bool:
    """Is `program` a bare name, resolvable only via PATH?

    The import probe *executes* the program, and the settings file that
    named it was found by walking cwd's ancestors for a `config.toml`
    (#637) -- so inside an untrusted tree (a cloned project, a directory
    under /tmp), a planted settings file could name `/that/tree/python3`
    and this module would run an attacker's binary with the user's
    privileges: `is_python_interpreter` below checks only the basename,
    and `shutil.which` resolves a path-qualified program as-is rather
    than via PATH. A bare name is resolved against PATH -- the user's own
    environment, which the walked-to directory cannot rewrite -- so only
    bare names are probed. Every launcher this repository ships is one.

    A path-qualified launcher (an `init`-ed project naming its venv's
    python by path) still gets `hook_launchers`' existence check; it
    forgoes the import probe, and silently -- emitting a "not probed"
    sentence every session would be a fault about the probe, not the
    hook, the exact false-positive class #509/m-38 removed. Reporting
    less is the accepted price of never executing a file merely because
    a directory this process walked into named it.

    Separators are checked as characters, not through PurePath: on a
    POSIX host `PurePath(r"..\\python.exe").name` is the whole string
    (backslash is not a separator there), yet the same settings file
    carried to a Windows host would resolve it as a path. `:` covers
    both a Windows drive prefix and there being no legitimate bare
    launcher name containing one.
    """
    # "Resolved against PATH" means `chitragupta.programs`, not a plain
    # lookup: on Windows `shutil.which` and `CreateProcess` both search cwd
    # first, so the premise above held only on POSIX, and only for a PATH
    # with no relative entry, until #974.
    return not any(sep in program for sep in ("/", "\\", ":"))


def is_python_interpreter(program: str) -> bool:
    """Does `program` name a Python interpreter?

    `import_fault` runs `<program> -c "import chitragupta"`, which is a
    Python invocation and nothing else. Running it against a launcher that
    is not Python -- `bash`, `uv`, `node` -- means the program either
    rejects `-c` or runs something unrelated, and either way exits
    non-zero, which this module would then report as "cannot import
    chitragupta" every single session. That fault would be about the
    probe, not about the hook (#509/m-38).

    Latent rather than observed: every launcher this repository ships is
    Python today. It is a *silent* latency, though -- a settings file
    naming `bash` is legal and would produce a false fault on every
    session with nothing pointing at the cause -- so the probe is gated
    on what it can actually answer for.

    Basename, with any version suffix and a Windows extension removed, so
    `/usr/bin/python3.12` and `C:/…/python.exe` are both recognised. Not
    a guess about arbitrary interpreters: an unrecognised program is
    simply not probed, which is the pre-package behaviour and reports
    nothing rather than something wrong.
    """
    stem = PurePath(program).name.lower()
    stem = stem[: -len(".exe")] if stem.endswith(".exe") else stem
    return stem.split("-")[0].rstrip("0123456789.") in ("python", "py", "pypy")


def probe_env(settings_path: Path) -> dict | None:
    """The probe's environment: safe-path unless this is a checkout (#822).

    `-c` puts cwd first on `sys.path`, where a scaffolded project may hold
    a stray `chitragupta/`. This module living inside the project that
    `settings_path` belongs to means a checkout; anywhere else, an install.
    """
    root = Path(settings_path).resolve().parent.parent
    if Path(__file__).resolve().is_relative_to(root):
        return None
    return {**os.environ, "PYTHONSAFEPATH": "1"}


def import_fault(program: str, env: dict | None = None) -> str | None:
    """Can `program` import the `chitragupta` package? One short subprocess.

    A program that does not resolve is not probed and not reported: the
    PATH check in `hook_launchers` already names it, so it is never
    reported twice. A
    non-zero exit and a timeout are both faults; an interpreter that
    cannot be spawned at all (`OSError`, e.g. a resolved-but-not-executable
    path) is left to that PATH check too.
    """
    # The absolute path, never the bare name, which `CreateProcess` would
    # look up in cwd all over again (#974).
    resolved = programs.resolve_program(program)
    if resolved is None:
        return None
    try:
        result = subprocess.run(
            [resolved, "-c", "import chitragupta"],
            capture_output=True,
            timeout=IMPORT_PROBE_TIMEOUT,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return (  # pragma: no cover-windows
            f"`{program}` did not respond within {IMPORT_PROBE_TIMEOUT:.0f}s "
            "probing whether it can import chitragupta -- treated as a fault, "
            "not as clean."
        )
    except OSError:
        return None
    if result.returncode != 0:
        return (  # pragma: no cover-windows
            f"`{program}` cannot import chitragupta, so a hook it launches will "
            "start and then fail silently. Activate the virtualenv chitragupta "
            "is installed into before starting this session."
        )
    return None
