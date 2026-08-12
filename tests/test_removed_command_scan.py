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


def _scanned_files():
    """Everything a command could be invoked or copied from.

    Roots are enumerated rather than swept from the repository root, for
    the reason tests/test_command_depth_scan.py gives: `.gitignore` lists
    `content/drafts/`, `content/dossiers/` and `content/review/` as
    per-host data, so a recursive glob would make the result depend on
    which drafts the developer happens to have locally.

    `bench/results/` is excluded on purpose. It holds recorded
    measurements -- `sweep.jsonl` names the command each run invoked --
    and rewriting an old result to spell a command the way the current
    release spells it would falsify the record.
    """
    patterns = ("*.py", "*.md", "*.sh", "*.toml", "*.yml", "*.yaml", "*.cfg")
    roots = ("src", "tests", "bench", "scripts", "docs", ".claude", ".github", "docker")
    found = set()
    for root in roots:
        for pattern in patterns:
            found.update((REPO_ROOT / root).glob(f"**/{pattern}"))
    for pattern in patterns:
        found.update(REPO_ROOT.glob(pattern))
    found.add(REPO_ROOT / "config.toml.example")
    results = REPO_ROOT / "bench" / "results"
    return sorted(
        path for path in found
        if path.is_file() and results not in path.parents
    )


def _offenders():
    """(relative path, matched text) for every invocation outside the
    allowlist.

    encoding="utf-8" explicitly on every read: without it read_text()
    uses the locale codec, which is cp1252 on CI's Windows leg, and
    these files are full of em dashes -- so the check would die there
    with a UnicodeDecodeError while passing on Linux. Same reason
    tests/test_command_depth_scan.py pins it.
    """
    out = []
    for path in _scanned_files():
        relative = path.relative_to(REPO_ROOT)
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

    def test_the_bench_harnesses_are_in_scope(self):
        """The two files #151 found, named rather than assumed.

        A scan whose roots quietly stopped including `bench/` would keep
        passing while checking nothing there -- the exact shape of the
        bug it exists to catch."""
        scanned = {p.relative_to(REPO_ROOT).as_posix() for p in _scanned_files()}
        assert "bench/repro_check.py" in scanned
        assert "bench/sweep_sync.py" in scanned


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
