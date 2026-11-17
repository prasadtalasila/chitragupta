"""`chitragupta/help_format.py` and `chitragupta/command_help.py`: the
click-style `--help` the dispatchers print (#1230).

What is pinned here is the truncation rule and the layout, because the
spec fixed both: a command list shows one cut line per command, and the
full text lives one level down in that command's own `--help`.
"""

import ast
import sys
from pathlib import Path

import pytest

from chitragupta import help_format
from chitragupta.help_format import commands_block, truncate
from tests.conftest import run_python


class TestTruncate:
    def test_text_that_fits_whole_is_kept_whole(self):
        """A clause break is a place to cut, not a reason to: the line
        keeps everything that fits."""
        text = "retrieval surfaced it -- did the draft cite it?"
        assert truncate(text, 60) == "Retrieval surfaced it -- did the draft cite it?"

    def test_a_clause_is_kept_when_the_whole_does_not_fit(self):
        text = "read-only view of what that run recorded -- takes no lock"
        assert truncate(text, 45) == "Read-only view of what that run recorded"

    def test_an_abbreviation_is_not_a_sentence_end(self):
        """`vs. the` is mid-sentence; cutting there printed "torch vs"."""
        text = "probe and report: OS binaries, torch vs. the GPU driver, and a great deal more"
        assert truncate(text, 50) == "Probe and report: OS binaries, torch vs. the..."

    def test_text_that_fits_whole_is_capitalised_and_loses_its_full_stop(self):
        assert truncate("what changed.", 60) == "What changed"

    def test_overlong_text_is_cut_at_a_word_and_marked(self):
        text = "the working state behind a draft: create it, inspect it, back it up, restore it"
        out = truncate(text, 64)
        assert out == "The working state behind a draft: create it, inspect it..."
        assert len(out) <= 64

    def test_one_word_longer_than_the_limit_is_cut_hard(self):
        assert truncate("x" * 100, 45) == "X" + "x" * 41 + "..."

    def test_an_abbreviation_with_a_capital_after_it_is_not_a_cut(self):
        """No sentence cuts at all: `e.g. Foo` once printed as "E.g"."""
        text = "e.g. Foo is a long example that will not fit in the limit we give"
        assert truncate(text, 45) == "E.g. Foo is a long example that will not..."

    def test_a_word_cut_that_keeps_too_little_falls_back_to_a_hard_cut(self):
        assert truncate("a " + "x" * 80, 45) == "A " + "x" * 40 + "..."

    def test_a_word_cut_after_a_full_stop_does_not_print_four_dots(self):
        assert truncate("torch vs. the GPU driver and a lot more", 14) == "Torch vs..."


class TestCommandsBlock:
    def test_the_limit_never_drops_below_45(self):
        block = commands_block([("discover", "y" * 80)], width=40)
        assert len(block.splitlines()[0]) == 2 + 8 + 2 + 45

    def test_nested_rows_align_on_the_widest_name(self):
        block = commands_block([("corpus", "a"), ("  sync", "b")], width=80)
        assert block == "  corpus  A\n    sync  B"


def test_help_index_is_import_light():
    """The top-level tree reads these two modules, and must never pay for
    a layer's imports -- `enrich`'s may not even be installed."""
    result = run_python(
        "-c",
        "import sys, chitragupta.command_help, chitragupta.help_format\n"
        "print(sorted(m for m in sys.modules if m.startswith('chitragupta')))",
    )
    loaded = set(ast.literal_eval(result.stdout.strip()))
    assert loaded <= {
        "chitragupta",
        "chitragupta.command_help",
        "chitragupta.help_format",
        "chitragupta.progname",
    }


