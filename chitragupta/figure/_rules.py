"""Every rule `chitragupta figure check` reports, by the id a finding, a
`% cg-allow:` line, docs/TIKZ-STYLE.md and the figure-drawer skill all
quote (#1053).

One registry, because the id is the contract between four places and a
test cross-checks them against this table: a rule only in prose ships
broken, and a rule only here is one no author can look up.

**Scope** says what an allow must name. A figure-scope rule is about the
whole picture and takes no target; an element-scope rule is about one
node, pair or point and requires one, so "allow every overlap" cannot be
written. **Class** says what the skill does with a finding: an objective
one is resolved or allowed with a reason, an advisory one is read.
Neither is an exit code. An advisory report has nothing an allow could
set aside, so none is allowable, and none is ever a finding: they are
reported apart, under their own heading (#1057). `figure check` exits 0 whatever it finds,
because SOUL.md allows one gate and this is not it.

The seven ids from `review figure` are the `kind` strings its `--json`
already ships, kept rather than renamed so one finding has one name
across both commands. Each is binary, so each is objective.

Order here is report order: a figure that does not compile, or names
nothing to measure, says so before anything measured, and the advisory
reports come last.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    scope: str  # "figure" or "element"
    cls: str  # "objective" or "advisory"
    # False for a compile failure, which is not a property of the drawing
    # that could be deliberate (nothing else can be checked until it is
    # fixed), and for every advisory report, which is read, not resolved.
    allowable: bool = True
    # The layouts (`% cg-layout:`) the rule is not evaluated for (#1054).
    exempt: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Finding:
    """One rule's report on one target. Here rather than in `_check.py`
    so `_advisory.py` builds the same thing without importing it."""

    rule: str
    target: str
    measurement: str


# Diagonal spokes are a radial network's grammar, and curved transitions
# an automaton's; orthogonal routing, and the attach points it puts at a
# side's midpoint, are everyone else's. A tree is held to it: #1083 drew
# the house tree with fanned orthogonal edges.
_NOT_ORTHOGONAL = frozenset({"state-machine", "hub-and-spoke-network"})

RULES: dict[str, Rule] = {
    rule.id: rule
    for rule in (
        Rule("does-not-compile", "figure", "objective", allowable=False),
        Rule("nothing-measurable", "figure", "objective"),
        Rule("size-width", "figure", "objective"),
        Rule("size-stray", "figure", "objective"),
        Rule("focal-count", "figure", "objective"),
        Rule("content-protrusion", "figure", "objective"),
        Rule("loads-library-by-hand", "figure", "objective"),
        Rule("node-overlap", "element", "objective"),
        Rule("node-text-overload", "element", "objective"),
        Rule("stranded-arrowhead", "element", "objective"),
        # The connector rules (#1054), measured from the lines TikZ drew.
        Rule("c1-orthogonal", "element", "objective", exempt=_NOT_ORTHOGONAL),
        Rule("c2-tag-clearance", "element", "objective"),
        Rule("c3-coincident", "element", "objective"),
        Rule("c4-attach", "element", "objective", exempt=_NOT_ORTHOGONAL),
        Rule("c5-transit", "element", "objective"),
        Rule("c6-tag-covered", "element", "objective"),
        Rule("c7-dangling-tip", "element", "objective"),
        # Contrast and wording (#1055): k1 and k2 from the probe's
        # colours, w4 from the source.
        Rule("k1-stroke", "element", "objective"),
        Rule("k2-text", "element", "objective"),
        Rule("w4-pictograph", "element", "objective"),
        Rule("size-height", "figure", "advisory", allowable=False),
        Rule("size-slack", "figure", "advisory", allowable=False),
        Rule("size-squash", "element", "advisory", allowable=False),
        Rule("budget-nodes", "figure", "advisory", allowable=False),
        Rule("budget-edges", "figure", "advisory", allowable=False),
        Rule("w1-case", "element", "advisory", allowable=False),
        Rule("w2-tag", "element", "advisory", allowable=False),
        Rule("w3-gloss", "element", "advisory", allowable=False),
    )
}
