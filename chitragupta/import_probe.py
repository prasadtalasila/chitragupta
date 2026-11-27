"""The import probe `hook_launchers` runs on each bare Python launcher.

Split from `chitragupta/hook_launchers.py` (#1025): can a launcher that
exists import `chitragupta`, which only spawning it can tell. Stdlib
only, importing no `chitragupta` module but `programs`, so it works
without a `config.toml`.
"""

import os
import subprocess
from pathlib import Path, PurePath

from chitragupta import programs

# Generous: once per session, and a cold venv on a network filesystem must
# not be misreported as unable to import.
IMPORT_PROBE_TIMEOUT = 5.0


def is_bare_command(program: str) -> bool:
    """Is `program` a bare name, resolvable only via PATH?

    The probe *executes* the program, and the settings file naming it was
    found by walking cwd's ancestors (#637), so a planted file in an
    untrusted tree could name its own binary. Only bare names, resolved
    against the user's PATH, are probed; a path-qualified launcher
    silently forgoes the probe (a "not probed" note would be a false
    fault, #509). Separators are checked as characters, not PurePath, so
    a Windows path is caught on POSIX too; `:` covers drive prefixes.
    """
    # Resolved by `chitragupta.programs`: on Windows `shutil.which` and
    # `CreateProcess` search cwd first (#974).
    return not any(sep in program for sep in ("/", "\\", ":"))


def is_python_interpreter(program: str) -> bool:
    """Does `program` name a Python interpreter?

    `-c "import chitragupta"` against `bash` or `node` would fail every
    session as a false fault (#509), so only Python is probed. Matched on
    the basename without version suffix or `.exe`; anything unrecognised
    is simply not probed.
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

    An unresolved or unspawnable program is left to `hook_launchers`'
    PATH check, so nothing is reported twice. Non-zero exit and timeout
    are both faults.
    """
    # The absolute path: `CreateProcess` would search cwd again (#974).
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
