# Adopting the two auto-improvement loops

Status: **decisions recorded, developer half designed.** Written
2026-08-21.

**#381 closed "Still open" items 2 and 3 below** (`missing-citekey` is
unattended; a draft with no dossier gets a reduced source set rather
than a refusal) when it built F2, the `agenda` aid -- see that section
for the answers as shipped. Item 1 is also moot now: the `prose` class
producer (#107/#183) landed before #381 did, so its contribution to N
was never actually zero-by-construction the way this item assumed. The
developer-side loop this plan is otherwise about remains unbuilt.

**This document does not restate [Theme F](../docs/FEATURE-ROADMAP.md).**
F1--F4 already carry the drafting loop's adoption -- `--json` on the
other two aids, the `agenda` aid, widening `overlap-reviser` into
`agenda-reviser`, and the gating decision that is closed rather than
pending. `plans/README.md` is explicit that restating a roadmap entry
"produces two documents that must agree", so where Theme F already
decides something, this file points at it and stops.

What is here is the part Theme F does not carry:

1. **Two decisions the user has now taken** -- the amendment, and the
   pass bound -- with the measurements behind the second.
2. **The developer-side loop**, which has no roadmap theme at all.
3. **Five questions settled** on 2026-08-21, four of them against rules
   already in the repository.

**Written for** whoever implements F2/F3 and whoever picks up the
developer loop. It assumes
[docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md),
[docs/AUTO-IMPROVEMENT-RATIONALE.md](../docs/AUTO-IMPROVEMENT-RATIONALE.md)
and [DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md).

## Why neither loop advances on its own

The rationale's opening section names it once and it applies twice:
**detection is built, remediation is not.**

- The **drafting loop** is specified and mostly unbuilt. It was blocked
  on one decision reserved for the user, now taken.
- The **developer loop** -- the C1/C2 ratchet plus
  [docs/TECHNICAL-DEBT.md](../docs/TECHNICAL-DEBT.md) -- is *built and
  enforced*, but is a regression brake with no driver. The register can
  only shrink; nothing proposes the next shrink, and
  `DEVELOPER-AGENTS.md` rule 3 deliberately forbids opportunistic
  cleanup inside an unrelated diff.

The two designs are **independent**: no shared module, no shared
requirement set, no cross-reference from the user-facing half to the
developer-facing half. A shared requirement set would force `AGENTS.md`
to name rules that also govern the developer loop, re-creating the
coupling this separation exists to avoid.

Independence means the developer half must **re-derive** the safety
rules, not drop them. Where it does, this document says so. (Part B
cites R3, which is not a new coupling: `TECHNICAL-DEBT.md`'s inclusion
criteria already cite R3 by name, and `DEVELOPER-AGENTS.md` already says
R3 "applies to code as written". Independence means not inheriting
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
project's premises, and it is why the rationale calls it the first thing
to settle before any code.

Per F3, the amendment gates **automation only**. Person-triggered
widening needs no amendment, so F1--F3 are not blocked on it.

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

**Measured, 2026-08-21, against the 21 real dossiers in this host's
corpus** (read-only; nothing was written):

| Class | Per draft | Unattended? |
| --- | --- | --- |
| `missing-citekey` | 0--2 (6 across all 21 dossiers) | yes |
| `verbatim-run` | 0--9 (four drafts scanned: 0, 3, 6, 9) | yes, minus the long runs #129 reserves |
| `prose` | 0 -- no producer until #103/#107 | partial |
| `candidate` | 7--155, median 49 | no -- surfaced |
| `unsupported-claim`, `uncited-source` | -- | no -- surfaced |

So N is 0--11 per invocation and three passes will almost never be
reached.

**Provenance of these numbers, because it qualifies them.** They were
measured against the checkout at `/workspace`, which is on the
pre-rename commit -- the commands were `src.review` / `src.draft`, not
`chitragupta.*`. The dossiers and drafts are the same real content, so
the corpus counts (6 missing, 1311 candidates, median 49) carry over
unchanged. The verbatim counts originally came from a different revision
of `verbatim_check.py` than this spec governs -- an 1880-line, actively
worked module -- so they were **re-measured against this worktree's
`chitragupta.review` and came back identical** (3 / 0 / 9 / 6). See
Q4 below.

**The R4 re-scan burden, measured properly.** R4 re-runs every aid after
every accepted edit -- roughly 22 full re-scans on an 11-item agenda at
two attempts each. Timed: `verbatim scan` 1s, `provenance` 2s,
`coverage` under 1s, so a full cycle is 3--4s and a pass costs on the
order of **80 seconds**, with three passes near four minutes. Modest,
and near-zero in tokens because the aids are deterministic Python -- but
not the "negligible" an earlier draft of this document claimed on the
strength of a mistimed run in which `coverage` had in fact exited 2 on
its argument shape.

**The one thing that would change this.** The `prose` class is empty *by
construction* until #103/#107 land. Style findings are numerous per
draft, so N could jump into the dozens and a 3-pass ceiling would begin
to bind for real. Therefore: **the bound is a named constant, not a
literal**, and it is re-measured when the prose producer lands.

## The developer loop -- a new design

### What it reads

Two sources, neither of which is a pipeline artefact. This is why the
loop belongs in `scripts/` and not in any of the four layers:
`DEVELOPER-AGENTS.md` already places dev tooling there, and
`ARCHITECTURE.md`'s artefact graph has no node for it.

- the C1/C2 registers, currently module-level literals in
  `tests/test_code_standards_scan.py` -- **21 entries**: 10 over-long
  functions (worst `chitragupta/dossier/_cli.py::main`, 50 statements)
  and 11 over-long modules (worst
  `chitragupta/review/verbatim_check.py`, 1880 lines);
- `docs/TECHNICAL-DEBT.md`'s tiers.

### The registers must move -- and this is a real decision, not a detail

An aid in `scripts/` importing from `tests/` is the wrong direction, and
the registers are the loop's own ground truth. Extract
`LEGACY_LONG_FUNCTIONS` and `LEGACY_LONG_FILES` to a data file that
**both** `tests/test_code_standards_scan.py` and the new aid read. "One
place a fact can be written" argues for it; the test keeps its authority
because it still fails on a new offender and on a stale entry.

If this is declined, the spec must say why and the aid must get its data
some other way. It may not import from `tests/`.

### The allowlist pin, re-derived

`AUTO-IMPROVEMENT-RATIONALE.md` names the failure mode this prevents: a
loop that can edit its own allowlist "is gaming a metric rather than
improving a draft". **The register is this loop's allowlist**, and the
tension is sharper here than on the drafting side, because the ratchet
*requires* an edit to complete a repair -- a function that comes back
under 25 statements fails the test until its entry is deleted.

The resolution is mechanically checkable:

> **The loop may DELETE a register entry. It may never add one, and it
> may never change a threshold.**

Deletion is not merely permitted on success -- it is **compelled**. The
ratchet already fails on an entry that has come back under its threshold,
saying to delete it. That is what makes the rule fully mechanical from
both sides: the existing test forces deletion on a real fix, and a diff
check on the register file forbids addition. Adding an entry is how an
over-long function would get "fixed" by being excused, which is the exact
failure the pin exists to stop.

### Item classes

The broader worklist was chosen deliberately over a register-only one.
Classification is what makes that safe: most `TECHNICAL-DEBT.md` items
have no detector *by design*, and an unattended loop must not act on
them. This table is the developer-side counterpart to the drafting
loop's six classes.

| Class | Source | Kind | Unattended? |
| --- | --- | --- | --- |
| `over-long-function` | C1 register | binary: under 25 statements or not | yes |
| `over-long-module` | C2 register | binary: under 250 code lines or not | yes |
| `inert-noqa` | TECHNICAL-DEBT 2 | 11 countable call sites | yes |
| `missing-annotation` | TECHNICAL-DEBT 2 | 394 of 433, countable per site | yes |
| `linter-baseline` | TECHNICAL-DEBT 5.2/5.3 | pylint / markdownlint, countable | yes |
| `duplication` | TECHNICAL-DEBT 3.2, 3.7, 3.8 | named call sites, but the fix is a design choice | no -- surfaced |
| `structural` | TECHNICAL-DEBT 3.4, 3.9, 4.x | judgement | no -- surfaced |
| `process` | standing-instruction budget, format adherence | judgement | no -- surfaced |

R3's discipline holds throughout: the check is *"is it under the
threshold"*, never *"minimise the count"*. `TECHNICAL-DEBT.md`'s own
inclusion criteria already say this, and cite R3 by name.

### Two constraints that must be stated, not assumed

- **Debt is not a gate, and this loop must not make it one.**
  `TECHNICAL-DEBT.md` is emphatic: nothing goes red because an item is
  unpaid, and "leaving an entry open forever is fine." An auto-repair
  driver must not convert the register into a de facto gate. This is the
  developer-side analogue of the review layer never blocking.
- **`chitragupta.draft gate` remains the only gate.** Unchanged, and
  nothing here is promoted beside it.

### Handoff, and the precondition nobody has noticed

The loop proposes; the **existing 10-step cycle in
`DEVELOPER-AGENTS.md` is the acceptance mechanism.** That is the
developer-side form of "the human closes the loop", and it already
exists, so the loop does not need its own acceptance ceremony.

But it creates a dependency that must be recorded:

> **GitHub's merge queue is a precondition for the developer loop, not an
> unrelated improvement.**

`TECHNICAL-DEBT.md` says items come off "in its own pull request". Step 2
of the cycle requires every PR to bump `[tool.poetry].version` in the
same branch. So a loop producing N debt PRs produces N version bumps --
and `scripts/check_version_bump.py`'s docstring records that two branches
picking the same number "merges silently", which happened three times on
2026-08-15, once reaching `main` and needing a corrective PR. Step 7
currently asks a human to notice `main` moved and redo the cycle by hand;
the doc is candid that a stale branch can go **"green on a state that no
longer exists."**

A merge queue tests each PR against the projected post-merge `main`
before landing, which converts step 7 from a discipline into a mechanism.
Until it is on, **the developer loop defaults to one open PR at a time.**

## Questions settled 2026-08-21

Four of the five closed against rules and facts already in the
repository, rather than by preference. Only one had a real dependency on
unbuilt work.

### Q1 -- does `AGENTS.md` name the drafting loop? Yes; R10 already says so

Not open. R10 requires that the aid and the skill "appear in AGENTS.md's
layer bullets, CLI.md, the README tables and `mkdocs.yml`", and
`AUTO-IMPROVEMENT.md`'s reachability table is blunt about the
consequence of omitting it: "An agent following AGENTS.md would not know
either exists." So `AGENTS.md` gains the drafting aid and skill.

It gains **nothing** about the developer loop. That asymmetry is the
whole user-facing/developer-facing split, and it is enforced by which
document names what, not by which files ship.

### Q2 -- register format: a root-level TOML file

Not a matter of taste; `tests/` is in `EXCLUDE_TOP_LEVEL`
(`scripts/release.py:53`) and does not ship, while `scripts/` does. A
dev-loop aid in `scripts/` reading a register that lives under `tests/`
would work here and be **broken in every release**, referencing a file
the archive never contains.

So the register moves to a **root-level `.toml`** that both
`tests/test_code_standards_scan.py` and the aid read:

- it ships, so the aid works in an unzipped release;
- it is data, not code, so it is outside C1/C2 and cannot itself become
  an over-long module;
- `tomllib` is stdlib and already used (`scripts/check_version_bump.py`),
  so it adds no dependency;
- TOML keeps comments, which the current literals need -- the trailing
  `# 50` on each entry exists so "the size of each debt is visible
  without running anything."

The test keeps its authority: it still fails on a new offender and on a
stale entry. Only the storage location changes.

### Q3 -- the developer loop gets no skill

A script plus the existing cycle. Two reasons, the second decisive.

The drafting side needs a skill because a `SKILL.md` description *is* the
trigger mechanism for a user phrase. The developer side's trigger is a
maintainer deciding to spend a PR, and `DEVELOPER-AGENTS.md`'s ten-step
cycle already governs everything that follows -- a skill would be a
second process document competing with it.

Decisively: **`.claude/skills/` ships.** `tests/test_release.py:110`
asserts it, because the genre skills are what cite `AGENTS.md` and "the
two have to travel together." A developer-loop skill would therefore
appear in a drafting user's unzipped release beside `survey-writer` and
`tutorial-writer`. The deterministic aid emits the ranked worklist; a
person picks an item and runs the ordinary cycle.

### Q4 -- verbatim counts re-measured, and they hold

The earlier figures came from the pre-rename checkout. Re-run against
**this** worktree's `chitragupta.review verbatim scan`, pointed at the
same corpus: `book-chapter` 3, `deep-research` 0, `survey` 9, `tutorial`
6 -- **identical**. The caveat is discharged, not merely noted, and
N = 0--11 stands.

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

## Still open

**Three items, and none is settleable by preference.**

**1. The `prose` class cannot be measured yet.** It has no producer until
issues #103/#107 land, so its contribution to N is zero *by construction*.
Style findings are numerous per draft, so N could move into the dozens
and the three-pass bound could begin to bind for real. The bound is
therefore a **named constant**, and re-measuring it is an acceptance
criterion for whichever of #103/#107 lands second.

**2. Should `missing-citekey` be acted on unattended at all?** *Closed
by #381, decided yes.* This raised the question and, at the time this
plan was written, explicitly did not close it -- `AUTO-IMPROVEMENT.md`'s
"yes" was inherited as an assumption rather than a decision. It was the
smaller of the two unattended classes (6 findings across all 21
dossiers), decided on its own merits rather than by default.

**3. How should the agenda behave on a draft with no dossier?** *Closed
by #381: a reduced source set, not a refusal.* The roadmap had quoted the
live possibility that *"refusing may be the right answer here even
though no other aid refuses"* -- decided against, so `agenda` keeps the
layer's "exit 0 whatever it finds" posture rather than becoming the one
aid that can decline to run.

Items 2 and 3 belonged to F2 and were recorded here only so this document
did not read as though it had closed them; both are now closed, by #381.
