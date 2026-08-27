# Adopting the two auto-improvement loops

Status: **decisions recorded; the developer half is retired rather than
built.** Written 2026-08-21. Re-measured and revised 2026-08-27.

**Read the re-measurement first.** The 2026-08-21 document designed a
developer-side loop around an eight-class worklist merged from two
sources. Re-measured against the tree on 2026-08-27, **six of those
eight classes are empty and one of the two sources is gone.** That is
not a design that needs correcting so much as a design whose problem
was solved by other means while it sat unbuilt -- and the revision
below says so rather than restating the plan with better numbers.

**#381 closed "Still open" items 2 and 3** (`missing-citekey` is
unattended; a draft with no dossier gets a reduced source set rather
than a refusal) when it built F2, the `agenda` aid. Item 1 is also
closed, though not in the way it expected -- see Decision 2.

**This document does not restate [Theme F](../docs/FEATURE-ROADMAP.md).**
Its F1 and F2 entries have been deleted from that document as shipped,
per its own rule that a roadmap accumulating its own history stops being
a list of what to do next; F4 is recorded there as closed-not-pending;
and only F3 -- widening `overlap-reviser` into `agenda-reviser` -- is
still live work.
`plans/README.md` is explicit that restating a roadmap entry "produces
two documents that must agree", so where Theme F already decides
something, this file points at it and stops.

What is here is the part Theme F does not carry:

1. **Two decisions the user has taken** -- the amendment, and the pass
   bound -- with the measurements behind the second.
2. **The developer-side loop**, which has no roadmap theme, and which
   this revision retires with the three pieces of it that survive.
3. **Five questions settled** on 2026-08-21, one of them (Q2) reversed
   on 2026-08-27 on evidence, with the reversal recorded rather than
   the original quietly deleted.

**Written for** whoever picks up F3, and whoever reads the developer
half and wonders why nothing was built. It assumes
[docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md),
[docs/AUTO-IMPROVEMENT-RATIONALE.md](../docs/AUTO-IMPROVEMENT-RATIONALE.md)
and [DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md).

## The 2026-08-27 re-measurement

Taken against this worktree with `/workspace/.venv-full`, read-only.
Nothing was written and no code was changed.

| Class | 2026-08-21 said | Measured 2026-08-27 |
| --- | --- | --- |
| `over-long-function` | C1 register, 10 entries | **3** |
| `over-long-module` | C2 register, 11 entries | **17** |
| `inert-noqa` | 11 countable call sites | **0** -- `RUF100` is in `pyproject.toml`'s `select`, so an inert `# noqa` now fails the lint job. 13 sites remain and every one is a checked claim |
| `missing-annotation` | 394 of 433 | **not debt** -- closed in #355; Tier 2 "holds no subsections at all"; no type checker in `ci.yml`'s `lint` job. 175 of 997 functions are unannotated and none is owed |
| `linter-baseline` | pylint / markdownlint, countable | **0** -- `pylint --rcfile=.pylintrc` scores 10.00/10 and `ruff check` reports "All checks passed!", both at the binary zero-messages bar `ci.yml` enforces |
| `duplication` | TECHNICAL-DEBT 3.2, 3.7, 3.8 | **gone** -- Tier 3 "holds no subsections at all" |
| `structural` | TECHNICAL-DEBT 3.4, 3.9, 4.x | **gone** -- Tier 3 as above; Tier 4 closed |
| `process` | the standing-instruction budget | **"Resolved in #238 and #357"** |

`docs/TECHNICAL-DEBT.md`'s "What to take first" is empty of items, and
`tests/test_code_standards_scan.py` plus `tests/test_technical_debt_scan.py`
pass 40 of 40 -- so the register is worst-first ordered, count-accurate
and doc-pinned already, with nothing left for a second tool to add.

