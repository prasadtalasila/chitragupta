# Widening `overlap-reviser` into `agenda-reviser`

Status: **designed, unbuilt.** Written 2026-08-27, for
[issue 384](https://github.com/prasadtalasila/chitragupta/issues/384) --
[F3](../docs/FEATURE-ROADMAP.md#-f3-widen-overlap-reviser-into-agenda-reviser),
build-order step 5 of
[docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md).

**Two issues, one plan.**
[Issue 421](https://github.com/prasadtalasila/chitragupta/issues/421)
was filed separately and is exactly Decision 1 below -- it asks for the
`prose` flag to be reconciled and does not take the decision. PR 1
closes it; PR 2 closes 384. They are kept as two `Closes` lines rather
than one comma list, because a comma list closes only the first.

**Written for** whoever builds F3. **It assumes**
[docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md) for R1--R11 and
the item-class table,
[plans/f-auto-improvement-adoption.md](f-auto-improvement-adoption.md)
for the three counters and the amendment, and
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the cycle each PR
below runs.

**Not covered here:** the developer-side loop, which is
`f-auto-improvement-adoption.md`'s Part B and shares no module with
this; and the gating decision (F4), closed and declined.

Everything in this file that contradicts the issue or an existing
document does so **on a measurement recorded below**, never on
preference. Where a number is quoted, the command that produced it is
named.

## 🔬 What was measured, and what it overturns

Three of this track's standing figures were re-taken on 2026-08-27
against the checkout this plan governs. All three moved, and one moved
enough to change a design.

### The R4 cycle costs 25 seconds, not 3--4

`f-auto-improvement-adoption.md` records `verbatim scan` 1s,
`provenance` 2s, `coverage` under 1s -- *"a full cycle is 3--4s and a
pass costs on the order of 80 seconds, with three passes near four
minutes."* That covered three aids. There are seven now, plus `style`,
the gate and `agenda` itself.

**Re-measured across five drafts** spanning 1,258 to 18,061 words, with
and without a dossier, at `--formats md`. Every figure is milliseconds,
and every aid is deterministic stdlib-or-local Python, so **the token
cost of this entire table is zero**:

| words | dossier | prov | verbatim | cover | synth | figure | uncited | quote | agenda | **cycle** |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,258 | no | 180 | 447 | 303 | 90 | 87 | 88 | 89 | 575 | **1,859** |
| 2,448 | no | 366 | 474 | 303 | 90 | 89 | 92 | 92 | 577 | **2,083** |
| 5,723 | yes | 144 | 19,737 | 310 | 95 | 486 | 99 | 88 | 508 | **21,467** |
| 10,003 | yes | 332 | 41,019 | 314 | 96 | 818 | 109 | 88 | 1,017 | **43,793** |
| 18,061 | yes | 277 | 35,698 | 315 | 98 | 641 | 121 | 90 | 1,282 | **38,522** |

**There is no single cycle cost, and quoting one is the mistake this
table exists to prevent.** It ranges from 1.9 s to 43.8 s -- a factor of
23 -- and the variable is not draft length.

- **`verbatim` is the whole story: 447 ms without the embedding tier,
  19.7--41.0 s with it.** The tier needs the dossier, the Docling
  sidecars and the enrichment layer together, so the two dossier-less
  drafts above simply do not pay it.
- **Its cost tracks distinct cited sources, not words.** The
  18,061-word chapter cites 28 and costs 35.7 s; the 10,003-word
  chapter cites 40 and costs 41.0 s. Roughly **1.0--1.5 s per distinct
  citekey**, because the tier compares each section against the sources
  that section cites.
- **Everything else is nearly free and nearly flat.** `synthesis`,
  `uncited` and `quotation` sit within noise of the ~86 ms interpreter
  startup floor; `coverage` is flat at ~305 ms because its work is a
  corpus query, not a draft scan.

**A book chapter is the unit that matters here.** This project's own
chapters are 10,000--18,000 words, where the cycle is **38.5--43.8 s** --
roughly double the 21.5 s of the 5,723-word chapter. Costing a pass off
the smaller draft understates it by half.

### What a pass therefore costs

R4 runs one cycle per accepted edit. N is 0--17 (Decision 1) at up to
two attempts each, so a pass is **0--34 cycles**:

| Draft | Cycle | Worst-case pass | Three passes |
| --- | ---: | ---: | ---: |
| dossier-less, ~2,000 words | 1.9 s | ~1 min | ~3 min |
| chapter, 5,723 words | 21.5 s | ~12 min | ~36 min |
| chapter, 10,003 words | 43.8 s | **~25 min** | **~74 min** |

**State the range, never a single number.** The figure on record is *"a
pass on the order of 80 seconds, three passes near four minutes"*. The
top of the measured range is out by a factor of eighteen; the bottom is
roughly right. Both are true, of different drafts.

### Peak memory, which bounds what can be parallelised

| Aid | Peak RSS |
| --- | ---: |
| `verbatim` | **1,492 MB** |
| `coverage`, `agenda` | 73 MB |
| `provenance` | 32 MB |
| `synthesis`, `uncited`, `quotation` | 23 MB |

The overlap index on disk is 547 MB across `index.bin` and
`skipgram_index.bin`, against a corpus of 642 ledger items and 6.4
million parsed words. This is a second reason not to parallelise the
cycle, beside the ceiling Decision 4 already gives: seven aids in
parallel is not seven times 23 MB, it is 1.5 GB plus change, because one
of them dominates memory the same way it dominates time.

### One aid's cost is not measured, and cannot be here

`quotation` returns in ~90 ms because it has **nothing to check**: zero
`quote:` lines exist in any dossier on this host, so its input universe
is empty on every real draft. Its ~90 ms is the cost of finding no work,
not the cost of doing it. Read that row as unmeasured rather than cheap,
and re-measure it if the A2 quote contract is ever adopted.

### `verbatim scan` has no cache, and the shipped skill says it does

Three consecutive scans of an unchanged draft: **20,172 / 20,141 /
20,340 ms**. There is no cache; the embedding tier re-runs every time,
which its own output confirms (`tier=embedding` on seven findings).

`.claude/skills/overlap-reviser/SKILL.md` step 2 tells the agent:

> *"Re-scanning is a sub-second cache hit, so there is nothing to save
> by reusing an old one."*

That is wrong by about four orders of magnitude on any draft where the
embedding tier runs, which is the configuration this project's own
corpus is in.

**And the repository already said so.**
`docs/PLAGIARISM-DESIGN.md` records that the enrichment layer's cache
does not cover tier 3's window vectors, and `docs/PLAGIARISM.md` has
priced a full scan in tens of seconds since it was written. The skill
contradicted two shipped documents, so this is a **skill defect, not an
open question** -- and it does not depend on F3. It is listed under
PR 2 only because that PR rewrites the file; it should be fixed whether
or not F3 proceeds.

`verbatim recheck` is not the cheap alternative its name suggests
either: **19,760 ms**, because it re-scans and only the baseline
comparison on top is free.

### The `prose` class is 0--6 per draft, not "dozens"

`f-auto-improvement-adoption.md`'s "Still open" item 1 reserved the
possibility that once the prose producer landed, *"N could move into
the dozens and the three-pass bound could begin to bind for real"*, and
made re-measuring it an acceptance criterion for whichever of issues
103 and 107 landed second. Both have landed. The re-measurement is
therefore owed, and this is it -- `draft style --json` over the four
real drafts:

| Draft | prose findings | Rules |
| --- | --- | --- |
| `deep-research` | 6 | `Acronyms` x5, `Just` x1 |
| `tutorial` | 2 | `Just`, `Acronyms` |
| `survey` | 2 | `Acronyms`, `TableNoCaption` |
| `book-chapter` | 0 | -- |

**The bound does not begin to bind.** N with prose included is 0--17,
so `PASS_BOUND = 3` stays a backstop against a miscounting bug rather
than a budget, exactly as Decision 2 requires it to be described.

One line falls with this: `chitragupta/review/agenda/_sources.py`'s
`StyleSource` docstring calls `prose` *"otherwise the most populous
class"*. On this corpus it is not -- `candidate` is, at 7--155 with a
median of 49.

### Two smaller corrections to the issue's own text

- The issue says *"three classes are surfaced"*. That was true of a
  six-class table. The table has eight classes now and **five** are
  surfaced: `unsupported-claim`, `uncited-source`, `uncited-claim`,
  `misquoted`, `candidate`.
- The issue treats the widening as reaching "the other classes". Before
  the decisions below, the agenda marks exactly two things
  `unattended`: `missing-citekey`, and `verbatim-run` at
  `severity == "short"`. The second is what `overlap-reviser` already
  repairs, so a literal reading of "the agenda decides" would make F3 a
  25-file rename that buys **one** new class, worth six findings across
  all 21 dossiers.

## ✅ Decision 1 -- the `prose` class becomes unattended

Three statements exist about `prose`. Two agree; the third is visibly
damaged.

- `docs/AUTO-IMPROVEMENT.md`'s class table, in its **"Unattended?"**
  column, reads *"only the mechanically re-checkable subset"* -- an
  answer of yes, for that subset.
- `chitragupta/review/agenda/_items_findings.py`'s `prose_items`
  docstring says the class *"already restricts itself to the decidable
  rules of docs/WRITING-STANDARDS.md's Section 9, so no further
  filtering for 'mechanically re-checkable' is needed here"* -- every
  prose item **is** the subset. Three lines later it sets
  `unattended=False`.
- `docs/CLI.md` lists prose under *"merely surfaced ... everything
  judgement-shaped"*. That sentence calls the mechanically re-checkable
  subset judgement-shaped, which is the definition of the other
  category, and it omits `misquoted`, which is genuinely surfaced. It
  is a damaged transcription, not a recorded decision.

No document argues the surfaced position, and the agenda module has one
commit. The likeliest history is that issue 381 had no consumer for
`unattended` and the conservative default cost nothing.

**The strongest counter-argument, which issue 421 states and this plan
must answer.** Two other classes are binary and deterministic yet still
surfaced, so "mechanically re-checkable" plainly is not sufficient on
its own. Why does `prose` not join them? Because neither is surfaced
*for failing R3* -- the table says both satisfy it. `uncited-claim` is
surfaced because *"the fix is evidence, not wording, and a reviser
rewording one would make it look supported without making it
supported"*; `misquoted` because *"the defect is in `evidence.md`, and
`agenda-reviser` edits drafts."*

So the real discriminator is not the check -- it is whether the repair
lies inside the write-set and genuinely fixes the defect rather than
hiding it. **`prose` passes both tests where those two fail.** The
repair is an edit to the draft, which is R1's write-set exactly; and
expanding an acronym or adding a caption fixes the finding rather than
disguising it, because there is no underlying evidential claim for the
edit to misrepresent. That is why prose flips and those two do not.

**R3 was tested rather than argued.** A scratch draft carrying an
uncaptioned table and an unreferenced figure reported
`chitragupta.TableNoCaption` and `chitragupta.FigureUnreferenced`;
adding a pandoc caption line with its `<!-- table: -->` marker and an
inline `<!-- figureref: -->` took `draft style` to **zero findings**.
Both repairs are binary and re-checkable by re-running one deterministic
command, which is all R3 asks.

**So the flag flips for the whole class, and no per-rule filter is
built.** A filter whose every entry is `True` is the thing
`prose_items`' own docstring already rules out. Rule coverage follows
for free: `style_check.check()` returns one flat `findings` list
combining Vale's rules, acronym drift, `style_tables` and
`style_figures`, so one flag covers all of them.

## ✅ Decision 2 -- `FigureNoCaption` is added, and §10 is amended

**This one reverses a decision that shipped two commits ago, and is
recorded as a user decision taken on 2026-08-27 rather than derived
from anything in the repository.**

`chitragupta/style_figures.py` carries a bolded carve-out --
*"**Deliberately no `FigureNoCaption` or `FigureNoId`.**"* -- resting on
`docs/WRITING-STANDARDS.md` §10, which since issue 411 states that *"a
figure with no caption line below it is unchanged -- still §10's
accepted uncaptioned case."*

The user's position is that an uncaptioned figure is a legacy artefact
of drafts generated by older versions of this pipeline, not a design
choice, and that missing table and figure captions should be identified
and repaired on the same footing as any other prose finding. §10
therefore stops accepting the uncaptioned case.

**Three boundaries this amendment does not cross:**

1. **`FigureNoId` stays absent.** A figure marker names the figure's
   base name, so it carries an id by construction; there is no
   marker-with-no-id state for a rule to find. The carve-out's second
   half survives on its own reasoning.
2. **The renderer does not change.** An uncaptioned marker still
   renders unnumbered, still matches neither caption pass, and is still
   invisible to `figureref` resolution. Every assertion in
   `tests/test_render_output_figure_captions.py` stands. What changes is
   only that `draft style` now reports the state -- a style finding, not
   a render failure, so no legacy draft stops rendering.
3. **It is not a gate.** `draft style` exits 0 whatever it finds, as it
   does today.

## ✅ Decision 3 -- a `missing-citekey` is de-cited, and the claim escalates

Issue 381 settled *that* this class is unattended. Nothing settled what
the repair is, and the options are narrow: the skill may not run
`corpus sync` (it takes the write lock and is the user's), may not
fabricate a citekey, and may not add a claim. Every available unattended
repair is therefore a deletion.

**The repair is: remove the `[@citekey]` marker so the gate passes,
leave the sentence standing, and escalate the now-uncited claim to the
human in the closing report.**

- It is the smaller diff, which R8 requires where two repairs both pass.
- It never silently deletes authored prose from a finished draft.
- The sentence it leaves behind becomes an `uncited-claim` on the next
  agenda -- a **surfaced** class, so the loop reports it and cannot
  repair it away. The consequence of the repair is visible in the same
  instrument that measures the loop, which is what stops this being a
  way to make a draft look better than it is.

  **Verified, not assumed.** A probe draft with two cited sentences had
  one marker removed from each of two blocks; `review uncited --json`
  went from 0 findings to 2, catching **both** the sentence whose block
  still carried another citation (`block_cites: true`) and the one whose
  block carried none (`block_cites: false`). The escalation is visible
  in either case, which is what this argument needs.

Where the sentence carries another citation that survives, only the
marker goes and nothing escalates.

## ✅ Decision 4 -- R4 stays per-item, and batching is a reserved lever

At 1.9--43.8 s a cycle, R4's *"after each accepted edit, every aid re-runs"*
is the dominant cost of the whole feature: 0--17 items at up to two
attempts is 0--34 cycles, so **a worst-case pass on a book chapter is
about 25 minutes**, and on a short dossier-less draft about one.

**Keep R4 exactly as written.** Reasons, in order:

- The expensive aid is the one that cannot be dropped. `verbatim scan`
  is **90--94%** of any cycle where the embedding tier runs, and R4
  exists precisely to catch *"a rewrite that fixes its own finding by
  lifting from a different source"* -- which is a verbatim finding.
  Every cheap aid could be dropped and the cycle would still cost
  19--41 s.
- Running the aids concurrently caps the saving at about 6--10%, since
  one aid dominates -- and the memory does not add up the way that
  arithmetic suggests, because `verbatim` peaks at **1,492 MB** against
  23--73 MB for every other aid. Not worth the machinery.
- The cost is wall-clock on a deterministic, zero-token, human-triggered
  operation. It is not a token cost and not a CI cost.

**One consequence to state rather than discover.** With `prose`
objective, R4's *"the total objective-class count must not rise"* now
couples classes that were independent: a `verbatim-run` repair that
introduces an unexpanded acronym or a `Just` raises the prose count and
**reverts the verbatim repair**. That is the correct reading of R4 --
the count is a total, and a repair that breaks something else is exactly
what it exists to catch -- but it is new behaviour, and it needs its own
test rather than being left for a reviewer to find.

**The reserved lever, if this ever binds:** one R4 cycle per *batch* of
same-class repairs instead of per item, with revert granularity staying
per item (R5 is about restoring one item's text, not about when the
scan runs). The trade is that a batch which raises the count must be
bisected or reverted whole. **That would be an amendment to a numbered
requirement**, and it must be taken and written down as one, not
reinterpreted quietly inside a skill.

## ✅ Decision 5 -- two PRs, not one

The issue and the roadmap both frame F3 as one PR of size L. Decisions
1 and 2 have since added a new detector and a writing-standards
amendment to its scope, so the seam is worth taking:

| | PR 1 -- what the agenda says | PR 2 -- what a skill does with it |
| --- | --- | --- |
| Layers | review + drafting | skills + docs |
| Shape | deterministic Python and prose | `SKILL.md` and a rename sweep |
| Testable alone | yes | yes, against PR 1's payload |

The earlier argument against splitting was that PR 1 would be *"flip a
boolean nothing consumes yet"*. **That is no longer what PR 1 is**: it
now carries `FigureNoCaption`, the §10 amendment and two payload fields,
each of which stands on its own merits. The one real cost is a second
version bump on a stacked pair, which
`scripts/check_version_bump.py`'s docstring records as having gone wrong
three times on 2026-08-15 -- so **check the tags, not just `main`,
before picking PR 2's number**.

## ✅ Decision 6 -- the R4 cycle becomes `agenda --baseline`, and it refreshes

**Decided 2026-08-27.** The cycle becomes one deterministic command,
built in PR 1, and it **re-runs the seven aids itself** rather than
refusing on a stale input.

[Issue 385](https://github.com/prasadtalasila/chitragupta/issues/385)
(B5, depends on this work) is why the question arose: *"Take that
machinery from #384 rather than re-deriving it there and here."* Its
consumers are the seven genre skills at their pre-gate step, so an R4
cycle that exists only as prose in one `SKILL.md` is a cycle seven
skills re-derive -- including the staleness rule, which is the part
prose is likeliest to get wrong and whose failure is **silent**: a
naive re-run of `agenda` alone reads pre-edit JSON and reports a
finding resolved that is not.

### The invariant this reverses, and the scope of the reversal

`chitragupta/review/agenda/__init__.py` states, in bold: **"Reads,
never invokes."** Refreshing breaks that, and the break must be
**scoped to the new mode, not to the aid**:

| Command | Contract |
| --- | --- |
| `review agenda <draft>` | unchanged -- reads the aids' `.json` off disk, never runs one, 0.5 s |
| `review agenda <draft> --baseline <stem>.agenda.json` | re-runs the seven aids, rebuilds, compares, ~21 s |

Keeping the bare form untouched is not politeness -- it is what stops
this being a breaking change to a command that `docs/CLI.md`,
`docs/AUTO-IMPROVEMENT.md`, R10's registration and the existing tests
all describe as free and read-only.

**A flag, not a subcommand.** `verbatim` takes an explicit mode
(`verbatim scan`), but its bare form does not exist, so it is no
precedent for adding an optional mode to a command whose bare form is
already documented and tested. `--baseline` avoids restructuring the
CLI and makes the two contracts visible in the command line. If the
implementer finds argparse makes a `recheck` subcommand cleaner without
breaking `review agenda <draft>`, that is a fair substitution -- the
contract above is what matters, not the spelling.

### Three things refreshing makes this command own

1. **`coverage`'s `--query`.** Q5 of
   `f-auto-improvement-adoption.md` answers where it comes from -- the
   draft's own `retrieval.md` rows, skipping mode `revision`. That was
   going to be a skill's job; refreshing makes it **this command's**,
   which is better: it is deterministic, and it is written once.
   Reading the dossier is already established here, since `agenda`
   calls `dossier.drift()` in-process.
2. **`--formats md` while refreshing.** Only three aids render at all --
   `provenance` drops 1,502 ms to 140, `coverage` 1,390 to 304, `agenda`
   1,822 to 525, about **2.5 s a cycle** and 21 PDF renders a pass. The
   other four write no report for these drafts and save nothing. The
   consequence to state: **each aid's `.tex`/`.pdf` goes stale against
   its `.md` during a pass**, which is acceptable only because reports
   are regenerable and carry no timestamp -- so the pass ends with one
   full-format run of every aid, and that is what the human reads.
3. **Its own module.** `agenda/_recheck.py`, mirroring
   `verbatim_check/_recheck.py`, and under the 250-code-line cap
   `docs/CODE-STANDARDS.md` enforces.

### What it emits

`verbatim recheck`'s payload shape, because the skill already has to
read that one: `resolved` / `persisting` / `new`, plus
`objective_before`, `objective_after` and `objective_delta`. That gives
R3 (is this item's `id` in `resolved`?) and R4 (did the total rise?) as
two field lookups instead of a model comparing two JSON documents by
hand.

### Revised cost

The 2.5 s a cycle this saves is real but small against a cycle ranging
**1.9--43.8 s**, so it does not change Decision 4 -- it strengthens it.
`verbatim` is 90--94% of any cycle where the embedding tier runs, so the
expensive aid remains the one that cannot be dropped, and the pass costs
in "What a pass therefore costs" above are the figures to plan against.

## 📦 PR 1 -- the detectors and the flags

`Closes #421.`

### Code

- `chitragupta/style_figures.py` -- add `no-caption` to `RULES` as
  `chitragupta.FigureNoCaption` and the check that raises it; reverse
  the module docstring's carve-out, keeping its `FigureNoId` half and
  its stated reason.
- `chitragupta/review/agenda/_items_findings.py` -- `prose_items` sets
  `unattended=True`. Its docstring gains the R3 evidence: the class is
  the mechanically re-checkable subset, tested, not asserted.
- `chitragupta/review/agenda/__init__.py` -- **`objective_class_count`'s
  docstring becomes wrong the moment that flag flips.** It currently
  reads *"unattended items only (`missing-citekey`, and verbatim-run's
  `"short"` bucket)"*, and this is the number the loop terminates on, so
  a stale description of it is the most expensive comment in the module.
  Update it to name `prose` as the third contributor.
- `chitragupta/review/agenda/_sources.py` -- correct `StyleSource`'s
  *"most populous class"* claim.
- `chitragupta/review/agenda/_render.py` -- `agenda_payload` gains
  `pass_bound` and `objective_class_count`.
- `chitragupta/review/agenda/_recheck.py` -- **new**, Decision 6: the
  `--baseline` mode, the seven-aid refresh at `--formats md`, the
  `retrieval.md` query source for `coverage`, and `verbatim
  recheck`'s payload shape. The module docstring's bolded *"Reads,
  never invokes"* is rescoped to the bare `agenda` mode, not deleted --
  it is still true of the command every other caller uses.

**Why those two fields are not optional.** `PASS_BOUND` lives only as a
Python constant and `objective_class_count` only as a property on
`Agenda`; neither is serialised. A `SKILL.md` cannot import either. If
the payload does not carry them, PR 2's skill hardcodes `3` in prose --
and *"a named constant, not a literal"* is exactly what Decision 2 of
`f-auto-improvement-adoption.md` forbids, for exactly the reason it
gives: it is how the backstop later gets mistaken for a budget.

### Prose

- `docs/WRITING-STANDARDS.md` §10 -- the amendment. Four sites: the
  *"unchanged / still §10's accepted uncaptioned case"* paragraph, the
  *"There is no `chitragupta.FigureNoCaption` or `FigureNoId`"*
  sentence, the marker-renders-unnumbered paragraph, and §9's
  decidability table row reading *"An uncaptioned figure is exempt from
  this row by design, not by gap"*.
- `docs/CLI.md` -- add `chitragupta.FigureNoCaption` to the style-rule
  table; correct the *"an uncaptioned one is accepted by §10"* line;
  repair the damaged surfaced/unattended sentence in the `review agenda`
  section, which must now read `prose` as unattended and add `misquoted`
  to the surfaced list; and document `--baseline` in that section's flag
  table, including that it is the one mode which runs other aids.
- `docs/AUTO-IMPROVEMENT.md` and `chitragupta/review/agenda/__init__.py`
  -- both say `agenda` *"reads, never runs, an aid"*. Decision 6 makes
  that true of the bare command and false of `--baseline`, so both must
  say which mode they mean rather than being left to read as absolute.
- `docs/AUTO-IMPROVEMENT.md` -- the class table's `prose` row states the
  flag as shipped; the build-order note records the re-measurement.
- `plans/f-auto-improvement-adoption.md` -- **issue 421 requires this
  and this plan would otherwise have missed it**: *"Decision 2 should
  record the outcome, since the pass bound depends on it."* Two sites
  go stale together -- Decision 2's own table, and "Still open" item 1,
  whose prediction that N would move "into the dozens" is now measured
  and false. `plans/README.md` allows a plan to go stale, but not one
  whose own issue asks for it to be updated.
- `chitragupta/render_output/_figure_captions.py` and
  `docs/RENDERING-FLOW.md` -- reword *"§10's accepted case"* where it
  names the amended text. **Behaviour unchanged in both**; this is a
  naming sweep, and saying so in the PR body keeps a reviewer from
  looking for a render change that is not there.
- Four skills state the accepted case in passing and must not contradict
  §10 after it changes: `survey-writer`,
  `textbook-chapter-writer`, `book-assembler`, `draft-reviser`.

### PR 1's tests, to the 100% bar

- `tests/test_style_figures.py` -- its module docstring and
  `test_an_uncaptioned_marker_reports_nothing` invert. A figure with a
  caption still reports nothing; one without now reports
  `FigureNoCaption`; the `FigureNoId` absence is still asserted and
  still for its own reason.
- The agenda's own tests -- a prose item is `unattended`; the payload
  carries `pass_bound` and `objective_class_count`; the count matches
  the number of `unattended` items.
- `--baseline`'s tests (Decision 6) -- a resolved item appears in
  `resolved`; a new finding raises `objective_delta`; the bare
  `review agenda <draft>` still runs no aid and still costs a fraction
  of the refresh; `coverage`'s query comes from `retrieval.md` with
  mode `revision` rows skipped; a draft with no `retrieval.md`
  degrades rather than raising.
- `tests/test_render_output_figure_captions.py` -- **must pass
  unchanged.** That is the assertion that Decision 2's boundary 2 held.

## 📦 PR 2 -- the skill

`Closes #384.`

### The rename

`.claude/skills/overlap-reviser/` becomes
`.claude/skills/agenda-reviser/`, frontmatter `name` included. Swept:
`docs/` (`GENRE.md`, `REVIEW.md`, `CLI.md`, `PLAGIARISM.md`,
`ARCHITECTURE.md`, `FEATURES.md`, `REQUIREMENTS.md`, `DOSSIER.md`,
`HOOKS.md`, `FEATURE-ROADMAP.md`, `AUTO-IMPROVEMENT.md`),
`.claude/skills/` (eight other skills hand off to it by name),
`AGENTS.md`, `DEVELOPER.md`, three test modules
(`test_skill_acronym_step.py`, `test_skill_verbatim_scan_step.py`,
`test_feature_workflows.py`), and
`chitragupta/review/agenda/_items_findings.py`'s comment.

**The anchor is the trap.** `docs/GENRE.md`'s heading gives
`#-repairing-overlap-overlap-reviser`, and three files link to it:
`docs/PLAGIARISM.md`, `docs/CLI.md`, `docs/REVIEW.md`. Renaming the
heading breaks all three, and the link check runs **after** the build,
so `mkdocs build --strict` will not catch it.

**Deliberately not swept:** `plans/` and `bench/RESULTS.md`. Both record
what was true when written -- `plans/README.md` says this directory *"is
allowed to go stale"* -- and rewriting a merged plan to match a later
rename destroys the record it exists to be. `docs/` is held to the
opposite contract and is swept in full.

### The widening

The skill's shape does not change; its input and its work do.

- **Input.** `python -m chitragupta.review agenda <draft>` replaces
  `verbatim scan --json` as the worklist. Which items it may act on is
  read from each item's `unattended` field -- **never re-derived in the
  skill**, which is the issue's own instruction and what keeps one
  answer in one place.
- **Repair payload.** An agenda item's `detail` is thin by design: a
  `verbatim-run` item carries `verbatim_id` but **not** `draft_text`,
  which the repair needs as its `Edit` `old_string` (the CRLF caveat in
  the current skill is about exactly that field). So: **the agenda is
  the worklist; the raising aid's own `.json` is the repair payload**,
  looked up by the id in `detail`. Write that down rather than letting
  it be discovered mid-implementation.
- **Staleness.** `agenda` *reads* the aids' JSON off disk and never runs
  an aid, and marks a report older than the draft as stale via an mtime
  comparison. A re-run of `agenda` alone after an edit would therefore
  read pre-edit findings and report a finding as resolved that is not.
  **Decision 6 makes one R4 cycle one command:**

  ```bash
  python -m chitragupta.review agenda <draft> \
      --baseline content/review/<topic>/<stem>.agenda.json --json
  ```

  It refreshes the seven aids, rebuilds the agenda and reports
  `resolved` / `persisting` / `new` with an `objective_delta`. The
  skill must **not** hand-roll the refresh: a bare `review agenda`
  after an edit reads pre-edit JSON and will report a finding resolved
  that is not.

- **`coverage`'s `--query` is no longer the skill's problem.** Q5 of
  `f-auto-improvement-adoption.md` answered where it comes from -- the
  draft's own `retrieval.md` rows, skipping mode `revision` -- and
  Decision 6 moves that from prose the skill must follow into code the
  command owns.
- **R9's baseline is now a file, not a discipline.** The agenda taken
  before the pass is what `--baseline` is pointed at for the whole
  pass, and the closing report is stated against it.
- **The pass loop.** Read `pass_bound` from the payload. Continue only
  while `objective_class_count` **strictly falls**; that is the
  terminator. Stop at `pass_bound` as a backstop against a miscounting
  bug, and say so in those words where it is written down.
- **The false cache sentence** in step 2 is replaced with the measured
  figure.
- **The style-check section reverses.** It currently says of prose
  findings: *"Report every finding and fix none of them."* Under
  Decision 1 they are work. The reversal must be explicit.
- **The boundary with `draft-reviser`** gains one sentence, because
  `draft-reviser`'s copy-edit mode also edits prose: `agenda-reviser`
  repairs a style finding **that appears as an agenda item**; every
  other change to wording is `draft-reviser`.

- **Close the pass with one full-format run.** Refreshes happen at
  `--formats md`, so each aid's `.tex`/`.pdf` is stale against its
  `.md` until then. The final run is what the human reads.

### What stays exactly as it is

The write-set (R1), two attempts per item (R7), the binary re-check
(R3), per-item revert (R5), `revisions.md` and never `rejected.md`
(R6), the paraphrase-or-quote question on every long verbatim run, and
the person-only trigger (R11). The description's closing clause --
*"never runs unless a person asked for it"* -- **stays true and stays
written**, which the issue asks for by name.

Person-triggered widening needs no amendment. The
[312](https://github.com/prasadtalasila/chitragupta/pull/312) amendment
matters only if this is later driven automatically, and
`python -m chitragupta.draft gate` remains the only gate.

### PR 2's tests, to the 100% bar

The issue names five; the first four are its wording:

1. An agenda item is repaired and the count falls.
2. A repair that raises the count reverts (R4).
3. Two attempts, then stop (R7).
4. A surfaced-only class is never edited.
5. The pass bound is reached only when the count stops falling --
   phrased as two tests, because they fail differently: a run whose
   count falls every pass **terminates before the bound**, and a run
   whose count never falls **stops at the bound**.

Two more this plan adds:

- A repair in one class that raises **another** class's count reverts --
  the cross-class coupling Decision 1 introduces (Decision 4).
- A `missing-citekey` repair removes the marker and leaves the sentence
  (Decision 3).
- The skill reads `pass_bound` from the payload rather than carrying a
  literal -- the mechanical form of Decision 2's "named constant".

## 🚫 Two things it must never do

Both are the issue's, restated because they are the failure modes this
whole track exists to prevent.

- **It may never edit its own allowlist.** Not
  `content/verbatim_allowlist.toml`, and now also not
  `assets/vale/styles/chitragupta/*.yml` -- Decision 1 gives the skill
  prose work, which puts the Vale rule definitions within reach of the
  same failure for the first time. A loop that can edit the list of
  things it is measured against *"is gaming a metric rather than
  improving a draft"*.
- **It may never become a gate.** `python -m chitragupta.draft gate`
  remains the only one, and the review layer still exits 0 whatever it
  finds.

## ❓ Still open

- **The prose re-measurement is four drafts.** 0--6 is enough to show
  the bound does not bind, but not enough to characterise the class.
  Worth re-taking across all 21 dossiers if PR 2 turns out to spend most
  of its cycles here.
- **Whether `FigureNoCaption` should also flag a `.tex` fragment.** It
  should not, and PR 1 should carry the same carve-out
  `style_figures.py` already states for the rest of the module --
  `thesis-chapter-writer` hand-authors a real `\caption`. Named here so
  it is decided rather than defaulted.
