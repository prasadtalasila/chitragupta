"""Which `chitragupta` may a hook's child import? -- decided once, before any.

`python -m chitragupta.draft ...` and `python -c "import chitragupta"` put
the child's working directory first on `sys.path`, and every hook here
runs its children with `cwd` at the project root. In a git checkout that
is the point: it is how the checkout finds its own `chitragupta/` with no
install and no PYTHONPATH. In a `chitragupta init`-scaffolded project it
is a hole (#822). `init` scaffolds no `chitragupta/`, so one found there
was put there by someone else -- a shared project directory, a cloned
one -- and it would shadow the installed package and run with the user's
privileges on SessionStart, before anything is typed, and again on every
draft write.

**How the two are told apart.** Not by whether `<root>/chitragupta/`
exists: in the case that matters, that directory is the planted file.
Instead, by where `chitragupta` resolves *without* the cwd entry. A hook
is run as `python <abs path>`, so its own `sys.path[0]` is `.claude/hooks`,
not the project root -- the same search a `python -P` child makes. If the
package resolves there to somewhere outside the project root, it is
installed, the project is a scaffolded one, and every child gets
`PYTHONSAFEPATH=1`, so the installed package is the one imported whatever
the directory holds. If it resolves inside the root (an editable install
of the checkout) or not at all (a checkout run from its own tree, which
is how this repository's own venv works), the launch is left as it was.

`find_spec` on a top-level name locates the package without executing
it, so the decision itself imports nothing from the project directory.
The environment variable rather than `-P` because it reaches the child's
own children too.

**What this cannot close.** An interpreter that finds no installed
`chitragupta` at all -- a scaffolded project whose harness started from a
shell that never activated the venv (#563) -- looks exactly like a
checkout, and there is no marker a checkout has that a shared directory
could not also carry. There the gate fails closed on its own, but a
planted package still runs. `chitragupta init` refusing to scaffold over
a `chitragupta/` or `chitragupta.py` is the other half; docs/HOOKS.md
records both.

Tier 1 and harness-free, like `draft_target.py`: standard library only,
and imported by the hooks rather than by anything under `chitragupta/`,
since the whole question is which `chitragupta` to trust.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def installed_elsewhere(repo_root: Path | None = None) -> bool:
    """Does `chitragupta` resolve, cwd aside, to a copy outside the project?

    True is the scaffolded shape: the package lives in some site-packages
    and nothing under the project root is entitled to replace it.
    """
    spec = importlib.util.find_spec("chitragupta")
    origin = spec.origin if spec else None
    if not origin:
        return False  # not installed, or a namespace package: the checkout shape
    root = (repo_root or REPO_ROOT).resolve()
    return not Path(origin).resolve().is_relative_to(root)


def child_env(repo_root: Path | None = None, base: dict | None = None) -> dict:
    """The environment every `python -m chitragupta...` child should get.

    `base` defaults to this process's own environment, which is what the
    children inherited before this module existed.
    """
    env = dict(os.environ if base is None else base)
    if installed_elsewhere(repo_root):
        env["PYTHONSAFEPATH"] = "1"
    return env
