from chitragupta.figure._layout import layout_names
from chitragupta.figure._rules import RULES

PLANNED = {"timeline", "quadrant"}

NOT_ORTHOGONAL = {"state-machine", "hub-and-spoke-network"}

EXEMPT = {
    "c1-orthogonal": NOT_ORTHOGONAL,
    "c4-attach": NOT_ORTHOGONAL | {"sequence"},
    "c5-transit": {"sequence"},
}


def test_every_exempt_layout_is_a_known_or_planned_layout():
    exempt = {layout for rule in RULES.values() for layout in rule.exempt}

    assert exempt and exempt <= set(layout_names()) | PLANNED


def test_each_rule_exempts_exactly_its_layouts():
    assert {rule: RULES[rule].exempt for rule in EXEMPT} == EXEMPT


def test_no_other_rule_exempts_a_layout():
    assert {rule.id for rule in RULES.values() if rule.exempt} == set(EXEMPT)
