# 🗂 The dossier

Status: **reference.** Written 2026-08-22. Updated 2026-08-24, describing the
format as it stands.

**Written for** the model or the person reading a dossier back -- most
often `draft-reviser` picking up a draft weeks later, and only sometimes
a human. **Assumed:** [FEATURES.md](FEATURES.md) for where the dossier
sits among the pipeline's features. **Not covered here:** what to *do*
with one. Revising a draft, re-grounding it after the corpus moves,
dispatching a subagent from it, and backing one up are all
[DRAFT-ITERATION.md](DRAFT-ITERATION.md); this page is the format those
depend on.

**This is machine-facing documentation, and that is the point.** The
dossier exists so a *drafting run* can be resumed by something that was
not present when it started. Its reader is usually an LLM: it is written
in Markdown because a model reads Markdown natively, its fields are named
for what a drafting step may and may not do with them, and its most
valuable file (`rejected.md`) exists to stop a model paying twice for a
judgement already made. A human can read it, and occasionally should --
but nothing here is shaped for that.

That is the clean split from its counterpart. **[REVIEW.md](REVIEW.md) is
for you; this is for the thing writing your draft.** A review report is
evidence you weigh before deciding a draft is done; a dossier is working
state a machine reloads to keep going. They mirror the same draft path
and are otherwise unalike -- different readers, different lifetimes, and
opposite answers to "is it a problem if nobody ever reads this?"

One dossier per draft, mirroring the draft's own path:

```text
content/drafts/dt-for-engineers/survey.md
   -> content/dossiers/dt-for-engineers/survey/
```

That rule is mechanical, needs no registry, and handles both layouts the
repository actually contains -- the flat `content/drafts/<slug>.md` and
the `content/drafts/<topic>/<genre>.md` the shipped example content uses.
Which one you get is the user's call: a genre skill settles the draft's
path with them before it starts (step 0), so "a book chapter in
`books/software-engineering`" becomes
`content/drafts/books/software-engineering/book-chapter.md`, at whatever
depth was asked for.

`content/rendered/` mirrors the same path, so a topic directory names a
draft, its dossier and its rendered `.md`/`.tex`/`.pdf` together --
[CLI.md](CLI.md#-chitragupta-draft-render) has the detail. That is
what makes `dossier export <topic> --with-rendered` able to find the
renders at all: it matches them by their path relative to
`content/rendered/`.

Seven files, each answering a question the draft itself cannot. The
"status before" column is kept because it is the argument for the file
existing: two were specified but never made durable, and the two that
were missing entirely are the two that matter most.

| File | What it holds | Status before this |
| --- | --- | --- |
| `scope.md` | genre, reader, dialect (`language:`), what the draft covers and excludes, glossary, corpus fingerprint | in the transcript only |
| `evidence.md` | each kept citekey, why it was kept, and its claim | **specified** (survey-writer step 2) but written as JSON |
| `rejected.md` | candidates retrieved and turned down, with the reason | **nowhere** |
| `sections.md` | section heading -> the citekeys cited under it, and while a run is still going, the ones it plans to cite | **specified** (survey-writer step 8) but written as JSON |
| `steering.md` | what the user asked for in chat that the draft doesn't show | **nowhere** |
| `revisions.md` | append-only log of what changed and why | **nowhere** |
| `retrieval.md` | every retrieval call and the size of what it returned | **nowhere** |
| `math.md` | ASCII in the draft -> the LaTeX it renders as ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §12) | **nowhere** |

**`math.md` is the one optional file**, and the only one whose absence is
not a defect: a draft with no mathematics has none, and a draft using
§12's inline `$…$` form does not need one. `render` reads it for every
format that reaches pandoc and ignores it for `--format md`, which is
what keeps the draft's own text ASCII. Two consequences worth knowing
before you rename anything:

- A draft and its dossier are tied by **path alone**, and there is no
  `dossier rename`. Moving a draft orphans its mapping, and every
  equation in it silently reverts to typewriter text on the next render.
  `render` refuses outright when a `<!-- math -->` marker has no mapping
  to resolve, which is what makes that case loud rather than mute.
