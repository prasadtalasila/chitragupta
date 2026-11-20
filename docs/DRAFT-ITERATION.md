# ✍ Iterating on a draft

Status: **implemented.**

**If you are here to change a draft you wrote weeks ago, read the
walkthrough in
[WRITING-PROCESS.md](WRITING-PROCESS.md#-phase-3-revise-a-draft)'s
Phase 3 instead of this page.** **Written for** someone changing the
drafting layer or the dossier format: this is the reasoning behind the
command surface that walkthrough uses. **Assumed:**
[ARCHITECTURE.md](ARCHITECTURE.md) for the layers and
[TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md)
for the two cost pools. **Not covered here:** how to *use* a dossier day
to day, which is [CLI.md](CLI.md)'s `dossier` section.

Why drafting costs what it costs, and how a draft is revised weeks later
without re-running the pipeline that produced it.

Related reading:

- [RETRIEVAL.md](RETRIEVAL.md): how the corpus is ranked, and what a
  snippet contains.
- [REJECTION.md](REJECTION.md): why turning a source down is the
  judgment everything here depends on.
- [CITATION-PROVENANCE.md](CITATION-PROVENANCE.md): the review aid that
  answers "does the cited paper actually say this?", a different
  question from anything here.
- [PERFORMANCE.md](PERFORMANCE.md): **measured** costs, including
  [what a drift sweep costs](PERFORMANCE.md#-what-a-drift-sweep-costs).
  A stopwatch number lives there and is cited from here; anything
  derived from file sizes or documented defaults is labelled an estimate.

## ⚖ The asymmetry

`chitragupta/citation_gate.py`, `chitragupta/references.py`,
`chitragupta/render_output/` and
`chitragupta/review/citation_provenance.py` are stateless with respect to
*how* a draft was written. Hand any of them last month's `.md` file and
they work.

The drafting layer is the exception. A genre skill produces the draft
and also the judgment behind it: the sub-themes, which of fifteen
retrieved candidates were kept and why the rest were not, who the reader
is, which definition of a contested term was settled, and what the user
asked for in chat. Without a record on disk all of that is lost when the
conversation ends, so "shorten section 3" would cost a full re-run. That
is a structural cost, and everything else here follows from removing it.

## ⚡ Where the tokens go

The accounting lives in
[TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md).
This page depends on one part of it. **Orchestrator-resident** costs are
re-sent on every remaining turn of the run; **subagent one-shot** costs
are paid once, because the context is discarded when the subagent
returns. Four things load the first pool: rejected candidates that stay
resident, fan-out packets held across phases, whole-file rewrites, and
**no revision path at all**. The dossier and `draft-reviser` exist to
remove the fourth, the only structural one: without them, altering a
paragraph would mean running every phase again.

## 🗂 The dossier

The format is in [DOSSIER.md](DOSSIER.md): the ten files, the
`claim:`/`quote:` contract, how `sections.md` is derived, and the corpus
fingerprint. This page covers what to *do* with a dossier once it exists.

## 🤖 Dispatching from the dossier

`brief` lets a subagent read the dossier in place of the orchestrator
pasting the same text into its prompt. `deep-research` Phase 5 dispatches
one writer per section, and each needs the kept claims its section
stands on. Typed into four prompts by the orchestrator, that is *output*
at 5x a cached input token: an estimated **16k input-token equivalents**
([TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md#-two-worked-examples)
has the weights). Phase 4 instead writes the section to citekey plan into
`sections.md`, and the dispatch prompt carries one line:

```bash
Your evidence: python -m chitragupta.draft dossier brief <draft> --section "2. Failure modes"
```

That is an estimated ~0.8k equivalents for the phase, and the writer's
context is discarded when it returns. Counted on the shipped example
report against the real 501-paper corpus, **15,660 characters of
evidence become 901 characters of dispatch line**
([TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md#-the-dispatch-payload-measured-on-real-material)).

**Addressing by section, not by citekey list.** A citekey list in the
prompt would exist in two places that can disagree; `sections.md` is
where the decision was made. Matching ignores numbering, and **an
ambiguous name matches nothing**: a wrong match hands a writer another
section's evidence and comes back as fluent, correctly cited prose on the
wrong subject, a failure no downstream check catches.

**What it does not do.** It does not reduce what the orchestrator
already carries: packets returned in Phase 2 stay in its context. Letting
each interviewer write its own file would avoid that, at the cost of
**one writer, one record**; that trade is rejected in
[TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md#-the-one-way-to-cut-residency-and-what-it-would-cost),
and the three subagent definitions declare no `Write` tool.

**The second effect.** A run that dispatches from the file cannot skip
transcribing it. `brief` exits 1 when nothing resolves and names every
citekey with no block, and `--check` finds that out before any writer
runs. Nothing in `brief` is `deep-research`-specific.

## 📉 Drift across every dossier

`chitragupta.corpus sync` adds papers and `--remove-stale` drops them,
and every draft written before that moment silently drifts. `status
--all` is the sweep that makes it visible: one report over every dossier
under `content/dossiers/`, always exiting 0, because "some drafts have
drifted" is the normal state of a live corpus. `sync` also names the
dossiers that reference a citekey it is about to drop
([CLI.md](CLI.md#-what-else-still-references-a-citekey-you-are-about-to-remove)),
but it sees only that removal and cannot tell a missing citekey from a
candidate.

### ⚖ Two findings, and they are not the same kind of thing

| Finding | What it is | What it costs to ignore |
| --- | --- | --- |
| **Missing**: a cited citekey that has left the ledger or no longer parses | a defect | the draft cites a paper the corpus no longer has; the citation gate will fail on it |
| **Candidate**: a newly reachable paper the dossier never weighed | a decision | nothing, until the sub-theme it bears on is revised |

They are never collapsed into one "drift" number, because the defect
would hide inside the offers.

**Missing is computed from `evidence.md` and `sections.md` only, not from
`rejected.md`.** A paper the draft turned down vanishing is a non-event.
Each missing citekey is reported with the sections that cite it, so the
reviser need not read the draft to find them.

**Candidates are matched against the queries in `retrieval.md`.** Each
recorded query is re-run against the current corpus, and anything in its
top 15 that the dossier never mentioned is a candidate. Fifteen is
`survey-writer`'s own `search(sub_theme, k=15)`, so a paper surfaces if
and only if the original search would have shown it. **Everything in
`rejected.md` is subtracted first**, so declined papers are not
re-judged.

### 💡 The third list, and why it is not drift

"Turned down because the corpus had nothing better" ages differently
from "turned down as off-topic", and only the reason column tells them
apart. So a declined paper the queries still reach is reported as
`reconsider`, with its recorded reason. A citekey both cited and
rejected is treated as cited.

**It deliberately does not count as drift.** A rejection that still
matches its query would otherwise mark every dossier that ever declined
a paper as permanently stale. The terminal prints `reconsider` only
beside a real finding; `--json` always carries it.

### 🔎 Why the new papers are not found with `search()`

Calling `chitragupta.retrieval.search(query, k=15)` is ruled out, because
a report must not change what it reports on:

- The ledger is opened read-only through `ledger.read_connection`, never
  through `ledger.connect()`, which creates directories, runs the schema
  and migrations. (It does wait out a writer's commit window; see
  [DOSSIER.md](DOSSIER.md#-the-corpus-fingerprint).)
- `search()` builds its index through `retrieval._load_index`, which
  calls `_save_cache()` whenever a fingerprint has moved, so after a sync
  the scan would rewrite `content/retrieval_index.json` every time.

The pure halves, `_tokenize_item` and `_bm25_scores`, are composed
directly instead: the existing cache is read with `_load_cache()`, stale
entries are tokenized in memory, and nothing is written back. A smoke
test pins `content/ledger.sqlite` and `content/retrieval_index.json` as
byte-identical after a scan. A cold sweep therefore repeats work the
next `search()` will do, which is accepted over a read-only command that
writes. Measured, sweeping 50 dossiers costs 0.19s more than one (about
2.1s cold, 0.2–0.4s warm); see
[PERFORMANCE.md](PERFORMANCE.md#-what-a-drift-sweep-costs).

### 🏷 Unknown is not the same as absent

A dossier on a machine with no readable ledger produces no findings.
Reporting that as "current" would assert the result of a check that
never ran, so the sweep says the result is unknown, and still exits 0.

### ⌨ `--json`, and who it is for

`--all --json` emits the same report as data: per dossier, the recorded
and current fingerprints, `missing` as citekey to citing sections,
`candidates` with title and the queries that surfaced them, and
`reconsider` with the recorded reason. Its consumer is usually a
re-grounding pass, which branches on the contents, not the exit status.

## ✍ Revising a draft

[WRITING-PROCESS.md](WRITING-PROCESS.md#-phase-3-revise-a-draft) has the
same loop as a command table, including how a hand-edited draft is
picked back up. This section gives the reasoning. The `draft-reviser`
skill reads the dossier instead of the corpus:

1. `python -m chitragupta.draft dossier status <draft>`: what is on disk,
   has the corpus moved, and has the *draft* moved since the last
   `dossier stamp` ("The draft fingerprint" in
   [DOSSIER.md](DOSSIER.md))? A changed draft surfaces up to five
   findings, offered one at a time. Then `python -m chitragupta.draft
   dossier mark-revision <draft>`, before any retrieval, so
   `retrieval.md` can tell two same-day revisions' costs apart.
2. Read `scope.md` and `steering.md`. A request that contradicts the
   recorded scope is a scope change, raised with the user.
3. `python -m chitragupta.draft dossier sections <draft> --citekeys --write`:
   heading to line range, with the citekeys under each.
4. Re-search only if the change opens new ground, consulting
   `rejected.md` first.
5. Read and edit *only* the affected sections.
6. Update `evidence.md` / `rejected.md` / `sections.md`, append to
   `revisions.md` and `steering.md`.
7. Re-gate (`python -m chitragupta.draft gate`), rebuild references,
   re-render, then `python -m chitragupta.draft dossier stamp <draft>`
   after the gate passes, so a failing draft is never stamped.

Steps 3 and 5 save output tokens (a scoped edit replaces an estimated
~4.6k-token whole-file rewrite); steps 1, 2 and 4 save input tokens (no
retrieval pass in the common case).

### 📝 The copy-edit pass, and the entry it leaves

A grammar pass, spelling fix, dialect conversion or style rephrasing
edits every section and is still cheap, because it skips retrieval
entirely: a copy-edit that needs a search has stopped being one.

It leaves one `revisions.md` entry naming the convention applied, for
example "converted to en-GB per `scope.md`'s `language:` (-ise, -our,
-re); no claim, citation or section order changed", ending like every
entry with a `Sections:` line (see [Reviewing a
revision](#-reviewing-a-revision)).

**It deliberately carries no evidence delta.** `evidence.md`,
`rejected.md` and `sections.md` describe the draft's relationship to the
corpus, which a wording change does not move; recording a change would
mislead the next revision, which trusts them. The one other file it may
write is `scope.md`'s `language:` line, when the pass settles the
dialect.

### 🔀 Reviewing a revision

Every `mark-revision` keeps a numbered snapshot of the draft and its
figures under the dossier's `versions/` (unless the draft is unchanged
since the last), and every reviser ends by running `draft diff` against
it and showing you the result. You can run the same commands yourself:

```bash
python -m chitragupta doctor    # latexdiff is listed; the PDF needs it
python -m chitragupta.draft dossier snapshot content/drafts/dt-overview/survey.md --label "sent to supervisor"
python -m chitragupta.draft dossier versions content/drafts/dt-overview/survey.md
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md --format pdf
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md --against "sent to supervisor" --format pdf
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md --against 2 --format pdf
python -m chitragupta.draft diff content/drafts/dt-overview/survey.md --against old/survey.md --format pdf
```

`snapshot` names a milestone; `versions` lists every snapshot. With no
`--against`, `diff` compares with the latest snapshot; `--against` takes
a label, a number or a file path. Outputs land in
`content/review/<topic>/`: `<stem>.diff.md` and `<stem>.diff.json`, and
with `--format pdf` the redline `<stem>.diff.pdf` (for the draft above,
`content/review/dt-overview/survey.diff.pdf`). With nothing changed the
report says `No changes.`; without latexdiff the report is written and
the command exits 1. [CLI.md](CLI.md#-chitragupta-draft-diff) has every
flag. The diff is a review copy: never gated, submitted or used as a
source.

The report ties each changed section to the `revisions.md` entries that
explain it, and lists under `## Needs a log entry` any section none
does. An entry starts with its date and ends with a `Sections:` line
naming sections by heading text or number; a `.tex` draft's go by title.
A heading containing a comma must be named by number (in a `.tex` draft,
expect it under `## Needs a log entry`):

```text
2026-11-13 -- shortened the background at the supervisor's request;
merged the two synchronisation paragraphs; no citation changed.
Sections: 2. Background, 4.1 Synchronisation
```

### 📚 Re-grounding after the corpus moves

Re-grounding is the reviser loop entered from the drift report instead
of a request, with no new machinery. It reads `status <draft> --json`
and refuses to proceed when `corpus_available` is false. A **missing**
citekey is repaired by citing a paper that supports the claim or
dropping the claim, only in the sections named. A **candidate** is
pursued only where it bears on the sub-theme in play, reached with
`evidence` instead of `search`, since the report already holds the
citekey. A **reconsider** entry is shown with its reason and reopened
only if that reason has stopped holding.

Then the fingerprint is re-stamped and the gate runs. The gate decides,
because `missing` comes from the dossier and only `citation_gate` reads
the draft body. Re-grounding promises an empty `missing` list, and
deliberately not an empty `candidates` list: silencing candidates by
writing them into `rejected.md` would turn a title into a permanent
judgment, the same objection that rules out a `triage` stage
([REJECTION.md](REJECTION.md)).

### ⚙ The scoped default, and the way out of it

Steps 3–5 are an economy, and an economy can start reading as a rule
about what the user may ask for. Whether a revision touches one
sub-theme is a judgment about someone else's draft, and
[SOUL.md](../SOUL.md) puts "let a machine outrank a human on a judgment
call" under what this assistant will not do.

So the way out is a second skill, `corpus-reviser`, which re-searches
every sub-theme the dossier records (the queries in `retrieval.md`, or
the headings in `sections.md`) and reads the whole draft. It is invoked
when the user asks for it, when an agreed scope change invalidated the
old queries, or when the draft is re-targeted at a different reader. Its
cost is stated and written into `revisions.md` before the first search
([GENRE.md](GENRE.md#-revising-widely-corpus-reviser)).

**Why a separate skill and not a mode.** A split only enforces anything
if it removes a capability. `draft-reviser` contains no instructions for
a wide search, so following it cannot produce one by drift, which is the
strongest enforcement available for a rule that must not become a gate.
It also makes the expensive path something the user opts into by name.
The same test is why re-grounding is *not* a third skill: its cost is
bounded by the queries already in `retrieval.md`, so splitting it out
would remove no dangerous capability while duplicating the repair loop.

The guardrail that remains is **never re-run the genre skill**, which
discards the dossier and pays to rediscover a worse version of it. A
wide re-search keeps and honours `rejected.md`, the reader and the
glossary, and still edits section by section, because wide *search* does
not imply wide *rewrite*. Nothing enforces any of this: the only
mechanical gate is `citation_gate`, and a token-economy heuristic does
not earn one.

### 🔗 Section anchors

`sections` extracts the outline from the draft itself, so it cannot go
stale and survives hand edits. It skips code first: a `# Step 1` comment
in a fenced block would otherwise read as a heading and cut a code block
in half. Markdown fences (``` and `~~~`) and LaTeX
`verbatim`/`lstlisting`/`minted` environments are both tracked.

## 💾 Backup and restore

`content/dossiers/` is gitignored, like `content/drafts/` and
`content/rendered/`, because `evidence.md` quotes copyrighted sources.
The only committed dossiers are real runs' records: the four samples
under `docs/examples/sample-project/content/dossiers/dt-overview/`, and
one per harness example under `docs/examples/codex/` and
`docs/examples/opencode/`. A dossier assembled for show would be a
reconstruction posing as a record.

What replaces version control is `python -m chitragupta.draft dossier
export` and `restore`. Archive paths are relative to `content/`, so a
bundle restores into a project whose `[content].dir` points elsewhere.
Restore is a dry run unless `--force`, and an unsafe member refuses the
whole archive, because a partial restore looks like it worked. A bundle
carries neither `content/ledger.sqlite` (regenerable by `sync`) nor
`papers/bibliography.bib`, which is your reference manager's and not
this pipeline's to own; on a machine with no corpus the gate cannot
verify anything until `sync` has run.
[MIGRATION.md](MIGRATION.md) has the commands, what a bundle holds, how
restore protects you, and how to move a project.

## 🚫 What this deliberately does not do

**It is not a gate and it takes no lock.** Nothing in
`chitragupta/dossier/` blocks a draft or writes to the corpus layer. A
missing, stale or hand-edited dossier degrades the next revision's
efficiency and can never make a draft wrong.

**It does not verify that a dossier matches its draft.** The reviser
rebuilds the section map from the draft instead of trusting the file,
and `chitragupta/review/citation_provenance.py` reconciles a draft
against its sources independently.

**It does not itself cut what enters the orchestrator's context.**
Trimming what retrieval returns was built and withdrawn
([REJECTION.md](REJECTION.md)). What works is the subagent boundary: one
subagent per sub-theme on a broad topic, keeping only the kept-evidence
packet. The dossier handles the structural cost by avoiding a re-run.

**It does not measure token counts directly.** `retrieval.md` records
each retrieval call's character payload, enough to compare runs but not
to price a whole draft. The estimates in
[TOKENS.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOKENS.md)
remain estimates.
