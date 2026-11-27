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
        cwd=tmp_path, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
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
