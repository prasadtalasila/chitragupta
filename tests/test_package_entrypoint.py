"""`chitragupta/__main__.py`: the console script's front door.

A front door, not a command surface -- every verb, flag and exit code
belongs to the layer this dispatches to. What is pinned here is the
dispatch itself, and the rule that the module form keeps working beside
it (docs/PACKAGING.md), because the hooks and skills depend on that and a
launcher that stops resolving fails silently.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import __main__ as entry

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDispatch:
    def test_every_layer_is_reachable(self):
        """The four layers, and nothing invented beside them."""
        assert sorted(entry.LAYERS) == ["corpus", "draft", "enrich", "review"]

    @pytest.mark.parametrize("layer", ["corpus", "draft", "review", "enrich"])
    def test_a_layer_forwards_help_to_that_layer(self, layer, capsys):
        with pytest.raises(SystemExit) as excinfo:
            entry.main([layer, "--help"])
        assert excinfo.value.code == 0
        assert layer in capsys.readouterr().out

    def test_no_layer_prints_usage_and_exits_zero(self, capsys):
        """"Tell me how to use this" is a request, not an error -- the
        rule every layer here already applies to a missing verb."""
        assert entry.main([]) == 0
        assert "corpus" in capsys.readouterr().out

    def test_the_verb_is_forwarded_verbatim(self, capsys):
        """This file parses the layer and nothing else: restating a
        layer's flags would be a second place for them to drift.

        `dossier` rather than `gate`, because gate is deliberately not
        argparse at all (it takes no options) and so does not raise
        SystemExit on --help the way every other verb does."""
        with pytest.raises(SystemExit):
            entry.main(["draft", "dossier", "--help"])
        assert "dossier" in capsys.readouterr().out

    def test_enrich_gets_a_rewritten_argv_and_it_is_restored(self):
        """enrich reads sys.argv itself rather than taking argv, so it is
        handed a rewritten one. A second call must not inherit the first
        call's arguments."""
        before = list(sys.argv)
        with pytest.raises(SystemExit):
            entry.main(["enrich", "--help"])
        assert sys.argv == before


class TestVersion:
    def test_it_reports_the_installed_distribution(self):
        assert entry._version() != ""

    def test_an_uninstalled_distribution_is_not_fatal(self, monkeypatch):
        """`--version` failing is a worse answer than an imprecise one."""
        import importlib.metadata as md

        def raise_missing(_name):
            raise md.PackageNotFoundError("chitragupta-cli")

        monkeypatch.setattr(md, "version", raise_missing)
        assert entry._version() == "unknown"


class TestTheModuleFormSurvives:
    """The hooks and the genre skills invoke `python -m chitragupta.draft
    gate`, never the console script: a console script lives in one venv's
    bin/, and a hook launcher that does not resolve produces nothing at
    all -- no error, no log line. If this ever stops working, the citation
    gate stops running and nothing says so."""

    @pytest.mark.parametrize("layer", ["corpus", "draft", "review"])
    def test_python_m_still_reaches_each_layer(self, layer):
        result = subprocess.run(
            [sys.executable, "-m", f"chitragupta.{layer}", "--help"],
            capture_output=True, text=True, cwd=REPO_ROOT, check=False,
        )
        assert result.returncode == 0
        assert f"python -m chitragupta.{layer}" in result.stdout

    def test_the_package_itself_is_runnable_as_a_module(self):
        result = subprocess.run(
            [sys.executable, "-m", "chitragupta"],
            capture_output=True, text=True, cwd=REPO_ROOT, check=False,
        )
        assert result.returncode == 0
        assert "corpus" in result.stdout
