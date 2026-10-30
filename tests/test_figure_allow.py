"""`chitragupta figure check`'s rule registry, `% cg-allow:` parser
(#1053) and the sorting of allows against what fired (#1058).

Pure string work, so every test here runs on a host with no TeX.
"""

import pytest

from chitragupta.figure._allow import Allow, parse_allows, settle
from chitragupta.figure._rules import RULES, Finding


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
                "type-below-floor",
                "colour-off-palette",
                "tint-outside-band",
                "unnamed-pic",
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
    return allows.wellformed, allows.malformed


class TestParseAllows:
    def test_a_figure_scope_allow_with_a_reason_is_well_formed(self):
        wellformed, malformed = _one(
            "\\begin{tikzpicture}\n% cg-allow: size-width -- five stages compared one by one\n"
        )

        [allow] = wellformed
        assert (allow.rule, allow.target, allow.line) == ("size-width", "", 2)
        assert allow.reason == "five stages compared one by one"
        assert malformed == []

    def test_an_element_scope_allow_keeps_its_target(self):
        [allow], malformed = _one("% cg-allow: node-overlap legend+pot -- on purpose\n")

        assert (allow.rule, allow.target, allow.reason) == (
            "node-overlap",
            "legend+pot",
            "on purpose",
        )
        assert malformed == []

    def test_a_quoted_target_may_hold_spaces_and_loses_its_quotes(self):
        [allow], malformed = _one('% cg-allow: k2-text "tag on parse->ledger" -- greyed\n')

        assert allow.target == "tag on parse->ledger"
        assert malformed == []

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
            ('% cg-allow: k2-text "" -- empty', "element-scope rule needs a target"),
            ("% cg-allow: node-overlap a+b c+d -- two", "more than one target"),
            ('% cg-allow: k2-text "tag on a->b" a -- two', "more than one target"),
            ('% cg-allow: k2-text "tag on a->b -- open', "unbalanced quote"),
            ('% cg-allow: k2-text a"b -- inside', "unbalanced quote"),
            ("% cg-allow: does-not-compile -- later", "cannot be allowed"),
        ],
    )
    def test_a_malformed_allow_says_what_is_wrong(self, line, problem):
        wellformed, malformed = _one(f"x\n{line}\n")

        [bad] = malformed
        assert (bad.line, bad.text, bad.problem) == (2, line.strip(), problem)
        assert wellformed == []

    def test_the_reason_may_itself_contain_a_double_dash(self):
        [allow], _ = _one("% cg-allow: size-width -- wide -- on purpose\n")

        assert allow.reason == "wide -- on purpose"

    def test_leading_space_and_a_doubled_percent_are_still_an_allow(self):
        wellformed, _ = _one("   %% cg-allow: focal-count -- two keys compared\n")

        assert [allow.rule for allow in wellformed] == ["focal-count"]

    def test_an_allow_after_code_on_the_same_line_is_not_one(self):
        """Only a full-line comment: a trailing comment on a drawing
        line is too easy to delete along with the line it explains."""
        assert _one("\\node (a) {A}; % cg-allow: size-width -- wide\n") == ([], [])

    def test_a_figure_with_no_allow_has_none(self):
        assert _one("\\begin{tikzpicture}\\end{tikzpicture}\n") == ([], [])


def _allow(rule, target="", line=1):
    return Allow(rule, target, "why", line)


def _settle(allows, fired, not_measured=(), layout="", names=None):
    return settle(list(allows), list(fired), list(not_measured), layout, names)


