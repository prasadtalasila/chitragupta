"""The `chitragupta-cli[...]` extras are quoted wherever a reader can copy
one, because zsh globs the brackets (see the class docstring).

This scan shared a file with the check that pyproject.toml's extras
matched their Poetry groups; that check went with the groups when the
project moved to uv, where each extra is declared once.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestTheExtraIsQuotedWhereverItIsPrinted:
    """`pip install chitragupta-cli[enrich]` is a broken command in zsh.

    Square brackets are a glob in zsh, so an unquoted extra matches no
    file and the shell refuses the line before pip ever runs::

        zsh: no matches found: chitragupta-cli[enrich]

    zsh is macOS's default shell, so this is not an edge case -- it is
    the first command a Mac user copies out of the README. Reported
    against 6.55.0 from a real shell, and confirmed against PyPI: the
    published metadata declares all three extras correctly, so nothing
    is wrong with the *package*. What was wrong is that this repository
    printed a command that cannot run.

    `pip install 'chitragupta-cli[enrich]'` is correct in bash, zsh and
    PowerShell alike, so there is one spelling rather than a per-shell
    note, and the fix is to use it everywhere the string appears --
    docs, comments, and the strings `chitragupta install` and
    `chitragupta doctor` print at a user.

    A scan rather than a per-site assertion, because the failure is
    re-introduction: this string is copied into new prose whenever a new
    surface names the extra, and a test naming today's sites cannot see
    tomorrow's.
    """

    # Where a reader can copy a command from. `.claude/` and `plans/` are
    # excluded for the same reason `uv.lock` is: nothing there is
    # addressed to a human at a shell prompt.
    SCANNED = ("*.md", "docs/*.md", "chitragupta/**/*.py", "scripts/*.sh", "*.toml")

    # Deliberately not `pip install ...`: the brackets are what zsh
    # globs, so the bug is present in any sentence naming the extra,
    # including one that wraps between `pip install` and the package.
    UNQUOTED = re.compile(r"(?<!')chitragupta-cli\[[a-z|.]+\](?!')")

    def test_no_unquoted_extra_anywhere_a_reader_can_copy_one(self):
        offenders = []
        for pattern in self.SCANNED:
            for path in sorted(REPO_ROOT.glob(pattern)):
                text = path.read_text(encoding="utf-8")
                for number, line in enumerate(text.splitlines(), start=1):
                    if self.UNQUOTED.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
        assert offenders == [], "quote the extra -- zsh globs the brackets:\n" + "\n".join(
            offenders
        )

    def test_the_scan_would_catch_a_regression(self, tmp_path):
        """The scan is a negative assertion over a tree that currently
        passes, so on its own it cannot tell "nothing is wrong" from
        "the pattern matches nothing". This fabricates the offender."""
        assert self.UNQUOTED.search("run pip install chitragupta-cli[enrich] to get it")
        assert not self.UNQUOTED.search("run pip install 'chitragupta-cli[enrich]' to get it")
