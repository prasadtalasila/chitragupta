"""`% cg-allow: <rule-id> [<target>] -- <reason>`: a figure's own record
that it breaks a rule on purpose (#1053).

The exception lives in the figure file because the figure file is what
travels: into the draft, into the render, into a thesis this project
never sees. The reason is required, so an exception is always a claim
someone can read and disagree with, never a rule silently switched off.

Only a full-line comment counts. A trailing comment on a drawing line is
too easy to delete along with the line it explains, and then the allow
would outlive its reason or vanish without one.

Element-scope allows are parsed and validated now but honoured only once
edge geometry can name their targets (#1058). Until then they are
listed as deferred, so a line written correctly today does not change
status when that lands.
"""

import re
from dataclasses import dataclass, field

from chitragupta.figure._rules import RULES

_ALLOW_RE = re.compile(r"^[ \t]*%+[ \t]*cg-allow:(?P<body>.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Allow:
    rule: str
    target: str
    reason: str
    line: int


@dataclass(frozen=True)
class Malformed:
    line: int
    text: str
    problem: str


@dataclass
class Allows:
    """Every allow in one file, sorted by what `figure check` does with
    it. `honoured` are the well-formed figure-scope ones."""

    honoured: list[Allow] = field(default_factory=list)
    deferred: list[Allow] = field(default_factory=list)
    malformed: list[Malformed] = field(default_factory=list)


def parse_allows(source: str) -> Allows:
    """Every `% cg-allow:` line in `source`, in source order."""
    allows = Allows()
    for match in _ALLOW_RE.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        rule, target, reason, problem = _parse(match.group("body"))
        if problem:
            allows.malformed.append(Malformed(line, match.group(0).strip(), problem))
        elif RULES[rule].scope == "figure":
            allows.honoured.append(Allow(rule, target, reason, line))
        else:
            allows.deferred.append(Allow(rule, target, reason, line))
    return allows


def _parse(body: str) -> tuple[str, str, str, str]:
    """`(rule, target, reason, problem)`; `problem` is empty when the
    line is well formed. The first `--` ends the head, so a reason may
    contain one of its own."""
    head, _, reason = body.partition("--")
    words = head.split()
    rule, target = (words + ["", ""])[:2]
    reason = reason.strip()
    if not reason:
        return rule, target, reason, "no reason"
    if not rule:
        return rule, target, reason, "names no rule"
    if rule not in RULES:
        return rule, target, reason, f"unknown rule `{rule}`"
    return rule, target, reason, _scope_problem(rule, target, len(words))


def _scope_problem(rule: str, target: str, words: int) -> str:
    """What is wrong with `rule`'s target, or `""`."""
    if not RULES[rule].allowable:
        return "cannot be allowed"
    if words > 2:
        return "more than one target"
    if RULES[rule].scope == "figure" and target:
        return "figure-scope rule takes no target"
    if RULES[rule].scope == "element" and not target:
        return "element-scope rule needs a target"
    return ""
