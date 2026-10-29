"""`chitragupta figure check`'s rule registry and `% cg-allow:` parser (#1053).

Pure string work, so every test here runs on a host with no TeX.
"""

import pytest

from chitragupta.figure._allow import parse_allows
from chitragupta.figure._rules import RULES


# The connector rules (#1054), `c1-` to `c7-`, each about one edge, pair,
# side, tag or point.
_CONNECTOR_NAMES = (
    "orthogonal",
    "tag-clearance",
    "coincident",
    "attach",
    "transit",
    "tag-covered",
    "dangling-tip",
)


class TestRules:
    def test_the_three_new_figure_scope_rules_are_objective(self):
        for rule_id in ("size-width", "size-stray", "focal-count"):
            assert RULES[rule_id].scope == "figure"
            assert RULES[rule_id].cls == "objective"

    def test_the_existing_findings_keep_their_shipped_json_kinds(self):
        """The ids are the `kind` strings `review figure --json` already
        emits, so one finding has one name across both commands."""
        shipped = {
            "does-not-compile",
            "nothing-measurable",
            "content-protrusion",
            "loads-library-by-hand",
            "node-overlap",
            "node-text-overload",
            "stranded-arrowhead",
        }
        assert shipped <= set(RULES)

    def test_the_element_rules_are_the_ones_with_a_target(self):
        element = {rule.id for rule in RULES.values() if rule.scope == "element"}
        connector = {f"c{n}-{name}" for n, name in enumerate(_CONNECTOR_NAMES, start=1)}
        assert (
            element
            == {
                "node-overlap",
                "node-text-overload",
                "stranded-arrowhead",
                "size-squash",
                "k1-stroke",
                "k2-text",
                "w1-case",
                "w2-tag",
                "w3-gloss",
                "w4-pictograph",
                "t1-labels",
                "t2-tags",
            }
            | connector
        )

    def test_a_compile_failure_a_missing_twin_and_the_advisory_reports_cannot_be_allowed(self):
        """An advisory report is read, so there is nothing for an allow
        to set aside (#1057). A missing twin is written, never excused
        (#1056)."""
        refused = [rule.id for rule in RULES.values() if not rule.allowable]
        advisory = [rule.id for rule in RULES.values() if rule.cls == "advisory"]

        assert refused == ["does-not-compile", "twin-missing", *advisory]
        assert len(advisory) == 8

    def test_each_rule_is_keyed_by_its_own_id(self):
        assert all(key == rule.id for key, rule in RULES.items())


def _one(source):
    allows = parse_allows(source)
    return allows.honoured, allows.deferred, allows.malformed


class TestParseAllows:
    def test_a_figure_scope_allow_with_a_reason_is_honoured(self):
        honoured, deferred, malformed = _one(
            "\\begin{tikzpicture}\n% cg-allow: size-width -- five stages compared one by one\n"
        )

        [allow] = honoured
        assert (allow.rule, allow.target, allow.line) == ("size-width", "", 2)
        assert allow.reason == "five stages compared one by one"
        assert deferred == [] and malformed == []

    def test_an_element_scope_allow_with_a_target_is_deferred_until_1058(self):
        honoured, deferred, malformed = _one("% cg-allow: node-overlap legend+pot -- on purpose\n")

        [allow] = deferred
        assert (allow.rule, allow.target, allow.reason) == (
            "node-overlap",
            "legend+pot",
            "on purpose",
        )
        assert honoured == [] and malformed == []

    @pytest.mark.parametrize(
        ("line", "problem"),
        [
            ("% cg-allow: size-width", "no reason"),
            ("% cg-allow: size-width --", "no reason"),
            ("% cg-allow: size-width --   ", "no reason"),
            ("% cg-allow: -- because", "names no rule"),
            ("% cg-allow: size-wide -- typo", "unknown rule `size-wide`"),
            ("% cg-allow: size-width figure -- why", "figure-scope rule takes no target"),
            ("% cg-allow: node-overlap -- every overlap", "element-scope rule needs a target"),
            ("% cg-allow: node-overlap a+b c+d -- two", "more than one target"),
            ("% cg-allow: does-not-compile -- later", "cannot be allowed"),
        ],
    )
    def test_a_malformed_allow_says_what_is_wrong(self, line, problem):
        honoured, deferred, malformed = _one(f"x\n{line}\n")

        [bad] = malformed
        assert (bad.line, bad.text, bad.problem) == (2, line.strip(), problem)
        assert honoured == [] and deferred == []

    def test_the_reason_may_itself_contain_a_double_dash(self):
        [allow], _, _ = _one("% cg-allow: size-width -- wide -- on purpose\n")

        assert allow.reason == "wide -- on purpose"

    def test_leading_space_and_a_doubled_percent_are_still_an_allow(self):
        honoured, _, _ = _one("   %% cg-allow: focal-count -- two keys compared\n")

        assert [allow.rule for allow in honoured] == ["focal-count"]

    def test_an_allow_after_code_on_the_same_line_is_not_one(self):
        """Only a full-line comment: a trailing comment on a drawing
        line is too easy to delete along with the line it explains."""
        assert _one("\\node (a) {A}; % cg-allow: size-width -- wide\n") == ([], [], [])

    def test_a_figure_with_no_allow_has_none(self):
        assert _one("\\begin{tikzpicture}\\end{tikzpicture}\n") == ([], [], [])
