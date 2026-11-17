"""`chitragupta/help_format.py` and `chitragupta/command_help.py`: the
click-style `--help` the dispatchers print (#1230).

What is pinned here is the truncation rule and the layout, because the
spec fixed both: a command list shows one cut line per command, and the
full text lives one level down in that command's own `--help`.
"""

import ast

from chitragupta.help_format import commands_block, truncate
from tests.conftest import run_python


class TestTruncate:
    def test_a_clause_that_fits_is_kept_and_the_rest_dropped(self):
        text = "read-only view of what that run recorded -- takes no lock"
        assert truncate(text, 66) == "Read-only view of what that run recorded"

    def test_a_first_sentence_is_kept(self):
        assert truncate("Create a skeleton. Then more text.", 60) == "Create a skeleton"

    def test_text_that_fits_whole_is_capitalised_and_loses_its_full_stop(self):
        assert truncate("what changed.", 60) == "What changed"

    def test_overlong_text_is_cut_at_a_word_and_marked(self):
        text = "the working state behind a draft: create it, inspect it, back it up, restore it"
        out = truncate(text, 64)
        assert out == "The working state behind a draft: create it, inspect it..."
        assert len(out) <= 64

    def test_one_word_longer_than_the_limit_is_cut_hard(self):
        assert truncate("x" * 100, 45) == "X" + "x" * 41 + "..."


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
