"""Nothing in this tree may invoke `python -m src.sync`.

That command was the corpus layer's entry point until 5.2.0. It is gone:
`python -m src.corpus sync` replaced it, and `src/sync.py`'s `__main__`
block now refuses the old spelling out loud.

This file exists because of *how* the two survivors survived. #150
repointed 181 command strings by hand and missed `bench/repro_check.py`
and `bench/sweep_sync.py`, where the command is not written as prose at
all but assembled as list elements:

    subprocess.run([python, "-m", "src.sync"], ...)

A search for the prose spelling does not match that, so both harnesses
kept "succeeding" -- against a no-op, on a run that parsed nothing --
for a whole release. Silent success in a measurement tool produces wrong
data rather than no data, which is why #151 asked for the class to be
closed rather than the two instances fixed.

So the pattern here matches the *invocation*, in either shape, rather
than the module path. `src.sync` on its own is legitimate and common:
it is the logger name pinned in `src/sync.py`, `docs/CONFIG.md` and
`docs/CLI.md`, and `src/sync.py` is a file path named throughout the
docs and the suite. Only `-m` in front of it makes it a command. Same
reasoning as tests/test_command_depth_scan.py, which draws the line in
the same place for nested commands.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# `-m src.sync` and `"-m", "src.sync"` are one pattern, not two: between
# the flag and the module there may be a closing quote, whitespace, a
# list comma and an opening quote, in that order and any of them absent.
# Written this way rather than as two alternatives so a third spelling
# (`'-m','src.sync'`, no space) cannot slip between them.
_INVOCATION = re.compile(r"""-m["']?      # the flag, and the quote closing it in a list
                             [\s,]*       # whitespace and/or the comma between elements
                             ["']?        # the quote opening the module string
                             src\.sync\b""", re.VERBOSE)

# The sites that own the removal, and must name the old spelling to do
# their job. An allowlist by path rather than by surrounding prose (the
# trick tests/test_command_depth_scan.py uses) because two of these are
# executable code, where there is no sentence to read: they *run* the
# command, and assert that it refuses.
_ALLOWED = {
    # The refusal itself.
    Path("src/sync.py"),
    # Pins that the refusal happens, by running it.
    Path("tests/test_corpus_entrypoint.py"),
    # This file.
    Path("tests/test_removed_command_scan.py"),
}


# Claude Code checks a whole second copy of this repository out at
# `.claude/worktrees/<name>/`, inside a root this scan walks. Every file
# in it is a *different commit's* version of a file already scanned at
# its real path, so without this exclusion the scan reports
# `.claude/worktrees/<name>/src/sync.py` -- the refusal machinery itself,
# at a path `_ALLOWED` cannot name -- as new, unrefused code. The report
# reads like stale code surviving a migration and is nothing of the kind.
# Not hypothetical, and it accumulates rather than clearing: the host
# docs/TECHNICAL-DEBT.md §4.3 was written on carried seven, all on
# branches long since merged, and the same host carried 26 by the time
# #236 fixed it. CI never sees any of it -- `actions/checkout` creates no
# worktree -- so the red is local-only, which is exactly the kind of
# failure a developer learns to scroll past.
_EXCLUDED_DIRS = (
    Path(".claude") / "worktrees",
    # Recorded measurements -- `sweep.jsonl` names the command each run
    # invoked -- and rewriting an old result to spell a command the way
    # the current release spells it would falsify the record.
    Path("bench") / "results",
)


def _scanned_files(root=REPO_ROOT):
    """Everything a command could be invoked or copied from.

    Roots are enumerated rather than swept from the repository root, for
    the reason tests/test_command_depth_scan.py gives: `.gitignore` lists
    `content/drafts/`, `content/dossiers/` and `content/review/` as
    per-host data, so a recursive glob would make the result depend on
    which drafts the developer happens to have locally.

    `root` is a parameter so the exclusion above can be *proved* against a
    fixture tree rather than asserted. The alternative -- writing a
    worktree-shaped fixture into the live `.claude/worktrees/` -- would
    have the test create a directory beside 26 real checkouts and rely on
    cleaning it up again.
    """
    patterns = ("*.py", "*.md", "*.sh", "*.toml", "*.yml", "*.yaml", "*.cfg")
    roots = ("src", "tests", "bench", "scripts", "docs", ".claude", ".github", "docker")
    found = set()
    for sub in roots:
        for pattern in patterns:
            found.update((root / sub).glob(f"**/{pattern}"))
    for pattern in patterns:
        found.update(root.glob(pattern))
    # Two files anyone runs commands out of that no suffix glob reaches:
    # `config.toml.example` is what you copy to `config.toml` and is read
    # as documentation, and `docker/Dockerfile` has no extension at all.
    # #151 names Docker among the places #150 rewrote command strings, so
    # leaving it out would exempt one of the sites this exists for.
    found.add(root / "config.toml.example")
    found.add(root / "docker" / "Dockerfile")
    excluded = [root / d for d in _EXCLUDED_DIRS]
    return sorted(
        path for path in found
        if path.is_file() and not any(d in path.parents for d in excluded)
    )


def _offenders(root=REPO_ROOT):
    """(relative path, matched text) for every invocation outside the
    allowlist.

    encoding="utf-8" explicitly on every read: without it read_text()
    uses the locale codec, which is cp1252 on CI's Windows leg, and
    these files are full of em dashes -- so the check would die there
    with a UnicodeDecodeError while passing on Linux. Same reason
    tests/test_command_depth_scan.py pins it.
    """
    out = []
    for path in _scanned_files(root):
        relative = path.relative_to(root)
        if relative in _ALLOWED:
            continue
        text = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
        for match in _INVOCATION.finditer(text):
            out.append((relative.as_posix(), match.group(0)))
    return out


class TestNothingInvokesTheRemovedCommand:
    def test_the_tree_is_clean(self):
        offenders = _offenders()
        assert not offenders, (
            "`python -m src.sync` was removed in 5.2.0 and now refuses. Use "
            "`python -m src.corpus sync`:\n"
            + "\n".join(f"  {path}: {text!r}" for path, text in offenders)
        )

    @pytest.mark.parametrize("path", [
        # The two files #151 found.
        "bench/repro_check.py",
        "bench/sweep_sync.py",
        # Extensionless, so no suffix glob reaches it, and named by #151
        # among the places #150 rewrote command strings.
        "docker/Dockerfile",
        # The file a user copies to config.toml, and reads as docs.
        "config.toml.example",
        # The install path, whose header comment lists commands.
        "scripts/install_full_pipeline.sh",
    ])
    def test_the_files_that_matter_are_in_scope(self, path):
        """Named rather than assumed. A scan whose roots quietly stopped
        covering one of these would keep passing while checking nothing
        there -- the exact shape of the bug it exists to catch."""
        scanned = {p.relative_to(REPO_ROOT).as_posix() for p in _scanned_files()}
        assert path in scanned


class TestANestedWorktreeIsNotScanned:
    """Proved against a fixture tree, not asserted.

    The exclusion is one line and looks obviously correct, which is
    precisely why it needs a test: nothing on CI can fail if it regresses
    (`actions/checkout` creates no worktree), so the only signal would be
    a developer's local red, months later, reading like stale code.

    The fixture puts the *same* offending file at both a real path and a
    nested-worktree path, so one run distinguishes "the exclusion works"
    from "the scan found nothing in this tree at all".
    """

    @staticmethod
    def _tree(root):
        for name in ("src", "tests", "bench", "scripts", "docs", ".github", "docker"):
            (root / name).mkdir(parents=True)
        (root / "docker" / "Dockerfile").write_text("FROM python\n", encoding="utf-8")
        (root / "config.toml.example").write_text("# example\n", encoding="utf-8")
        # A real offender, at a path the allowlist does not cover.
        (root / "docs" / "OLD.md").write_text(
            "run python -m src.sync nightly\n", encoding="utf-8"
        )
        # The same offence inside a worktree-shaped checkout, plus a copy
        # of the refusal machinery at a path `_ALLOWED`'s `src/sync.py`
        # cannot match -- the shape §4.3 actually reported.
        # A skill file at a real `.claude/` path, which must stay in
        # scope: dropping `.claude` from `roots` altogether would also
        # make the worktree assertions below pass, and would silently
        # stop scanning the drafting layer.
        (root / ".claude" / "skills").mkdir(parents=True)
        (root / ".claude" / "skills" / "SKILL.md").write_text(
            "use python -m src.corpus sync\n", encoding="utf-8"
        )
        nested = root / ".claude" / "worktrees" / "issue-999"
        (nested / "docs").mkdir(parents=True)
        (nested / "src").mkdir(parents=True)
        (nested / "docs" / "OLD.md").write_text(
            "run python -m src.sync nightly\n", encoding="utf-8"
        )
        (nested / "src" / "sync.py").write_text(
            'subprocess.run([python, "-m", "src.sync"])\n', encoding="utf-8"
        )

    def test_the_nested_checkout_is_not_reported(self, tmp_path):
        self._tree(tmp_path)
        reported = {path for path, _ in _offenders(tmp_path)}
        assert reported == {"docs/OLD.md"}

    def test_the_nested_checkouts_files_are_not_even_walked(self, tmp_path):
        """The exclusion drops the files, rather than the offenders it
        finds in them -- so a future check added to `_offenders` inherits
        it instead of having to repeat it."""
        self._tree(tmp_path)
        scanned = {p.relative_to(tmp_path).as_posix() for p in _scanned_files(tmp_path)}
        assert "docs/OLD.md" in scanned
        assert not any(name.startswith(".claude/worktrees/") for name in scanned)

    def test_the_rest_of_claude_is_still_walked(self, tmp_path):
        """The exclusion is `.claude/worktrees/`, not `.claude/`.

        Without this, the cheapest way to make the two assertions above
        pass would be to stop scanning the drafting layer entirely --
        which is the failure this whole file exists to prevent, one
        directory over.
        """
        self._tree(tmp_path)
        scanned = {p.relative_to(tmp_path).as_posix() for p in _scanned_files(tmp_path)}
        assert ".claude/skills/SKILL.md" in scanned


class TestThePatternCatchesBothSpellings:
    """The prose form was already searchable in #150; the list form is
    what got through. Both are pinned, so neither can be lost to a later
    tightening of the regex."""

    def test_it_catches_the_prose_form(self):
        assert _INVOCATION.search("run python -m src.sync nightly")

    def test_it_catches_the_list_form(self):
        assert _INVOCATION.search('subprocess.run([python, "-m", "src.sync"])')

    def test_it_catches_the_unspaced_list_form(self):
        assert _INVOCATION.search("[python,'-m','src.sync']")

    def test_it_ignores_the_logger_name(self):
        """`src.sync` is the pinned logger name in every logs/pipeline.log
        line, and docs/CLI.md tells a scheduler to grep for it."""
        assert not _INVOCATION.search("sync logs as src.sync whatever the")

    def test_it_ignores_the_file_path(self):
        assert not _INVOCATION.search("src/sync.py's parse loop is serial")

    def test_it_ignores_the_replacement(self):
        assert not _INVOCATION.search("python -m src.corpus sync --reparse")
