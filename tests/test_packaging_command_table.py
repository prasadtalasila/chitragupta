import re
from pathlib import Path
from tests.conftest import run_python

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGING_TEXT = (REPO_ROOT / "docs" / "PACKAGING.md").read_text(encoding="utf-8")

CHOICES_RE = re.compile(r"\{([a-z0-9,_-]+)\}")

TOP_LEVEL = {"corpus", "draft", "review", "enrich", "init", "doctor", "install", "figure"}

PACKAGE_COMMANDS = {"init", "doctor", "install", "figure"}
FIGURE_VERBS = {"sync", "check", "new", "look"}

DRAFT_SUBCOMMANDS = {
    "retrieve": {"search", "evidence"},
    "dossier": {
        "init",
        "status",
        "mark-revision",
        "apply-renames",
        "snapshot",
        "versions",
        "stamp",
        "sections",
        "prune",
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
    "registry": {"build", "check", "excerpt", "index"},
    "tldr": {"write", "show"},
}
DRAFT_FLAT_VERBS = {"gate", "references", "evidence", "render", "style", "figures", "diff"}

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
    "digest",
}

CORPUS_VERBS = {"sync", "ledger", "topics", "discover"}


_VERB_BREAKDOWN_RE = re.compile(r"verbs and aids \(([\d\s+]+)\)")
_LEAF_BREAKDOWN_RE = re.compile(r"invocable leaf commands\*{0,2}:\s*([\d\s+()]+?)\.")


def _stated_terms(pattern: re.Pattern) -> tuple[int, ...]:
    match = pattern.search(PACKAGING_TEXT)
    assert match, (
        f"docs/PACKAGING.md no longer states a breakdown matching {pattern.pattern!r}. "
        "If the sentence was reworded, update this pattern -- do not delete the check: "
        "the breakdown is the part a human recomputes by hand during a merge conflict."
    )
    return tuple(int(term) for term in re.findall(r"\d+", match.group(1)))


def _verb_terms() -> tuple[int, ...]:
    return (
        len(CORPUS_VERBS),
        len(DRAFT_FLAT_VERBS) + len(DRAFT_SUBCOMMANDS),
        len(REVIEW_FLAT_AIDS) + len(REVIEW_SUBCOMMANDS),
        1,  # enrich, a single command with no verbs of its own
    )


def _leaf_terms() -> tuple[int, ...]:
    return (
        len(PACKAGE_COMMANDS) - 1 + len(FIGURE_VERBS),
        len(CORPUS_VERBS),
        len(DRAFT_FLAT_VERBS),
        sum(len(v) for v in DRAFT_SUBCOMMANDS.values()),
        len(REVIEW_FLAT_AIDS),
        sum(len(v) for v in REVIEW_SUBCOMMANDS.values()),
        1,  # enrich
    )


def _help(*module_args) -> str:
    result = run_python("-m", "chitragupta", *module_args, "--help", check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _choices(help_text: str) -> set:
    _, found, rest = help_text.partition("\nCommands:\n")
    if found:
        rows = rest.split("\n\n", 1)[0].splitlines()
        return {row.split()[0] for row in rows if row[2] != " "}
    match = CHOICES_RE.search(help_text)
    return set(match.group(1).split(",")) if match else set()


def _documented(*names: str) -> None:
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
    def test_the_two_working_stages_are_documented(self):
        _documented("os-deps", "gpu-torch")

    def test_the_refused_stages_are_real_choices_not_invented(self):
        import chitragupta.install as install

        assert _choices(_help("install")) == {
            "os-deps",
            "gpu-torch",
            "enrich",
            *install.REFUSED,
        }


class TestFigure:
    def test_matches_the_live_choices(self):
        assert _choices(_help("figure")) == FIGURE_VERBS

    def test_every_verb_is_documented(self):
        _documented(*(f"chitragupta figure {verb}" for verb in FIGURE_VERBS))


class TestStatedCounts:
    def test_the_stated_verb_total_matches_the_live_structures(self):
        assert f"{sum(_verb_terms())} verbs and aids" in PACKAGING_TEXT

    def test_the_stated_leaf_total_matches_the_live_structures(self):
        assert f"{sum(_leaf_terms())} invocable leaf commands" in PACKAGING_TEXT

    def test_the_stated_verb_breakdown_matches_it_term_by_term(self):
        assert _stated_terms(_VERB_BREAKDOWN_RE) == _verb_terms()

    def test_the_stated_leaf_breakdown_matches_it_term_by_term(self):
        assert _stated_terms(_LEAF_BREAKDOWN_RE) == _leaf_terms()

    def test_each_stated_breakdown_sums_to_the_total_beside_it(self):
        assert sum(_stated_terms(_VERB_BREAKDOWN_RE)) == sum(_verb_terms())
        assert sum(_stated_terms(_LEAF_BREAKDOWN_RE)) == sum(_leaf_terms())
