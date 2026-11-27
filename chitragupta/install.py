"""`chitragupta install os-deps|gpu-torch`: reach the two
`scripts/install_full_pipeline.sh` stages a `pip install` cannot do
itself, without a second install path (DEVELOPER-AGENTS.md).

`python-deps`, `dev-deps` and `all` are refused by name: they are
repo-shaped (`uv sync` on a checkout's lock), and running something
else under their name would be worse. `os-deps` is Debian/Ubuntu and
bash only, and says so. `enrich` is `pip install` of this package's own
extra pinned to the running version (`docker/Dockerfile.claude` ships
without the torch-heavy extra). `gpu-torch` targets the running
interpreter via `CHITRAGUPTA_PYTHON`; a `CHITRAGUPTA_PIP` beside it
named nothing on Windows (#985).
"""

import argparse
import importlib.metadata
import os
import shlex
import subprocess
import sys
from pathlib import Path

from chitragupta import programs
from chitragupta.progname import prog_for
from chitragupta.help_format import ClickParser

PACKAGE_ROOT = Path(__file__).resolve().parent
# Not imported from chitragupta.config, as in init.py: config raises
# without a config.toml.
SOURCE_ROOT = PACKAGE_ROOT.parent
SCRIPT = SOURCE_ROOT / "scripts" / "install_full_pipeline.sh"

DESCRIPTION = "Run the install_full_pipeline.sh stage a pip install cannot do itself."

# Never spelled inline; see _run_enrich.
EXTRA = "enrich"

# Each refused stage, with the pip equivalent named in its refusal.
REFUSED = {
    "python-deps": "chitragupta install enrich",
    "dev-deps": "pip install 'chitragupta-cli[dev]'",
    "all": "'chitragupta install enrich', plus 'chitragupta install "
    "os-deps' separately -- 'all' means something different here",
}

STAGES = ("os-deps", "gpu-torch", "enrich", *REFUSED)


# The checkout's route to the enrich stack, where `install enrich` refuses.
CHECKOUT_ENRICH = "bash scripts/install_full_pipeline.sh python-deps"


def remedy(stage: str) -> str:
    """The command a message should tell its reader to run, quoted.

    One spelling for both project shapes (#1022): an `init` project has
    no `scripts/`.
    """
    if stage not in STAGES or stage in REFUSED:
        raise ValueError(f"{stage!r} is not a stage chitragupta install runs")
    return f"`chitragupta install {stage}`"


def enrich_remedy() -> str:
    """How to get the enrich stack, for whichever project shape the
    reader is in. The one install `remedy` cannot spell alone: `install
    enrich` refuses in a checkout (see `main`), where the install script
    is the command, and a `chitragupta init` project has no `scripts/`."""
    return f"in a git checkout, `{CHECKOUT_ENRICH}`; in an installed project, {remedy('enrich')}"


# Shows which stages run and which refuse (#369): `choices=` alone did not.
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
    bash = programs.resolve_program("bash")
    if not (programs.resolve_program("apt-get") and bash):
        print(
            "os-deps is Debian/Ubuntu and bash only. Install by hand: TeX Live, "
            "Pandoc, poppler-utils, git/curl/unzip, libgl1/libglib2.0 -- and make "
            "sure the name `python` resolves, which is what the hooks launch.",
            file=sys.stderr,
        )
        return 1
    command = [bash, str(SCRIPT), "os-deps"]
    print(f"About to run (needs root): {' '.join(command)}")
    return subprocess.run(command, check=False).returncode


def _run_enrich() -> int:
    """`pip install 'chitragupta-cli[enrich]=='<what is running>`.

    Pinned, because an unpinned install of the same package may upgrade
    it mid-command. Refused outside an installed distribution, where the
    install script's `python-deps` stage is the equivalent.
    """
    try:
        version = importlib.metadata.version("chitragupta-cli")
    except importlib.metadata.PackageNotFoundError:
        print(
            "enrich needs chitragupta-cli installed as a package. In a git "
            f"checkout the equivalent is: {CHECKOUT_ENRICH}",
            file=sys.stderr,
        )
        return 1
    # Square brackets are a glob in zsh, so the echo is shlex-quoted and the
    # bare bracketed spelling appears nowhere in this file
    # (tests/test_pyproject_extras.py). argv stays unquoted: pip gets it
    # directly.
    requirement = f"chitragupta-cli[{EXTRA}]=={version}"
    command = [sys.executable, "-m", "pip", "install", requirement]
    print(f"About to run: {shlex.join(command)}")
    return subprocess.run(command, check=False).returncode


def _run_gpu_torch() -> int:
    bash = programs.resolve_program("bash")
    if not bash:
        print(
            "gpu-torch needs bash. Reinstall by hand from "
            "https://pytorch.org/get-started/locally/.",
            file=sys.stderr,
        )
        return 1
    # Not .resolve(): a venv's bin/python is a symlink out of the venv (#369).
    env = {**os.environ, "CHITRAGUPTA_PYTHON": sys.executable}
    command = [bash, str(SCRIPT), "gpu-torch"]
    return subprocess.run(command, check=False, env=env).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = ClickParser(prog=prog_for("install"), description=DESCRIPTION)
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
