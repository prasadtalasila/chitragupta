"""Which layouts a connector rule is not evaluated for (#1054).

A figure names its layout with `% cg-layout:` (#1057's reader,
`chitragupta/figure/_layout.py`); a rule a layout exempts is skipped for
it. Orthogonal routing and midpoint attach points are wrong for a tree's
and a hub's diagonal edges and an automaton's curves.
"""

from chitragupta.figure._layout import layout_names
from chitragupta.figure._rules import RULES

# Layouts phase 3 of the v3 plan adds; an exemption may name one before
# its scaffold and reference file exist.
PLANNED = {"state-machine", "sequence", "timeline", "quadrant", "comparison"}

NOT_ORTHOGONAL = {"state-machine", "hub-and-spoke-network", "branching-tree"}


def test_every_exempt_layout_is_a_known_or_planned_layout():
    exempt = {layout for rule in RULES.values() for layout in rule.exempt}

    assert exempt and exempt <= set(layout_names()) | PLANNED


def test_c1_and_c4_exempt_the_layouts_whose_edges_are_not_orthogonal():
    assert RULES["c1-orthogonal"].exempt == NOT_ORTHOGONAL
    assert RULES["c4-attach"].exempt == NOT_ORTHOGONAL


def test_no_other_rule_exempts_a_layout():
    assert {rule.id for rule in RULES.values() if rule.exempt} == {"c1-orthogonal", "c4-attach"}
