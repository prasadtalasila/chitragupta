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


@dataclass(frozen=True)
class Finding:
    """One rule's report on one target. Here rather than in `_check.py`
    so `_advisory.py` builds the same thing without importing it."""

    rule: str
    target: str
    measurement: str


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
        Rule("size-height", "figure", "advisory", allowable=False),
        Rule("size-slack", "figure", "advisory", allowable=False),
        Rule("size-squash", "element", "advisory", allowable=False),
        Rule("budget-nodes", "figure", "advisory", allowable=False),
        Rule("budget-edges", "figure", "advisory", allowable=False),
    )
}
