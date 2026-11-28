"""uvicorn's own `host` is never used; bind_socket asserts the bound
address is loopback.
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
    pass


def bind_socket(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform != "win32":
        # POSIX only: on Windows it lets another process steal a listening port.
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

    # Pinned so the tests exercise what ships; every client is 127.0.0.1,
    # which uvicorn would otherwise trust for X-Forwarded-*.
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
    # uvicorn re-raises SIGTERM after shutdown; under the default handler
    # that kills the process before main's cleanup runs.
    return signal.signal(signal.SIGTERM, _raise_interrupt)


def _when_started(server, callback: Callable[[], object]) -> None:
    while not server.started and not server.should_exit:
        time.sleep(0.05)
    if server.started:
        callback()


def serve(app, sock: socket.socket, on_started: Callable[[], object] | None = None) -> None:
    # Not before serving: webbrowser.open blocks for a $BROWSER command,
    # and a browser waiting on its first page would wait on this server.
    server = make_server(app)
    if on_started is not None:
        threading.Thread(target=_when_started, args=(server, on_started), daemon=True).start()
    server.run(sockets=[sock])
