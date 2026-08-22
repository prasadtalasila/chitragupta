"""docs/PACKAGING.md's command-surface table, walked against the live
argparse trees rather than trusted by eye (#267).

Modelled on tests/test_cli_help_is_short.py: a hand-maintained structure
here, cross-checked against the real `--help` output via subprocess (not
a private argparse attribute, so what's checked is exactly what a reader
typing the command sees) *and* against docs/PACKAGING.md's own text. A
verb or subcommand added to the code without updating both sides fails
one of the two checks; a doc row naming one that doesn't exist fails the
live-parser check.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGING_TEXT = (REPO_ROOT / "docs" / "PACKAGING.md").read_text(encoding="utf-8")

CHOICES_RE = re.compile(r"\{([a-z0-9,_-]+)\}")

# The top-level layers and package-level commands docs/PACKAGING.md's
# tables document -- checked against `python -m chitragupta --help`'s own
# `{...}` choices list below, not restated as a magic number.
TOP_LEVEL = {"corpus", "draft", "review", "enrich", "init", "doctor", "install"}

# Every drafting-layer verb that has its own subcommands, and what
# docs/PACKAGING.md's "draft" table row lists for it.
DRAFT_SUBCOMMANDS = {
    "retrieve": {"search", "evidence"},
    "dossier": {"init", "status", "mark-revision", "sections", "brief",
                "set-language", "acronyms-suggest", "check-evidence", "list",
                "export", "restore"},
    "spec": {"init", "show", "sign", "status"},
    "unit": {"contract", "accept", "status"},
    "registry": {"build", "check", "excerpt"},
}
DRAFT_FLAT_VERBS = {"gate", "references", "evidence", "render", "style"}

REVIEW_SUBCOMMANDS = {"verbatim": {"overlap", "scan", "recheck", "locate"}}
REVIEW_FLAT_AIDS = {"provenance", "coverage", "synthesis", "figure", "uncited"}

CORPUS_VERBS = {"sync", "ledger", "topics"}


def _help(*module_args) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "chitragupta", *module_args, "--help"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _choices(help_text: str) -> set:
    """The `{a,b,c}` set argparse prints in its own usage line for a
    subparsers action or a choices-constrained positional."""
    match = CHOICES_RE.search(help_text)
    return set(match.group(1).split(",")) if match else set()


def _documented(*names: str) -> None:
    """Every name appears somewhere in the doc's text -- some as their
    own backtick-quoted word (`gate`, `search`), some embedded in a
    larger command string (`chitragupta review coverage <draft>`), so a
    bare substring check is what both shapes have in common. The cheap
    half of the cross-check: code and doc agree on content, this half
    only confirms neither side invented an undocumented one silently by
    omission."""
    for name in names:
        assert name in PACKAGING_TEXT, f"{name!r} is not documented in PACKAGING.md"


class TestTopLevel:
    def test_matches_the_live_choices(self):
        assert _choices(_help()) == TOP_LEVEL

    def test_every_top_level_command_is_documented(self):
        _documented(*TOP_LEVEL)


class TestCorpus:
    def test_matches_the_live_choices(self):
        assert _choices(_help("corpus")) == CORPUS_VERBS

    def test_every_verb_is_documented(self):
        _documented(*CORPUS_VERBS)


class TestDraft:
    def test_top_level_verbs_match_the_live_choices(self):
        expected = DRAFT_FLAT_VERBS | set(DRAFT_SUBCOMMANDS)
        assert _choices(_help("draft")) == expected

    def test_every_top_level_verb_is_documented(self):
        _documented(*DRAFT_FLAT_VERBS, *DRAFT_SUBCOMMANDS)

    def test_every_subcommand_matches_the_live_choices_and_is_documented(self):
        for verb, subcommands in DRAFT_SUBCOMMANDS.items():
            assert _choices(_help("draft", verb)) == subcommands, verb
            _documented(*subcommands)


class TestReview:
    def test_top_level_aids_match_the_live_choices(self):
        expected = REVIEW_FLAT_AIDS | set(REVIEW_SUBCOMMANDS)
        assert _choices(_help("review")) == expected

    def test_every_aid_is_documented(self):
        _documented(*REVIEW_FLAT_AIDS, *REVIEW_SUBCOMMANDS)

    def test_verbatim_subcommands_match_the_live_choices_and_are_documented(self):
        for aid, subcommands in REVIEW_SUBCOMMANDS.items():
            assert _choices(_help("review", aid)) == subcommands, aid
            _documented(*subcommands)


class TestInstall:
    """`install`'s own doc row lists only the two stages that actually
    run (`os-deps`, `gpu-torch`); `python-deps`/`dev-deps`/`all` are
    valid argparse choices that immediately refuse (chitragupta/install.py's
    REFUSED), so the live choices are a superset of what's documented
    rather than an exact match -- checked against install.REFUSED
    directly, not restated as a second literal set here."""

    def test_the_two_working_stages_are_documented(self):
        _documented("os-deps", "gpu-torch")

    def test_the_refused_stages_are_real_choices_not_invented(self):
        import chitragupta.install as install
        assert _choices(_help("install")) == {"os-deps", "gpu-torch", *install.REFUSED}


class TestStatedCounts:
    """The formula docs/PACKAGING.md states in prose: 4 layers, 20 verbs
    and aids, 44 invocable leaf commands -- computed here from the same
    structures the tests above already verified against the live code,
    not retyped as a fresh set of literals."""

    def test_twenty_verbs_and_aids(self):
        verbs_and_aids = (len(CORPUS_VERBS) + len(DRAFT_FLAT_VERBS) + len(DRAFT_SUBCOMMANDS)
                           + len(REVIEW_FLAT_AIDS) + len(REVIEW_SUBCOMMANDS) + 1)  # enrich
        assert verbs_and_aids == 20
        assert "20 verbs and aids" in PACKAGING_TEXT

    def test_forty_four_leaf_commands(self):
        draft_leaves = len(DRAFT_FLAT_VERBS) + sum(len(v) for v in DRAFT_SUBCOMMANDS.values())
        review_leaves = len(REVIEW_FLAT_AIDS) + sum(len(v) for v in REVIEW_SUBCOMMANDS.values())
        package_level = 3  # init, doctor, install -- each one atomic command
        total = package_level + len(CORPUS_VERBS) + draft_leaves + review_leaves + 1  # enrich
        assert total == 44
        assert "44 invocable leaf commands" in PACKAGING_TEXT
