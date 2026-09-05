"""`chitragupta install os-deps|gpu-torch`: reach the two
`scripts/install_full_pipeline.sh` stages a `pip install` cannot do
itself, without reimplementing the script's logic a second time
(DEVELOPER-AGENTS.md: "don't add a second install path").

**A subset of the script's stages, not all of them, refused rather than
silently accepted.** `python-deps`, `dev-deps` and `all` mean "create
`.venv-full/` and `poetry install`" -- repo-shaped, needing a checkout's
`poetry.lock`, and exactly what `pip install 'chitragupta-cli[...]'`
already replaces. Accepting them here would run something with a
different meaning than the argument implies, which is worse than
refusing by name.

**`os-deps` is Debian/Ubuntu and bash only**, and says so rather than
stack-tracing on a host that lacks `apt-get`: the script itself already
is (`apt-get install`), so this is a promise made explicit at the one
new surface that makes it a shipped command rather than something only a
checkout runs.

**`enrich` installs this package's own extra**, into the environment
`chitragupta` is already running from, at the version already installed.
It is the one stage that is not a `scripts/install_full_pipeline.sh`
stage at all: it is `pip install 'chitragupta-cli[enrich]'` with the
version pinned to what is running, which is exactly what a user would
otherwise have to type. Added because `docker/Dockerfile.claude` ships
the CLI and nothing else, and told its user to reach for `pip` for the
one dependency set that image exists to make reachable -- the extra is
deliberately not baked in, since it is torch.

**`gpu-torch` targets the environment `chitragupta` is installed into**,
not `.venv-full` -- `CHITRAGUPTA_PIP`/`CHITRAGUPTA_PYTHON`, derived from
`sys.executable`, are what tell the shipped script's `gpu-torch` stage
which pip/python to reinstall torch into (its own `ensure_gpu_torch`
function already takes both as parameters; nothing there needed to
change).
"""

import argparse
import importlib.metadata
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from chitragupta.progname import prog_for

PACKAGE_ROOT = Path(__file__).resolve().parent
# Same reason chitragupta/init.py computes this rather than importing
# chitragupta.config: this module has to work before a project exists,
# and config.py raises without a config.toml.
SOURCE_ROOT = PACKAGE_ROOT.parent
SCRIPT = SOURCE_ROOT / "scripts" / "install_full_pipeline.sh"

DESCRIPTION = "Run the install_full_pipeline.sh stage a pip install cannot do itself."

# The extra `enrich` installs. Named once, and not spelled inline --
# see _run_enrich's comment on why the bare bracketed form is kept out
# of this file's text.
EXTRA = "enrich"

# What this refuses, and the pip equivalent each one names -- every
# refusal is a repo-shaped stage this environment has no real analogue
# of, not merely an unimplemented one.
REFUSED = {
    "python-deps": "chitragupta install enrich",
    "dev-deps": "pip install 'chitragupta-cli[dev]'",
    "all": "'chitragupta install enrich', plus 'chitragupta install "
    "os-deps' separately -- 'all' means something different here",
}

STAGES = ("os-deps", "gpu-torch", "enrich", *REFUSED)

# Derived, not restated: choices= alone gives --help no way to show which
# of the five actually run something (#369 -- a reader who tried
# python-deps/dev-deps/all off the usage line alone had no reason to
# expect an immediate refusal instead of a stage running).
_STAGE_HELP = (
    f"{'/'.join(sorted(s for s in STAGES if s not in REFUSED))} run a "
    f"stage; {'/'.join(sorted(REFUSED))} refuse by name and print the "
    "pip command that reaches them instead"
)


def _refuse(stage: str) -> int:
    print(
        f"'{stage}' is not reachable from an installed package -- "
        f"the pip equivalent is: {REFUSED[stage]}",
        file=sys.stderr,
    )
    return 1


def _run_os_deps() -> int:
    if not (shutil.which("apt-get") and shutil.which("bash")):
        print(
            "os-deps is Debian/Ubuntu and bash only. Install by hand: TeX Live, "
            "Pandoc, poppler-utils, git/curl/unzip, libgl1/libglib2.0 -- and make "
            "sure the name `python` resolves, which is what the hooks launch.",
            file=sys.stderr,
        )
        return 1
    command = ["bash", str(SCRIPT), "os-deps"]
    print(f"About to run (needs root): {' '.join(command)}")
    return subprocess.run(command, check=False).returncode


def _run_enrich() -> int:
    """`pip install 'chitragupta-cli[enrich]=='<what is running>`.

    Version-pinned to the running distribution rather than left open,
    because an unpinned install of the *same* package is free to upgrade
    it: a user asking for an extra would get a different chitragupta
    than the one they invoked, mid-command, which is not what "install
    the enrich extra" means.

    Refused outside an installed distribution -- a checkout has no
    `chitragupta-cli` on any index to add an extra to, and
    `poetry install --with enrich` is the operation that means this
    there.
    """
    try:
        version = importlib.metadata.version("chitragupta-cli")
    except importlib.metadata.PackageNotFoundError:
        print(
            "enrich needs chitragupta-cli installed as a package. In a git "
            "checkout the equivalent is: poetry install --with enrich",
            file=sys.stderr,
        )
        return 1
    # The extra's name is a variable and the echo goes through
    # shlex.join for the same single reason: square brackets are a glob
    # in zsh, so the bracketed extra printed bare is a line that fails
    # in the shell of anyone who copies it
    # (tests/test_pyproject_extras.py has the full reckoning). argv
    # itself must stay unquoted -- pip receives it directly, never
    # through a shell -- so the quoting belongs in the echo, and the
    # name is split out so the bare spelling appears in neither.
    requirement = f"chitragupta-cli[{EXTRA}]=={version}"
    command = [sys.executable, "-m", "pip", "install", requirement]
    print(f"About to run: {shlex.join(command)}")
    return subprocess.run(command, check=False).returncode


def _run_gpu_torch() -> int:
    if not shutil.which("bash"):
        print(
            "gpu-torch needs bash. Reinstall by hand from "
            "https://pytorch.org/get-started/locally/.",
            file=sys.stderr,
        )
        return 1
    # Not .resolve(): a venv's bin/python is a symlink to the base
    # interpreter, and resolving it walks straight out of the venv to the
    # base interpreter's own directory -- sys.executable is already
    # documented absolute, so nothing here needs normalizing (#369).
    bin_dir = Path(sys.executable).parent
    env = {
        **os.environ,
        "CHITRAGUPTA_PIP": str(bin_dir / "pip"),
        "CHITRAGUPTA_PYTHON": str(bin_dir / "python"),
    }
    command = ["bash", str(SCRIPT), "gpu-torch"]
    return subprocess.run(command, check=False, env=env).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog_for("install"), description=DESCRIPTION)
    parser.add_argument("stage", choices=sorted(STAGES), help=_STAGE_HELP)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.stage in REFUSED:
        return _refuse(args.stage)
    if args.stage == "os-deps":
        return _run_os_deps()
    if args.stage == "enrich":
        return _run_enrich()
    return _run_gpu_torch()


if __name__ == "__main__":
    raise SystemExit(main())