class TestSettle:
    def test_an_element_allow_sets_aside_only_its_own_target(self):
        """The point of #1058: excusing one overlap leaves the next one
        found."""
        fired = [Finding("node-overlap", "a+b", "boxes intersect")] + [
            Finding("node-overlap", "a+c", "boxes intersect")
        ]

        settled = _settle([_allow("node-overlap", "a+b")], fired)

        assert [f.target for f in settled.findings] == ["a+c"]
        assert [(a.target, measured) for a, measured in settled.allowed] == [
            ("a+b", "boxes intersect")
        ]
        assert settled.stale == [] and settled.unchecked == []

    def test_a_pair_matches_in_either_order(self):
        settled = _settle(
            [_allow("node-overlap", "pot+legend")],
            [Finding("node-overlap", "legend+pot", "boxes intersect")],
        )

        assert settled.findings == [] and len(settled.allowed) == 1

    def test_an_edge_matches_only_in_its_drawn_direction(self):
        fired = [Finding("c1-orthogonal", "twin->decide", "off")]

        settled = _settle(
            [_allow("c1-orthogonal", "decide->twin")], fired, names={"twin", "decide"}
        )

        assert settled.findings == fired
        assert [why for _, why in settled.stale] == ["no longer fires on decide->twin"]

    def test_a_node_does_not_cover_its_sides(self):
        fired = [Finding("c4-attach", "decide.south", "off the even spacing")]

        settled = _settle([_allow("c4-attach", "decide")], fired, names={"decide"})

        assert settled.findings == fired and len(settled.stale) == 1

    def test_one_allow_covers_every_finding_on_its_target(self):
        fired = [Finding("c2-tag-clearance", "a->b", "tag 0.4mm")] + [
            Finding("c2-tag-clearance", "a->b", "tag 0.3mm")
        ]

        settled = _settle([_allow("c2-tag-clearance", "a->b")], fired)

        assert settled.findings == []
        assert [measured for _, measured in settled.allowed] == ["tag 0.4mm; tag 0.3mm"]

    def test_two_allows_for_one_finding_both_report_it(self):
        fired = [Finding("size-width", "figure", "475.0pt wide")]

        settled = _settle([_allow("size-width", line=1), _allow("size-width", line=2)], fired)

        assert [measured for _, measured in settled.allowed] == ["475.0pt wide"] * 2

    def test_a_quoted_finding_target_matches_its_unquoted_allow(self):
        """w4 prints an unnamed label in quotes; the allow's quotes are
        gone once parsed, so the two must meet without them."""
        fired = [Finding("w4-pictograph", '"Raw PDF"', "1 pictograph")]

        settled = _settle([_allow("w4-pictograph", "Raw PDF")], fired)

        assert settled.findings == [] and len(settled.allowed) == 1

    def test_a_figure_scope_allow_whose_rule_did_not_fire_is_stale(self):
        settled = _settle([_allow("size-width")], [])

        [(allow, why)] = settled.stale
        assert allow.rule == "size-width" and why == "no longer fires"

    def test_a_target_naming_no_drawn_node_says_so(self):
        settled = _settle([_allow("c1-orthogonal", "twin->decide")], [], names={"twin", "choose"})

        assert [why for _, why in settled.stale] == ["no node named decide"]

    def test_a_sides_node_is_looked_up_without_its_side(self):
        settled = _settle([_allow("c4-attach", "pot.south")], [], names={"legend"})

        assert [why for _, why in settled.stale] == ["no node named pot"]

    @pytest.mark.parametrize(
        ("rule", "target"),
        [
            ("c7-dangling-tip", "(3.0,4.0)"),
            # A node TikZ named itself is shown by its centre (#1101).
            ("c4-attach", "(3.0,4.0).south"),
            ("c1-orthogonal", "(3.0,4.0)->(9.0,4.0)"),
            ("k2-text", "tag on a->b"),
            ("t1-labels", "Ledger"),
        ],
    )
    def test_points_spaced_targets_and_label_text_are_not_looked_up(self, rule, target):
        """A point is not a name, and t1, t2 and w4 name an unnamed
        node by its label text, which is never among the drawn names."""
        settled = _settle([_allow(rule, target)], [], names=set())

        assert [why for _, why in settled.stale] == [f"no longer fires on {target}"]

    def test_a_point_half_of_a_pair_is_not_looked_up(self):
        """An unnamed node overlapping a named one prints as its centre,
        on either side of the `+`."""
        settled = _settle([_allow("node-overlap", "pot+(3.0,2.0)")], [], names={"pot"})

        assert [why for _, why in settled.stale] == ["no longer fires on pot+(3.0,2.0)"]

    def test_without_drawn_names_a_stale_allow_only_says_it_no_longer_fires(self):
        settled = _settle([_allow("node-overlap", "a+b")], [], names=None)

        assert [why for _, why in settled.stale] == ["no longer fires on a+b"]

    def test_an_allow_for_a_rule_that_did_not_run_is_unchecked(self):
        not_measured = [("k2-text", "the figure uses `transform canvas`")]

        settled = _settle([_allow("k2-text", "a")], [], not_measured, names=set())

        assert [why for _, why in settled.unchecked] == ["the figure uses `transform canvas`"]
        assert settled.stale == []

    def test_an_allow_for_a_rule_its_layout_exempts_is_unchecked(self):
        settled = _settle([_allow("c1-orthogonal", "a->b")], [], layout="state-machine")

        assert [why for _, why in settled.unchecked] == ["exempt for layout state-machine"]

    def test_a_partly_run_rule_still_honours_what_matched(self):
        fired = [Finding("c4-attach", "a.south", "off")]
        not_measured = [("c4-attach", "round nodes, which have no sides: r")]

        settled = _settle(
            [_allow("c4-attach", "a.south"), _allow("c4-attach", "b.east")], fired, not_measured
        )

        assert [a.target for a, _ in settled.allowed] == ["a.south"]
        assert [a.target for a, _ in settled.unchecked] == ["b.east"]

    def test_an_allow_covers_only_its_own_rule_on_a_shared_target(self):
        fired = [Finding("k1-stroke", "a->b", "line 2.1:1")]

        settled = _settle([_allow("c1-orthogonal", "a->b")], fired)

        assert settled.findings == fired and len(settled.stale) == 1

    def test_findings_no_allow_names_are_kept_in_order(self):
        fired = [Finding("size-width", "figure", "wide")] + [Finding("node-overlap", "a+b", "x")]

        assert _settle([], fired).findings == fired
