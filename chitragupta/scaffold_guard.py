"""Is this `chitragupta` the planted copy inside a scaffolded project?

Split from `chitragupta/config.py` (#891), the same way config_load,
config_path and config_enrich already are: `config.py` calls
`refuse_if_shadowed` at import time, right after it discovers
`PROJECT_ROOT`, and this is the one check small and self-contained enough
to live beside that call rather than inside it.

**The gap this closes (#891 gap 1, following #822).** A hook's own
children are already protected: `.claude/hooks/safe_path.py` sets
`PYTHONSAFEPATH=1` on a child whose interpreter resolves `chitragupta` to
somewhere outside the project root, so a `chitragupta/` planted in a
`chitragupta init`-scaffolded project can never shadow the install there.
But the genre skills and the drafting `AGENTS.md` run `python -m
chitragupta.draft gate`, `python -m chitragupta.corpus sync`, etc.
directly from the project root, with no hook and no `safe_path.py` in
between -- `-m` puts cwd first on `sys.path` regardless, so a planted
package shadows the install the moment one of those commands runs.

**How this is told apart from the many legitimate shapes.** Not by
whether `<root>/chitragupta/` exists -- in the case that matters, that
directory *is* the planted file, same as `safe_path.py`'s own reasoning.
Instead, by `chitragupta/init.py`'s `SCAFFOLD_MARKER`: an empty file
`scaffold()` writes into every project it creates, and that `init` never
writes a `chitragupta/` of its own into (`ScaffoldTargetUnsafe` refuses
to scaffold over one that is already there). So the marker's presence
means this root is *definitely* not a checkout -- and the only way the
`chitragupta` module actually running can still resolve to a location
*inside* that root is a package planted there after scaffolding. A
checkout never carries the marker (`cp config.toml.example config.toml`
does not write it), so this adds no false positive there, and a project
that was scaffolded and then properly `pip install`-ed resolves outside
the root regardless of the marker, so it is silent there too.

**Keyed to `package_file`'s own location, never to `PROJECT_ROOT` or
`CHITRAGUPTA_PROJECT`.** An earlier version of this check took
`config.PROJECT_ROOT` and asked whether `package_file` resolved inside
*that* -- which answers "where does the user's data live", not "where
does the code I am actually running live", and `CHITRAGUPTA_PROJECT`
(`config.discover_project_root`'s first, overriding source) can point
those two questions at different directories entirely: running from a
marked, shadowed root with `CHITRAGUPTA_PROJECT` pointed elsewhere would
have checked the override's root for the marker and found nothing,
silently running the planted copy anyway (raised in review). Deriving
the relevant root from `package_file` itself removes the dependency on
`PROJECT_ROOT` altogether, and is also *not* every ancestor of
`package_file`: a second review round caught that shape rejecting a
project-local venv's own install (`<root>/.venv/lib/.../site-packages/
chitragupta/` -- a real install that merely sits *somewhere* under a
marked `<root>`, several directories down). What is checked instead is
the one directory immediately above `package_file`'s own `chitragupta/`
ancestor -- exact for the planted shape (`<root>/chitragupta/` directly)
and silent for an install nested arbitrarily deep below `<root>`, whose
immediate parent (a venv's `site-packages`) `chitragupta init` never
marks either. `scaffolded_ancestor`'s own docstring has the full
reasoning.

**What this still cannot close, and why.** This check runs *from inside*
the very `chitragupta` that was imported -- it is reached only once
Python has already selected a module and started executing it. Against
an adversarial planted package that is written to defeat this exact
check -- one whose `config.py` never calls `refuse_if_shadowed` at all,
or whose malicious behaviour sits in `__init__.py` or another module
reached before `config.py` is -- there is no version of "the package
checks itself" that can close the gap: by the time any code here runs,
an uncooperating planted package has already had the chance to act.
Closing *that* would need a trusted bootstrap outside the package being
selected entirely -- a `sitecustomize.py` the installed distribution
ships, run by Python's own site initialisation before `-m` resolves its
target -- which is a materially larger, more invasive mechanism (global
to every Python invocation in the venv, not only `chitragupta`'s) than
this issue's surgical scope calls for, and is not implemented here.

**A single top-level `chitragupta.py` is one shape of that same
limitation, not a separate bug.** `-m chitragupta.draft` imports
`chitragupta` first either way, but a plain module (no `__path__`) can
never have a `chitragupta.config` submodule to reach -- Python fails
resolving `chitragupta.draft` right after, with the planted file's own
top-level code already having run. No check placed inside
`chitragupta/config.py` can be reached through a shape that has no
`chitragupta/config.py` in it at all; this is the same "a self-check
cannot run before the code hosting it does" limit above, concretely.
What this guard closes is the `chitragupta/` *directory* shape -- the
one a shared or cloned project directory actually produces, and the one
#891 names first. `chitragupta/init.py`'s `ScaffoldTargetUnsafe` still
refuses to scaffold *over* either shape at `init` time, single file or
directory alike; that half is unchanged.

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
    ancestor above it. An earlier version walked all the way up, and
    flagged a project-local venv's own install: `<root>/.venv/lib/.../
    site-packages/chitragupta/` is a real, properly installed package
    that merely happens to sit *somewhere* under a marked `<root>` --
    checking every ancestor read that as planted and refused every
    command, a regression caught in review. Checking only the one
    directory immediately above the package itself is exact: it is the
    planted shape (`<root>/chitragupta/`, `init` having scaffolded
    `<root>` and written no `chitragupta/` of its own into it) and not
    the installed one (`chitragupta/` several directories below `<root>`,
    inside a venv's own `site-packages`, where `init` never wrote a
    marker either).

    Walked from `package_file`'s own directory, deliberately never from
    `config.PROJECT_ROOT` or `CHITRAGUPTA_PROJECT` -- see the module
    docstring for why mixing in the user's configured data root would
    have let that override blind this check to a package actually
    shadowing cwd.
    """
    resolved = package_file.resolve()
    for ancestor in resolved.parents:
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
