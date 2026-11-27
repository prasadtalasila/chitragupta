"""Every rule `chitragupta figure check` reports, by the id a finding, a
`% cg-allow:` line, docs/figure-checks/README.md and the figure-drawer skill all
quote (#1053).

One registry, cross-checked by a test against those places: a rule only in
prose ships broken, one only here cannot be looked up.

**Scope**: a figure-scope rule takes no target; an element-scope rule requires
one, so "allow every overlap" cannot be written. **Class**: objective findings
are resolved or allowed; advisory reports are only read, never allowable, and
listed apart (#1057). Exit is 0 regardless: SOUL.md allows one gate and this
is not it. The seven `review figure` ids keep its `--json` `kind` names.
Order here is report order.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    id: str
    scope: str  # "figure" or "element"
    cls: str  # "objective" or "advisory"
    # False for a compile failure (not a deliberate property; nothing else can be
    # checked until fixed) and for every advisory report, which is read, not resolved.
    allowable: bool = True
    # The layouts (`% cg-layout:`) the rule is not evaluated for (#1054).
    exempt: frozenset[str] = frozenset()


# A figure-scope finding's target: the rule is about the whole picture.
FIGURE = "figure"


@dataclass(frozen=True)
class Finding:
    """One rule's report on one target. Here rather than in `_check.py`
    so `_advisory.py` builds the same thing without importing it."""

    rule: str
    target: str
    measurement: str


# Diagonal spokes are a radial network's grammar and curved transitions an
# automaton's; everyone else routes orthogonally, trees included (#1083).
_NOT_ORTHOGONAL = frozenset({"state-machine", "hub-and-spoke-network"})

# A sequence's messages meet lifelines at heights time sets, and skipping
# lifelines between ends is its grammar, not a line through a box (#1063).
_LIFELINES = frozenset({"sequence"})

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
        Rule("c4-attach", "element", "objective", exempt=_NOT_ORTHOGONAL | _LIFELINES),
        Rule("c5-transit", "element", "objective", exempt=_LIFELINES),
        Rule("c6-tag-covered", "element", "objective"),
        Rule("c7-dangling-tip", "element", "objective"),
        # Contrast and wording (#1055): k1 and k2 from the probe's
        # colours, w4 from the source.
        Rule("k1-stroke", "element", "objective"),
        Rule("k2-text", "element", "objective"),
        Rule("w4-pictograph", "element", "objective"),
        # The house vocabulary (#1016): type, palette, tint from the
        # probe, an unplaced pic from the source.
        Rule("type-below-floor", "element", "objective"),
        Rule("colour-off-palette", "element", "objective"),
        Rule("tint-outside-band", "element", "objective"),
        Rule("unnamed-pic", "element", "objective"),
        # A figure without its twin is fixed, never excused (#1056).
        Rule("twin-missing", "figure", "objective", allowable=False),
        Rule("t1-labels", "element", "objective"),
        Rule("t2-tags", "element", "objective"),
        Rule("t3-panels", "figure", "objective"),
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
