import ast
import builtins
import importlib
import inspect
import shutil
import subprocess
from pathlib import Path

import pytest

from chitragupta import render_output
from chitragupta.render_output._failures import RENDER_FAILURES
from tests.conftest import content_draft


class TestRequire:
    def test_raises_missing_binary_when_not_on_path(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: None)
        with pytest.raises(render_output.MissingBinary):
            render_output._require("some-binary-that-does-not-exist")

    def test_no_raise_when_found(self, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
        render_output._require("pandoc")  # should not raise


def _raised_classes():
    package = Path(render_output.__file__).parent
    for source in sorted(package.glob("*.py")):
        if source.name == "_cli.py":
            continue
        module = (
            render_output
            if source.name == "__init__.py"
            else importlib.import_module(f"chitragupta.render_output.{source.stem}")
        )
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                dotted = ast.unparse(node.exc.func).split(".")
                found = vars(module).get(dotted[0]) or getattr(builtins, dotted[0])
                for part in dotted[1:]:
                    found = getattr(found, part)
                yield source.name, node.lineno, found


def _is_the_caller_mistake(name, line, cls):
    lines, first = inspect.getsourcelines(render_output._refuse_misdeferred)
    return (name, cls) == ("__init__.py", ValueError) and first <= line < first + len(lines)


def _instance(failure):
    if failure is subprocess.CalledProcessError:
        return failure(1, ["pandoc"], stderr="pandoc said no")
    return failure("render refused")


class TestRenderFailures:
    def test_the_caller_mistake_exemption_is_one_site(self):
        lines, first = inspect.getsourcelines(render_output._refuse_misdeferred)
        inside = [line for name, line, _ in _raised_classes() if name == "__init__.py"]
        assert any(_is_the_caller_mistake("__init__.py", line, ValueError) for line in inside)
        assert not _is_the_caller_mistake("_paths.py", first + 1, ValueError)
        assert not _is_the_caller_mistake("__init__.py", first + len(lines), ValueError)

    def test_every_raise_in_the_package_is_a_render_failure(self):
        sites = list(_raised_classes())
        assert sites, "the walk found no raise sites at all"
        strays = [
            (name, line, cls.__name__)
            for name, line, cls in sites
            if not issubclass(cls, RENDER_FAILURES) and not _is_the_caller_mistake(name, line, cls)
        ]
        assert not strays

    @pytest.mark.parametrize("failure", RENDER_FAILURES, ids=lambda c: c.__name__)
    def test_the_cli_reports_every_render_failure_without_a_traceback(
        self, isolated_config, monkeypatch, capsys, failure
    ):
        def _fail(*a, **k):
            raise _instance(failure)

        monkeypatch.setattr(render_output, "render", _fail)
        draft = content_draft(isolated_config, "draft.md")
        draft.write_text("text\n")
        assert render_output.main([str(draft), "--format", "tex"]) == 1
        assert capsys.readouterr().out.startswith(("[error]", "[missing-binary]"))
