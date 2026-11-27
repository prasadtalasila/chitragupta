import sys

import pytest

from chitragupta import __main__ as entry
from tests.conftest import run_python


class TestDispatch:
    def test_every_layer_is_reachable(self):
        assert sorted(entry.LAYERS) == ["corpus", "draft", "enrich", "review"]

    def test_commands_are_reachable_beside_the_layers(self):
        assert "init" in entry.COMMANDS
        assert "figure" in entry.COMMANDS
        assert entry.CHOICES == {**entry.LAYERS, **entry.COMMANDS}

    def test_the_review_line_counts_the_aids_the_registry_holds(self):
        from chitragupta.review import __main__ as review_main
        from chitragupta.review._registry import AIDS

        words = "zero one two three four five six seven eight nine ten eleven twelve thirteen"
        count = words.split()[len(AIDS)]
        from chitragupta import command_help

        assert f"{count} read-only aids" in entry.LAYERS["review"][1]
        assert f"{count} read-only aids" in command_help.HELP["review"][0]
        assert f"{count} read-only aids" in review_main.DESCRIPTION

    @pytest.mark.parametrize("layer", ["corpus", "draft", "review", "enrich"])
    def test_a_layer_forwards_help_to_that_layer(self, layer, capsys):
        with pytest.raises(SystemExit) as excinfo:
            entry.main([layer, "--help"])
        assert excinfo.value.code == 0
        assert layer in capsys.readouterr().out

    @pytest.mark.parametrize("command", ["init", "doctor", "install"])
    def test_a_command_forwards_help_to_that_command(self, command, capsys):
        with pytest.raises(SystemExit) as excinfo:
            entry.main([command, "--help"])
        assert excinfo.value.code == 0
        assert command in capsys.readouterr().out

    def test_no_layer_prints_usage_and_exits_zero(self, capsys):
        assert entry.main([]) == 0
        assert "corpus" in capsys.readouterr().out

    def test_the_verb_is_forwarded_verbatim(self, capsys):
        with pytest.raises(SystemExit):
            entry.main(["draft", "dossier", "--help"])
        assert "dossier" in capsys.readouterr().out

    def test_enrich_gets_a_rewritten_argv_and_it_is_restored(self):
        before = list(sys.argv)
        with pytest.raises(SystemExit):
            entry.main(["enrich", "--help"])
        assert sys.argv == before


class TestVersion:
    def test_it_reports_the_installed_distribution(self):
        assert entry._version() != ""

    def test_an_uninstalled_distribution_is_not_fatal(self, monkeypatch):
        import importlib.metadata as md

        def raise_missing(_name):
            raise md.PackageNotFoundError("chitragupta-cli")

        monkeypatch.setattr(md, "version", raise_missing)
        assert entry._version() == "unknown"


class TestTheModuleFormSurvives:
    @pytest.mark.parametrize("layer", ["corpus", "draft", "review"])
    def test_python_m_still_reaches_each_layer(self, layer):
        result = run_python("-m", f"chitragupta.{layer}", "--help", check=False)
        assert result.returncode == 0
        assert f"python -m chitragupta.{layer}" in result.stdout

    def test_the_package_itself_is_runnable_as_a_module(self):
        result = run_python("-m", "chitragupta", check=False)
        assert result.returncode == 0
        assert "corpus" in result.stdout


class TestTheHelpTree:
    def _help(self, monkeypatch, capsys) -> str:
        monkeypatch.setenv("COLUMNS", "80")
        monkeypatch.setattr("sys.argv", ["chitragupta"])
        with pytest.raises(SystemExit) as excinfo:
            entry.main(["--help"])
        assert excinfo.value.code == 0
        return capsys.readouterr().out

    def test_help_shows_every_layers_verbs(self, monkeypatch, capsys):
        from chitragupta import command_help

        out = self._help(monkeypatch, capsys)
        for name, (_, verbs) in command_help.HELP.items():
            assert f"\n  {name} " in out
            for verb in verbs:
                assert f"\n    {verb} " in out
        assert out.endswith(
            "Run 'chitragupta COMMAND --help' for a command's commands and flags.\n"
        )

    def test_the_diff_row_is_not_cut_in_the_tree(self, monkeypatch, capsys):
        out = self._help(monkeypatch, capsys)
        (row,) = [line for line in out.splitlines() if line.startswith("    diff ")]
        assert "since a snapshot" in row
        assert not row.endswith("...")

    def test_the_version_flag_reads_like_click(self, monkeypatch, capsys):
        assert "--version   Show the version and exit." in self._help(monkeypatch, capsys)

    def test_a_verb_is_not_a_top_level_command(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            entry.main(["sync"])
        assert excinfo.value.code == 2
        assert "invalid choice: 'sync'" in capsys.readouterr().err

    def test_help_does_not_import_any_layer(self):
        result = run_python(
            "-c",
            "import sys\n"
            "from chitragupta import __main__ as entry\n"
            "try:\n    entry.main(['--help'])\n"
            "except SystemExit:\n    pass\n"
            "print(sorted(m for m in sys.modules if m.startswith('chitragupta')))",
        )
        loaded = result.stdout.splitlines()[-1]
        for layer in (
            "chitragupta.draft",
            "chitragupta.corpus",
            "chitragupta.review.__main__",
            "chitragupta.enrich.__main__",
            "chitragupta.figure.__main__",
        ):
            assert f"'{layer}'" not in loaded

    def test_help_survives_a_broken_enrich(self, monkeypatch, capsys):
        monkeypatch.setitem(sys.modules, "chitragupta.enrich", None)
        assert "enrich" in self._help(monkeypatch, capsys)

    def test_review_and_figure_help_come_from_the_index(self):
        import argparse

        from chitragupta import command_help
        from chitragupta.figure.__main__ import build_parser
        from chitragupta.review._registry import AIDS

        assert {aid: text for aid, (_, text) in AIDS.items()} == command_help.verbs("review")
        subparsers = next(
            a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction)
        )
        figure = {a.dest: a.help for a in subparsers._choices_actions}
        assert figure == command_help.verbs("figure")
