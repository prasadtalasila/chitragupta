import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from chitragupta import config, style_check, style_rules, style_vendored
from chitragupta.style_language import rule_filter

REPO_ROOT = Path(__file__).resolve().parent.parent
VALE = REPO_ROOT / "assets" / "vale"
STYLES = VALE / "styles"
INI = VALE / "vale.ini"
MANIFEST = VALE / "VENDORED.sha256"

HOUSE = "chitragupta"


def enabled_in_ini() -> set[str]:
    text = INI.read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Za-z-]+\.[A-Za-z-]+) = suggestion$", text, re.M))


def vendored_files() -> set[str]:
    return {
        f"{rule.parent.name}.{rule.stem}"
        for rule in STYLES.glob("*/*.yml")
        if rule.parent.name != HOUSE
    }


class TestTheTablesAgree:
    def test_every_vendored_file_is_switched_on_and_nothing_else_is(self):
        assert vendored_files(), "the glob found no vendored rule files"
        assert enabled_in_ini() == vendored_files()

    def test_every_vendored_rule_names_a_section(self):
        assert set(style_vendored.SECTIONS) == vendored_files()

    def test_each_section_is_one_the_standard_has(self):
        standard = (REPO_ROOT / "docs" / "WRITING-STANDARDS.md").read_text(encoding="utf-8")
        for rule, section in style_vendored.SECTIONS.items():
            assert re.search(rf"^## \S+ {section}\. ", standard, re.M), (rule, section)

    def test_every_vendored_package_carries_its_licence(self):
        for package in {name.split(".")[0] for name in vendored_files()}:
            assert (STYLES / package / "LICENSE").is_file(), package

    def test_every_vendored_file_is_byte_identical_to_its_pinned_release(self):
        pinned = {}
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                digest, path = line.split(maxsplit=1)
                pinned[path] = digest
        on_disk = {
            path.relative_to(VALE).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in STYLES.glob("*/*")
            if path.parent.name != HOUSE
        }
        assert on_disk == pinned

    def test_every_shadowing_pair_names_rules_that_run(self):
        house = {f"{HOUSE}.{rule.stem}" for rule in (STYLES / HOUSE).glob("*.yml")}
        known = vendored_files() | house
        for loser, winners in style_vendored.SHADOWED_BY.items():
            assert loser in known
            assert set(winners) <= known, loser


class TestRepair:
    @staticmethod
    def _repair(rule: str) -> str:
        found = {"rule": rule, "match": "x", "line": 1, "count": 1}
        return style_rules.with_repair([found], "scope.md")[0]["repair"]

    def test_a_vendored_rule_is_left_for_a_person(self):
        assert self._repair("proselint.Cliches") == "review"
        assert self._repair("Journals.Prove") == "review"

    @pytest.mark.parametrize(
        "rule",
        [
            "ai-tells.SycophancyMarkers",  # "absolutely continuous"
            "ai-tells.ClosingPleasantries",  # "If anything is unclear, see step 2"
            "proselint.Nonwords",  # "the pettifogger"
        ],
    )
    def test_even_the_narrowest_lists_are_left_for_a_person(self, rule):
        assert self._repair(rule) == "review"

    @pytest.mark.parametrize(
        "rule",
        [
            "BorrowedAuthority",
            "DeepSaying",
            "Inflated",
            "KnowledgeLimit",
            "PlainVerbs",
            "RunUp",
            "Strawman",
        ],
    )
    def test_the_machine_prose_rules_are_left_for_a_person(self, rule):
        assert self._repair(f"{HOUSE}.{rule}") == "review"

    def test_the_house_defect_markers_are_unchanged(self):
        assert self._repair(f"{HOUSE}.DefectMarkers") == "edit"


def alert(check: str, line: int, start: int, end: int, match: str = "x") -> dict:
    return {
        "Check": check,
        "Line": line,
        "Span": [start, end],
        "Match": match,
        "Message": f"{check} says so.",
        "Severity": "suggestion",
    }


