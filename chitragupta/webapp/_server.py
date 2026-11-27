"""Bind the loopback socket ourselves and hand it to uvicorn (#1262).

uvicorn's own `host` setting is never used: the address is the constant
below, and `bind_socket` refuses to return a socket whose bound address
is not loopback, so a later change that loosens the constant fails loudly
instead of quietly serving the network.
"""

import ipaddress
import signal
import socket
import sys
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uvicorn

LOOPBACK = "127.0.0.1"


class PortUnavailable(OSError):
    """The requested port is taken or not ours to bind."""


def bind_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        # POSIX only: on Windows SO_REUSEADDR lets a second process steal a
        # port that is already listening.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((LOOPBACK, port))
    except OSError as exc:
        sock.close()
        raise PortUnavailable(exc.errno, f"port {port} is not available ({exc.strerror})") from exc
    if not ipaddress.ip_address(sock.getsockname()[0]).is_loopback:
        sock.close()
        raise RuntimeError("refusing to serve on a non-loopback address")
    sock.listen()
    return sock


def make_server(app) -> "uvicorn.Server":
    import uvicorn

    # Every protocol choice pinned, so what the tests exercise is what ships:
    # h11 whatever else is installed, no WebSocket stack, and no trust in
    # X-Forwarded-* (every client here is 127.0.0.1, which uvicorn trusts).
    config = uvicorn.Config(
        app,
        http="h11",
        ws="none",
        proxy_headers=False,
        server_header=False,
        access_log=False,
        log_level="warning",
        lifespan="off",
    )
    return uvicorn.Server(config)


def _raise_interrupt(_signum, _frame) -> None:
    raise KeyboardInterrupt


def terminate_as_interrupt() -> Any:
    """Make SIGTERM end the process the way Ctrl-C does.

    uvicorn shuts down on SIGTERM, then restores the previous handler and
    re-raises the signal. Under the default handler that kills the process
    before `main`'s cleanup runs, leaving the launch file behind; this
    handler turns it into a `KeyboardInterrupt`, which `main` handles.
    Returns the handler it replaced, for the caller to restore.
    """
    return signal.signal(signal.SIGTERM, _raise_interrupt)


def _when_started(server, callback: Callable[[], object]) -> None:
    while not server.started and not server.should_exit:
        time.sleep(0.05)
    if server.started:
        callback()


def serve(app, sock: socket.socket, on_started: Callable[[], object] | None = None) -> None:
    """Run until stopped; `on_started` runs on its own thread once serving.

    The browser is opened there, not before: `webbrowser.open` blocks for
    a `$BROWSER` command or a console browser, and a browser that waits
    for its first page would wait on a server that has not started.
    """
    server = make_server(app)
    if on_started is not None:
        threading.Thread(target=_when_started, args=(server, on_started), daemon=True).start()
    server.run(sockets=[sock])
