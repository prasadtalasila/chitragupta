"""chitragupta/render_output/_errors.py: the PATH probe behind MissingBinary.

Split from one test module to mirror `chitragupta/render_output/`'s own split,
the way `tests/test_enrich_*.py` mirrors `chitragupta/enrich/`. Shared setup --
the binary probes and the figure fixtures -- lives in `tests/conftest.py`
so the eight modules do not each re-run a `kpsewhich` subprocess at
import.
"""

import ast
import importlib
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
    """`(module, line, class)` for every `raise X(...)` in the package.

    `_cli.py` is left out: its one raise is argparse's own
    `ArgumentTypeError`, a refusal of the command line before `render()`
    is called, which argparse reports itself.
    """
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
                found = vars(module)[dotted[0]]
                for part in dotted[1:]:
                    found = getattr(found, part)
                yield source.name, node.lineno, found


def _instance(failure):
    if failure is subprocess.CalledProcessError:
        return failure(1, ["pandoc"], stderr="pandoc said no")
    return failure("render refused")


class TestRenderFailures:
    def test_every_raise_in_the_package_is_a_render_failure(self):
        # #949: `review.write` listed the exceptions render() raised when
        # it was written and missed the four added since. Walking every
        # raise site is what keeps a new one from being forgotten again.
        sites = list(_raised_classes())
        assert sites, "the walk found no raise sites at all"
        strays = [
            (name, line, cls.__name__)
            for name, line, cls in sites
            if not issubclass(cls, RENDER_FAILURES)
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
