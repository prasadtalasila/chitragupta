"""Is the `chitragupta` now running a copy planted in a scaffolded project?

Split from `chitragupta/config.py` (#891), the same way config_load,
config_path and config_enrich already are: `config.py` calls
`refuse_if_shadowed` at import time, before it discovers `PROJECT_ROOT`
(that discovery follows `CHITRAGUPTA_PROJECT`, which says where the
user's data lives and must not also decide which code is trusted).
`chitragupta/init.py` is the other caller, for `SCAFFOLD_MARKER` and
`unsafe_marker_reason`.

**The gap (#891 gap 1, following #822).** `.claude/hooks/safe_path.py`
protects a hook's own children. The genre skills and `AGENTS.md` also run
`python -m chitragupta.draft gate` and friends directly, from the project
root or any directory inside it (docs/CONFIG.md), with no hook in
between. `-m` puts that directory first on `sys.path`, so a `chitragupta/`
planted there is imported in place of the install.

**What this cannot close -- read before trusting it further.** The check
runs *inside* the `chitragupta` Python already selected, so it runs only
if that copy's own `config.py` calls it. A `chitragupta/` committed before
this check existed -- every real stale or cloned duplicate, hostile or
not -- has no such call, and runs unchecked. The only plant this can ever
catch is one that already carries this exact check (one copied from a
`chitragupta-cli` release built after it shipped). A single top-level
`chitragupta.py` cannot reach it at all: it has no `__path__`, so there is
no `chitragupta.config` for the check to live in, and its own top-level
code has run before `-m` fails to find `chitragupta.draft`. Closing either
needs a trusted bootstrap that runs before `-m` resolves its target -- a
`sitecustomize.py` or a `.pth` file's exec lines shipped by the
distribution, global to every Python run in the venv -- which is larger
than this issue's surgical scope and is not implemented. `init` still
refuses to scaffold over either shape (`ScaffoldTargetUnsafe`).

**What it keys on: the mechanism that lets a plant win.** A plant wins
only because the directory a command runs from is `sys.path[0]`. So the
running copy is refused when all three hold:

1. the directory it was imported from -- the parent of its `chitragupta/`
   -- is `sys.path[0]` (`''` meaning the current directory);
2. that directory is not also elsewhere on `sys.path` *for a reason other
   than `PYTHONPATH`*; and
3. the project that directory belongs to -- the nearest `config.toml`
   above it, found by `config.discover_project_root`'s own walk with no
   `CHITRAGUPTA_PROJECT` -- carries `SCAFFOLD_MARKER`.

An install anywhere -- a venv's `site-packages` (including one nested
inside the project), `--target`, or an editable checkout reached through
its `.pth` file -- is never imported from `sys.path[0]` (1). `cd`-ing into
an editable checkout and running there is exempt because the `.pth` file
also puts it later on `sys.path` (2), and that entry did not come from
`PYTHONPATH`. A plain checkout run from its own tree has its own,
unmarked `config.toml` (3), even when the checkout sits inside a marked
directory such as a scaffolded `~`. Paths are made absolute without
resolving symlinks, so a symlinked `<root>/chitragupta` is judged, and
named in the `[fatal]` message, at the path Python imported, not at the
link's target. Earlier versions of this check keyed on
`config.PROJECT_ROOT`, on the one directory above the package, on every
ancestor, on the name `site-packages`, and on any `sys.path[1:]` entry
regardless of its source; each missed a plant or refused an install, and
review on #928 records which.

**Why `PYTHONPATH` entries are excluded from condition 2.** `PYTHONPATH=.`
(or `PYTHONPATH=$PWD`, the same shell or `direnv` habit) adds the current
directory to `sys.path` a second time, which used to satisfy condition 2
and switch the whole check off for a plant sitting in plain sight
(raised, and reproduced, in review). Condition 2 exists only for the
editable-checkout shape, and that shape is still exempt without counting
`PYTHONPATH`: an editable install's own `.pth` file is processed by
`site.py`, not by the `PYTHONPATH` environment variable, so its entry
survives the exclusion. `PYTHONPATH` entries are found by splitting
`os.environ.get("PYTHONPATH", "")` on `os.pathsep`, the same splitting
Python's own interpreter start-up does.

`init` writes the marker into every project it scaffolds, and writes it
on any rerun if it is missing, with no `--force`, so re-running `chitragupta
init` adopts a project an older release scaffolded. A project never
re-initialised stays unmarked, and this check stays silent for it. Nothing
here depends on whether `chitragupta` is installed anywhere visible --
that residue belongs to `chitragupta/hook_launchers.py`'s probe of a
different interpreter, and to the SessionStart hook (#891 gap 2).

**A known, accepted misfire, not fixed here.** An *unconfigured* checkout
(no `config.toml` of its own yet) reached only through `PYTHONPATH` --
not a real `.pth` entry -- sitting under a marked directory and run from
inside itself is refused rather than exempted: condition 2 cannot tell
that shape apart from the actual bypass it exists to close, and condition
3's walk passes straight through a directory with no `config.toml` to the
marked one above it. A checkout that already has its own `config.toml`
is unaffected (condition 3 stops there regardless), so this is narrower
than it sounds, and it trades the actionable
`cp config.toml.example config.toml` error for a `[fatal] ... planted
chitragupta/` one -- a worse message for a case this project considers
rare enough not to special-case.

Standard library only, and it imports nothing from `chitragupta`.
"""

