"""Does this `chitragupta` carry the marker-check a planted copy of
itself would need to be caught by it?

Split from `chitragupta/config.py` (#891), the same way config_load,
config_path and config_enrich already are: `config.py` calls
`refuse_if_shadowed` at import time, right after it discovers
`PROJECT_ROOT`, and this is the one check small and self-contained enough
to live beside that call rather than inside it.

**What this narrows, and what it does not close (#891 gap 1, following
#822).** A hook's own children are already protected: `.claude/hooks/
safe_path.py` sets `PYTHONSAFEPATH=1` on a child whose interpreter
resolves `chitragupta` to somewhere outside the project root, so a
`chitragupta/` planted in a `chitragupta init`-scaffolded project can
never shadow the install there. But the genre skills and the drafting
`AGENTS.md` run `python -m chitragupta.draft gate`, `python -m
chitragupta.corpus sync`, etc. directly from the project root, with no
hook and no `safe_path.py` in between -- `-m` puts cwd first on
`sys.path` regardless, so a planted package shadows the install the
moment one of those commands runs, and nothing before this PR said so.

**Read this paragraph before trusting what follows protects more than it
does.** This check runs *from inside* the very `chitragupta` module
Python already selected and started executing -- it is reached only if
that module's own `config.py` contains the call to it. Issue #891's own
example is "a `chitragupta/` ... someone committed to a shared project";
a `chitragupta/` committed *before this PR existed* -- which is every
real-world stale or cloned duplicate, adversarial or not -- has no
`scaffold_guard.py` and no call to it at all, so Python runs it without
ever reaching this code. Review on this PR caught that generalisation
late (it was first framed, incompletely, as "protects passive
duplicates, not adversarial ones" -- the honest statement is narrower
still: **the only shape this can structurally ever catch is a planted
`chitragupta/` that happens to already carry this exact check**, e.g. one
copied from a `chitragupta-cli` release built after this PR shipped.
Closing the general case -- any stale or hostile duplicate, carrying the
check or not -- needs a trusted bootstrap outside the package being
selected entirely: a `sitecustomize.py` (or a `.pth` file's exec lines)
the installed distribution ships, run by Python's own site
initialisation before `-m` resolves its target at all. That is global to
every Python invocation in the venv, not only `chitragupta`'s -- a
materially larger, more invasive mechanism than this issue's surgical
scope calls for, and is not implemented here. #891 is not fully closed by
this file; what it closes is gap 2 and gap 3 (session_start_hook.py,
DEVELOPER-AGENTS.md), and this narrow slice of gap 1.

**How the shape this check *can* catch is told apart from the many
legitimate ones.** Not by whether `<root>/chitragupta/` exists -- in the
case that matters, that directory *is* the planted file, same as
`safe_path.py`'s own reasoning. Instead, by `chitragupta/init.py`'s
`SCAFFOLD_MARKER`: an empty file `scaffold()` writes into every project
it creates, and that `init` never writes a `chitragupta/` of its own
into (`ScaffoldTargetUnsafe` refuses to scaffold over one that is already
there, or over a non-regular-file already at the marker's own path).
The marker's presence means this root is *definitely* not a checkout --
a checkout never carries it (`cp config.toml.example config.toml` does
not write it) -- so a package whose own directory sits *directly* under
a marked root is either installed outside that root entirely (silent) or
planted there after scaffolding (refused).

**Keyed to `package_file`'s own lexical location, never to `PROJECT_ROOT`
or `CHITRAGUPTA_PROJECT`, and never fully symlink-resolved.** An earlier
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
no marker exists (also raised in review). `package_file.absolute()` is
used instead: makes the path absolute without resolving any symlink in
it, so the check stays keyed to the lexical path Python's import actually
selected.

**Keyed to the one directory immediately above `package_file`'s own
`chitragupta/` ancestor, never to every ancestor above that.** An
intermediate version walked every ancestor of `package_file` looking for
the marker, and flagged a project-local venv's own install:
`<root>/.venv/lib/.../site-packages/chitragupta/` is a real, properly
installed package that merely sits *somewhere* under a marked `<root>`,
several directories down -- checking every ancestor read that as planted
and refused every ordinary command (a regression caught in review).
Checking only the one directory immediately above the package itself is
exact: it is the planted shape (`<root>/chitragupta/` directly) and not
the installed one (`chitragupta/` nested arbitrarily deep below `<root>`,
inside a venv's own `site-packages`, whose own immediate parent
`chitragupta init` never marks either).

**A single top-level `chitragupta.py` cannot reach this check at all --
a distinct, un-closable shape, not a bug in the check above.** `-m
chitragupta.draft` imports `chitragupta` first either way, but a plain
module (no `__path__`) can never have a `chitragupta.config` submodule to
carry this call -- Python fails resolving `chitragupta.draft` right
after, with the planted file's own top-level code already having run.
`chitragupta/init.py`'s `ScaffoldTargetUnsafe` still refuses to scaffold
*over* either shape (single file or directory) at `init` time; that half
is unaffected by anything above.

**Protects a newly- or freshly-re-scaffolded project; an existing one
needs one `chitragupta init` re-run to pick it up.** `scaffold()` writes
`SCAFFOLD_MARKER` unconditionally if it is missing, with no `--force`
needed (`_write_marker` in `chitragupta/init.py`), so re-running
`chitragupta init` on a project scaffolded by an older `chitragupta-cli`
adds only the marker -- every other file's "exists, unchanged" path is
untouched. A project that is never re-initialised after upgrading stays
unmarked, and this guard stays silent for it, same as it does for a
checkout.

A second, narrower residue, the same one `safe_path.py` documents: an
interpreter that finds no installed `chitragupta` at all sees nothing
inside the project root to flag, however this imported -- there is no
marker a checkout could not also carry. `chitragupta doctor` and the
SessionStart preflight name that state instead (#891 gap 2).

Standard library only, and `config.py` is the only caller: like
`config_load`/`config_path`/`config_enrich`, this cannot import `config`
back (that module raises without a `config.toml`, which is exactly the
state a freshly-scaffolded, not-yet-configured project is in).
"""