- Because it is keyed on the exact span text, a revision that *rewords*
  an equation desyncs it. Which skill fixes that is not left open --
  each of `draft-reviser`, `corpus-reviser` and `overlap-reviser` carries
  the step, and the four Markdown genre writers create the file.

**`scope.md` -- the boundary.** Genre, the reader the draft is written
for, the dialect it is written in (`language:`, so an en-GB draft stays
en-GB through a revision six weeks later), what the draft covers, what it
deliberately excludes, and a glossary of the terms it commits to. It also
records a **corpus fingerprint**: how many citekeys the ledger held and a
digest of that set. That last line is what makes drift *detectable* --
`draft dossier status` recomputes it, and a mismatch means the corpus
moved under the draft. Without `scope.md` a reviser has no way to tell an
omission from an exclusion, and will helpfully add back the section you
asked to leave out.

**`evidence.md` -- what was kept, and why.** One block per kept citekey,
carrying `relevance:` (why this source bears on the sub-theme), `claim:`
(what it establishes, in the drafter's own words) and an optional
`quote:` (its exact wording). **Only `claim:` may be drafted prose
from**, and the ordering is the whole mechanism: it is written at the
moment the evidence is judged, before any sentence of the draft exists,
so it cannot be a lightly-edited copy of the passage. `quote:` is absent
by default -- a quotation is a deliberate act, not the residue of
retrieval -- and is what the evidence sidecar renders. Blocks written
before this contract carry a single `support:` field and are never
rewritten; old and new coexist by construction.

**`rejected.md` -- the candidates turned down, with the reason.** This is
the file whose absence *is* the expensive mistake. Without it, the next
revision retrieves the same papers, re-reads them, and re-reaches the
same judgement, paying the full cost of a decision already made. A
reviser is required to honour it: a candidate listed here with a reason
is not retrieved and re-judged. It is also the largest file in the
dossier, which is why the dossier is seven files rather than one -- a
revision loads only what it needs, and this one is needed only when a
change reopens a sub-theme for searching.

**`sections.md` -- which citekeys are cited under which heading.**
Derived, not maintained: a heading owns a line range, a citekey is cited
on a line, and the relation falls out of the intersection.
`draft dossier sections --citekeys --write` rebuilds it from the draft,
skipping fenced code and LaTeX verbatim so a `# Step 1` comment in an
example listing is neither a heading nor a citation. That matters because
a hand-maintained version disagreeing with the draft hands a reviser the
wrong section for a citation. `deep-research` is the one exception, and
only for timing: it writes *planned* rows before the sections exist, and
replaces them with what the finished report actually cites.

**`steering.md` -- what you asked for that the prose cannot show.**
"Don't lead with tooling." "Shorter." "Drop the adoption angle." This
guidance shaped the draft and is invisible in it, so without this file it
survives only in a chat log nobody will reread. Its practical effect is
that a revision months later does not quietly undo a decision you made
deliberately -- the commonest way a revised draft comes back subtly wrong.

**`revisions.md` -- an append-only log of what changed and why.**
Including the attempts that failed. A repair tried and reverted is
knowledge: without the record, the next session re-tries it, re-discovers
the same problem, and reverts again. `overlap-reviser` logs every attempt
here, refusals and reverts included, and a copy-edit pass leaves one
entry naming the convention it applied. Append-only because the value is
the sequence, not the current state.

**`retrieval.md` -- every retrieval call, and the size of what came
back.** Two jobs. It lets you compare one run's retrieval cost against
another's on a real corpus, and -- more load-bearing -- it **bounds
re-grounding**: when a draft has to be brought back into line after the
corpus moved, the candidates come from the queries already recorded here,
so that pass cannot invent a new search and quietly become a full
re-draft. One honest limit worth knowing: it records the *character
payload* of each call, not tokens, and nothing records what the drafting
turns themselves cost. Enough to compare two runs; not enough to price a
whole draft.

## 💡 Why Markdown

Everything a dossier holds is read by a model or by a human, both of
which read Markdown natively. Nothing in it is a data structure another
module consumes -- `chitragupta/dossier/` parses only two things out of it (the
corpus fingerprint line and backticked citekeys), and both degrade to
"unavailable" rather than to an error if a human has been editing freely.
A restored tarball is also legible on its own a year later, without this
code.

The cost of that choice is real: there is no schema, so nothing validates
that `evidence.md` is well-formed. This is accepted deliberately, on the
same principle as `chitragupta/review/citation_provenance.py` -- a check that
blocked on
something it cannot verify exactly would train people to work around it.
A malformed dossier makes the next revision less efficient. It cannot
make a draft wrong, because the citation gate still stands between any
draft and the user.

## 📖 `evidence.md`'s `claim:`/`quote:` contract (A2, #306)

One `## \`citekey\`` block carries three possible fields:

```markdown
## `talasila_realising_2024`

relevance: why this source bears on the sub-theme
claim: what the source establishes, in the drafter's own words
quote: an optional verbatim span, quotable-only
```

- **`relevance:`** is unchanged from before this section existed.
- **`claim:`** is required, and is **the only field a drafting step may
  write prose from.** Written by whoever judged the evidence, at the
  moment they judged it -- before any sentence of the draft exists. That
  ordering is the whole mechanism: a claim written from memory, once the
  passage is no longer the thing on screen, cannot be a lightly-edited
  copy of it.
- **`quote:`** is optional, verbatim, and usable in a draft **only**
  inside quotation marks with an attribution. Absent by default -- a
  captured quote is a quote in the drafter's context, which is the thing
  this contract removes, so one is captured only when a quotation is
  actually intended.

**Migration.** This replaces a `support:` field that held, in practice, a
raw retrieval window -- `EVIDENCE_CHARS = 600` in `chitragupta/retrieval.py`,
handed straight to the drafter. `support:` is **read but never written**
after this landed: existing dossiers keep it as-is, and nothing rewrites
one to the new shape. `evidence_blocks()` already returns a block
verbatim without owning its shape, so old and new coexist by
construction. A skill meeting a `support:`-only block reads it as
`quote:` -- the conservative reading, since that is usually what it is.

**That rule is about what a drafter *may quote from*, and it does not
extend to anything that *prints* the field.** The two are different
questions with opposite safe answers, and conflating them would publish
source wording:

| | Reads a `support:`-only block as... | Why |
| --- | --- | --- |
| A drafting or revising skill | `quote:` | It is deciding whether the block may be quoted at all. Treating unknown provenance as quotable-only is the cautious answer -- it *restricts* what the skill may do with it |
| `chitragupta/evidence_appendix.py` | nothing at all | It is deciding what to put in a rendered document. A legacy `support:` holds a raw 600-character retrieval window (`EVIDENCE_CHARS`), and printing one as an attributed quotation would publish it |

So the evidence sidecar
([CLI.md](CLI.md#-chitragupta-draft-evidence)) reads `quote:` and
only `quote:`. A pre-A2 dossier therefore renders no sidecar, which is
correct rather than a gap: nobody ever decided those windows were worth
quoting. `claim:` is excluded from it for the mirror-image reason -- it is
the drafter's own words, so quoting it back would attribute this
project's prose to the source.

If you are changing that module and this looks like an oversight against
the rule above, it is not; `plans/a4-evidence-appendix.md` records the
decision and `tests/test_evidence_appendix.py` pins it.

**The self-check.** `python -m chitragupta.draft dossier check-evidence <draft>`
compares each block's `claim:` against its own `quote:`
(`chitragupta/dossier/_evidence_check.py`, reusing
`chitragupta/overlap_skipgram.py`'s stemmed word stream) and warns when the
claim reads like the quote with its words moved. **Advisory, printed,
never blocking**, and deliberately silent about the score by default --
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s R3 rules out a similarity
number a drafting step could optimise against, so a bare warning is what
prints; `--score` opts into the number for a human reading the output by
hand.

## 💡 Why several files rather than one

So that a revision loads only what it needs. `scope.md` and `sections.md`
are small and almost always relevant; `rejected.md` is the largest and is
only needed when a change opens a sub-theme up for re-searching. One
combined file would have to be read whole every time, which is the cost
this module exists to avoid.

## 🔄 `sections.md` is derived, not maintained

Its own template says the file is "rebuildable from the draft", and it is:
a heading owns a line range, a citekey is cited on a line, and the
relation falls out of the intersection. Five genre skills nonetheless
had a model read the outline and attribute each key by hand -- a
mechanical step with a wrong answer available, and a `sections.md` that
disagrees with the draft hands `draft-reviser` the wrong section for a
citation.

```bash
python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
```

builds it instead, from both citation syntaxes, skipping fenced code and
LaTeX verbatim so a `# Step 1` comment in an example listing is neither a
heading nor a citation. A key cited above the first heading belongs to no
section; it is reported on stderr rather than filed under one that does
not contain it.

`deep-research` is the exception, and only for timing: Phase 4 writes
*planned* rows before the sections exist, and Phase 5 dispatches its
writers from them. There is no draft to derive from at that point, so
that write stays by hand and the derived form belongs at Phase 7(e),
where the plan is replaced by what the finished report actually cites.

## 💡 Why not merge the provenance JSON into the rest of the dossier

`thesis-chapter-writer` and `deep-research` also write a
`provenance.json`, and the thesis genre additionally writes an
`evidence.json`. Both live **inside** the dossier directory, at
`content/dossiers/<draft path minus suffix>/provenance.json`, for two
reasons.

They are drafting state, produced by the run that wrote the draft, so
they belong with the rest of that run's state. And `dossier_dir()`
mirrors the draft's path, so two drafts named `survey.md` in different
topics do not share one file.

They stay separate *files*, and neither replaces the other, because they
answer different questions for different readers. The argument for that
is about Markdown-versus-JSON, not about directories:

| | `provenance.json` | the dossier's Markdown |
| --- | --- | --- |
| Shape | JSON, machine-readable | Markdown, human-readable |
| Holds | section -> citekey, and why that source supports that claim | reader, scope, glossary, kept evidence, **rejected candidates and why**, steering |
| Read by | tooling, and a reviewer auditing one claim | `draft-reviser`, and a human months later |
| Lost if absent | an audit trail for a finished draft | the ability to revise without re-running the whole topic |

The overlap is one column of `sections.md`. Collapsing them would mean
either putting prose a human needs into JSON, or putting a machine record
into Markdown that nothing parses -- so they stay separate files, and the two
skills that produce both write both.

## 📚 The corpus fingerprint

`scope.md` records how many citekeys the ledger held when the draft was
written, plus a 12-character digest of that set:

```text
- corpus: 501 citekeys, digest `a1b2c3d4e5f6`
```

`python -m chitragupta.draft dossier status` recomputes it. If it differs, the corpus
has moved, and the command names the citekeys that appear nowhere in the
dossier -- neither kept nor rejected -- so a reviser can see what was
never considered rather than just that a number changed.

The ledger is opened read-only with `timeout=0`, exactly as
`python -m chitragupta.corpus ledger` does. This is an inspection: it must not
take a write lock, run a migration, or block behind a sync that is
mid-run.

**Drift is not itself a reason to redraft.** It is a reason to re-search
if, and only if, the change being made touches a sub-theme the new papers
could bear on. That is a claim about a corpus that *grew*. A corpus that
*lost* a paper the draft cites has produced a broken citation, which is
fixed whether or not anyone asked.

The line between the two is drawn in "Two findings, and they are not the
same kind of thing" below, and acted on in "Re-grounding after the corpus
moves".

The fingerprint is written once, by `init`, and is not maintained by any
command -- the only thing that rewrites it is a re-grounding pass, which
re-stamps it as the record that the draft was brought back into line with
that corpus.
