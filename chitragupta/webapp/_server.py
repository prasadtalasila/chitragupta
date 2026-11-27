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

    config = uvicorn.Config(app, access_log=False, log_level="warning", lifespan="off")
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


def serve(app, sock: socket.socket) -> None:
    make_server(app).run(sockets=[sock])
