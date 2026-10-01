"""Is this `chitragupta` the planted copy inside a scaffolded project?

Split from `chitragupta/config.py` (#891), the same way config_load,
config_path and config_enrich already are: `config.py` calls
`refuse_if_shadowed` at import time, right after it discovers
`PROJECT_ROOT`, and this is the one check small and self-contained enough
to live beside that call rather than inside it.

**The gap this closes (#891 gap 1, following #822).** A hook's own
children are already protected: `.claude/hooks/safe_path.py` sets
`PYTHONSAFEPATH=1` on a child whose interpreter resolves `chitragupta` to
somewhere outside the project root, so a `chitragupta/` or
`chitragupta.py` planted in a `chitragupta init`-scaffolded project can
never shadow the install there. But the genre skills and the drafting
`AGENTS.md` run `python -m chitragupta.draft gate`, `python -m
chitragupta.corpus sync`, etc. directly from the project root, with no
hook and no `safe_path.py` in between -- `-m` puts cwd first on
`sys.path` regardless, so a planted package shadows the install the
moment one of those commands runs.

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

What this *does* catch, and is sized for: the shape issue 891 actually
names -- "a `chitragupta/` or `chitragupta.py` someone committed to a
shared project", a passive duplicate (stale, cloned, or accidentally
co-located) that is not specifically hostile to this detector. For that
shape, and for the shape #822 already closes (a hook's own children),
this guard is exact: no false positive on a checkout or a properly
installed scaffold, and a refusal on every planted copy that is not
purpose-built to evade it.

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


def shadowed(package_file: Path, project_root: Path) -> bool:
    """Is `package_file` the planted copy inside a scaffolded `project_root`?

    True only when `project_root` carries `SCAFFOLD_MARKER` *and*
    `package_file` resolves to somewhere inside it -- see the module
    docstring for why each half is necessary.
    """
    if not (project_root / SCAFFOLD_MARKER).is_file():
        return False
    return package_file.resolve().is_relative_to(project_root.resolve())


def refuse_if_shadowed(package_file: Path, project_root: Path) -> None:
    """Fail closed, the way a hook's protected child already does,
    instead of silently running the planted copy `shadowed` found."""
    if not shadowed(package_file, project_root):
        return
    print(
        f"[fatal] {package_file.resolve()} is running from inside a project "
        f"`chitragupta init` marked as scaffolded ({project_root}) -- this is a "
        "planted chitragupta/ or chitragupta.py, not the installed package "
        "(#822, #891). Remove it, or reinstall chitragupta-cli and activate "
        "that virtualenv.",
        file=sys.stderr,
    )
    raise SystemExit(1)
