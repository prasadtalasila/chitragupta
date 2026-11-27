import argparse
import importlib.util
import socket

import pytest

from chitragupta import config
from chitragupta.runlock import pipeline_lock
from chitragupta.webapp import __main__ as webapp
from chitragupta.webapp import _launch, _server
from tests.conftest import run_python


@pytest.mark.parametrize("value, expected", [("1", 1), ("8123", 8123), ("65535", 65535)])
def test_port_arg_accepts_the_valid_range(value, expected):
    assert webapp.port_arg(value) == expected


@pytest.mark.parametrize("value", ["0", "65536", "-1", "abc", ""])
def test_port_arg_refuses_everything_else(value):
    with pytest.raises(argparse.ArgumentTypeError):
        webapp.port_arg(value)


def test_outside_a_project_refuses(monkeypatch, capsys):
    monkeypatch.setattr(config, "discover_project_root", lambda: None)
    assert webapp.main(["--no-browser"]) == webapp.EXIT_REFUSED
    assert "chitragupta init" in capsys.readouterr().err


def test_missing_extra_refuses(monkeypatch, capsys):
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name, *a: None if name == "fastapi" else real(name, *a)
    )
    assert webapp.missing_extra() == ["fastapi"]
    assert webapp.main(["--no-browser"]) == webapp.EXIT_REFUSED
    assert "pip install 'chitragupta-cli[webapp]'" in capsys.readouterr().err


def test_the_command_and_the_cli_never_import_the_web_stack():
    code = (
        "import sys, contextlib, io\n"
        "import chitragupta.webapp.__main__\n"
        "from chitragupta import __main__ as entry\n"
        "with contextlib.redirect_stdout(io.StringIO()):\n"
        "    entry.main([])\n"
        "print(sorted(m for m in ('fastapi', 'uvicorn', 'starlette') if m in sys.modules))\n"
    )
    result = run_python("-c", code)
    assert result.stdout.strip() == "[]"


@pytest.fixture
def served(isolated_config, monkeypatch):
    """`main` with `serve` replaced: records the app and the socket's port."""
    calls = {"opened": []}

    def fake_serve(app, sock, on_started=None):
        calls["port"] = sock.getsockname()[1]
        calls["files"] = sorted(p.name for p in _launch.runtime_dir().iterdir())
        calls["opened_before_serving"] = list(calls["opened"])
        if on_started:
            on_started()
        hook = calls.get("during")
        if hook:
            hook()

    monkeypatch.setattr(_server, "serve", fake_serve)
    monkeypatch.setattr(_launch, "open_browser", lambda page: calls["opened"].append(page))
    return calls


def test_clean_run_prints_url_and_cleans_up(served, capsys):
    assert webapp.main(["--no-browser"]) == 0
    out = capsys.readouterr().out
    assert f"http://127.0.0.1:{served['port']}/#token=" in out
    assert {"open.html", "server.json"} <= set(served["files"])
    assert not (_launch.runtime_dir() / "open.html").exists()
    assert not (_launch.runtime_dir() / "server.json").exists()
    assert served["opened"] == []


def test_the_browser_is_opened_on_the_launch_file(served):
    assert webapp.main([]) == 0
    assert served["opened"] == [_launch.runtime_dir() / "open.html"]


def test_the_browser_is_opened_only_once_the_server_is_serving(served):
    assert webapp.main([]) == 0
    assert served["opened_before_serving"] == []


def test_the_requested_port_is_used(served):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    free = sock.getsockname()[1]
    sock.close()
    assert webapp.main(["--no-browser", "--port", str(free)]) == 0
    assert served["port"] == free


def test_port_taken_refuses(served, capsys):
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen()
    port = holder.getsockname()[1]
    try:
        assert webapp.main(["--no-browser", "--port", str(port)]) == webapp.EXIT_REFUSED
    finally:
        holder.close()
    assert str(port) in capsys.readouterr().err


def test_second_instance_refuses_with_the_port(served, capsys):
    directory = _launch.runtime_dir()
    _launch.write_server_file(directory, 8123, 1)
    with pipeline_lock(directory / "server.lock"):
        assert webapp.main(["--no-browser"]) == webapp.EXIT_REFUSED
    assert "8123" in capsys.readouterr().err


def test_second_instance_while_the_first_is_starting(served, capsys):
    with pipeline_lock(_launch.runtime_dir() / "server.lock"):
        assert webapp.main(["--no-browser"]) == webapp.EXIT_REFUSED
    assert "starting" in capsys.readouterr().err


def test_does_not_take_the_corpus_lock(served):
    def take_corpus_lock():
        with pipeline_lock():
            served["corpus_lock"] = True

    served["during"] = take_corpus_lock
    assert webapp.main(["--no-browser"]) == 0
    assert served["corpus_lock"] is True


def test_stale_runtime_files_are_overwritten(served):
    directory = _launch.runtime_dir()
    _launch.write_server_file(directory, 1, 1)
    _launch.write_open_file(directory, "http://127.0.0.1:1/#token=old")
    assert webapp.main(["--no-browser"]) == 0
    assert served["port"] != 1


def test_keyboard_interrupt_is_a_clean_stop(served):
    def interrupt():
        raise KeyboardInterrupt

    served["during"] = interrupt
    assert webapp.main(["--no-browser"]) == 0
    assert not (_launch.runtime_dir() / "server.json").exists()
