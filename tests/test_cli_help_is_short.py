"""`--help` answers "how do I run this", and nothing else (#152).

Every layer entry point in this project carries a long module docstring:
why the verbs import lazily, which of them takes the write lock, what
invariant the file exists to serve. That prose is worth keeping -- it is
this repository's house style, and it is aimed at whoever opens the file.
It is not worth *printing*. Passing `description=__doc__` to argparse put
forty lines of design commentary between the usage line and the flags, so
the two lines that answer the reader's question were the two hardest to
find.

So the docstring stays and `--help` gets one sentence. This file pins
that split at both ends: the constant each entry point declares, and what
a real `--help` run actually prints.

Deliberately not asserting the wording. A description that has to match a
string here is a description nobody will improve; what matters is that it
is short, and that it is not the docstring.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from chitragupta import corpus, draft
from chitragupta.enrich import __main__ as enrich_main
from chitragupta.review import __main__ as review_main

REPO_ROOT = Path(__file__).resolve().parent.parent

# Every entry point, and the module whose docstring it must not print.
ENTRY_POINTS = {
    "chitragupta.corpus": corpus,
    "chitragupta.draft": draft,
    "chitragupta.review": review_main,
    "chitragupta.enrich": enrich_main,
}

# One sentence, hand-measured against the four that exist: the longest is
# well under this, and anything over it has stopped being a summary. Not
# a line count -- these are wrapped by argparse at the terminal's width,
# not by the author.
_MAX_DESCRIPTION_CHARS = 200

# What a whole `--help` is allowed to run to. The four entry points land
# between 12 and 20 lines; 30 leaves room for a verb or a flag to be added
# without re-tuning, and still fails loudly on a docstring coming back.
_MAX_HELP_LINES = 30


def _help(module_path):
    result = subprocess.run(
        [sys.executable, "-m", module_path, "--help"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("module_path", sorted(ENTRY_POINTS))
class TestTheDescriptionIsASummary:
    def test_it_is_not_the_module_docstring(self, module_path):
        module = ENTRY_POINTS[module_path]
        assert module.DESCRIPTION != module.__doc__

    def test_it_is_one_short_sentence(self, module_path):
        description = ENTRY_POINTS[module_path].DESCRIPTION
        assert len(description) <= _MAX_DESCRIPTION_CHARS
        # No blank line: a second paragraph is the shape the docstring
        # has, and the shape this is not allowed to grow into.
        assert "\n\n" not in description


@pytest.mark.parametrize("module_path", sorted(ENTRY_POINTS))
class TestHelpStaysShort:
    def test_the_whole_help_fits_a_screen(self, module_path):
        """The observable half. The check above can be satisfied by a
        short `description` while `epilog` grows instead, which is the
        same failure by another route."""
        assert len(_help(module_path).splitlines()) <= _MAX_HELP_LINES

    def test_it_does_not_reprint_the_docstrings_prose(self, module_path):
        """Every one of these docstrings cites docs/ARCHITECTURE.md while
        explaining the one-entry-point invariant. None of that belongs in
        `--help`, and its absence is a cheap, wording-independent way to
        notice the docstring coming back."""
        module = ENTRY_POINTS[module_path]
        assert "ARCHITECTURE.md" in module.__doc__
        assert "ARCHITECTURE.md" not in _help(module_path)