**The C2 register grew, and that is not a regression.** C1 went 10 to
3; C2 went 11 to 17, for 20 entries against 21. The register's own
comments say why the second moved the wrong way, and it is not
complexity: ten files entered or grew when `line-too-long` was enabled,
because wrapping a 105-character line spends a physical line to save a
column, and six more entered on #362's `ruff format` adoption, whose
hanging-indent style spends more lines to say the same thing. "None of
the six is a real complexity increase" is the register's own verdict.
A ranking aid reading only the counts would have promoted sixteen
formatting artefacts over the two real splits.

The worst two offenders the plan named by hand are meanwhile both gone:
`chitragupta/dossier/_cli.py::main` at 50 statements, and
`chitragupta/review/verbatim_check.py` at 1880 lines -- the latter split
into a package whose `__init__.py` is now 260.

**Six of the eight classes drained without a driver.** Between
2026-08-21 and 2026-08-27, three linter adoptions at a zero bar, #355's
annotation pass, and #294's compaction of the debt register emptied
every class the registers do not hold. Nothing that resembles the
proposed loop was involved. The design below is what is left once that
is admitted.

## Why the two loops advance differently

The rationale's opening section names it once -- **detection is built,
remediation is not** -- and the two halves have since diverged.

- The **drafting loop** is specified and partly built.
  `AUTO-IMPROVEMENT.md`'s build-order steps 1, 2, 3, 4 and 6 have
  shipped and step 7 is a closed, declined decision; only step 5's
  widening, F3, is live.
- The **developer loop** was described as "a regression brake with no
  driver". It turned out not to need one. `DEVELOPER-AGENTS.md` rule 3
  forbids opportunistic cleanup inside an unrelated diff, and that is
  still true -- but a debt taken deliberately, one PR at a time,
  cleared the register faster than a ranking aid would have found work
  for it.

The two designs remain **independent**: no shared module, no shared
requirement set, no cross-reference from the user-facing half to the
developer-facing half. A shared requirement set would force `AGENTS.md`
to name rules that also govern the developer loop, re-creating the
coupling this separation exists to avoid. (The developer half cites R3 below,
which is not a new coupling: `TECHNICAL-DEBT.md`'s inclusion criteria
already cite R3 by name, and `DEVELOPER-AGENTS.md` already says R3
"applies to code as written". Independence means not inheriting
R1--R11 as a governing set.)

## Decision 1 -- the amendment is approved

Twelve sites in code and prose, plus three diagrams, state that the
review aids are "never invoked automatically". The loop's driver invokes
them, so that wording becomes **"advisory, never blocking"**. The
surviving invariant, in the rationale's words: *a review finding may be
read, may be invoked by a driver, and may never block a draft.*
`chitragupta.draft gate` remains the only gate.

[SOUL.md](../SOUL.md) needs **no** change -- its review bullet only
claims the layer "never blocks, and must not be made to", which survives
intact. That is what makes this an amendment rather than a rewrite of the
project's premises.

Per F3, the amendment gates **automation only**. Person-triggered
widening needs no amendment, so F3 is not blocked on it.

## Decision 2 -- the pass bound is three

Three counters are easy to conflate. Only the second is being set here.

| Counter | Value | Status |
| --- | --- | --- |
| attempts per item | 2 | R7, unchanged |
| **passes per invocation** | **max 3** | **this change** (was 1) |
| invocations | unbounded, human-triggered | unchanged, and correct |

**The primary terminator is not the bound.** The loop continues only
while the objective-class finding count *strictly falls*. That count is a
non-negative integer, so the loop halts in at most N passes where N is
the count at the start. The hard maximum of 3 is a **backstop against a
miscounting bug**, not a cost control, and it must be documented as such
-- naming it wrong is how it later gets mistaken for the budget and stops
anyone adding a real one.

**Shipped as asked.** #381 put it in
`chitragupta/review/agenda/__init__.py` as `PASS_BOUND = 3`, a named
constant with the "backstop, not a budget" reasoning beside it, next to
the `Agenda.objective_class_count` property it bounds. Nothing loops on
it yet; F3 is what will.

**Measured, 2026-08-21, against the 21 real dossiers in this host's
corpus** (read-only; nothing was written):