class TestDispatcherParser:
    def test_parser_kwargs_suggests_only_on_314(self, monkeypatch):
        """`suggest_on_error` raises TypeError on 3.12 and 3.13, which
        pyproject.toml still supports."""
        monkeypatch.setattr(sys, "version_info", (3, 14, 0))
        assert help_format.parser_kwargs() == {"suggest_on_error": True}
        monkeypatch.setattr(sys, "version_info", (3, 13, 5))
        assert help_format.parser_kwargs() == {}

    def test_dispatcher_help_matches_click(self, monkeypatch, capsys):
        monkeypatch.setenv("COLUMNS", "80")
        parser = help_format.dispatcher_parser(
            "chitragupta corpus",
            "The corpus layer.",
            [("sync", "bib file -> ledger"), ("ledger", "read it -- no lock")],
            "verb",
        )
        parser.print_help()
        assert capsys.readouterr().out == (
            "Usage: chitragupta corpus [OPTIONS] COMMAND [ARGS]...\n\n"
            "  The corpus layer.\n\n"
            "Options:\n  -h, --help  Show this message and exit.\n\n"
            "Commands:\n  sync    Bib file -> ledger\n  ledger  Read it -- no lock\n\n"
            "  Run 'chitragupta corpus COMMAND --help' for a command's flags.\n"
        )

    def test_a_long_description_wraps_indented(self, monkeypatch, capsys):
        monkeypatch.setenv("COLUMNS", "40")
        parser = help_format.dispatcher_parser("x", "word " * 20, [("a", "s")], "verb")
        parser.print_help()
        lines = capsys.readouterr().out.splitlines()
        body = lines[2 : lines.index("Options:") - 1]
        assert len(body) > 1
        assert all(line.startswith("  word") and len(line) <= 40 for line in body)

    def test_choices_and_hint_override_the_rows(self, capsys):
        parser = help_format.dispatcher_parser(
            "x", "d", [("a", "s"), ("  b", "t")], "verb", choices=["a"], hint="Go."
        )
        parser.print_help()
        assert capsys.readouterr().out.endswith("\n  Go.\n")
        with pytest.raises(SystemExit):
            parser.parse_args(["b"])

    def test_the_command_and_the_rest_parse_as_before(self):
        parser = help_format.dispatcher_parser("x", "d", [("sync", "s")], "verb")
        args = parser.parse_args(["sync", "--help", "a"])
        assert (args.verb, args.rest) == ("sync", ["--help", "a"])
        assert parser.parse_args([]).verb is None

    def test_an_unknown_command_still_names_the_choices(self, capsys):
        parser = help_format.dispatcher_parser("x", "d", [("sync", "s")], "verb")
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["bogus"])
        assert excinfo.value.code == 2
        assert "invalid choice: 'bogus'" in capsys.readouterr().err