class TestReconcile:
    def test_a_shadowed_finding_on_the_same_words_is_dropped(self):
        found = [
            alert("ai-tells.ConclusionMarkers", 3, 1, 21),
            alert("proselint.Cliches", 3, 1, 21),
        ]
        kept = style_vendored.reconcile(found)
        assert [f["Check"] for f in kept] == ["ai-tells.ConclusionMarkers"]

    def test_a_partial_overlap_counts(self):
        found = [
            alert("Microsoft.Wordiness", 3, 1, 21),
            alert("proselint.Cliches", 3, 4, 21),
        ]
        assert [f["Check"] for f in style_vendored.reconcile(found)] == ["Microsoft.Wordiness"]

    def test_the_same_columns_on_another_line_do_not(self):
        found = [
            alert("ai-tells.ConclusionMarkers", 3, 1, 21),
            alert("proselint.Cliches", 4, 1, 21),
        ]
        assert len(style_vendored.reconcile(found)) == 2

    def test_words_side_by_side_do_not(self):
        found = [
            alert("ai-tells.ConclusionMarkers", 3, 1, 10),
            alert("proselint.Cliches", 3, 11, 20),
        ]
        assert len(style_vendored.reconcile(found)) == 2

    def test_two_different_checks_on_the_same_words_both_stay(self):
        found = [alert("chitragupta.Acronyms", 2, 1, 3), alert("proselint.RASSyndrome", 2, 1, 11)]
        assert len(style_vendored.reconcile(found)) == 2

    def test_a_house_marker_shadows_the_vendored_copy_of_it(self):
        found = [
            alert("ai-tells.SycophancyMarkers", 1, 1, 9),
            alert("chitragupta.DefectMarkers", 1, 1, 9),
        ]
        assert [f["Check"] for f in style_vendored.reconcile(found)] == [
            "chitragupta.DefectMarkers"
        ]

    def test_a_vendored_message_names_its_section(self):
        (kept,) = style_vendored.reconcile([alert("Journals.Prove", 1, 1, 5)])
        assert kept["Message"] == "Journals.Prove says so. (WRITING-STANDARDS.md §7)"

    def test_a_house_message_is_left_as_written(self):
        (kept,) = style_vendored.reconcile([alert("chitragupta.Just", 1, 1, 4)])
        assert kept["Message"] == "chitragupta.Just says so."


def tokens_of(rule: Path) -> list[str]:
    data = yaml.safe_load(rule.read_text(encoding="utf-8"))
    phrases = [str(t) for t in (data.get("tokens") or [])]
    phrases += [str(t) for t in (data.get("swap") or {})]
    literal = [p for p in phrases if re.fullmatch(r"[A-Za-z][A-Za-z' -]*[A-Za-z.]", p)]
    examples = [
        line
        for case in data.get("tests") or []
        for line in str(case.get("input", "")).splitlines()
        if line.strip()
    ]
    return [f"The {p} here." for p in literal] + examples


SAMPLES = (
    "It's not just a cache; it's a coordination layer.",
    "It's not about speed; it's about trust.",
    "It's not about speed. It's about trust.",
    "This isn't about speed; it's about trust.",
    "This isn't a cache. It's a coordination layer.",
    "It's more than a cache; it's a coordination layer.",
    "It's less about speed and more about trust.",
    "Speed isn't the point; trust is.",
    "The real problem isn't speed; it's trust.",
    "What matters isn't speed; it's trust.",
    "The question isn't speed; it's trust.",
    "It's not whether it works; it's how it fails.",
    "Caching isn't a feature. It's a layer.",
    "A refinement, not a rivalry.",
    "Not only fast but also cheap.",
    "Not because it is fast, but because it is cheap.",
    "These aren't features. They're layers.",
    "These aren't features; they're layers.",
    "Plugins aren't features. They're layers.",
    "It doesn't mean speed. It means trust.",
    "Caching doesn't mean speed. It means trust.",
    "The colophon isn't a disclaimer. It's a feature.",
    "A cache isn't a feature. It's a layer.",
    "Our cache isn't a feature. It's a layer.",
    "WCAG 2.1 AA isn't a checkbox. It's a constraint.",
    "It runs with no database and no network.",
    "It runs without a database or a round-trip.",
    "It needs neither the database nor a round-trip.",
    "It doesn't need credentials and doesn't call the network.",
    "Neither the database nor the network is required.",
    "What you get is one row per blob.",
    "What changed is the direction.",
    "All you need is the offset.",
    "The only thing that changes is the direction.",
    "Where this pays off is the read path.",
    "This result is very unique.",
    "It works!!",
    "Check the file(s) first.",
    "Do NOT CHANGE this file.",
)


