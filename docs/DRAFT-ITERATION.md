# ✍ Iterating on a draft

Status: **implemented.** Written 2026-08-06. Updated 2026-08-24.

**Written for** someone changing the drafting layer or the dossier
format. **Assumed:** [ARCHITECTURE.md](ARCHITECTURE.md) for the layers
and [TOKENS.md](TOKENS.md) for the two cost pools. **Not covered here:**
how to *use* a dossier day to day, which is [CLI.md](CLI.md)'s
`dossier` section.

Why drafting costs what it costs, and how a draft is revised weeks later
without re-running the pipeline that produced it.

Related reading:

- [TOKENS.md](TOKENS.md) -- where a run's tokens go, the two-pool
  framing this document assumes, and how to measure any of it. It holds
  the arithmetic behind ["Where the tokens go"](#-where-the-tokens-go)
  below.
- [ARCHITECTURE.md](ARCHITECTURE.md) -- the four layers this sits inside.
- [RETRIEVAL.md](RETRIEVAL.md) -- how the corpus is ranked, and what a
  snippet actually contains.
- [REJECTION.md](REJECTION.md) -- why turning a source down is the
  load-bearing judgment here, and the accounting behind a retrieval change
  that was built and then withdrawn.
- [CITATION-PROVENANCE.md](CITATION-PROVENANCE.md) -- the review aid that
  answers "does the cited paper actually say this?", which is a different
  question from anything here.
- [PERFORMANCE.md](PERFORMANCE.md) -- **measured** costs, including
  [what a drift sweep costs](PERFORMANCE.md#-what-a-drift-sweep-costs),
  which is the one figure this document quotes rather than estimates.
  That split is the rule here: a stopwatch number lives there and is
  cited from here, and anything derived from file sizes or documented
  defaults is labelled an estimate every time it appears.

## 🧭 Table of contents

- [The asymmetry](#-the-asymmetry)
- [Where the tokens go](#-where-the-tokens-go)
- [The dossier](#-the-dossier)
- [Dispatching from the dossier](#-dispatching-from-the-dossier)
- [Drift across every dossier](#-drift-across-every-dossier)
- [Revising a draft](#-revising-a-draft)
- [Backup and restore](#-backup-and-restore)
- [What this deliberately does not do](#-what-this-deliberately-does-not-do)

## ⚖ The asymmetry

Half of this pipeline already survives a session ending, and half of it
doesn't.

`chitragupta/citation_gate.py`, `chitragupta/references.py`,
`chitragupta/render_output/` and
`chitragupta/review/citation_provenance.py` are all stateless with respect to
*how* a
draft was written. Hand any of them a `.md` file from last month and they
work: the gate re-checks its citekeys, `references` rebuilds the
bibliography, `render_output` produces the PDF, `citation_provenance`
scores each claim against its source. None of them needs to know what
searches were run or which candidates were turned down.

The drafting layer is the exception. A genre skill's real product is not
only the draft -- it is also the judgment that produced it. Which
sub-themes the topic was broken into. Which of the fifteen retrieved
candidates were worth keeping, and why the other twelve weren't. Who the
reader is. Which definition of a contested term the draft settled on. And
what the user asked for in chat that the prose doesn't show.

Before this module, all of that lived in one conversation and died with
it.

So "shorten section 3" cost a full re-run: retrieve, score every
candidate again, re-cluster, rewrite. **That is a structural cost, not a
constant factor.** Everything else in this document follows from removing
it.

## ⚡ Where the tokens go

The accounting lives in [TOKENS.md](TOKENS.md), together with the same
argument from [REJECTION.md](REJECTION.md) and two worked examples --
one subject, kept in one place.

The part this document depends on, in one paragraph. Costs split into
two pools. **Orchestrator-resident** costs are re-sent on every remaining
turn of the run, and so multiplied by everything that comes after them.
**Subagent one-shot** costs are paid once, because the context is
discarded when the subagent returns.

Four things load the first pool: retrieved candidates that are rejected
but stay resident, fan-out packets held across phases, whole-file
rewrites, and **no revision path at all**.

The fourth is the one this module exists to remove, and the only one of
the four that is *structural* rather than a constant factor. Before
`chitragupta/dossier/` and the `draft-reviser` skill, no genre skill had a
branch for "an existing draft plus a change request", so the only way to
alter a paragraph was to run Phase 1 through Phase 7 again.

## 🗂 The dossier

**The format moved to [DOSSIER.md](DOSSIER.md)** -- the seven files, the
`claim:`/`quote:` contract, why it is Markdown, why it is several files
rather than one, how `sections.md` is derived, and the corpus
fingerprint. It is machine-facing documentation, because its reader is
usually the model resuming a draft rather than a person.

This page is the other half: what to *do* with a dossier once it exists.
Everything below assumes that format and does not restate it.

## 🤖 Dispatching from the dossier

The dossier was built to be read by the *next* session. `brief` is the
part that is read by the *current* one -- specifically by a subagent, and
specifically instead of the orchestrator pasting the same text into its
prompt. It closes
[#74](https://github.com/prasadtalasila/chitragupta/issues/74).

**The problem, in one phase.** `deep-research` Phase 5 dispatches one
writer per section, and each needs the kept claims its section stands on.
Written the obvious way, the orchestrator selects those claims from the
Phase 2 packets it is holding and types them into four prompts. That is
*output*, at 5x a cached input token, spent once per writer: an estimated
four writers x ~800 tokens = 3.2k output, or **16k input-token
equivalents** ([TOKENS.md](TOKENS.md#-two-worked-examples) has the
weights). The same material is already on disk by then, because Phase 2's
transcription put it there.

**The mechanism.** Phase 4 writes the section -> citekey plan into
`sections.md`, and the dispatch prompt carries one line:

```bash
Your evidence: python -m chitragupta.draft dossier brief <draft> --section "2. Failure modes"
```

An estimated ~40 output tokens per writer, ~0.8k equivalents for the
phase, against 16k -- **an estimated 15k equivalents saved**, in the
expensive direction. The writer runs the command in its own context,
which is discarded when it returns, so the blocks land in the one-shot
pool at 1.25x once rather than being carried anywhere.

Counted rather than estimated, on the shipped example report against the
real 501-paper corpus: **15,660 characters of evidence become 901
characters of dispatch line**, 17.4x, across its seven sections. Method
and caveats in
[TOKENS.md](TOKENS.md#-the-dispatch-payload-measured-on-real-material) --
it is a payload size, not a run.

**Addressing by section, not by citekey list.** A prompt carrying the
citekeys is already most of the way back to carrying the evidence, and
the list would then exist in two places that can disagree. `sections.md`
is where that decision was made, so it is what the command names. Section
matching ignores numbering (`"Failure modes"` finds the row a skill wrote
as `"2. Failure modes"`) and **an ambiguous name matches nothing**: a
wrong match hands a writer another section's evidence, which comes back
as fluent, correctly-cited prose about the wrong subject -- the one
failure here that no downstream check catches.

**What it does not do, and cannot.** It does not reduce what the
orchestrator is already carrying. A context is append-only between
compactions, so six packets returned into it in Phase 2 stay there
whether or not they are also on disk. Reading an extract back *adds*
tokens rather than removing any.

The only way to avoid that residency would be to let each interviewer
write its own file, so the long-form material never enters the
orchestrator at all. That would cost the invariant which makes a dossier
trustworthy -- **one writer, one record** -- and it is written down as a
rejected trade in
[TOKENS.md](TOKENS.md#-the-one-way-to-cut-residency-and-what-it-would-cost)
rather than implemented here.

The three subagent definitions still declare
`tools: Bash, Read, Grep, Glob` with no `Write`, and still say in prose
that they write nothing.

**The second effect, which is not about tokens.** Until now, an
orchestrator that moved past Phase 2 without transcribing lost six
packets' worth of judgment and nothing reported it -- the draft looked
finished and the record was absent. A run that *dispatches* from
the file cannot skip the file: `brief` exits 1 when nothing resolves and
names every citekey with no block, and `--check` lets the orchestrator
find that out before four writers are already running. Silent loss became
a named failure at the moment it is still cheap to fix.

**Who else can use it.** Nothing in `brief` is `deep-research`-specific:
any skill that fans out over sections has the same shape.
`survey-writer`'s step 2a subagents read retrieval results rather than
transcribed evidence, so they have nothing to point at yet; when that
changes, the command is already there.

## 📉 Drift across every dossier

`status <draft>` answers "did the corpus move under this one draft?",
which is only useful if you already suspect it did. The corpus half of
the bottleneck is the one nobody is watching: `chitragupta.corpus sync` adds
papers and
`--remove-stale` drops them, and every draft written before that moment
silently drifts. `status --all` is the sweep that makes it visible --
one report over every dossier under `content/dossiers/`, always exiting
0, because "some drafts have drifted" is the normal state of a live
corpus and not a build failure.

### ⚖ Two findings, and they are not the same kind of thing

| Finding | What it is | What it costs to ignore |
| --- | --- | --- |
| **Missing** -- a cited citekey that has left the ledger | a defect | the draft cites a paper the corpus no longer has; the citation gate will fail on it |
| **Candidate** -- a newly reachable paper the dossier never weighed | a decision | nothing, until the sub-theme it bears on is revised |

Collapsing the two into one "drift" number was the thing worth avoiding.
A missing citekey is work that has to happen; a candidate is an offer
that is usually correct to decline. Reported together as a count, the
first hides inside the second.

**Missing is computed from `evidence.md` and `sections.md` only, not from
`rejected.md`.** A paper the draft *stands on* vanishing is a defect; a
paper the draft *turned down* vanishing is a non-event, and reporting the
second as the first would make every `--remove-stale` run look like a
pile of broken drafts. Each missing citekey is reported with the
`sections.md` sections that cite it, because the reviser's next question
is always "which prose leans on this?" and reading the draft to find out
is exactly the cost this document exists to remove.

**Candidates are matched against the queries in `retrieval.md`.** That
file was added to measure what a run cost -- how many characters each
retrieval call returned. It turns out to be the only record of *what
this draft went looking for*, which is what makes "the corpus grew"
answerable as "and here is the part of the growth this draft would have
wanted". Each recorded query is re-run against the current corpus, and
anything landing in its top 15 that the dossier has never mentioned is a
candidate. Fifteen is not arbitrary: it is `survey-writer`'s own
`search(sub_theme, k=15)`, so the report surfaces a paper if and only if
the draft's original search would have put it in front of the writer.

**Everything in `rejected.md` is subtracted first.** Re-offering a
candidate the draft already read and declined would cost precisely the
re-judging that `rejected.md` exists to prevent -- the report would
recreate the bottleneck it is meant to expose.

### 💡 The third list, and why it is not drift

Subtracting the rejections throws away something worth keeping, though.
"Turned down because the corpus had nothing better on this sub-theme"
and "turned down because it is about a different field" age completely
differently, and only the first is worth revisiting once the corpus
grows. Membership in `rejected.md` cannot tell those apart; the reason
column can.

So a declined paper that the dossier's queries *still* reach is reported
as a third list, `reconsider`, carrying the recorded reason. A citekey
that is both cited and listed as rejected is treated as cited -- that is
a stale `rejected.md` row, not an open question, and offering it back
would send a reviser to re-decide something the draft already acts on.

**It deliberately does not count as drift.** A rejection that still
matches its query was true before the corpus moved and will be true on
every sweep after it. Letting it mark a dossier stale would mean every
dossier that ever declined a paper is permanently stale, which destroys
the one signal this command exists to give. So `reconsider` never makes
a dossier "drifted", and the terminal output prints it only alongside a
real finding -- context for a re-grounding pass that is already
warranted, rather than a standing reminder. `--json` always carries it,
because there the consumer reads it at the moment it acts.

### 🔎 Why the new papers are not found with `search()`

The obvious implementation -- call `chitragupta.retrieval.search(query, k=15)`
for each recorded query -- is the one thing this could not do, for two
reasons that are both about a report having no business changing what it
reports on:

- `search()` reaches the ledger through `ledger.connect()`, which mkdirs
  `content/`, executes the schema and runs migrations. That is a write
  connection, and the whole point of `status` opening the ledger
  `mode=ro, timeout=0` is that an inspection must not take a write lock
  or block behind a sync that is mid-run.
- `search()` builds its index through `retrieval._load_index`, which
  calls `_save_cache()` whenever any document's fingerprint has moved.
  After the sync that caused the drift being reported, that is not an
  edge case -- it is guaranteed. The scan would rewrite
  `content/retrieval_index.json` every time it ran.

**The BM25 index was never in the ledger to begin with**, which is what
makes the alternative easy. The ledger holds bibliographic rows and a
`parsed_path`; the index is a separate `content/retrieval_index.json`
mapping each citekey to `{fingerprint, length, term_freqs}`, derived from
the parsed text. And the two halves of `chitragupta.retrieval` that matter --
`_tokenize_item` and `_bm25_scores` -- are pure; the only thing that
persists is the cache write sitting between them.

So the drift scan composes those two halves and skips the middle. It
reads the existing cache with `_load_cache()` (which only reads), reuses
every entry whose fingerprint still matches, tokenizes the rest into
memory, ranks against that, and drops the whole thing when the scan
returns. The ledger is read once and the index built once and lazily, so
a sweep over dossiers that logged no queries never builds one at all.
Nothing is written back, and the smoke test pins exactly that:
`content/ledger.sqlite` and `content/retrieval_index.json` are both
byte-identical after a scan.

The cost of throwing the index away is that a cold-cache sweep re-does
work the next `search()` will do again. That is accepted deliberately.
The alternative is a read-only command that writes to the corpus layer
as a side effect, which is a much worse thing to owe the reader.

**What that costs is measured, not assumed** -- and unlike the token
estimates in [TOKENS.md](TOKENS.md), it is a stopwatch figure, so it
lives in [PERFORMANCE.md](PERFORMANCE.md#-what-a-drift-sweep-costs) with
the rest of the measurements. The load-bearing result, on this project's own
corpus: sweeping 50 dossiers costs **0.19s more than sweeping one**
(2.227s vs 2.032s cold), because the tokenization is shared. Had it been
per dossier, 50 would have taken well over a minute. A warm cache is
5.1-9.3x faster again. The first draft of this section called a warm
sweep "nearly free"; the measurement says about 0.2-0.4s warm and ~2.1s
cold -- cheap enough to run after every sync, but not nothing, and the
wording here was corrected to match.

### 🏷 Unknown is not the same as absent

A dossier on a machine with no readable ledger produces no findings, and
reporting that as "current" would be the one way this command could
actively mislead -- it would assert the result of a check that never ran.
The sweep says so explicitly and still exits 0.

### ⌨ `--json`, and who it is for

`--all --json` emits the same report as data: per dossier, the recorded
and current fingerprints, `missing` as citekey -> citing sections,
`candidates` as citekey, title and the queries that surfaced it, and
`reconsider` as the same plus the recorded rejection reason. This
exists because the consumer is not only a human. A re-grounding pass has
to swap the missing citations, triage the candidates, and edit only the
affected sections -- and having it re-parse a report written for a
terminal would be a fragile way to hand over structured facts it already
knows. Exiting 0 regardless is part of the same contract: the caller
branches on the contents, not on the status code.

## ✍ Revising a draft

The `draft-reviser` skill reads the dossier instead of the corpus. Its
loop:

1. `python -m chitragupta.draft dossier status <draft>` -- what is on disk,
   has the corpus moved, and has the *draft* moved since the last
   `dossier stamp` (#454, FEATURE-ROADMAP.md's E3 -- "The draft
   fingerprint" in [docs/DOSSIER.md](DOSSIER.md))? A changed draft
   fingerprint surfaces up to four findings, offered to the user one at a
   time rather than applied. Then `python -m chitragupta.draft dossier
   mark-revision <draft>`, before any retrieval call, so `retrieval.md`
   can tell this revision's cost apart from the last one -- its rows
   otherwise carry only a date, and two revisions on the same day would
   merge into one figure.
2. Read `scope.md` and `steering.md`. These bound what the revision may
   change: a request that contradicts the recorded scope is a scope
   change, and gets said out loud rather than silently applied.
3. `python -m chitragupta.draft dossier sections <draft>` -- heading to line range.
4. Read *only* the affected sections, at those line ranges, and edit
   inside them.
5. Re-search only if the change genuinely opens new ground, consulting
   `rejected.md` first so the same candidates aren't re-judged.
6. Update `evidence.md` / `rejected.md` / `sections.md` for whatever
   actually changed, append to `revisions.md` and `steering.md`.
7. Re-gate (`python -m chitragupta.draft gate`), rebuild references,
   re-render, then `python -m chitragupta.draft dossier stamp <draft>` --
   after the gate passes, so a draft that fails it is never stamped as
   accepted.

Steps 3 and 4 are where the output-token saving lives: a scoped edit
inside one section replaces an estimated ~4.6k-token whole-file rewrite.
Steps 1, 2 and 5 are where the input-token saving lives: no retrieval
pass at all in the common case.

### 📝 The copy-edit pass, and the entry it leaves

One class of revision inverts every economy above: a grammar pass, a
spelling fix, a dialect conversion, a rephrasing to meet a style
guideline. It reads the whole draft rather than one section, and it edits
every section rather than one -- and it is still the cheap path, because
what makes the ordinary loop cheap is skipping *retrieval*, and this pass
skips it entirely. Steps 4 and 5 short-circuit to "no, and never": a
copy-edit that needs a search has stopped being one.

What it leaves behind is one `revisions.md` entry for the whole document,
naming the convention applied rather than the sections touched --
"converted to en-GB per `scope.md`'s `language:` (-ise, -our, -re); no
claim, citation or section order changed". One entry rather than forty
because the later reader's question is *which convention governs this
draft now*, and a per-section log answers a question nobody asks.

**It carries no evidence delta, and that is the point rather than an
omission.** `evidence.md`, `rejected.md` and `sections.md` all describe
the relationship between the draft and the corpus, and a wording change
moves neither end of it: no citekey is added or dropped, no candidate is
judged, no heading moves. A copy-edit entry that recorded an evidence
change would be recording something that did not happen -- and the next
revision, which is told to trust `rejected.md` rather than re-judge it,
would inherit the fiction. The dossier stays truthful by staying silent
here.

The one dossier file a copy-edit may legitimately write besides the log is
`scope.md`'s `language:` line, when the pass is what settles the dialect
in the first place. A conversion applied against an unrecorded target
cannot be repeated or checked by the next session.

### 📚 Re-grounding after the corpus moves

The sweep above makes drift visible. Re-grounding is the same reviser
loop entered from that report instead of from a request, and it is
composition rather than new machinery: every command it runs already
existed.

It reads `status <draft> --json`, refuses to proceed when
`corpus_available` is false (an empty finding list from a check that
never ran is not a clean bill of health), and then treats the three
findings as the three different things they are. A **missing** citekey is
repaired: cite a paper that supports the same claim, or drop the claim,
editing only the sections the report names. A **candidate** is pursued
only where it bears on the sub-theme in play, and reached with `evidence`
rather than `search` -- the report already carries the citekey and the
query that surfaced it, so re-running the search would pay for fifteen
snippets to be handed back the same fifteen keys. A **reconsider** entry
is not re-judged at all; it is shown with its recorded reason, and
re-opened only when that reason has stopped holding.

Then the fingerprint is re-stamped and the gate runs, and the gate is
what decides the draft is presentable. This matters because `missing` is
computed from `evidence.md` and `sections.md` rather than from the draft
body: a citation the dossier never recorded cannot appear in the report,
and only `citation_gate` reads the draft itself.

What re-grounding promises is an empty `missing` list, and deliberately
not an empty `candidates` list. A recorded query returns fifteen hits and
a revision accepts one or two, so a healthy draft keeps showing
candidates on every sweep; that is the sweep working. The way to silence
them would be to write the unpursued ones into `rejected.md`, which would
turn a title into a permanent judgment that every later revision trusts
-- the same objection that withdrew `triage` ([REJECTION.md](REJECTION.md)).

### ⚙ The scoped default, and the way out of it

Steps 3-5 above are an economy, and economies have a failure mode: they
can start reading as rules about what the user is allowed to ask for. A
revision that touches one sub-theme should re-search one sub-theme --
but whether that is what this revision is remains a judgment about
someone else's draft, and [SOUL.md](../SOUL.md) puts "let a machine
outrank a human on a judgment call" under what this assistant will not
do.

So the way out is a second skill, `corpus-reviser`: a wide pass that
re-searches every sub-theme in `sections.md` and reads the whole draft.
It is invoked when the user asks for it, when an agreed scope change
invalidated the old queries, or when the draft is being re-targeted at a
different reader -- and its cost is stated before it runs rather than
discovered afterwards in `retrieval.md`.

**Why a separate skill rather than a mode.** A split only enforces
anything if it removes a capability. `draft-reviser` now contains no
instructions for a wide search, so following it cannot produce one by
drift -- which is the strongest enforcement available for a rule that
must not become a gate. It also makes the expensive path something the
user opts into by name, once, instead of something a model decides on
their behalf mid-revision.

The same test is why re-grounding is *not* a third skill. Its cost is
bounded by construction -- candidates come from the queries already in
`retrieval.md`, so it cannot invent one -- and splitting it out would
remove no dangerous capability while duplicating the repair-and-edit
loop.

The guardrail that survives is narrower than "never re-search widely". It
is **never re-run the genre skill**, which is a different act: it
discards the dossier and pays to rediscover a worse version of it. A wide
re-search keeps `rejected.md` and honours it, keeps the recorded reader
and glossary, still edits section by section rather than rewriting the
file, and still logs every call. Wide *search* does not imply wide
*rewrite* -- most sections survive a re-check untouched, and rewriting
those is pure cost.

Nothing enforces any of this. The only mechanical gate in the pipeline is
`citation_gate`, and the reason is the same principle: a token-economy
heuristic is not the kind of claim that earns a gate.

### 🔗 Section anchors

`sections` extracts the outline from the draft itself rather than from
stored state, so it cannot go stale, and it survives a draft that was
hand-edited outside this pipeline.

It skips code first, which is not a nicety. The shipped example
`tutorial.md` is mostly shell and Python, and a `# Step 1: ...` comment
inside a fenced block is indistinguishable from a Markdown heading to
anything that doesn't track fences -- an outline built without that
reports sections that don't exist and hands a reviser line ranges that
cut a code block in half. Markdown fences (``` and `~~~`) and LaTeX
`verbatim`/`lstlisting`/`minted` environments are both tracked, since
`thesis-chapter-writer` emits `.tex`.

## 💾 Backup and restore

`content/dossiers/` is gitignored, like `content/drafts/` and
`content/rendered/` before it. That is a deliberate choice, not an
oversight: `evidence.md` quotes passages from copyrighted sources, and
this project already treats per-host content as the user's own to keep.
Nothing under `content/dossiers/` is tracked, and no example one ships --
a dossier is a record of a real run, and one assembled to be looked at
would be a reconstruction wearing a record's clothes.

What replaces version control is an explicit bundle:

```bash
# everything
python -m chitragupta.draft dossier export

# one topic, including rendered PDFs
python -m chitragupta.draft dossier export digital-twins-for-software-engineers --with-rendered

# restore -- a dry run that reports what it would write
python -m chitragupta.draft dossier restore drafts-all-2026-08-06.tar.gz
python -m chitragupta.draft dossier restore drafts-all-2026-08-06.tar.gz --force
```

Three properties worth knowing:

- **Archive paths are relative to `content/`, not to the repo root**, so
  a bundle restores correctly into a checkout whose `[content].dir`
  points somewhere else.
- **Restore is a dry run unless `--force`.** It is the only destructive
  operation in the module, and the case it exists for -- "I need last
  month's draft back" -- is exactly the case where the working copy might
  be something you would rather not lose to a mistyped archive name.
- **An unsafe member refuses the whole archive**, rather than being
  skipped. A member is unsafe if it is not a regular file or directory
  (a symlink, a device node), if it escapes the extraction directory, or
  if its top-level directory is not one of `drafts/`, `dossiers/`,
  `rendered/`, `review/`. A partially extracted backup is worse than none, because
  it looks like it worked.

### 🚫 What a bundle does not carry

`content/ledger.sqlite` and `papers/bibliography.bib`. The ledger is
regenerable with `python -m chitragupta.corpus sync`, and the bib file is your reference
manager's export -- AGENTS.md's invariant is that the bib file is the
source of truth *and not this pipeline's to own*, so a bundle does not
start keeping copies of it. Back it up where you back up that tool.

The practical consequence: restore a bundle onto a machine with no
corpus and the drafts and dossiers are all there and readable, but the
citation gate cannot verify anything until `sync` has run. That is the
correct failure -- the gate refusing to confirm a citekey it cannot see
beats a gate that passes because there is nothing to check against.

## 🚫 What this deliberately does not do

**It is not a gate and it takes no lock.** Nothing in `chitragupta/dossier/`
blocks a draft, and nothing in it writes to the corpus layer. A dossier
that is missing, stale or hand-edited degrades the next revision's
efficiency and can never make a draft wrong.

**It does not verify that a dossier matches its draft.** `sections.md`
can disagree with the draft's actual headings if someone edits by hand.
The reviser rebuilds the section map from the draft rather than trusting
the file, and `chitragupta/review/citation_provenance.py` already reconciles a draft
against its sources independently.

**It does not itself cut what enters the orchestrator's context.** That is
the other half of the problem, and the answer turned out not to be
trimming what retrieval returns -- see [REJECTION.md](REJECTION.md) for
why a cheaper first read was built and then withdrawn. What does work is
the subagent boundary: a genre skill on a broad topic dispatches one
subagent per sub-theme and keeps only the kept-evidence packet, so the
candidates it discarded are paid for once instead of sitting resident for
the whole run. The dossier's job is the *structural* cost -- not
re-running the pipeline at all -- and the two are complementary: the
cheapest retrieval pass is still more expensive than the one you didn't
have to make.

**It does not measure token counts directly.** `retrieval.md` records the
character payload of each retrieval call, not tokens, and nothing records
what the drafting turns themselves cost. That is enough to compare one
run against another on a real corpus; it is not enough to put a number on
a whole draft. The estimates in [TOKENS.md](TOKENS.md) remain estimates,
and are labelled as such there.
