# 🎯 XII-2g: element-scope `cg-allow` and stale allows

Status: **built.** Written 2026-10-30 against `main` at `dad488b`,
from a brainstorming session on issue
[#1058](https://github.com/prasadtalasila/chitragupta/issues/1058), to be
implemented in the same PR as this plan, as #1053, #1056 and #1057 were.
The decisions marked *user* were agreed in that session; the rest was the
session's proposal, accepted as a whole.

**Written for** whoever builds #1058: a session that changes
`chitragupta/figure/`, the `figure-drawer` skill's `references/check.md`,
`tests/` and `docs/`, and is therefore governed by `DEVELOPER-AGENTS.md`
and `docs/CODE-STANDARDS.md`.

**Assumed:** `plans/fig-xii-figure-drawer-v3.md` ("Exceptions:
`cg-allow`"), `plans/1053-figure-check-skeleton.md` (the registry, the
report and the allow grammar this finishes), and the rule modules
of #1054, #1055 and #1056, whose finding targets an allow now names.

**Not covered here:** changing how any rule names its target (each keeps
the string it prints today); matching an allow on a finding's
measurement; anything that blocks a draft. `figure check` still exits 0
whatever it finds.

## What it is for

A figure-level exception silently covers every future instance of its
rule. Since #1053 an element-scope allow (`node-overlap legend+pot`) has
been parsed and validated but only *deferred*: its finding still prints,
so no element rule can be excused at all. This item honours an element
allow for the one target it names and no other, and reports an allow
that no longer sets anything aside as **stale**, so an exception cannot
outlive its reason unseen.

Already true on `main` and kept: a target-less allow for an element rule,
and a target on a figure-scope rule, are malformed (`_allow._scope_problem`).

## Decisions

| Question | Decision |
| --- | --- |
| How an allow matches a finding | Same rule id and the **same target string** the finding prints (*user*). No widening: `decide` does not cover `decide.south`, and `a->b` does not cover `b->a`, which is another drawn line |
| Pairs | `a+b` matches `b+a` (*user*): which half prints first follows draw order, and reordering two `\node` lines must not stale an allow |
| One allow, several findings | One allow covers every finding of its rule on its target (*user*), e.g. two c2 tags on one edge. Accepted gap: a later `c5-transit a->b` crossing of a *new* node is covered too, because the target is the finest thing an author writes by hand, and matching on the measurement would stale on every 0.1mm nudge |
| Targets with spaces | A target may be **double-quoted** (*user*, option A). The text report quotes any finding or allow target that contains a space, so every printed target can be pasted verbatim: `k2-text "tag on parse->ledger"`, `t1-labels "Raw PDF"`. Matching compares the targets with one pair of surrounding quotes removed, so w4's already-quoted `"Raw PDF"` matches too. Rejected: space-free tokens (option B), since t1, t2 and w4 have only label text to name an unnamed node by |
| Stale covers figure-scope allows | Yes (*user*, option A). An allow that sets nothing aside on a rule that ran is stale, whatever its scope; `size-width` on a figure that now fits is stale, not "allowed, did not fire" |
| A rule that did not run | Its allow is **unchecked**, never stale: the rule is under "not measured" (no compile, `transform canvas`, several pictures, no twin), or the figure's layout is in the rule's `exempt` set. A partly-run rule (c4 skipping round nodes) honours what matched; what did not match is unchecked |
| Why an allow is stale | `no node named <x>` when the probe drew nodes and a name in a space-free, non-point target (its parts split at `->`, `+` and `.`) is not among them; otherwise `no longer fires on <target>` |
| Version | MINOR (*user*): the `--json` payload drops `deferred` and adds `stale` and `unchecked`, and the summary line changes, as earlier v3 items changed it under MINOR |

## Sorting an allow

Every well-formed allow lands in exactly one bucket, tested in this
order:

| Bucket | When | Its findings |
| --- | --- | --- |
| allowed | its rule fired on its target (`figure` for a figure-scope allow) | removed from the findings, shown beside the allow |
| unchecked | its rule did not run, or ran only partly and did not match | none; the reason the rule did not run is shown |
| stale | its rule ran and did not fire on its target | none; why it is stale is shown |

Example: `% cg-allow: c1-orthogonal twin->decide -- curved on purpose`
is allowed while the curve exists. Rename `decide` to `choose` and c1
fires on `twin->choose` (a finding), while the allow is stale with
`no node named decide`: the curve is unexcused and the allow points at
nothing. The same figure with a `transform canvas` lists a k2 allow as
unchecked, and honours it again once the canvas goes, with no edit.

## Parsing

The head before the first `--` is a rule id, then nothing, one bare
word, or one `"double-quoted"` target that may hold spaces. Malformed,
beside today's five problems: an unbalanced quote, and anything after
the target (`more than one target`, as now).

## The report

Sections, each left out when empty: findings; advisory; **allowed**;
**stale allows**; **unchecked allows**; malformed allows; not measured;
diagnostics. "not honoured until #1058" goes. An allowed row always has
a measurement now, so `did not fire` goes too. Quoting applies to
finding and allow rows only; the advisory rows (`w2-tag`'s
`tag "Fetch"`) are not allowable and print as today.

```text
fig/loop.tex
  c1-orthogonal         twin->choose   off by 6.0mm in x and 9.0mm in y
stale allows
  c1-orthogonal         twin->decide   no node named decide -- curved on purpose (line 3)
figure check: 1 finding, 0 allowed, 1 stale, 0 unchecked, 0 malformed
```

`--json`: `deferred` is removed; `allowed[]` keeps
`{rule, target, reason, line, measurement}`, with `measurement` never
`null`; `stale[]` and `unchecked[]` are `{rule, target, reason, line,
why}`, where an unchecked `why` is the "not measured" reason or
`exempt for layout <name>`. `target` is the allow's unquoted target;
findings keep the target their rule produced.

## Code

- **`_allow.py`** owns all of it. `parse_allows` returns the
  well-formed allows and the malformed ones (the `honoured`/`deferred`
  split goes). A new pure function sorts them:
  `settle(allows, fired, not_measured, layout, drawn_names) ->
  Settled(findings, allowed, stale, unchecked)`. No TeX, so it is
  tested on every CI leg, Windows included.
- **`_check.py`** replaces its inline matching in `apply` with one
  `settle` call; `CheckResult.deferred` becomes `stale` and `unchecked`.
  It is at the 250-code-line ceiling, so this must not grow it.
- **`_check_report.py`**: the sections, the summary line, a quoting
  helper for target columns, and the JSON keys.

## Tests and fixtures

- `tests/test_figure_allow.py`: quoted targets (honoured, unbalanced,
  trailing word); `settle` for each bucket, pair order, a quoted w4
  target, a layout exemption, a partly-run c4, both stale reasons, and
  a figure-scope allow going stale.
- `tests/fixtures/figure/check/`, each with its `.txt` twin so
  `twin-missing` stays quiet: `allowed-overlap.tex` (a `node-overlap`
  allow written `b+a` for a finding printed `a+b`) and
  `stale-overlap.tex` (an allow naming a node that is not drawn).
  Malformed allows stay unit-tested in `test_figure_allow.py`.
- `tests/test_figure_check.py`: the deferred test becomes an honoured
  one; the text and JSON report tests move to the new sections and keys.
- 100% line and branch coverage, as `docs/CODE-STANDARDS.md` requires.

## Docs

- `.claude/skills/figure-drawer/references/check.md`: "Recording a
  deliberate exception" gains quoting, stale and unchecked, and loses
  "not honoured until #1058"; its sample summary line changes.
- `docs/TIKZ-STYLE.md` (the `cg-allow` bullets), `docs/CLI.md` (the
  sections list, the sample summary line, the `--json` row).
- `plans/fig-xii-figure-drawer-v3.md`: 2g marked built.
