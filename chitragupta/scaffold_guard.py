"""Does this `chitragupta` carry the marker-check a planted copy of
itself would need to be caught by it?

Split from `chitragupta/config.py` (#891), the same way config_load,
config_path and config_enrich already are: `config.py` calls
`refuse_if_shadowed` at import time, deliberately *before* it discovers
`PROJECT_ROOT` below -- see "keyed to the package's own location" below
for why. `chitragupta/init.py` is the other caller, for
`unsafe_marker_reason` (used when writing the marker itself, not when
detecting a planted copy of it).

**What this narrows, and what it does not close (#891 gap 1, following
#822).** A hook's own children are already protected: `.claude/hooks/
safe_path.py` sets `PYTHONSAFEPATH=1` on a child whose interpreter
resolves `chitragupta` to somewhere outside the project root, so a
`chitragupta/` planted in a `chitragupta init`-scaffolded project can
never shadow the install there. But the genre skills and the drafting
`AGENTS.md` run `python -m chitragupta.draft gate`, `python -m
chitragupta.corpus sync`, etc. directly from the project root (or any
subdirectory of it -- docs/CONFIG.md's project-root discovery walks up
for `config.toml` from wherever the command runs), with no hook and no
`safe_path.py` in between -- `-m` puts cwd first on `sys.path`
regardless, so a planted package shadows the install the moment one of
those commands runs, and nothing before this PR said so.

**Read this before trusting what follows protects more than it does.**
This check runs *from inside* the very `chitragupta` module Python
already selected and started executing -- it is reached only if that
module's own `config.py` contains the call to it. Issue #891's own
example is "a `chitragupta/` ... someone committed to a shared project";
a `chitragupta/` committed *before this PR existed* -- every real-world
stale or cloned duplicate, adversarial or not -- has no
`scaffold_guard.py` and no call to it at all, so Python runs it without
ever reaching this code. **The only shape this can structurally ever
catch is a planted `chitragupta/` that happens to already carry this
exact check** (e.g. one copied from a `chitragupta-cli` release built
after this PR shipped), not a stale or hostile duplicate that predates
it. Closing the general case needs a trusted bootstrap outside the
package being selected entirely -- a `sitecustomize.py` (or a `.pth`
file's exec lines) the installed distribution ships, run by Python's own
site initialisation before `-m` resolves its target at all, global to
every Python invocation in the venv, not only `chitragupta`'s -- a
materially larger, more invasive mechanism than this issue's surgical
scope calls for, and is not implemented here. A single top-level
`chitragupta.py` is a second, un-closable shape for an unrelated reason:
no `__path__`, so no `chitragupta.config` submodule ever exists for the
check to live in -- `-m chitragupta.draft` imports the file (its own
top-level code already runs) and only then fails resolving
`chitragupta.draft`. `chitragupta/init.py`'s `ScaffoldTargetUnsafe` still
refuses to scaffold *over* either shape at `init` time; that half is
unaffected by any of this. #891 is not fully closed by this file -- what
it closes is gap 2 and gap 3 (session_start_hook.py,
DEVELOPER-AGENTS.md), and this narrow slice of gap 1.

**How the shape this check *can* catch is told apart from the many
legitimate ones.** Not by whether `<root>/chitragupta/` exists -- in the
case that matters, that directory *is* the planted file. Instead, by
`chitragupta/init.py`'s `SCAFFOLD_MARKER`: an empty file `scaffold()`
writes into every project it creates, and that `init` never writes a
`chitragupta/` of its own into (`ScaffoldTargetUnsafe` refuses to
scaffold over one that is already there, or over a non-regular-file
already at the marker's own path). The marker's presence means this root
is *definitely* not a checkout -- a checkout never carries it (`cp
config.toml.example config.toml` does not write it).

**Keyed to the package's own lexical location, never to `PROJECT_ROOT` or
`CHITRAGUPTA_PROJECT`, and never fully symlink-resolved.** An earlier
version took `config.PROJECT_ROOT` and asked whether `package_file`
resolved inside *that* -- which answers "where does the user's data
live", not "where does the code I am actually running live", and
`CHITRAGUPTA_PROJECT` (`config.discover_project_root`'s first, overriding
source) can point those two questions at different directories entirely:
running from a marked, shadowed root with `CHITRAGUPTA_PROJECT` pointed
elsewhere would have checked the override's root for the marker and
found nothing (raised in review). A later version called
`package_file.resolve()`, which also follows a symlinked package
directory (`<root>/chitragupta -> vendor/chitragupta`, committable, and
one `-m` still imports through the top-level, marked `<root>` entry) --
losing track of `<root>` entirely and checking `vendor/` instead, where
no marker exists (also raised in review). `.absolute()` is used instead,
both here and in `refuse_if_shadowed`'s own `[fatal]` message: makes the
path absolute without resolving any symlink in it, so both the decision
and what it prints stay keyed to the lexical path Python's import
actually selected.

**Told apart from an installed package -- in a venv anywhere, including
nested inside the project -- by the *name* of the directory holding it,
not by how many directories separate it from the marked root.** The
first version checked only the one directory immediately above the
package's own `chitragupta/` ancestor: exact against a plant directly at
`<root>/chitragupta/`, but it also missed a plant several directories
down (`<root>/content/chitragupta/`, run from `content/` -- a supported
shape per docs/CONFIG.md's own project-root walk, reproduced and raised
in review: no refusal at all). A second version walked *every* ancestor
instead, and over-corrected: `<root>/.venv/lib/.../site-packages/
chitragupta/` is a real, properly installed package that merely sits
somewhere under a marked `<root>`, and every ancestor carrying the
marker read that as planted too (a regression also caught in review).
What actually distinguishes the two is not depth but the installer's own
naming convention: every Python packaging tool -- `venv`, `virtualenv`,
`pip`, `poetry` -- places an install inside a directory named
`site-packages` (POSIX: `lib/pythonX.Y/site-packages`; Windows:
`Lib/site-packages`) or, on a Debian-family system Python,
`dist-packages`. So the walk-up-to-the-marker that catches a plant
anywhere under the project root is correct precisely when the
`chitragupta/` found is *not* sitting directly inside one of those two
names -- checked once, where the search for the marker would otherwise
begin, rather than by comparing against the running interpreter's own
`site.getsitepackages()` (which answers for *this* interpreter's own
install locations, not for an arbitrary nested venv being inspected, and
would not generalise to a synthetic test fixture either).

**Protects a newly- or re-scaffolded project.** `scaffold()` writes
`SCAFFOLD_MARKER` unconditionally if it is missing, with no `--force`
needed (`_write_marker` in `chitragupta/init.py`), so re-running
`chitragupta init` on a project scaffolded by an older `chitragupta-cli`
adds only the marker -- every other file's "exists, unchanged" path is
untouched. A project that is never re-initialised after upgrading stays
unmarked, and this guard stays silent for it, same as for a checkout.
Nothing about *this* check depends on whether anything else is
"installed" and visible to the running interpreter -- it only needs the
currently-running module's own path and the marker, and works
unconditionally (verified with `python -S`, which hides every
site-packages install from the interpreter and changes nothing here).
The residue that genuinely depends on install visibility belongs to a
different mechanism -- `chitragupta/hook_launchers.py`'s probe of a
*different* interpreter than the one running this check, and the
SessionStart hook's own in-process import -- and is #891 gap 2, not this
file's concern.

Standard library only.
"""

