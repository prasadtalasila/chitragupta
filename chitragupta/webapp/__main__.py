"""`chitragupta webapp [--port N] [--no-browser]`.

Refuses (exit 2) outside a chitragupta project and without the `webapp`
extra. Imports nothing from FastAPI or uvicorn at module level, so asking
for `--help`, or the CLI importing this module, never loads them.
"""

import argparse
import importlib.util
import sys

from chitragupta import config
from chitragupta.help_format import ClickParser
from chitragupta.progname import prog_for

EXIT_REFUSED = 2
REQUIRED_MODULES = ("fastapi", "uvicorn")
INSTALL_HINT = "pip install 'chitragupta-cli[webapp]'"

DESCRIPTION = (
    "Serve the browser workbench on 127.0.0.1 only. The URL it prints carries "
    "a one-run token; open it in your browser. There is no way to bind another "
    "address: from another machine, use an SSH tunnel (ssh -L PORT:127.0.0.1:PORT HOST)."
)


def port_arg(value: str) -> int:
    """A TCP port the user asked for: 1-65535, never 0 (0 is the default's job)."""
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a port number: {value!r}") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port must be 1-65535, got {port}")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = ClickParser(prog=prog_for("webapp"), description=DESCRIPTION)
    parser.add_argument(
        "--port",
        type=port_arg,
        default=0,
        help="Serve on this port (1-65535). Without it the OS picks a free one.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the URL and do not open a browser.",
    )
    return parser


def missing_extra() -> list[str]:
    """The modules of the `webapp` extra that cannot be imported here."""
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def _refuse(message: str) -> int:
    print(f"{prog_for('webapp')}: {message}", file=sys.stderr)
    return EXIT_REFUSED


def main(argv=None) -> int:
    build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if config.discover_project_root() is None:
        return _refuse("not inside a chitragupta project (no config.toml); run 'chitragupta init'")
    missing = missing_extra()
    if missing:
        return _refuse(f"the webapp extra is not installed ({', '.join(missing)}); {INSTALL_HINT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
