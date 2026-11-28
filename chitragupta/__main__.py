"""The package's single front door: `chitragupta <layer> <verb> ...`.

Four layers, each already a complete entry point of its own:

    chitragupta corpus <verb> ...   the deterministic corpus run
    chitragupta draft  <verb> ...   work on one draft
    chitragupta review <aid>  ...   read-only aids, never a gate
    chitragupta enrich        ...   the optional enrichment layer

Plus package-level commands that only make sense once the code is
installed rather than cloned (#258):

    chitragupta init [DIR]     ...   scaffold a project directory (#263)
    chitragupta doctor         ...   probe the toolchain, report, never install (#265)
    chitragupta install <stage> ...  os-deps or gpu-torch, the two pip cannot do itself (#265)
    chitragupta figure sync [PATH] ... stamp the house figure-style block (#1013)
    chitragupta figure check FILE  ... report every rule one figure breaks (#1053)
    chitragupta figure new DIR NAME --layout ID ... start a figure from a scaffold (#1052)
    chitragupta figure look FILE [--draft DRAFT] ... see one figure as it will print (#1052)
    chitragupta webapp [--port N] [--no-browser] ... the loopback workbench (#1262)

**A front door, not a command surface.** Like `chitragupta/draft.py`,
this parses only the layer name and forwards the rest verbatim, so a
layer's flags cannot drift.

**The module form keeps working on purpose.** `python -m
chitragupta.<layer>` is what hooks and skills invoke: a console script
lives in one venv's `bin/`, and a hook launcher that does not resolve
fails silently (`chitragupta/hook_launchers.py`), so the gate must not
depend on a PATH lookup. The console script is for humans.

The command-depth invariant (#144) is unchanged: `chitragupta review
verbatim scan` is one layer, one aid and that aid's own subcommand.
docs/ARCHITECTURE.md states it; docs/PACKAGING.md carries the surface.
"""

import argparse
import importlib
import sys

from chitragupta.command_help import HELP, verbs
from chitragupta.help_format import dispatcher_parser
from chitragupta.progname import prog_for

# Imported lazily by name, as corpus.py does: `draft gate` must run on a
# bare interpreter and never pay for `enrich`'s optional imports.
LAYERS = {
    name: (module, HELP[name][0])
    for name, module in {
        "corpus": "chitragupta.corpus",
        "draft": "chitragupta.draft",
        "review": "chitragupta.review.__main__",
        "enrich": "chitragupta.enrich.__main__",
    }.items()
}

# Package-level commands (#258): they act on the environment around the
# pipeline rather than entering one of its four layers.
COMMANDS = {
    name: (module, HELP[name][0])
    for name, module in {
        "init": "chitragupta.init",
        "doctor": "chitragupta.doctor",
        "install": "chitragupta.install",
        "figure": "chitragupta.figure.__main__",
        "webapp": "chitragupta.webapp.__main__",
    }.items()
}

# Reachable but out of the `--help` tree until WA-1 (#1261) adds panes.
HIDDEN = frozenset({"webapp"})

CHOICES = {**LAYERS, **COMMANDS}

DESCRIPTION = (
    "Turn a curated bibliography into grounded drafts, "
    "with every citekey verified against a real parse."
)


def _version() -> str:
    """The installed distribution's version, via `importlib.metadata`
    (an install has no `pyproject.toml`); "unknown" rather than raising.
    """
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("chitragupta-cli")
    except (ImportError, PackageNotFoundError):
        return "unknown"


def tree_rows() -> list[tuple[str, str]]:
    """Each layer or command, then its verbs indented under it: the
    two-level tree `chitragupta --help` prints (#1230). Read from
    command_help.py, so help imports no layer."""
    rows = []
    for name, (one_line, _) in HELP.items():
        if name in HIDDEN:
            continue
        rows.append((name, one_line))
        rows.extend((f"  {verb}", text) for verb, text in verbs(name).items())
    return rows


def build_parser() -> argparse.ArgumentParser:
    prog = prog_for("")
    parser = dispatcher_parser(
        prog,
        DESCRIPTION,
        tree_rows(),
        "layer",
        choices=sorted(CHOICES),
        hint=f"Run '{prog} COMMAND --help' for a command's commands and flags.",
    )
    parser.add_argument(
        "--version", action="version", version=_version(), help="Show the version and exit."
    )
    return parser


def main(argv=None) -> int:
    """No layer at all prints the usage and exits 0, as every layer does
    for a missing verb."""
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.layer is None:
        parser.print_help()
        return 0
    module = importlib.import_module(CHOICES[args.layer][0])
    # `enrich` reads sys.argv itself, so it gets a rewritten one, restored
    # afterwards so a second main() call does not inherit it.
    if args.layer == "enrich":
        saved, sys.argv = sys.argv, [prog_for("enrich"), *args.rest]
        try:
            return module.main()
        finally:
            sys.argv = saved
    return module.main(args.rest)


if __name__ == "__main__":
    raise SystemExit(main())