import sys
from pathlib import Path

# The literal `chitragupta/init.py`'s `scaffold()` writes into every
# project it creates.
SCAFFOLD_MARKER = ".chitragupta-scaffold"

# What every mainstream Python packaging tool names the directory it
# installs into -- not a guess, see the module docstring's "told apart
# from an installed package" paragraph for why this is the right axis
# (installer convention, not path depth) and why comparing against the
# running interpreter's own `site.getsitepackages()` would not do.
_INSTALL_DIRECTORY_NAMES = frozenset({"site-packages", "dist-packages"})


def scaffolded_ancestor(package_file: Path) -> "Path | None":
    """The project root a planted `package_file` sits under, if `init`
    marked that root as scaffolded, or `None` if `package_file` is
    installed or the root carries no marker.

    Finds the nearest ancestor of `package_file` named `chitragupta` --
    its own package directory -- and, unless that directory's immediate
    parent is itself an install location (`_INSTALL_DIRECTORY_NAMES`),
    walks *up* from there for `SCAFFOLD_MARKER`: a plant can sit directly
    at the marked root or in any subdirectory of it, and the nearest
    marker found going up is the root that planted it. See the module
    docstring for the two regressions this design is the fix for.

    Walked from `package_file`'s own location, deliberately never from
    `config.PROJECT_ROOT` or `CHITRAGUPTA_PROJECT` -- see the module
    docstring for why mixing in the user's configured data root would
    have let that override blind this check to a package actually
    shadowing cwd.
    """
    absolute = package_file.absolute()
    for ancestor in absolute.parents:
        if ancestor.name != "chitragupta":
            continue
        start = ancestor.parent
        if start.name in _INSTALL_DIRECTORY_NAMES:
            return None
        for candidate in (start, *start.parents):
            if (candidate / SCAFFOLD_MARKER).is_file():
                return candidate
        return None
    return None


def refuse_if_shadowed(package_file: Path) -> None:
    """Fail closed, the way a hook's protected child already does,
    instead of silently running the planted copy `scaffolded_ancestor`
    found."""
    root = scaffolded_ancestor(package_file)
    if root is None:
        return
    print(
        f"[fatal] {package_file.absolute()} is running from inside a project "
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

    Two shapes, both caught in review, and both about the marker *path*
    rather than about `scaffolded_ancestor`'s logic above:

    - A symlink, dangling or not. `Path.exists()` follows a symlink, so a
      *dangling* one reports False and would reach `init.py`'s
      `_write_marker` unblocked -- whose `touch()` then follows the link
      too, writing a new file at the link's target (possibly outside the
      project root entirely) while reporting the marker itself as
      created. A symlink to an existing file would otherwise also pass as
      a "regular file" (`is_file()` follows symlinks). `is_symlink()`,
      checked first and never followed, catches both.
    - An existing non-symlink that is not a regular file (a directory,
      most plausibly). `Path.touch()` on an existing directory only
      updates its mtime and succeeds, so `_write_marker` would have
      reported "created" while writing no actual marker file --
      `scaffolded_ancestor` above requires `is_file()`, so the guard
      stays silently disabled under a report that claims success.
    """
    # Creating a symlink on CI's Windows leg needs Developer Mode or an
    # elevated process, neither available there, so the tests that would
    # exercise this branch are structurally unrunnable on that platform
    # (tests/test_scaffold_guard.py and tests/test_init.py both skip
    # their symlink cases on win32) -- the same "platform" category
    # coveragerc-windows.toml's own module docstring names.
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