DIFFERENT_CHECKS = {
    ("chitragupta.Acronyms", "proselint.RASSyndrome"),  # unexpanded / redundant
    ("chitragupta.Acronyms", "Microsoft.Uppercase"),  # unexpanded / shouting
    ("chitragupta.DefectMarkers", "proselint.Cliches"),  # "easy" inside "easy as pie"
    ("chitragupta.Just", "proselint.Cliches"),  # "just" inside "just the ticket"
    ("Journals.PValueCase", "PLOS.PValues"),  # case / precision
    ("Journals.PValueCase", "Journals.PValueZero"),  # case / zero
    ("ai-tells.ContrastiveFormulas", "chitragupta.Just"),  # "just" inside "not just X; it's Y"
    ("ai-tells.ContrastiveFormulas", "chitragupta.Acronyms"),
    ("ai-tells.ContrastiveFormulas", "chitragupta.DefectMarkers"),
    ("ai-tells.ContrastiveFormulas", "Journals.Hype"),
    ("ai-tells.ContrastiveFormulas", "Journals.Significant"),
    ("ai-tells.ContrastiveFormulas", "proselint.Very"),
    ("ai-tells.NegatedPair", "Journals.Prove"),
}


@pytest.mark.skipif(shutil.which("vale") is None, reason="vale not installed")
class TestAgainstRealVale:
    @staticmethod
    def _raw(path: Path) -> list[dict]:
        result = subprocess.run(
            [
                "vale",
                f"--config={config.VALE_CONFIG_PATH}",
                "--output=JSON",
                "--no-exit",
                f"--filter={rule_filter(None)}",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return [a for alerts in json.loads(result.stdout or "{}").values() for a in alerts]

    @staticmethod
    def _overlapping_pairs(alerts: list[dict]) -> set[tuple[str, str]]:
        pairs = set()
        for a in alerts:
            for b in alerts:
                if (
                    a["Check"] < b["Check"]
                    and a["Line"] == b["Line"]
                    and a["Span"][0] <= b["Span"][1]
                    and b["Span"][0] <= a["Span"][1]
                ):
                    pairs.add((a["Check"], b["Check"]))
        return pairs

    @pytest.fixture(scope="class")
    @classmethod
    def probe(cls, tmp_path_factory) -> Path:
        lines = [phrase for rule in sorted(STYLES.glob("*/*.yml")) for phrase in tokens_of(rule)]
        lines += SAMPLES
        path = tmp_path_factory.mktemp("probe") / "probe.md"
        path.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_every_vendored_rule_runs_at_suggestion(self, probe):
        alerts = [a for a in self._raw(probe) if a["Check"] in style_vendored.SECTIONS]
        assert {a["Check"] for a in alerts} == set(style_vendored.SECTIONS)
        assert {a["Severity"] for a in alerts} == {"suggestion"}

    def test_no_two_rules_report_the_same_words_unless_decided(self, probe):
        undecided = {
            pair
            for pair in self._overlapping_pairs(self._raw(probe))
            if pair not in {tuple(sorted(p)) for p in DIFFERENT_CHECKS}
            and not (
                pair[0] in style_vendored.SHADOWED_BY.get(pair[1], ())
                or pair[1] in style_vendored.SHADOWED_BY.get(pair[0], ())
            )
        }
        assert not undecided

    def test_draft_style_reports_each_shadowed_pair_once(self, probe):
        left = self._overlapping_pairs(style_vendored.reconcile(self._raw(probe)))
        shadowed = {
            tuple(sorted((loser, winner)))
            for loser, winners in style_vendored.SHADOWED_BY.items()
            for winner in winners
        }
        assert not left & shadowed

    def test_a_finding_inside_a_quote_or_a_citation_is_not_reported(self, tmp_path):
        draft = tmp_path / "q.md"
        draft.write_text(
            "> In order to proceed, we very carefully wrote a groundbreaking cliche.\n",
            encoding="utf-8",
        )
        assert style_check.check(draft, override="en-GB", propose=False)["findings"] == []
