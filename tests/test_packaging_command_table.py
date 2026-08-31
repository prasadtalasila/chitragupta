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
    "dossier": {
        "init",
        "status",
        "mark-revision",
        "stamp",
        "sections",
        "outline",
        "brief",
        "set-language",
        "acronyms-suggest",
        "check-evidence",
        "list",
        "export",
        "restore",
    },
    "spec": {"init", "show", "sign", "status", "align", "seed"},
    "unit": {"contract", "accept", "status"},
    "registry": {"build", "check", "excerpt"},
    "tldr": {"write", "show"},
}
DRAFT_FLAT_VERBS = {"gate", "references", "evidence", "render", "style"}

REVIEW_SUBCOMMANDS = {"verbatim": {"overlap", "scan", "recheck", "locate"}}
REVIEW_FLAT_AIDS = {
    "provenance",
    "coverage",
    "synthesis",
    "figure",
    "uncited",
    "quotation",
    "agenda",
    "support",
    "union",
}

CORPUS_VERBS = {"sync", "ledger", "topics"}


# The two arithmetic breakdowns docs/PACKAGING.md states alongside its
# totals. Parsed rather than retyped: #348 found that the totals were
# pinned and the breakdowns were not, so the document could state
# per-layer numbers contradicting both its own tables and its own total
# and stay green. Deliberately anchored on the surrounding prose rather
# than on "the first parenthesis", so a reworded sentence fails loudly
# here instead of silently matching something else.
_VERB_BREAKDOWN_RE = re.compile(r"verbs and aids \(([\d\s+]+)\)")
_LEAF_BREAKDOWN_RE = re.compile(r"invocable leaf commands\*{0,2}:\s*([\d\s+()]+?)\.")


def _stated_terms(pattern: re.Pattern) -> tuple[int, ...]:
    """The integers docs/PACKAGING.md's breakdown lists, left to right.

    Parentheses inside the leaf breakdown (`(5 + 23)`) group terms for a
    reader; they carry no arithmetic this needs, so they are stripped and
    the terms compared in order against the per-layer counts below.
    """
    match = pattern.search(PACKAGING_TEXT)
    assert match, (
        f"docs/PACKAGING.md no longer states a breakdown matching {pattern.pattern!r}. "
        "If the sentence was reworded, update this pattern -- do not delete the check: "
        "the breakdown is the part a human recomputes by hand during a merge conflict."
    )
    return tuple(int(term) for term in re.findall(r"\d+", match.group(1)))


def _verb_terms() -> tuple[int, ...]:
    """Verbs and aids per layer: corpus, draft, review, enrich."""
    return (
        len(CORPUS_VERBS),
        len(DRAFT_FLAT_VERBS) + len(DRAFT_SUBCOMMANDS),
        len(REVIEW_FLAT_AIDS) + len(REVIEW_SUBCOMMANDS),
        1,  # enrich, a single command with no verbs of its own
    )


def _leaf_terms() -> tuple[int, ...]:
    """Invocable leaves in the order the prose lists them: package-level,
    corpus, draft flat, draft subcommand leaves, review flat, review
    subcommand leaves, enrich.
    """
    return (
        3,  # init, doctor, install -- each one atomic command
        len(CORPUS_VERBS),
        len(DRAFT_FLAT_VERBS),
        sum(len(v) for v in DRAFT_SUBCOMMANDS.values()),
        len(REVIEW_FLAT_AIDS),
        sum(len(v) for v in REVIEW_SUBCOMMANDS.values()),
        1,  # enrich
    )


def _help(*module_args) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "chitragupta", *module_args, "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
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
    """The formula docs/PACKAGING.md states in prose -- both the totals
    and the arithmetic behind them -- checked against the same structures
    the tests above already verified against the live parsers.

    No total is written down here. It used to be, and every command added
    then had to change three things: the sets, a literal, and the test's
    own name (`test_forty_three_leaf_commands`). Deriving instead means a
    new aid edits docs/PACKAGING.md and nothing in this file -- which is
    the point, since #348 exists because that sentence is a merge-conflict
    magnet.
    """

    def test_the_stated_verb_total_matches_the_live_structures(self):
        assert f"{sum(_verb_terms())} verbs and aids" in PACKAGING_TEXT

    def test_the_stated_leaf_total_matches_the_live_structures(self):
        assert f"{sum(_leaf_terms())} invocable leaf commands" in PACKAGING_TEXT

    def test_the_stated_verb_breakdown_matches_it_term_by_term(self):
        """`(3 + 10 + 6 + 1)`, not just the 20 it sums to.

        The breakdown is the half a human recomputes by hand while
        resolving a merge conflict -- #346 hit exactly that, with two
        branches adding a command in different layers -- and until #348
        it was the half nothing checked. A breakdown reading
        `(99 + 99 + 99 + 99)` under a correct total was green.
        """
        assert _stated_terms(_VERB_BREAKDOWN_RE) == _verb_terms()

    def test_the_stated_leaf_breakdown_matches_it_term_by_term(self):
        assert _stated_terms(_LEAF_BREAKDOWN_RE) == _leaf_terms()

    def test_each_stated_breakdown_sums_to_the_total_beside_it(self):
        """Term-by-term agreement already implies this, but a reader
        checks the sum by eye, and a future refactor of the term lists
        should not be able to drop that property silently.
        """
        assert sum(_stated_terms(_VERB_BREAKDOWN_RE)) == sum(_verb_terms())
        assert sum(_stated_terms(_LEAF_BREAKDOWN_RE)) == sum(_leaf_terms())
