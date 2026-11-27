import argparse
import importlib.util

import pytest

from chitragupta import config
from chitragupta.webapp import __main__ as webapp
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


def test_inside_a_project_with_the_extra_passes_the_checks():
    assert webapp.main(["--no-browser"]) == 0
