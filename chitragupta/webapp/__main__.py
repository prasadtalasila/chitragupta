"""Imports nothing from FastAPI or uvicorn at module level: the CLI imports this."""

import argparse
import importlib.util
import os
import signal
import sys

from chitragupta import config
from chitragupta.runlock import AlreadyRunning, pipeline_lock
from chitragupta.webapp import _launch
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
    return [name for name in REQUIRED_MODULES if importlib.util.find_spec(name) is None]


def _refuse(message: str) -> int:
    print(f"{prog_for('webapp')}: {message}", file=sys.stderr)
    return EXIT_REFUSED


def main(argv=None) -> int:
    args = build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    if config.discover_project_root() is None:
        return _refuse("not inside a chitragupta project (no config.toml); run 'chitragupta init'")
    missing = missing_extra()
    if missing:
        return _refuse(f"the webapp extra is not installed ({', '.join(missing)}); {INSTALL_HINT}")
    return _run(args)


def _already_running(directory) -> int:
    port = _launch.read_server_port(directory)
    if port is None:
        return _refuse("another webapp is starting in this project; try again in a moment")
    return _refuse(
        f"already running on port {port} for this project; use the URL printed in its terminal"
    )


def _run(args) -> int:
    # Its own lock, never the corpus writer lock, so `corpus sync` still runs.
    directory = _launch.runtime_dir()
    try:
        with pipeline_lock(directory / "server.lock"):
            return _serve_locked(args, directory)
    except AlreadyRunning:
        return _already_running(directory)


def _serve_locked(args, directory) -> int:
    from chitragupta.webapp import _server
    from chitragupta.webapp._app import build_app

    try:
        sock = _server.bind_socket(args.port)
    except _server.PortUnavailable as exc:
        return _refuse(f"{exc.strerror}; choose another --port, or leave it out")
    port = sock.getsockname()[1]
    token = _launch.new_token()
    url = _launch.launch_url(port, token)
    # Before any runtime file exists, so a SIGTERM at any point still cleans up.
    previous = _server.terminate_as_interrupt()
    try:
        _launch.write_server_file(directory, port, os.getpid())
        page = _launch.write_open_file(directory, url)
        print(f"chitragupta workbench: {url}\nStop it with Ctrl-C.", flush=True)
        opener = None if args.no_browser else (lambda: _launch.open_browser(page))
        _server.serve(build_app(port=port, token=token), sock, on_started=opener)
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, previous)
        sock.close()
        _launch.remove_runtime_files(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