| Class | Per draft | Unattended? |
| --- | --- | --- |
| `missing-citekey` | 0--2 (6 across all 21 dossiers) | yes |
| `verbatim-run` | 0--9 (four drafts scanned: 0, 3, 6, 9) | yes, minus the long runs #129 reserves |
| `prose` | see below | shipped as **no** -- surfaced |
| `candidate` | 7--155, median 49 | no -- surfaced |
| `unsupported-claim`, `uncited-source` | -- | no -- surfaced |

So N is 0--11 per invocation and three passes will almost never be
reached.

**Provenance of these numbers, because it qualifies them.** They were
measured against the checkout at `/workspace`, on the pre-rename commit
-- the commands were `src.review` / `src.draft`, not `chitragupta.*`.
The dossiers and drafts are the same real content, so the corpus counts
(6 missing, 1311 candidates, median 49) carry over unchanged. The
verbatim counts came from a different revision of `verbatim_check.py`
than this spec governs, so they were **re-measured against this
worktree and came back identical** (3 / 0 / 9 / 6). See Q4.

**`prose` does not move N, and the reason is a defect, not a
measurement.** The 2026-08-21 document made re-measuring N an acceptance
criterion for the prose producer, expecting N to jump into the dozens
once it landed. It landed -- #107 in 5.13.0, #183 in 5.19.0 -- and N did
not move, because `agenda/_items_findings.py`'s `prose_items` sets
`unattended=False` on every finding and `objective_class_count` counts
only unattended items. But `docs/AUTO-IMPROVEMENT.md`'s table says
`prose` *is* unattended for "the mechanically re-checkable subset", and
`prose_items`' own docstring argues that subset was already applied
upstream. Spec and code disagree; issue
[#421](https://github.com/prasadtalasila/chitragupta/issues/421) carries
it. **N = 0--11 stands today, and is contingent on that issue closing
the way the code currently behaves.**

**The R4 re-scan burden, measured properly.** R4 re-runs every aid after
every accepted edit -- roughly 22 full re-scans on an 11-item agenda at
two attempts each. Timed: `verbatim scan` 1s, `provenance` 2s,
`coverage` under 1s, so a full cycle is 3--4s and a pass costs on the
order of **80 seconds**, with three passes near four minutes. Modest,
and near-zero in tokens because the aids are deterministic Python -- but
not the "negligible" an earlier draft of this document claimed on the
strength of a mistimed run in which `coverage` had in fact exited 2 on
its argument shape.

## The developer loop -- retired, and what survives

The 2026-08-21 design was a ranking aid in `scripts/` that merged the
C1/C2 registers with `docs/TECHNICAL-DEBT.md`'s tiers into one worklist
of eight classes. **Do not build it.** On the re-measurement above it
would emit 20 entries from one source, in an order that source already
holds, with counts a test already keeps honest -- and
`plans/README.md`'s own bar ("do not write a plan for a change whose
whole design fits in its roadmap entry") applies at least as strongly
to the tool as to the plan.

Two smaller reasons, both worth stating so the aid is not re-proposed:

- **A test failure is already the report.** The C2 ratchet's own
  assertion prints each offender with its count and what to do about
  it. A second renderer of the same 20 lines is a second place the same
  fact is written.
- **Ranking is not the missing piece.** The register is ordered
  worst-first by construction and re-ordered whenever a count moves.
  What a maintainer actually lacks in front of
  `chitragupta/sync.py` at 548 lines is a *seam*, which is judgement --
  the 2026-08-21 table classified exactly that as `no -- surfaced`.

Three pieces of the design survive its retirement.

### 1. The allowlist pin, and the one thing it gates

`AUTO-IMPROVEMENT-RATIONALE.md` names the failure this prevents: a loop
that can edit its own allowlist "is gaming a metric rather than
improving a draft". **The register is this loop's allowlist**, and the
tension is sharper here than on the drafting side, because the ratchet
*requires* an edit to complete a repair -- a function that comes back
under 25 statements fails the test until its entry is deleted.

The rule, in the form a diff can be checked against:

> **Deleting a register entry is compelled. Adding one is gated on a
> stated reason. Changing a threshold is out of scope entirely.**

Deletion is already forced:
`test_the_function_register_holds_no_entry_that_is_already_fixed` fails
on an entry that has come back under its threshold, saying to delete it.
The other half has no detector. A ~30-line check over the PR diff --
fail if `LEGACY_LONG_FUNCTIONS`/`LEGACY_LONG_FILES` gained a line, or
`MAX_STATEMENTS`/`MAX_CODE_LINES` changed, unless the PR body says why
-- is the whole of it.

**It gates the escape hatch, not the debt, and that distinction is the
whole design.** The ratchet already fails on a new offender; adding a
register entry is how that failure gets excused rather than fixed; and
`plans/a1a-mandatory-verbatim-scan.md` already leans on this pin
forbidding exactly that move, calling it "the tempting fix" for a
module it must not grow. Gating the excuse leaves "leaving an entry
open forever is fine" completely untouched -- no unpaid item goes red,
which is what the third constraint below requires. What it stops is a
new entry arriving *silently*.

**It is a keyword grep, and saying so is the point.** A machine can
detect that the PR body names the register; it cannot check that the
reason is a reason. So this is not "mechanically checkable from both
sides", as the 2026-08-21 draft claimed -- one side is checked and the
other is made visible. That is also why the ratchet's own escape stays
open: its failure message says "if the split is genuinely wrong, add it
to LEGACY_LONG_FILES in this file and say why in the PR", and #405
exercised that path for `figure_layout/__init__.py`. The check makes
the addition impossible to make silently; a reviewer is still what
makes it hard to make badly.

### 2. The merge queue, which was always the real precondition

> **GitHub's merge queue is a precondition for any batch of debt PRs,
> not an unrelated improvement.**

`TECHNICAL-DEBT.md` says items come off "in its own pull request". Step
2 of `DEVELOPER-AGENTS.md`'s ten-step cycle requires every PR to bump
`[tool.poetry].version` in the same branch. So N debt PRs produce N
version bumps -- and `scripts/check_version_bump.py`'s docstring records
that two branches picking the same number "merges silently", which
happened three times on 2026-08-15, once reaching `main` and needing a
corrective PR. Step 7 asks a human to notice `main` moved and redo the
cycle by hand; the document is candid that a stale branch can go
**"green on a state that no longer exists."**

A merge queue tests each PR against the projected post-merge `main`
before landing, which converts step 7 from a discipline into a
mechanism. It is a repository setting, not code, and it is the one item
here that would still pay for itself with no loop at all. **Until it is
on, debt PRs go one at a time.**

### 3. The identity constraint, for whatever comes later

`docs/TECHNICAL-DEBT.md` renumbers its sections when an item closes --
its own "How something gets on this list" asks for numbers to be
"closed up when an item goes", and #294 deleted thirteen closed
sections and renumbered the survivors behind them. So a
section number is not an identity: item 3.7 today and item 3.7 next
month are different debts, and nothing could then decide whether a given
item had survived a revision.

This is the developer-side form of a rule the drafting half already
holds. `chitragupta/review/agenda/_identity.py` refuses line-based
identity for exactly the analogous reason, and says so:

> an identity built on `line` would rename every remaining item the
> moment an edit above it shifted line numbers.

**Section numbers are the developer-side line numbers.** Any future
class sourced from `TECHNICAL-DEBT.md` must key on a path, a call site
or a count -- the three things that document's own inclusion criteria
already require every entry to carry -- never on a tier number. The two
classes that survive today need none of this: a register entry's key
*is* `path::function` or `path`.

### Three constraints that still hold

- **R3's discipline: the check is "is it under the threshold", never
  "minimise the count".** This is why the surviving pieces are a
  diff-check and a setting rather than a driver aimed at emptying the
  register -- a loop rewarded for the count is a loop that will excuse
  an entry rather than split a function. `TECHNICAL-DEBT.md`'s own
  inclusion criteria say this and cite R3 by name; the retired ranking
  aid was the part of the 2026-08-21 design most exposed to getting it
  wrong, because a ranked worklist reads as a queue to empty.
- **Debt is not a gate, and nothing here makes it one.**
  `TECHNICAL-DEBT.md` is emphatic: nothing goes red because an item is
  unpaid, and "leaving an entry open forever is fine." This is the
  developer-side analogue of the review layer never blocking. The
  diff-check above does not touch it: it fires on a register *addition*
  in a diff, never on an item left unpaid.
- **`chitragupta.draft gate` remains the only gate.** Unchanged, and
  nothing here is promoted beside it.

### What would revive a developer-side aid

One shape, recorded so it is not confused with the retired one. Where
the ranking aid re-printed a worklist, a **seam proposer** would compute
the mechanical half of the judgement a maintainer actually makes: for
each registered module, the split the register's own comments describe
by hand. #405's entry already names one --

> The seam available is `build_parser`/`main`/`run`/`_command` into a
> `_cli.py`, which is a pure line-count move rather than a split by
> responsibility

-- and that is a claim about the import graph and the call graph, both
of which are `ast`-visible. It is L-sized, speculative, and nobody has
asked for it. It is here because it is the only version of a
developer-side tool that would add something the register does not
already say.

### It does not enter `review.AIDS`

Stated as a non-goal, since Q3 only implies it. `agenda` was the eighth
aid, and `support` (#386) is the ninth; registering a developer tool as
a tenth would put it in a drafting user's review layer, and would
trigger the sweep across `REVIEW.md`,
`FEATURES.md`, `PACKAGING.md` and four diagrams that
`chitragupta/review/__main__.py`'s import-time check enforces. The
developer loop's surface is `scripts/`, a test, and the ten-step cycle.

## Questions settled 2026-08-21

Four closed against rules and facts already in the repository, rather
than by preference. Q2 has since been reversed on evidence.

### Q1 -- does `AGENTS.md` name the drafting loop? Yes; R10 already says so

Not open. R10 requires that the aid and the skill "appear in AGENTS.md's
layer bullets, CLI.md, the README tables and `mkdocs.yml`", and
`AUTO-IMPROVEMENT.md`'s reachability table is blunt about the
consequence of omitting it: "An agent following AGENTS.md would not know
either exists." So `AGENTS.md` gains the drafting aid and skill.

It gains **nothing** about the developer loop. That asymmetry is the
whole user-facing/developer-facing split, and it is enforced by which
document names what, not by which files ship.

### Q2 -- REVERSED 2026-08-27: the register does not move

**The 2026-08-21 answer was a root-level `.toml` read by both
`tests/test_code_standards_scan.py` and the aid**, on the reasoning that
`tests/` is in `EXCLUDE_TOP_LEVEL` (`scripts/release.py`) and does not
ship, so an aid in `scripts/` reading a register under `tests/` would
work here and be broken in every release.

That reasoning was sound and is now moot: **there is no aid.** With one
consumer, the move buys nothing, and it was going to cost more than the
original answer counted. Three findings against it:

- **Its stated rationale is false of the parser.** "TOML keeps comments,
  which the current literals need" is true of the format and not of
  `tomllib`, which discards them:
  `tomllib.loads('a = 1  # 32')` returns `{'a': 1}`. The trailing
  `# 32` is load-bearing -- `_recorded_counts()` regex-parses
  `tests/test_code_standards_scan.py`'s own source, and
  `test_every_registered_offender_records_its_current_count`
  fails on a stale one -- so the move forces a choice the original
  answer never names: promote the count to a real TOML value and rewrite
  both the test and the "the comment is what a reader sees" rationale,
  or text-parse the TOML and gain nothing over the status quo.
- **The blast radius is four files and two pinned sentences**, none of
  them enumerated: the registers and `_recorded_counts` in
  `tests/test_code_standards_scan.py`, that file's
  `test_the_registers_are_the_size_this_document_says`,
  `docs/CODE-STANDARDS.md`'s "**3 functions** and **17 modules**"
  sentence which that test pins, `docs/TECHNICAL-DEBT.md`'s Tier 1 copy
  of the same pair, and `tests/test_technical_debt_scan.py`, which pins
  *that* and reaches the registers by
  `from test_code_standards_scan import LEGACY_LONG_FILES,
  LEGACY_LONG_FUNCTIONS` -- a cross-test import the move would have to
  rewrite as well.
- **The release-archive argument no longer applies.** It was entirely
  about an aid in `scripts/` reaching data under `tests/`. Nothing in
  `scripts/` reads the register.

**Reopen this only with the aid.** If a seam proposer is ever built, the
2026-08-21 reasoning becomes live again unchanged -- and the comment
question above is then the first thing to settle, not the last.

### Q3 -- the developer loop gets no skill

A script plus the existing cycle -- and, after this revision, not even
the script. Two reasons, the second decisive.

The drafting side needs a skill because a `SKILL.md` description *is*
the trigger mechanism for a user phrase. The developer side's trigger is
a maintainer deciding to spend a PR, and `DEVELOPER-AGENTS.md`'s
ten-step cycle already governs everything that follows -- a skill would
be a second process document competing with it.

Decisively: **`.claude/skills/` ships.** `tests/test_release.py`
asserts it by name -- `".claude/skills/survey-writer/SKILL.md" in paths`
-- because the genre skills are what cite `AGENTS.md` and "the two
have to travel together." A developer-loop skill would therefore
appear in a drafting user's unzipped release beside `survey-writer` and
`tutorial-writer`.

### Q4 -- verbatim counts re-measured, and they hold

The earlier figures came from the pre-rename checkout. Re-run against
**this** worktree's `chitragupta.review verbatim scan`, pointed at the
same corpus: `book-chapter` 3, `deep-research` 0, `survey` 9, `tutorial`
6 -- **identical**. The caveat is discharged, not merely noted.

### Q5 -- `coverage`'s query source is the dossier's `retrieval.md`

`coverage` exits 2 without `--query`, so R4's re-run needs a source. The
dossier already keeps one: `retrieval.md` records every retrieval call as
a table of `date | mode | query | asked | results | chars`, appended by
`draft retrieve --log` and "never by hand". `dossier status` already
replays exactly these to attribute a candidate to the query that
surfaced it.

So an R4 re-check uses **the draft's own recorded `retrieval.md`
queries**. Rows with mode `revision` are not calls and are skipped. This
also keeps the re-check honest: it measures coverage against what this
draft actually asked the corpus, not a query invented at re-check time.
`agenda`'s module docstring records this answer so F3 does not have to
re-derive it.

## Still open

**Two items, and neither is settleable by preference.**

**1. Is the `prose` class unattended?** Issue
[#421](https://github.com/prasadtalasila/chitragupta/issues/421).
`docs/AUTO-IMPROVEMENT.md`'s table says yes for the mechanically
re-checkable subset; `agenda/_items_findings.py` ships `unattended=False`
for every finding, with a docstring arguing the subset filter already
ran upstream. One of the two is wrong. This is the successor to the
2026-08-21 document's first open item -- which asked for N to be
re-measured once the prose producer landed, and is answered above: N did
not move, but by implementation rather than by construction. If the flag
is flipped to match the table, N moves after all and the three-pass
bound has to be re-measured then. **Decide this before F3 relies on the
bound.**

**2. The merge queue is not on.** Checked 2026-08-27: the active `main`
ruleset holds `deletion`, `non_fast_forward`, `required_linear_history`
and `pull_request`, and no `merge_queue` rule. Not a decision anyone has
declined -- nobody has taken it. It is a repository setting, it converts
the ten-step cycle's step 7 from a discipline into a mechanism, and it
pays for itself with or without a loop. Until it is on, debt PRs go one
at a time.

Two items from the 2026-08-21 list are closed by #381 and are recorded
here only so this document does not read as though they were dropped:
whether `missing-citekey` should be acted on unattended (**yes**), and
how the agenda should behave on a draft with no dossier (**a reduced
source set, not a refusal** -- so `agenda` keeps the layer's "exit 0
whatever it finds" posture rather than becoming the one aid that can
decline to run).
