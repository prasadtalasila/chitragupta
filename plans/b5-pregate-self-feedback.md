# Pre-gate self-feedback: one critique pass, R4's count as its acceptance test

Status: **the step shipped; four amendments to it are unbuilt.** Written
2026-08-28, for
[issue 385](https://github.com/prasadtalasila/chitragupta/issues/385) --
[B5](../docs/FEATURE-ROADMAP.md#-b5-pre-gate-self-feedback-loop) in
docs/FEATURE-ROADMAP.md -- and built the same day by
[PR #438](https://github.com/prasadtalasila/chitragupta/pull/438), which
added this file and the implementation in one commit and so never got
the outcome line `plans/README.md` asks for. It is recorded now, in
["Outcome"](#outcome) below.

**Read this file in two parts.** Everything from here to "Outcome" is
the design as built, left in the present tense it was written in and
not rewritten into the past -- it is what the shipped step is checked
against. **The open work is [Part 2](#part-2-the-four-amendments), at
the end**: the four amendments a 2026-08-28 read of four upstreams left
owed, written down by #439 the day after this merged, so none of them
reached what shipped.

**Written for** whoever builds B5. **It assumes**
[docs/AUTO-IMPROVEMENT.md](../docs/AUTO-IMPROVEMENT.md) for R1-R11 and the
`agenda` aid's item classes, [docs/GENRE.md](../docs/GENRE.md) for what the
nine skills share and what distinguishes a "genre skill" from a reviser,
and [DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the cycle the
implementing PR runs.

**Not covered here:** widening `overlap-reviser` into `agenda-reviser`
(that is F3/#384's own design, in
[plans/f3-agenda-reviser.md](f3-agenda-reviser.md), unbuilt) and the
`support` (C2) entailment aid's own scope (shipped, #428). B5 touches
neither module and calls neither skill.

One fact in the issue no longer matches what is on disk, and one tool
the issue names has a newer sibling that turns out not to fit this job.
Both are stated here, in full, because a plan that quietly
reinterpreted the issue -- or silently swapped a tool -- would be worse
than the issue.

## #384 is closed, but "agenda-reviser" does not exist yet

The issue depends on #384 for "that machinery" -- the revert-on-a-rise
mechanism -- rather than re-deriving it. #384 shows `state_reason:
completed` and was closed by hand on 2026-08-27 with no attached commit
or PR (`gh api repos/prasadtalasila/chitragupta/issues/384/events` has
one `labeled` event and one `closed` event, `commit_id: null` on both).
What actually exists at `origin/main` (7b162ddd) is:

- `.claude/skills/overlap-reviser/` -- still its pre-#384 self, narrow to
  the `verbatim-run` class, description unchanged.
- `plans/f3-agenda-reviser.md` -- "Status: **designed, unbuilt**," the
  design for the widening, added by #429 ("Closes nothing on its own").
- No `.claude/skills/agenda-reviser/` directory.

So #384 is closed as a *decision* (the design is settled and the ticket
serves no further purpose open), not as *shipped code*. "Take that
machinery from #384" resolves to: take it from what #384's own
machinery already looks like where it **is** built --
`overlap-reviser`'s steps 2 (baseline), 5 (accept-or-revert) and 6 (log)
-- because that narrow skill already implements exactly the shape B5
needs (baseline before editing, gate-plus-recheck after, revert on a
rise, two-line log entry) over one class. B5 reuses that shape, not a
skill that does not exist yet. If `agenda-reviser` ships later, B5's
step does not change: it never calls a reviser skill (R11), only the
CLI commands beneath one.

## Considered and rejected: `agenda --baseline`

The issue names `verbatim recheck` as the acceptance path. `agenda
--baseline` shipped after #385 was filed
(`chitragupta/review/agenda/_recheck.py`, #433, the commit at the tip
of `origin/main` as this plan is written), and its comparison spans
every **unattended** class -- `missing-citekey`, short `verbatim-run`,
`prose` -- rather than one aid's count, which reads like a closer match
to R4's own wording ("every aid re-runs and the total objective-class
count must not rise"). It was considered as a replacement for
`verbatim recheck` and rejected, on one ground that holds and one that
does not.

**Cost is not the reason -- checked, and the first draft of this plan
had it wrong.** `verbatim recheck` re-scans to compare, so it pays
verbatim's own tier-3 cost regardless; `agenda --baseline` pays that
same cost plus the other six aids', which are cheap by comparison. On
the 10,003-word row (`docs/REVIEW.md:229`): `verbatim recheck` alone
is ~41.0 s; `agenda --baseline`'s refresh is
332+41,019+314+96+818+109+88+1,017 ms = 43.8 s -- REVIEW.md's own
"dearest run" figure, confirming the sum. That is a 1.07x difference,
not the 5x an earlier draft of this section claimed (which had wrongly
taken its high end from the *all-nine* column, the one that includes
`support`'s 62 s -- an aid neither option refreshes). Where tier 3
cannot run, both options cost under two seconds and the gap is
invisible either way. Cost does not decide this.

**The bare form cannot establish a real baseline, and that does
decide it.** `agenda` (without `--baseline`) only *reads* the seven
aids' `.json` files; it never runs them (`docs/REVIEW.md:145`, and
`_recheck.py`'s own module docstring: "a naive re-run of `agenda`
alone reads the aids' pre-edit `.json` and reports a finding resolved
that is not"). None of those seven files exist yet at pre-gate time
inside a genre skill -- the verbatim scan is each skill's own *later*
step, and provenance, coverage, synthesis, figure, uncited and
quotation are never run by a genre skill at all. `agenda --write` at
this point would file a baseline built from six absent inputs and one
to-be-taken verbatim scan, i.e. `objective_class_count` near zero
regardless of the draft's real state -- and the very first `--baseline`
refresh afterward would then report a rise from that hollow number to
whatever the real scan finds, failing every edit for a reason that has
nothing to do with the edit. `verbatim scan --write` has no such
failure mode: it always runs the scan it reports on.

**Decision: use the issue's own three tools, unmodified.** `gate`
already runs after every edit and already is the check for
`missing-citekey` -- that is its entire job, and this step adds no new
call for it. `verbatim recheck --baseline <scan.json>` is R4's count
made deterministic for the `verbatim-run` class, exactly as the issue
names it, and it is what `overlap-reviser` already uses for the same
purpose. `draft style --json`'s finding count, taken once before
editing and re-taken after, is the `prose` class's count -- cheap and
deterministic Python with no model call, per its own docstring, though
not a row in REVIEW.md's table (that table is the review layer;
`style` is a drafting-layer command, per `docs/AUTO-IMPROVEMENT.md`'s
own build-order note on `style_check`). Together the three cover the
same three unattended classes `agenda --baseline` would compare,
without the hollow-baseline failure mode.

### What this step costs

Not free, and the number belongs here rather than in the PR that
first measures it (the standing-figure lesson #429 exists to teach).
One pass is a baseline scan plus up to three rechecks -- four verbatim
runs total. On the 10,003-word draft above, where tier 3 runs: **about
2.7 minutes** (4 x ~41.0 s). Where the dossier, Docling sidecars or
enrichment layer are absent and tier 3 cannot run: **about 1.8
seconds** (4 x 447 ms). `gate` and `style` add well under a second per
call either way. A range with its condition attached, not a single
number -- the same form #429 adopted after the layer's last uncaveated
figure went stale by 18x.

## The shape

Three sentences, mirroring how docs/AUTO-IMPROVEMENT.md states its own.

- **The critique is generative, and that is fine.** One inline
  self-critique call -- no subagent, no re-critique -- reads the
  dossier's `evidence.md` (`claim:`/`quote:` per citekey, A2) against the
  draft's own prose and produces a short, prioritised list of places
  where a cited claim is weaker, missing or overstated relative to what
  `claim:` actually recorded. This is a judgement call, same shape as
  step "read it once as the reader" every genre skill already has, and
  R3 does not govern it -- R3 governs the **acceptance test for an
  edit**, not what prompts the edit.
- **The repair is bounded and single-shot.** At most three items from
  that list are edited, one attempt each, no retry within a failed item
  and no second critique pass after the three are done. This is
  deliberately lighter than `overlap-reviser`'s R7 (two attempts per
  finding): the issue calls this "smaller than 'loop' suggests," and a
  retry loop over the skill's own subjective list is a second place the
  self-marking objection could sneak back in through the acceptance
  side. One try, revert cleanly, move on.
- **The acceptance test is external, binary, and already built.** After
  each edit, three checks, all required: `python -m chitragupta.draft
  gate` exits `OK` (the `missing-citekey` class); `python -m
  chitragupta.review verbatim recheck --baseline <scan.json>` reports
  `objective_delta` not positive (the `verbatim-run` class, R4 made
  deterministic, shipped in 5.7.0); and a fresh `python -m
  chitragupta.draft style --json` finding count is no higher than the
  count taken before editing (the `prose` class, decided unattended in
  #421). Fail any one and the edit reverts to the text held before it.
  Length is never the criterion; it is checked only as the sanity floor
  the issue keeps from upstream -- **the edited section must not fall
  below 90% of its own pre-edit length**, logged when it fires, and
  never overriding a pass the three checks above already gave. A
  rewrite that guts a paragraph to make a finding disappear is a
  different failure than the one R4 catches, and this is the one line
  in the step that exists only to catch it.

## Why this is admissible where A1b was declined

State this in the skill text, not just here, because the issue is
explicit that a version of this whose accept/reject decision is the
critiquing model's own judgement "is the thing that was declined,
wearing this issue's number." The distinction that makes B5 different
from A1b (auto-routing findings into a reviser on the strength of the
skill's own opinion of them) is where the decision boundary sits:

| | A1b (declined) | B5 |
| --- | --- | --- |
| What decides *what* to look at | the skill's own opinion | the skill's own opinion -- **same**, and that's not the part R3 governs |
| What decides whether an edit is *kept* | the skill's own opinion that the edit is better | `gate`'s exit code, `verbatim recheck`'s `objective_delta`, and `draft style`'s finding count -- all external and deterministic |

A1b was declined because both columns were the skill marking its own
homework. B5 keeps the first column (a model has to read prose against
a claim; nothing deterministic does that job) and replaces the second
with the same machinery R4 already uses everywhere else in this
pipeline. Say this plainly in every affected `SKILL.md`'s step, in
close proximity to the accept/revert commands -- not just in this plan
-- because a future reader of the skill file alone is exactly who this
distinction has to survive for.

## Which skills, and why not the others

"Genre skill" is this repository's own term for the five that draft new
prose from the corpus, as distinct from a reviser
(`docs/GENRE.md:357,375`): `survey-writer`, `thesis-chapter-writer`,
`textbook-chapter-writer`, `tutorial-writer`, `deep-research`. All five,
and only these five, get the new step.

Excluded, with the reason recorded rather than assumed:

- **`draft-reviser`, `corpus-reviser`.** Both already gate-and-recheck
  per edit, at a *section* granularity (`Edit` inside the named
  section, never a whole-file rewrite) rather than a whole fresh draft.
  A whole-draft claim-vs-evidence critique does not compose with that
  discipline -- there is no single moment analogous to "the draft is
  finished, critique it before the gate," because a revision's unit of
  work is the section the human asked to change, not the whole
  document. Grepping `draft gate` alone (not `claim:`) would have
  wrongly pulled these two and `overlap-reviser` in; scoping on the
  `claim:`/`quote:` evidence-writing step instead of the gate string is
  what excludes them correctly.
- **`overlap-reviser`.** Writes no `claim:`/`quote:` evidence of its own
  and never adds a claim (its own stated invariant) -- there is no
  fresh evidence packet for it to critique a draft against.
- **`book-assembler`.** "Writes no prose of its own"
  (`docs/GENRE.md:366`); composes units the other five already gated.
  Nothing here for it to critique.

`deep-research` needs a note of its own: it already runs a self-critique
before its own gate -- Phase 7's multi-perspective peer review with a
concession threshold. That step judges rigor and coverage across five
personas; it has no binary acceptance test and is not this mechanism.
B5's step sits **after** that reconciliation and **before** "(c) Save,
log provenance, and gate" as its own, separate step -- the two do not
merge, because peer review's output is a scorecard a human reads and
B5's is an autonomous single-pass edit with its own revert path.

## The step, per skill

One step, added once per file, in the position each file's own current
numbering puts "just before the gate step." Renumber every later step in
that file by one; nothing later changes in content.

| Skill | New step goes before... | Anchor (current numbering) |
| --- | --- | --- |
| `survey-writer` | step 10, "Gate before presenting" | `.claude/skills/survey-writer/SKILL.md:451` |
| `thesis-chapter-writer` | step 10, "Gate before presenting" | `.claude/skills/thesis-chapter-writer/SKILL.md:375` |
| `textbook-chapter-writer` | step 11, "Never write a citekey you didn't get from `search()`" (the gate call is inside this step) | `.claude/skills/textbook-chapter-writer/SKILL.md:434` |
| `tutorial-writer` | step 12, "Gate any citations" | `.claude/skills/tutorial-writer/SKILL.md:476` |
| `deep-research` | inside step "(c) Save, log provenance, and gate" -- after the save, before the `gate` call | `.claude/skills/deep-research/SKILL.md:508` |

`deep-research` cannot take the step *between* "(b) Assemble" and "(c)":
`dossier sections`, `verbatim scan` and `gate` all read the draft
**from disk**, and (c) is where the assembled report is first saved --
"the gate reads a file," in that step's own words. Nothing before the
save exists as a path any of this step's commands can take. The step
goes inside (c), after `Save the assembled report to
content/drafts/deep-research-<slug>.md` and before the existing
`python -m chitragupta.draft gate` call.

Each of the four numbered skills is unaffected by that constraint --
every one of them saves the draft at its own section-mapping step,
which already precedes the insertion point in the table above.

### Step text (the four numbered skills; `deep-research` adapts it)

The draft path below is `<draft-path>`, standing for whatever each
skill's own gate step already names -- `content/drafts/<slug>.md` for
`survey-writer`, `textbook-chapter-writer` and `tutorial-writer`,
`content/drafts/<slug>.tex` for `thesis-chapter-writer` (a LaTeX
fragment gates the same way a Markdown draft does -- its own step 10
already does this), `content/drafts/deep-research-<slug>.md` for
`deep-research`. `dossier sections`, `verbatim scan`/`recheck` and
`draft style` all already run against whichever of these each skill
uses, at that skill's own later steps -- nothing here asks a command to
accept a file type it does not already handle.

````markdown
N. **Critique against the evidence packet, before gating.** Read the
   dossier's `evidence.md` -- the `claim:`/`quote:` blocks step 2
   recorded -- against the draft's own prose, section by section. List,
   in priority order, up to five places where the prose claims more
   than its `claim:` line supports, omits a kept `claim:` the draft
   never used, or drifts from the wording `claim:` actually recorded.
   This is one inline judgement call, not a subagent dispatch and not a
   deterministic check -- nothing in this pipeline scores this
   automatically, and R3 does not apply to *this* list, only to what
   happens next.

   Take the baseline before touching anything:

   ```bash
   python -m chitragupta.draft dossier sections <draft-path> --citekeys --write
   python -m chitragupta.review verbatim scan <draft-path> --write --json
   python -m chitragupta.draft style <draft-path> --json
   ```

   The first two are `overlap-reviser`'s own baseline discipline
   (uncapped, never `--limit`): they file
   `content/review/<topic>/<stem>.verbatim.json`, the file every edit
   below is rechecked against. The third's finding count -- not the
   file, `style` never writes one -- is the number you compare after
   each edit; note it down. Take all three fresh now rather than
   reusing anything on disk from an earlier run; each must reflect the
   draft as it stands the moment before you start editing.

   Work the top of your list, **at most three items, one edit each, no
   retry and no second critique pass** once the three are done or the
   list runs out first. For each:

   1. Keep the pre-edit text of the section you are about to touch.
   2. Edit with `Edit`, inside that section only. Preserve the citekey;
      reword the claim to match what `claim:` says, or drop a sentence
      that overstates it. Never add a claim `evidence.md` does not
      already record, and never touch a `quote:` span -- a quotation is
      captured when the evidence is judged, never rewritten here.
   3. Check, all three required:

      ```bash
      python -m chitragupta.draft gate <draft-path>
      python -m chitragupta.review verbatim recheck <draft-path> \
          --baseline content/review/<topic>/<stem>.verbatim.json --json
      python -m chitragupta.draft style <draft-path> --json
      ```

      Accept the edit only if: the gate exits `OK`; the recheck's
      `objective_delta` is not positive; and the fresh `style` finding
      count is no higher than the count noted before editing. Also
      check the edited section did not fall under 90% of its own
      pre-edit length -- a secondary sanity floor against a rewrite
      that deletes its way to a lower count, never itself a reason to
      accept one that the three checks above already failed.
   4. If any check fails, restore the text you kept in step 1 and move
      to the next item. Do not retry the same item.
   5. Log the attempt in the dossier's `revisions.md`: which gap, what
      you changed, and the outcome -- accepted or reverted. Never write
      any of this to `rejected.md`.

   **This is not a condition of presenting.** If nothing on the list
   clears the bar, or the list was empty, continue to the gate exactly
   as if this step had not run -- the gate remains the only thing that
   blocks a draft, and this step only ever makes a passing draft better
   or leaves it unchanged.
````

`deep-research`'s adaptation keeps every requirement above; only the
prose around it changes to match the lettered list already in that
file, and its own `content/drafts/deep-research-<slug>.md` path is
already saved to disk by the time this step runs (see the placement
note above).

### Why these three commands, and why no new `chitragupta/` module

Every command the step above runs already exists and is already
tested: `dossier sections --citekeys --write`, `draft gate`,
`review verbatim scan`/`recheck`, and `draft style`. B5 adds no Python.
This matches the issue's own "smaller than 'loop' suggests" and keeps
the whole mechanism at the same layer as every other genre-skill step
-- a documented procedure over existing CLI commands, not a new aid.
It also matches the issue's Scope section literally: "The acceptance
path: `verbatim recheck`'s count before and after, revert on a rise,
two attempts then stop" -- except single-shot rather than two
attempts, per "The shape" above.

## `docs/AUTO-IMPROVEMENT.md`: what changes and what does not

Add a short section stating the boundary explicitly, because R11 ("no
other skill invokes the `agenda-reviser` skill... only trigger is a
person asking") is easy to misread as covering this too if the two
mechanisms are not told apart in the same document the issue names:

- B5's step runs **inside** a genre skill, at generation time, on the
  draft that skill itself is producing. It is not `agenda-reviser` (that
  skill does not exist yet, and the run-only-when-a-person-asks rule
  governs the *reviser skill*, not a genre skill's own step over its own
  output).
- It does not widen the build order's step 5 and is not a build-order
  step in its own right; it is a sibling mechanism the roadmap tracks as
  B5, and this plan is what B5 links to once it exists.
- It calls `verbatim scan`/`recheck` and `draft style` directly, the
  same commands `overlap-reviser` and every genre skill's own later
  steps already call. It never calls `review agenda` -- there is no
  overlap with F3's build order to state an exemption from.

## `docs/FEATURE-ROADMAP.md`

B5's existing subsection is not removed -- nothing has shipped yet. Add
one line linking this plan, the way F3's entry links
`plans/f3-agenda-reviser.md`. Its prose already names the right
dependency ("Depends on: the amendment, A2, and `verbatim recheck`");
what is wrong is the **build-order table**, whose row 6 reads
"**amendment**, A2, F3" -- F3 is not a dependency (this plan calls no
`agenda-reviser` machinery, widened or not; see the file table above),
so correct that cell to "**amendment**, A2, `verbatim recheck`
(shipped)," matching the prose it currently contradicts.

> **What actually happened, recorded 2026-08-30.** #438 made both edits
> above and then left the entry reading "Designed, unbuilt" while
> shipping the step in the same commit, so the roadmap described B5 as
> unbuilt for two days and #439 wrote the four amendments against that
> reading. The entry now says which half shipped; the paragraph above is
> kept as written because Part 2 below is what the roadmap's B5 entry
> tracks from here.

## Tests

No new runtime behaviour is added -- `gate`, `verbatim scan`/`recheck`
and `draft style` are exercised by their own existing suites
(`tests/test_citation_gate.py`, `tests/test_verbatim_check.py`,
`tests/test_style_check.py`). What this change adds is five `SKILL.md`
files each carrying the same procedure, which is exactly the shape
`tests/test_skill_verbatim_scan_step.py` already pins for a different
shared step (added by #312). Add
`tests/test_skill_pregate_feedback_step.py` on that model: a text scan
over `.claude/skills/*/SKILL.md`, asserting, for each of the five genre
skills and no others:

- the step names `evidence.md` and `claim:` together, near a mention of
  the critique;
- `at most three` (or the exact cap phrase used) appears near the step;
- `no retry` / `no second critique pass` (or the exact wording used)
  appears -- pins the single-shot rule so a later edit cannot quietly
  turn this into a loop;
- `python -m chitragupta.review verbatim scan`, `... recheck`,
  `python -m chitragupta.draft style` and `python -m chitragupta.draft
  gate` all appear within the step, in that relative order -- the gate
  call inside this step is the per-edit recheck, not the genre skill's
  own later "Gate before presenting" step, and the two must not be
  conflated in the text;
- the 90%-length sentence appears, and in the same breath states it is
  secondary -- a regex requiring both "90%" and a negation near
  "gate"/"recheck"/"style" in the same paragraph, mirroring how the
  existing test file requires the `tiers_not_run` caveat to sit within
  `_LOOKAHEAD_CHARS` of the scan command rather than merely exist in
  the file;
- `revisions.md` is named and `rejected.md` is explicitly excluded, near
  the step;
- the step explicitly says it is never a condition of presenting (same
  invariant `test_no_skill_makes_the_scan_a_condition_of_presenting`
  checks for the verbatim-scan step -- add the equivalent assertion for
  this one, in the same file or a shared helper).

Also assert the four excluded-but-plausible files
(`draft-reviser`, `corpus-reviser`, `overlap-reviser`, `book-assembler`)
do **not** carry this step's marker phrase, so a future edit that copies
it into the wrong file by habit is caught the same day.

`docs/GENRE.md`'s "What all nine have in common" section
(`docs/GENRE.md:382`) is not the tenth shared invariant to add this
to -- it is not shared by all nine, only by five. That section already
carries the precedent for saying so anyway: its own second paragraph
notes `book-assembler` is "not a drafting skill" and states how each
rule differs for it rather than leaving it quietly exempt. Add one
sentence in that same place, on the same pattern: this step exists in
the five genre skills and not in `book-assembler` or the three
revisers, and why (per "Which skills, and why not the others" above),
so the asymmetry is stated once rather than discoverable only by
reading five files and noticing a sixth doesn't have it.

## File table

| File | Change |
| --- | --- |
| `.claude/skills/survey-writer/SKILL.md` | new step before current step 10 |
| `.claude/skills/thesis-chapter-writer/SKILL.md` | new step before current step 10 |
| `.claude/skills/textbook-chapter-writer/SKILL.md` | new step before current step 11 |
| `.claude/skills/tutorial-writer/SKILL.md` | new step before current step 12 |
| `.claude/skills/deep-research/SKILL.md` | new lettered step inside "(c)", after the save and before `gate` |
| `docs/AUTO-IMPROVEMENT.md` | new section stating the boundary with `agenda-reviser`/R11 |
| `docs/FEATURE-ROADMAP.md` | B5 entry gains a link to this plan; build-order dependency line corrected |
| `docs/GENRE.md` | one sentence noting the five-of-nine asymmetry, wherever that distinction is already drawn |
| `tests/test_skill_pregate_feedback_step.py` | new, per "Tests" above |

## Outcome

**Shipped by [PR #438](https://github.com/prasadtalasila/chitragupta/pull/438),
merged 2026-08-28, closing issue 385** -- the same commit that added this
file, which is why the outcome was never recorded at merge time and is
recorded here two days later. Five `SKILL.md` files, `docs/GENRE.md`,
`docs/AUTO-IMPROVEMENT.md`, the roadmap entry and
`tests/test_skill_pregate_feedback_step.py`, exactly the file table
above.

Three things read differently in the shipped skills than in the step
text above, all of them additions rather than reversals, and none of
them a decision this plan had taken the other way:

- The baseline paragraph names **`agenda-reviser`**'s discipline, not
  `overlap-reviser`'s. That skill was widened and renamed by #440 a day
  later; the discipline is the same one.
- The shipped step quotes `verbatim scan`'s **`tiers_not_run`** when it
  is non-empty, so a recheck that can only see the deterministic tiers
  says so rather than reading as a clean bill of health. This plan did
  not ask for it.
- It says twice, where this plan says once, that `draft style`'s count
  is **a proxy and not a work list** -- §9 marks those findings
  decidable and the step is told to fix none of them.

Nothing in the design above was reversed on the way. That comparison
was made after the fact, in the 2026-08-30 pass that recorded this
outcome, rather than by the merging PR.

## Part 2: the four amendments

Status: **unbuilt.** Written 2026-08-30, when the roadmap entry was
corrected to say the step had shipped.
[FEATURE-ROADMAP.md's B5](../docs/FEATURE-ROADMAP.md#-b5-pre-gate-self-feedback-loop)
is the ticket; this is the design.

The four are stated in
[outline-driven-drafting-and-manual-edits.md](outline-driven-drafting-and-manual-edits.md#-amendments-owed-to-b5-not-a-new-item),
out of a 2026-08-28 read of OpenScholar, RAGFlow, papersgpt-for-zotero
and local-deep-research, merged by #439 on 2026-08-29. They are **not restated
here**; what follows is what each one costs now that the step exists,
which is a different question from what each one meant when it was
written against a step that did not.

### A1 -- the length ratio: satisfied, no work

The shipped step keeps the 90% floor as a secondary sanity check and
never as the acceptance test, which is what R3 requires and what "The
shape" above already specified. The amendment adds *evidence* for a
decision already taken -- OpenScholar accepts an edit iff it is ≥90% as
long as the original, so a longer and wronger answer is always accepted
and a correct compression always rejected -- and no code or skill text
follows from it. Close it by citing it, not by editing anything.

The one thing worth doing is cheap: `tests/test_skill_pregate_feedback_step.py`
already pins that the ratio never decides an acceptance on its own
(`test_every_step_s_acceptance_test_is_external_and_deterministic`).
Leave it exactly as it is. A test that grew a citation to an upstream's
behaviour would be pinning someone else's code.

### A2 -- coverage on evidence retrieved: a located defect

**This is the only one of the four that is a bug rather than a
sentence.** `chitragupta/dossier/_outline.py::declared_vs_actual` builds
its `run` set from a logged call's **origin**:

```python
run = {_normalised(query) for query, origin in pairs if origin in ("declared", "reground")}
```

`pairs` comes from `recorded_queries_with_origin`, which returns
`(query, origin)` and drops the rest of the row -- including
`retrieval.md`'s **`results`** cell, which `_retrieval_rows` already
parses and hands back as `cells[4]`. So a declared query that ran and
returned nothing joins `run` and is indistinguishable from one that
returned twelve candidates, and `dossier status` prints it under
"followed the outline." That is local-deep-research's failure mode --
a topic marked covered because a query was *issued* -- reproduced here
by a set comprehension.

**The fix is binary, so R3 is satisfied by construction**: evidence came
back for this declared query, or it did not. No score, no threshold.

Three design decisions the implementer should not have to re-take:

1. **Add a bucket; do not redefine `run`.** `SectionDrift` gains a third
   list beside `run` and `not_run` -- suggested name **`run_empty`**,
   for a declared query that was issued and returned zero results. `run`
   keeps meaning "issued", and the new list is a subset of it rather
   than a fourth state carved out of it. The reason is not taste: #470
   landed two tests asserting a `reground`-origin call joins the `run`
   set -- `test_dossier_outline.py::test_a_regrounded_query_is_reported_run_and_regrounded`
   and `test_dossier.py::test_outline_block_reports_a_regrounded_query_as_run`,
   the second over the printed report -- and both sit beside
   `test_an_unspecified_origin_call_is_neither_run_nor_extended`, the
   invariant they were written not to disturb. Redefining `run` to mean
   "returned evidence" would flip them on a row whose result count
   happens to be zero -- a real behaviour
   change smuggled in under a reporting fix. If a later PR wants `run`
   to mean "grounded", that is its own decision with its own test edit,
   not this one's side effect.
2. **Read the count, do not re-run the query.** The row is on disk;
   `recorded_queries_with_origin` needs a sibling (or a widened return)
   that carries `cells[4]` through. `_retrieval_queries.py` is 146 code
   lines and already documents this exact "three-function family"
   pattern, so a fourth sibling is the local idiom rather than a new
   shape. Nothing retrieves anything: this is a read of `retrieval.md`.
3. **A zero-result row is a fact, not a finding.** `dossier status`
   reports it in the same advisory register as `not_run` -- one line per
   query, no exit-code change, no gate. A declared query returning
   nothing is frequently *correct* (the corpus genuinely has nothing on
   that sub-theme), which is precisely why A4 below cuts a sentence
   rather than failing a draft.

**Aggregate before deduplicating, not after**, and this is the one place
the sibling's shape is forced. `recorded_queries_with_origin` dedupes on
`(query, origin)` and keeps the *first* row it sees, so by the time it
returns, the counts of every later row for that pair are gone -- a query
logged twice, once returning nothing and once returning four after a
reformulation, would report as whichever row happened to come first. It
must read as **evidence retrieved**: the sibling folds the rows for a
pair together as it goes, keeping `max(results)`, and a query is
`run_empty` only when that maximum is zero. Deduplicating first makes
the rule uncomputable, and reporting a defect the draft's own history
already fixed is worse than not reporting one.

### A3 -- the exhaustible query list: a termination condition

All four upstreams stop after a fixed number of rounds because a web
search has no edge. A closed, human-curated corpus does, and
`outline.md` (#455) makes the declared query list finite and written
down -- so "every declared query has either returned evidence or been
recorded as returning none" is a reachable end state, not an
approximation of one. **It is B5's sentence to write**, and A2 above is
what makes it computable: the end state is `not_run` empty, with every
remaining query in `run` or `run_empty`.

**It does not replace the cap of three.** Two different bounds, and
conflating them would undo "The shape" above:

| Bound | What it limits | Why |
| --- | --- | --- |
| At most three repairs, single-shot | how much *editing* one pass may do | cost, and the self-marking objection -- a retry loop over the skill's own subjective list is where A1b's argument would sneak back in through the acceptance side |
| The declared list is exhausted | whether the *evidence* behind the draft is complete | a real termination condition, available because the corpus is closed |

So the step gains one sentence, not a loop: after the repairs, report
whether the outline's declared queries are exhausted, and name the ones
that are not. It stays advisory -- **this step is never a condition of
presenting**, and A3 must not become the first thing that makes it one.

Only where an `outline.md` exists. It is optional (#455), and a draft
without one has no declared list to exhaust; there, the shipped step is
unchanged and says so, rather than reporting a vacuous "exhausted."

### A4 -- an empty result set is informative

No skill's text says this today -- `grep -rn "cannot be grounded"
.claude/skills/` returns nothing. Every upstream is built to always
produce a citation; against a closed bibliography, "nothing came back"
means the claim **cannot be grounded in this corpus**, so the sentence
is cut rather than cited to whatever ranked nearest.

One paragraph in the critique step, in the repair list's vocabulary:
a claim whose sub-theme is `run_empty` is a fourth kind of gap beside
the three the step already lists (prose claims more than `claim:`
supports, omits a kept `claim:`, drifts from the recorded wording), and
its repair is to **cut the sentence, never to re-point it at an adjacent
citekey**. That last clause is the load-bearing one: re-pointing is how a
citation becomes decorative, and the gate cannot see it because the
citekey is real.

Two guards it must carry, both already built:

- **The 90% floor catches the abuse.** "Cut the sentence" is a licence
  to delete, and deleting lowers every count the acceptance test reads.
  The floor exists for exactly this and needs no change -- but the step
  text must put A4's cut *inside* the same accept/revert cycle as every
  other repair, not beside it as a special case.
- **`rejected.md` is not for this.** The step logs to `revisions.md`
  and never to `rejected.md` (shipped, and pinned by
  `test_every_step_logs_to_revisions_md_and_never_to_rejected_md`). A
  cut sentence is a revision. The candidate that was never kept is what
  `rejected.md` records, and that decision was made at evidence time.

### Build order: two PRs, in this order

**PR 1 -- A2, the `declared_vs_actual` defect**
([issue 480](https://github.com/prasadtalasila/chitragupta/issues/480)).
`chitragupta/dossier/`
only: the `results`-carrying sibling in `_retrieval_queries.py`, the
`run_empty` bucket in `_outline.py`, and the reporting in `_status.py`'s
`_print_status_outline`, which already has the right shape to copy --
`regrounded` is counted inside `run` and listed separately underneath,
which is exactly what `run_empty` needs, so the summary line gains a
clause and the loop below gains a sibling. Docs: `docs/DOSSIER.md`'s
`retrieval.md`/`outline.md` sections and `docs/CLI.md`'s `dossier
status` row. Tests to the 100% bar -- a declared query whose only row is
`0` results reports `run_empty` and stays in `run`; the same query with
one zero row and one non-zero row does not (the aggregate-before-dedupe
rule above, and the test that pins it); the printed report names it once
under `run_empty` and does not double-count it in the summary's `run`
figure; a `reground` call still joins `run` (#470's two tests,
unchanged); an unspecified-origin call is still neither; a dossier with
no `outline.md` still reports every section empty.

**PR 2 -- A3 and A4, five `SKILL.md` files**
([issue 481](https://github.com/prasadtalasila/chitragupta/issues/481)).
One paragraph each into
the shipped step, in all five skills, plus the two new assertions in
`tests/test_skill_pregate_feedback_step.py` in the shape its seven
existing ones use (a text scan over `.claude/skills/`, five in and four
out). A1 closes with PR 2's description citing it; nothing is edited for
it.

PR 2 depends on PR 1 only for A3's wording -- "the outline's declared
queries are exhausted" is a claim about a thing `dossier status` must
already be able to print. A4 does not depend on PR 1 at all and could
lead if PR 1 slips.

### What Part 2 deliberately does not do

| Not proposed | Why |
| --- | --- |
| Re-critique after a repair | "Smaller than 'loop' suggests" is the whole shape of this item, and A3 gives the *evidence* a termination condition, not the *editing* one |
| Make the step block a draft | No second gate. `python -m chitragupta.draft gate` means one thing ([WRITING-STANDARDS.md](../docs/WRITING-STANDARDS.md) §10) |
| A "coverage" percentage in `dossier status` | R3. `run_empty` is a list of queries; a ratio over it would be a continuous score, and someone would optimise it |
| Re-running an empty declared query automatically | A retrieval call costs, and "the corpus has nothing" is a stable fact about a closed corpus. E4 (#456) already covers the case where a *person* wants another round |
