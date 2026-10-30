"""`% cg-allow: <rule-id> [<target>] -- <reason>`: a figure's own record
that it breaks a rule on purpose (#1053), and what each one set aside
(#1058).

The exception lives in the figure file because the figure file is what
travels: into the draft, into the render, into a thesis this project
never sees. The reason is required, so an exception is always a claim
someone can read and disagree with, never a rule silently switched off.

Only a full-line comment counts. A trailing comment on a drawing line is
too easy to delete along with the line it explains, and then the allow
would outlive its reason or vanish without one.

An element-scope allow sets aside its rule on the one target it names,
spelt as the finding prints it, so a later defect of the same kind is
still found. A target with a space in it is written in double quotes.
An allow that set nothing aside on a rule that ran is stale, so an
exception cannot outlive its reason unseen; one whose rule did not run
is unchecked, never stale, since nothing was measured to say so.
"""

import re
from dataclasses import dataclass, field

from chitragupta.figure._rules import RULES, Finding

_ALLOW_RE = re.compile(r"^[ \t]*%+[ \t]*cg-allow:(?P<body>.*)$", re.MULTILINE)

# The head before `--`: a rule id, then nothing, one bare word or one
# double-quoted target, then whatever is left over.
_HEAD_RE = re.compile(
    r'\s*(?P<rule>\S*)\s*(?:"(?P<quoted>[^"]*)"|(?P<bare>[^\s"]+))?\s*(?P<rest>.*)'
)

# The rules that name an unnamed node by its label text, which is never
# among the drawn names, so a missing name says nothing about them.
_LABEL_TARGETS = frozenset({"t1-labels", "t2-tags", "w4-pictograph"})


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
    """Every allow in one file: the well-formed ones, which `settle`
    sorts, and the malformed ones, which allow nothing."""

    wellformed: list[Allow] = field(default_factory=list)
    malformed: list[Malformed] = field(default_factory=list)


@dataclass
class Settled:
    """What the allows did to what fired. `allowed` pairs an allow with
    the measurements it set aside, `stale` and `unchecked` with why."""

    findings: list[Finding] = field(default_factory=list)
    allowed: list[tuple[Allow, str]] = field(default_factory=list)
    stale: list[tuple[Allow, str]] = field(default_factory=list)
    unchecked: list[tuple[Allow, str]] = field(default_factory=list)


def parse_allows(source: str) -> Allows:
    """Every `% cg-allow:` line in `source`, in source order."""
    allows = Allows()
    for match in _ALLOW_RE.finditer(source):
        line = source.count("\n", 0, match.start()) + 1
        rule, target, reason, problem = _parse(match.group("body"))
        if problem:
            allows.malformed.append(Malformed(line, match.group(0).strip(), problem))
        else:
            allows.wellformed.append(Allow(rule, target, reason, line))
    return allows


def _parse(body: str) -> tuple[str, str, str, str]:
    """`(rule, target, reason, problem)`; `problem` is empty when the
    line is well formed. The first `--` ends the head, so a reason may
    contain one of its own."""
    head, _, reason = body.partition("--")
    parts = _HEAD_RE.fullmatch(head)
    rule, rest = parts.group("rule"), parts.group("rest")
    target = parts.group("quoted") or parts.group("bare") or ""
    reason = reason.strip()
    if not reason:
        return rule, target, reason, "no reason"
    if not rule:
        return rule, target, reason, "names no rule"
    if rule not in RULES:
        return rule, target, reason, f"unknown rule `{rule}`"
    return rule, target, reason, _scope_problem(rule, target, rest)


def _scope_problem(rule: str, target: str, rest: str) -> str:
    """What is wrong with `rule`'s target, or `""`. `rest` is whatever
    followed the target in the head."""
    if not RULES[rule].allowable:
        return "cannot be allowed"
    if '"' in rest:
        return "unbalanced quote"
    if rest:
        return "more than one target"
    if RULES[rule].scope == "figure" and target:
        return "figure-scope rule takes no target"
    if RULES[rule].scope == "element" and not target:
        return "element-scope rule needs a target"
    return ""


def settle(
    allows: list[Allow],
    fired: list[Finding],
    not_measured: list[tuple[str, str]],
    layout: str,
    names: set[str] | None,
) -> Settled:
    """Sort each allow into allowed, unchecked or stale, in that order of
    precedence, and keep the findings no allow covers. `not_measured` is
    every rule that did not run, with why; `names` the nodes the probe
    drew, `None` where it drew nothing to look a target up in."""
    settled, covered = Settled(), set()
    skipped = dict(reversed(not_measured))
    for allow in allows:
        matched = [i for i, finding in enumerate(fired) if _covers(allow, finding)]
        covered.update(matched)
        if matched:
            settled.allowed.append((allow, "; ".join(fired[i].measurement for i in matched)))
        elif allow.rule in skipped or layout in RULES[allow.rule].exempt:
            why = skipped.get(allow.rule) or f"exempt for layout {layout}"
            settled.unchecked.append((allow, why))
        else:
            settled.stale.append((allow, _stale(allow, names)))
    settled.findings = [finding for i, finding in enumerate(fired) if i not in covered]
    return settled


def _covers(allow: Allow, finding: Finding) -> bool:
    if finding.rule != allow.rule:
        return False
    return RULES[allow.rule].scope == "figure" or _key(allow.target) == _key(finding.target)


def _key(target: str) -> tuple[str, ...]:
    """A target as matched: without one pair of surrounding quotes, and a
    pair (`a+b`) in either order, since which half prints first follows
    the order the nodes were drawn in."""
    if len(target) > 1 and target[0] == target[-1] == '"':
        target = target[1:-1]
    return (target,) if " " in target else tuple(sorted(target.split("+")))


def _stale(allow: Allow, names: set[str] | None) -> str:
    if not allow.target:
        return "no longer fires"
    if names is not None and _named(allow):
        # A point (an unnamed node's centre) is not a name, on either
        # side of a pair.
        ends = [end for end in re.split(r"->|\+", allow.target) if not end.startswith("(")]
        missing = [node for node in (end.split(".")[0] for end in ends) if node not in names]
        if missing:
            return f"no node named {missing[0]}"
    return f"no longer fires on {allow.target}"


def _named(allow: Allow) -> bool:
    """Whether `allow`'s target is spelt in node names rather than label
    text."""
    return allow.rule not in _LABEL_TARGETS and " " not in allow.target