class TestClickParser:
    """PR 2 of #1230: every parser in chitragupta/ prints the click look,
    not only the three dispatchers."""

    @staticmethod
    def _help(parser, monkeypatch, capsys) -> str:
        monkeypatch.setenv("COLUMNS", "80")
        parser.print_help()
        return capsys.readouterr().out

    def test_a_leaf_collapses_its_usage(self):
        parser = help_format.ClickParser(prog="x")
        parser.add_argument("one")
        parser.add_argument("maybe", nargs="?")
        parser.add_argument("pair", nargs=2)
        parser.add_argument("--flag", action="store_true")
        parser.add_argument("phrase", nargs="*")
        assert parser.format_usage() == "Usage: x [OPTIONS] ONE [MAYBE] PAIR PAIR [PHRASE]...\n"
        plus = help_format.ClickParser(prog="g")
        plus.add_argument("file", nargs="+", metavar="FILE")
        assert plus.format_usage() == "Usage: g [OPTIONS] FILE...\n"

    def test_no_options_means_no_options_placeholder(self):
        parser = help_format.ClickParser(prog="x", add_help=False)
        parser.add_argument("one")
        assert parser.format_usage() == "Usage: x ONE\n"

    def test_positionals_are_listed_under_arguments_and_options_capitalised(
        self, monkeypatch, capsys
    ):
        parser = help_format.ClickParser(prog="x", description="Does a thing.")
        parser.add_argument("phrase", help="a topic to look up")
        parser.add_argument("--json", action="store_true", help="machine-readable output")
        out = self._help(parser, monkeypatch, capsys)
        assert out == (
            "Usage: x [OPTIONS] PHRASE\n\n"
            "  Does a thing.\n\n"
            "Arguments:\n  PHRASE      A topic to look up\n\n"
            "Options:\n"
            "  -h, --help  Show this message and exit.\n"
            "  --json      Machine-readable output\n"
        )

    def test_subcommands_render_as_a_commands_block_in_registration_order(
        self, monkeypatch, capsys
    ):
        parser = help_format.ClickParser(prog="d", description="Dossier.")
        sub = parser.add_subparsers(dest="command", required=True)
        sub.add_parser("init", help="create a dossier skeleton for a draft")
        sub.add_parser("status", help="what a dossier holds")
        out = self._help(parser, monkeypatch, capsys)
        assert out == (
            "Usage: d [OPTIONS] COMMAND [ARGS]...\n\n"
            "  Dossier.\n\n"
            "Options:\n  -h, --help  Show this message and exit.\n\n"
            "Commands:\n"
            "  init    Create a dossier skeleton for a draft\n"
            "  status  What a dossier holds\n\n"
            "  Run 'd COMMAND --help' for a command's flags.\n"
        )

    def test_a_subparser_is_a_click_parser(self):
        parser = help_format.ClickParser(prog="d")
        child = parser.add_subparsers(dest="command").add_parser("init", help="i")
        assert isinstance(child, help_format.ClickParser)
        assert child.format_usage() == "Usage: d init [OPTIONS]\n"

    def test_a_parser_with_commands_and_its_own_options_reads_both(self, monkeypatch, capsys):
        parser = help_format.ClickParser(prog="v")
        parser.add_argument("--json", action="store_true", help="json")
        sub = parser.add_subparsers(dest="mode")
        sub.add_parser("scan", help="whole-draft scan")
        out = self._help(parser, monkeypatch, capsys)
        assert out.startswith("Usage: v [OPTIONS] COMMAND [ARGS]...\n")
        assert "  --json      Json\n" in out
        assert "Commands:\n  scan  Whole-draft scan\n" in out

    def test_a_usage_error_prints_the_collapsed_usage_on_stderr_and_exits_2(self, capsys):
        parser = help_format.ClickParser(prog="x")
        parser.add_argument("one")
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args([])
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert err.startswith("Usage: x [OPTIONS] ONE\n")
        assert "required: one" in err

    def test_an_epilog_still_prints(self, monkeypatch, capsys):
        parser = help_format.ClickParser(prog="r", epilog="search ranks the corpus.")
        assert self._help(parser, monkeypatch, capsys).endswith("\n  search ranks the corpus.\n")

    def test_explicit_rows_win_over_subparsers(self, monkeypatch, capsys):
        parser = help_format.ClickParser(prog="x", command_rows=[("a", "shown")])
        parser.add_subparsers(dest="c").add_parser("b", help="hidden")
        out = self._help(parser, monkeypatch, capsys)
        assert "  a  Shown\n" in out
        assert "Hidden" not in out


_PACKAGE = Path(__file__).resolve().parent.parent / "chitragupta"


def _sources() -> list[Path]:
    files = sorted(_PACKAGE.rglob("*.py"))
    # Non-vacuous: a glob that matched nothing would pass every check below.
    assert len(files) > 100
    return files


def test_every_parser_is_a_click_parser():
    """A parser built from plain argparse prints the old look, so a new
    command would silently be the one --help that differs (#1230)."""
    plain = [
        str(path.relative_to(_PACKAGE.parent))
        for path in _sources()
        if path.name != "help_format.py"
        and "argparse.ArgumentParser(" in path.read_text(encoding="utf-8")
    ]
    assert plain == []


def test_no_parser_hardcodes_the_module_form():
    """`prog="python -m ..."` names the module form even when the reader
    typed `chitragupta`; progname.prog_for chooses the one they used."""
    hardcoded = [
        str(path.relative_to(_PACKAGE.parent))
        for path in _sources()
        if 'prog="python -m' in path.read_text(encoding="utf-8")
    ]
    assert hardcoded == []