import os
import sys
from pathlib import Path

# The empty file `chitragupta/init.py`'s `scaffold()` writes into every
# project it creates. A checkout never has one.
SCAFFOLD_MARKER = ".chitragupta-scaffold"


def _lexical(path) -> Path:
    """`path` made absolute with `..` collapsed but no symlink resolved;
    `''` (how `sys.path[0]` names the current directory) becomes cwd."""
    return Path(os.path.abspath(path or os.getcwd()))


def _import_root(package_file: Path) -> "Path | None":
    """The directory `package_file`'s package was imported from: the
    parent of its nearest ancestor named `chitragupta`."""
    for ancestor in _lexical(package_file).parents:
        if ancestor.name == "chitragupta":
            return ancestor.parent
    return None


def _pythonpath_entries(environ) -> set:
    """`PYTHONPATH`'s own entries, lexically normalised -- the same
    splitting Python's interpreter start-up does, so a `PYTHONPATH`-only
    duplicate of `sys.path[0]` can be told apart from one a `.pth` file
    put there (see "why PYTHONPATH entries are excluded" in the module
    docstring)."""
    raw = environ.get("PYTHONPATH", "")
    return {_lexical(entry) for entry in raw.split(os.pathsep) if entry}


def scaffolded_ancestor(
    package_file: Path, find_project_root, search_path=None, environ=None
) -> "Path | None":
    """The marked project root a planted `package_file` was imported
    from, or `None` -- the three conditions in the module docstring.

    `find_project_root(start)` returns the project directory `start`
    belongs to, or `None`; `config.py` passes its own
    `discover_project_root` with `CHITRAGUPTA_PROJECT` ignored, so this
    module needs no second copy of that walk. `search_path` defaults to
    `sys.path`, `environ` to `os.environ`.
    """
    search_path = sys.path if search_path is None else search_path
    environ = os.environ if environ is None else environ
    import_root = _import_root(package_file)
    if import_root is None or not search_path:
        return None
    if import_root != _lexical(search_path[0]):
        return None
    rest = {_lexical(entry) for entry in search_path[1:]} - _pythonpath_entries(environ)
    if import_root in rest:
        return None
    project = find_project_root(import_root)
    if project is not None and (project / SCAFFOLD_MARKER).is_file():
        return project
    return None


def refuse_if_shadowed(
    package_file: Path, find_project_root, search_path=None, environ=None
) -> None:
    """Fail closed, the way a hook's protected child already does,
    instead of silently running the planted copy `scaffolded_ancestor`
    found."""
    root = scaffolded_ancestor(package_file, find_project_root, search_path, environ)
    if root is None:
        return
    print(
        f"[fatal] {_lexical(package_file)} is running from inside a project "
        f"`chitragupta init` marked as scaffolded ({root}) -- this is a "
        "planted chitragupta/, not the installed package (#822, #891). "
        "Remove it, or reinstall chitragupta-cli and activate that "
        "virtualenv.",
        file=sys.stderr,
    )
    raise SystemExit(1)


def unsafe_marker_reason(marker: Path) -> "str | None":
    """Why `chitragupta/init.py`'s `scaffold()` must refuse to write
    `SCAFFOLD_MARKER` at `marker`, or `None` if it is safe to.

    - A symlink, dangling or not: `exists()` follows it, so a dangling
      one would reach `_write_marker`, whose `touch()` follows it too and
      creates the link's target -- possibly outside the project -- while
      reporting the marker created. A link to a file would also pass
      `is_file()`. `is_symlink()`, checked first, never follows.
    - Anything else that is not a regular file, a directory most likely:
      `touch()` on a directory only updates its mtime, so the report
      would claim a marker that `scaffolded_ancestor`'s `is_file()` never
      sees.
    """
    # Creating a symlink on CI's Windows leg needs Developer Mode or an
    # elevated process, neither available there, so the tests for this
    # branch skip on win32 -- the "platform" category
    # coveragerc-windows.toml's own docstring names.
    if marker.is_symlink():  # pragma: no cover-windows
        return (
            f"{marker} is a symlink, which this would follow when writing "
            "the scaffold marker (#891)."
        )
    if marker.exists() and not marker.is_file():
        return (
            f"{marker} exists but is not a regular file, so the scaffold "
            "marker this would write there could never actually protect "
            "this project (#891)."
        )
    return None
