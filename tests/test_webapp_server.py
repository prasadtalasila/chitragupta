import http.client
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

import pytest

from chitragupta.webapp import _server
from chitragupta.webapp._app import build_app
from tests.conftest import REPO_ROOT

TOKEN = "t" * 43


def test_bind_is_loopback_on_port_zero():
    sock = _server.bind_socket(0)
    try:
        host, port = sock.getsockname()
        assert host == "127.0.0.1"
        assert port > 0
    finally:
        sock.close()


def test_taken_port_raises():
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen()
    try:
        with pytest.raises(_server.PortUnavailable):
            _server.bind_socket(holder.getsockname()[1])
    finally:
        holder.close()


def test_non_loopback_bind_is_fatal(monkeypatch):
    monkeypatch.setattr(_server, "LOOPBACK", "0.0.0.0")
    with pytest.raises(RuntimeError, match="loopback"):
        _server.bind_socket(0)


def _get(port, host, token=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request("GET", "/api/status", headers=headers)
    status = conn.getresponse().status
    conn.close()
    return status


def test_real_uvicorn_round_trip():
    sock = _server.bind_socket(0)
    port = sock.getsockname()[1]
    server = _server.make_server(build_app(port=port, token=TOKEN))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        assert _get(port, f"127.0.0.1:{port}", TOKEN) == 200
        assert _get(port, f"evil.example:{port}", TOKEN) == 403
        assert _get(port, f"127.0.0.1:{port}") == 401
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()


def test_serve_runs_the_server_on_the_given_socket(monkeypatch):
    seen = {}

    class FakeServer:
        def run(self, sockets):
            seen["sockets"] = sockets

    monkeypatch.setattr(_server, "make_server", lambda app: FakeServer())
    _server.serve("app", "sock")
    assert seen == {"sockets": ["sock"]}


@pytest.mark.parametrize("platform, reuse", [("linux", True), ("win32", False)])
def test_address_reuse_only_where_it_cannot_steal_a_port(monkeypatch, platform, reuse):
    monkeypatch.setattr(_server.sys, "platform", platform)
    sock = _server.bind_socket(0)
    try:
        assert bool(sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR)) is reuse
    finally:
        sock.close()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM cannot be sent to a child on Windows")
def test_sigterm_stops_cleanly_and_removes_the_runtime_files(tmp_path):
    shutil.copy(REPO_ROOT / "config.toml.example", tmp_path / "config.toml")
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT), "CHITRAGUPTA_PROJECT": str(tmp_path)}
    child = subprocess.Popen(
        [sys.executable, "-m", "chitragupta", "webapp", "--no-browser"],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert "#token=" in child.stdout.readline()
        runtime = tmp_path / "content" / ".webapp"
        assert (runtime / "server.json").exists()
        child.send_signal(signal.SIGTERM)
        assert child.wait(timeout=20) == 0
    finally:
        child.kill()
        child.communicate()
    assert not (runtime / "server.json").exists()
    assert not (runtime / "open.html").exists()


def test_terminate_becomes_an_interrupt():
    previous = signal.getsignal(signal.SIGTERM)
    try:
        _server.terminate_as_interrupt()
        with pytest.raises(KeyboardInterrupt):
            signal.raise_signal(signal.SIGTERM)
    finally:
        signal.signal(signal.SIGTERM, previous)


def test_the_server_pins_its_parser_and_trusts_no_proxy():
    config = _server.make_server(build_app(port=1, token=TOKEN)).config
    assert config.http == "h11"
    assert config.ws == "none"
    assert config.proxy_headers is False
    assert config.server_header is False
    assert config.access_log is False


def test_on_started_runs_while_the_server_is_serving(monkeypatch):
    seen = []

    class FakeServer:
        started = False
        should_exit = False

        def run(self, sockets):
            self.started = True
            deadline = time.monotonic() + 5
            while not seen and time.monotonic() < deadline:
                time.sleep(0.01)
            seen.append("run returned")

    monkeypatch.setattr(_server, "make_server", lambda app: FakeServer())
    _server.serve("app", "sock", on_started=lambda: seen.append("opened"))
    assert seen == ["opened", "run returned"]


def test_on_started_is_skipped_when_the_server_never_starts(monkeypatch):
    seen = []

    class FakeServer:
        started = False
        should_exit = True

        def run(self, sockets):
            time.sleep(0.2)

    monkeypatch.setattr(_server, "make_server", lambda app: FakeServer())
    _server.serve("app", "sock", on_started=lambda: seen.append("opened"))
    time.sleep(0.2)
    assert seen == []


@pytest.fixture(scope="module")
def live():
    """A real uvicorn on a loopback port, for requests the test client would rewrite."""
    sock = _server.bind_socket(0)
    port = sock.getsockname()[1]
    server = _server.make_server(build_app(port=port, token=TOKEN))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    yield port
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()


def _raw(port, head, body=b""):
    """Send exactly these bytes; return the status code uvicorn answered with."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as conn:
        conn.sendall(head.replace("\n", "\r\n").encode("latin-1") + b"\r\n" + body)
        reply = b""
        while b"\r\n" not in reply:
            chunk = conn.recv(4096)
            if not chunk:
                break
            reply += chunk
    return int(reply.split(b" ", 2)[1]) if reply else None


def _head(path, port, extra=""):
    return f"GET {path} HTTP/1.1\nHost: 127.0.0.1:{port}\nConnection: close\n{extra}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/status",
        "/api",
        "//api/status",
        "/API/status",
        "/x/../api/status",
        "/%2e%2e/api/status",
        "/%61pi/status",
        "/api%2fstatus",
        "/api/status/",
        "/./api/status",
    ],
)
def test_no_path_spelling_reaches_the_api_without_the_token(live, path):
    assert _raw(live, _head(path, live)) in {401, 404}


def test_the_token_still_works_on_the_wire(live):
    assert _raw(live, _head("/api/status", live, f"Authorization: Bearer {TOKEN}\n")) == 200


@pytest.mark.parametrize("path", ["/../config.toml", "/%2e%2e/config.toml", "/..%2fconfig.toml"])
def test_static_traversal_on_the_wire(live, path):
    assert _raw(live, _head(path, live)) == 404


@pytest.mark.parametrize(
    "extra", ["Host: 127.0.0.1:{port}\n", "Authorization: Bearer x\nAuthorization: Bearer x\n"]
)
def test_a_repeated_security_header_on_the_wire(live, extra):
    assert _raw(live, _head("/api/status", live, extra.format(port=live))) == 400


def test_an_absolute_form_target_is_not_served(live):
    head = (
        f"GET http://evil.example/api/status HTTP/1.1\nHost: 127.0.0.1:{live}\nConnection: close\n"
    )
    assert _raw(live, head) != 200


def test_a_websocket_upgrade_never_reaches_the_app(live):
    extra = (
        "Upgrade: websocket\nConnection: Upgrade\nSec-WebSocket-Version: 13\n"
        "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\n"
        f"Authorization: Bearer {TOKEN}\n"
    )
    head = f"GET /api/status HTTP/1.1\nHost: 127.0.0.1:{live}\n{extra}"
    assert _raw(live, head) != 101


def test_chunked_cannot_carry_a_body_past_the_limit(live):
    head = (
        f"POST /api/status HTTP/1.1\nHost: 127.0.0.1:{live}\nOrigin: http://127.0.0.1:{live}\n"
        f"Authorization: Bearer {TOKEN}\nContent-Length: 5\nTransfer-Encoding: chunked\n"
        "Connection: close\n"
    )
    assert _raw(live, head, b"5\r\nhello\r\n0\r\n\r\n") == 400