import sys
from pathlib import Path

# The literal `chitragupta/init.py`'s `scaffold()` writes into every
# project it creates -- duplicated rather than imported, for the same
# reason that module's own copy of `PACKAGE_ROOT` is: `init` cannot
# import anything from `chitragupta.config` (nor, by extension, from a
# module `config.py` itself imports) without running into the same
# config.toml-or-raise this module exists to run *before*.
# `tests/test_init.py` pins the two copies equal.
SCAFFOLD_MARKER = ".chitragupta-scaffold"


def scaffolded_ancestor(package_file: Path) -> "Path | None":
    """The project root `package_file`'s own `chitragupta/` directory
    sits *directly* under, if `init` marked that root as scaffolded, or
    `None` if there is none.

    Finds the nearest ancestor of `package_file` named `chitragupta` --
    its own package directory -- and checks only *that* directory's
    immediate parent for `SCAFFOLD_MARKER`, deliberately not every
    ancestor above it (a project-local venv install, several directories
    further down, must not be flagged) and deliberately not a fully
    symlink-resolved path (a symlinked package directory must still be
    checked at the lexical location Python's import actually selected).
    See the module docstring for both reasons in full.

    Walked from `package_file`'s own location, deliberately never from
    `config.PROJECT_ROOT` or `CHITRAGUPTA_PROJECT` -- see the module
    docstring for why mixing in the user's configured data root would
    have let that override blind this check to a package actually
    shadowing cwd.
    """
    absolute = package_file.absolute()
    for ancestor in absolute.parents:
        if ancestor.name == "chitragupta":
            root = ancestor.parent
            return root if (root / SCAFFOLD_MARKER).is_file() else None
    return None


def shadowed(package_file: Path) -> bool:
    """Is `package_file` the planted copy inside some scaffolded project?"""
    return scaffolded_ancestor(package_file) is not None


def refuse_if_shadowed(package_file: Path) -> None:
    """Fail closed, the way a hook's protected child already does,
    instead of silently running the planted copy `shadowed` found."""
    root = scaffolded_ancestor(package_file)
    if root is None:
        return
    print(
        f"[fatal] {package_file.resolve()} is running from inside a project "
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
    if marker.is_symlink():
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
