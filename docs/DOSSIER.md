# 🗂 The dossier

Status: **reference.**

**Written for** whoever reads a dossier back: most often `draft-reviser`
picking up a draft weeks later. **Assumed:** [FEATURES.md](FEATURES.md)
for where the dossier sits among the pipeline's features. **Not covered
here:** what to *do* with one. Revising a draft, re-grounding it after the
corpus moves, dispatching a subagent from it, and backing one up are all
[DRAFT-ITERATION.md](DRAFT-ITERATION.md); this page is the format those
depend on.

**This is machine-facing documentation.** The dossier lets a drafting
run be resumed by something that was not present when it started,
usually an LLM, and its fields are named for what a drafting step may
and may not do with them. [REVIEW.md](REVIEW.md) is its counterpart for
you: a review report is evidence you weigh, a dossier is working state a
machine reloads.

One dossier per draft, mirroring the draft's own path, with no registry:

```text
content/drafts/dt-for-engineers/survey.md
   -> content/dossiers/dt-for-engineers/survey/
```

The draft may be flat or nested at any depth. `content/rendered/` mirrors
the same path, which is how `dossier export <topic> --with-rendered` finds
the renders ([CLI.md](CLI.md#-chitragupta-draft-render)).

`dossier init` writes eight files: `README.md` and the seven core files
below. Three more are optional, `math.md`, `outline.md` and `paper.md`,
and the only three whose absence is not a defect. Each answers a
question the draft itself cannot.

| File | What it holds |
| --- | --- |
| `README.md` | what the directory is and how to back it up; for a person, parsed by nothing |
| `scope.md` | genre, reader, dialect (`language:`), what the draft covers and excludes, glossary (terms only), corpus fingerprint, draft fingerprint |
| `evidence.md` | each kept citekey, why it was kept, and its claim |
| `rejected.md` | candidates retrieved and turned down, with the reason |
| `sections.md` | section heading -> the citekeys cited under it, and while a run is still going, the ones it plans to cite |
| `steering.md` | what the user asked for in chat that the draft doesn't show |
| `revisions.md` | append-only log of what changed and why |
| `retrieval.md` | every retrieval call and the size of what it returned |
| `math.md` | ASCII in the draft -> the LaTeX it renders as ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §12), an optional "Not mathematics" table of spans that are code, and `## Symbols`, what each mapped symbol means |
| `outline.md` | the human's own per-section brief/claim/declared queries |
| `paper.md` | a research paper's paper-level inputs: the software, venue, message, contributions and the evidence for each. Written by `init` for that genre only |
| `versions/` | numbered snapshots of the draft and both forms of its figures, taken by `mark-revision` when the draft changed and by `dossier snapshot --label`; what `draft diff` compares against. Not written by `init` |

Four filled dossiers, written by real drafting runs, are committed under
`docs/examples/sample-project/content/dossiers/dt-overview/`; the
survey's
[`evidence.md`](examples/sample-project/content/dossiers/dt-overview/survey/evidence.md)
and
[`rejected.md`](examples/sample-project/content/dossiers/dt-overview/survey/rejected.md)
show both halves of one judgement.

## 📁 Every file, one by one

Each section says who writes the file and who reads it, its format, what
a drafting step may and may not do with it, and what goes wrong when it
is missing or stale.

### `README.md`: the label on the folder

**Written** by `dossier init`, once, and never rewritten; **read** by a
person, parsed by nothing. Missing, nothing breaks: `init` writes it
back.

### `scope.md`: the boundary

**Written** by `dossier init` (genre, draft, date, the corpus
fingerprint), then by the genre skill as it settles the draft with you:
the reader, the dialect (`language:`, so an en-GB draft stays en-GB
through a later revision), what the draft covers, what it deliberately
excludes, any House style it commits to, and a glossary. `dossier stamp`
writes the draft digest line. **Read** by every reviser before any edit,
by `dossier status` (both fingerprints), by the acronym checks,
`draft style`, a book's `registry`, and `render`.

```markdown
# Scope

- genre: survey
- language: en-GB
- corpus: 5 citekeys, digest `ded95cf5e89c`
- draft digest: `02a5914a9d6e`

## Reader

An engineer joining a digital-twin project who has read none of the corpus.

## Covers
## Does not cover
## Glossary

- **Digital shadow (DS)** -- an automated flow from PT to DO, and a
  return flow that exists but is carried by a person.
```

**The glossary** is one bullet per term, `- **Term** -- definition`, with
a wrapped definition indented and a trailing abbreviation in brackets
belonging to the term. `registry check` reports and `registry build
--glossary` refuses any other shape: a colon instead of ` -- `, two terms
in one bullet, a definition that cites, or a symbol. A symbol and its
meaning live in `math.md`'s `## Symbols`, linked to its term as ``| `M_0`
| **Baseline** |``. A book prints the bullets as written ([the Glossary
and List of
Symbols](book/REGISTRIES.md#-the-glossary-and-the-list-of-symbols)), so a
drafting note belongs in `steering.md`, not a definition.

**May:** change the scope statement only when you agreed to it, and
keep the glossary in step with the prose. **May not:** edit the two
digest lines by hand; only `stamp` and a re-grounding pass rewrite them.
**Missing or stale:** a reviser cannot tell an omission from an
exclusion. A stale corpus line is what drift detection reads, so it is
never "refreshed" to silence `status` ([the corpus fingerprint](#-the-corpus-fingerprint)).

### `evidence.md`: what was kept, and why

One block per kept citekey, carrying `relevance:`, `claim:` and an
optional `quote:`; [the contract](#-evidencemds-claimquote-contract-a2)
below says what each may be used for. Where two blocks share a citekey,
the **first** is the one every reader gets, and `check-evidence` reports
the rest, so a second block never silently displaces evidence a run was
already handed.

### `rejected.md`: the candidates turned down, with the reason

**Written** by the genre skill and every reviser, one row per candidate
retrieved, read and turned down; **read** by every later reviser and by
a re-grounding pass, which needs the sentence and not only the citekey.

```markdown
| citekey | query that surfaced it | why rejected |
|---|---|---|
| `sample_std_interop_2021` | digital twin synchronisation staleness | surfaced for this query but says nothing about staleness; kept for the integration theme instead |
```

"Nothing better in the corpus" and "a different field" age differently,
and only the first is worth revisiting when the corpus grows. **May:**
add rows; move a citekey to `evidence.md` when a change genuinely reopens
it, and say why in `revisions.md`. **May not:** re-judge a listed
candidate as though it were new. **Missing:** the next revision
re-retrieves and re-reads the same papers to reach the same judgement.

### `sections.md`: which citekeys are cited under which heading

Rebuilt from the draft rather than maintained by hand; see
[derived, not maintained](#-sectionsmd-is-derived-not-maintained).

### `steering.md`: what you asked for that the prose cannot show

**Written** by the genre skill and every reviser: one dated entry per
instruction you gave in chat. **Read** by every reviser before it edits.

```markdown
- Keep it under 1,000 words -- this is a documentation sample.
- British English.
- Close with gaps, not a summary of summaries.
```

Such guidance shaped the draft and is invisible in it. It is also where a
drafting note goes when moved out of something that prints it, under a
dated heading such as `## Moved from the glossary (2026-11-04)`. **May:**
append. **May not:** rewrite or drop an earlier entry because a later
revision went another way; add the new instruction instead. **Missing:** a
revision months later silently undoes a decision you made deliberately,
the commonest way a revised draft comes back subtly wrong.

### `revisions.md`: an append-only log of what changed and why

**Written** by every reviser: one entry per revision session, newest
last, naming what changed, which sections and why, including attempts
that failed. `agenda-reviser` logs every attempt, refusals and reverts
included, and a copy-edit pass leaves one entry naming the convention
it applied. **Read** by the next reviser, and by you.

```markdown
## 2026-09-02 -- first complete draft

Drafted from the five kept evidence blocks; all three declared queries
answered. Gate passed on first run.
```

**May:** append. **May not:** edit history. `dossier prune` and
`dossier sections --write` log nothing, so the step that runs one logs
it here. **Missing:** a repair tried and reverted is tried again by the
next session.

### `retrieval.md`: every retrieval call, and the size of what came back

**Written** only by commands, never by hand: `python -m chitragupta.draft
retrieve ... --log <draft>` appends a row per call, and `dossier
mark-revision` appends a `revision` marker row at the start of each
reviser pass. **Read** by `dossier status` (cost per revision, whether the
outline's declared queries ran), by a re-grounding pass, and by
`bench/bench_retrieval_live_logs.py`'s replay. The template's own comment
documents every column; one row of the sample survey's:

```text
date        2026-09-02
mode        search
query       anomaly detection state stream
asked       5
results     3
chars       1247
collection  (empty: corpus-wide)
origin      declared
```

It **bounds re-grounding**: after the corpus moves, candidates come from
the queries already recorded here, so that pass cannot invent a new search
and become a full re-draft. It records each call's character payload, not
tokens: enough to compare two runs, not to price a draft. **Missing or
edited:** re-grounding has nothing to bound it, and `status` cannot say
whether the outline was followed.

### `outline.md`: the human's own structure, declared instead of guessed

**Optional.** **Written** by you, after `dossier init --outline` (or
added later), before drafting; **read** by `dossier outline`, by the
genre skill, which drafts from it, and by `dossier status`. Per section:
a `##`-or-deeper heading (a level-1 line is the file's title), a
`brief:` (steering, never in the draft) and/or `claim:` blocks (your own
prose, rewritten; any sentence that can't be grounded is reported
instead of shipped), and optional declared `queries:` a genre skill runs
verbatim instead of inventing sub-themes.

```markdown
## Failure modes of co-simulation

brief: Focus on timestep mismatch and solver divergence; skip
FMI-specific tooling.

queries:
- failure modes co-simulation
- timestep mismatch solver divergence
```

`dossier outline <draft>` prints the sections and `--check` only
validates them. **May:** a skill adds an `--origin extended` query when a declared
section came up thin. **May not:** a skill rewrites your outline.
`retrieval.md`'s `origin` column (`declared`, `extended` or `reground`)
is what lets `dossier status` answer "did this draft follow its
outline?" from the record. **Missing:** most dossiers have none, which
is not a defect.

**A declared query that came back empty counts as run but not
answered.** `status` reads the `results` column and names such a query
separately:

```text
Outline: 2 declared queries run (1 with no evidence), 1 not, 0 extended, 0 regrounded.
  no evidence  Fault tolerance: 'fault injection digital twin'
  not run   Fault tolerance: 'co-simulation standards validation'
```

This is advisory and **binary**; a query that returned results on any
attempt counts as answered.

### `math.md`: how the draft's mathematics is set, and what each symbol means

**Optional.** A draft with no mathematics, or only §12's inline `$…$`
form, has none. **Written** by the four Markdown genre writers when a
draft first has mathematics, and kept in step by every reviser.
**Read** by `render` for every format that reaches pandoc (not
`--format md`); by `dossier status`, which reports a row the draft no
longer uses; and by a book's `registry`. It holds up to three tables (a
mapping from the exact ASCII span to its LaTeX, a one-column "Not
mathematics" table of spans that are code, and `## Symbols`), whose
format and rules are in
[WRITING-STANDARDS.md](WRITING-STANDARDS.md) §12.

**May:** add, re-key or drop a row as the quantity is added, reworded or
cut. **May not:** borrow another unit's row; each unit's maths resolves
through its own mapping. **Missing or stale:** a draft and its dossier are
tied by **path alone**, and there is no `dossier rename`, so moving a
draft orphans its mapping; `render` refuses when a `<!-- math -->` marker
has no mapping, and lists rewording gaps and orphans among its `[math]`
warnings.

## 🔑 Which tokens count as a citekey, and why the rule has two halves

A citekey is read out of a dossier from a backticked or `@`-prefixed
token. The default shape requires a separator run (a letter start, then
at least one `_`/`:`/`-` followed by more alphanumerics), so
`@noauthor_digital_nodate` is a citekey and `@someone` and `@2` are not.
The separator is required because this set is differenced against the
ledger in *both* directions, and on the "what has left the corpus?" side
an invented token would be reported as a broken citation.

On its own, that rule would make `Doe2024` and `Lamport94`, the default
style of several reference managers, invisible, so a paper such a
dossier cited could leave the corpus and **never** be reported: the
worse failure of the two. So a separator-free token is admitted only
when it is a member of the ledger or a citekey the dossier *declares* by
opening an `evidence.md` heading with it, which catches a key that has
left the ledger. Only a declared key (in an `evidence.md` heading or a
`sections.md` cell) can be reported missing; a backticked word in prose
never is. The strict scan is never replaced by the loose one, only
added to.

## 💡 Why Markdown

A model and a human both read Markdown natively, and a restored tarball
stays legible without this code. `chitragupta/dossier/` parses only the
corpus fingerprint line and backticked citekeys, and both degrade to
"unavailable" rather than an error after free hand edits. There is no
schema, so nothing validates `evidence.md`; a check that blocked on what
it cannot verify exactly would train people to work around it. A
malformed dossier makes the next revision less efficient, never a draft
wrong, because the citation gate still stands between any draft and the
user.

## 📖 `evidence.md`'s `claim:`/`quote:` contract (A2)

One `## \`citekey\`` block carries three possible fields:

```markdown
## `sample_dt_sync_2023`

relevance: why this source bears on the sub-theme
claim: what the source establishes, in the drafter's own words
quote: an optional verbatim span, quotable-only
```

- **`relevance:`** says why this source bears on the sub-theme.
- **`claim:`** is required, and is **the only field a drafting step may
  write prose from.** It is written by whoever judged the evidence, at
  the moment they judged it, before any sentence of the draft exists.
  Because of that ordering, a claim written from memory, once the passage
  is off screen, cannot be a lightly edited copy of it.
- **`quote:`** is optional, verbatim, and usable in a draft **only**
  inside quotation marks with an attribution, except in a verbatim
  digest ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)), whose body is
  copied runs rendered in place with their citations: there each
  source's `quote:` records the passage the digest leans on most, every
  other run is checked where it stands by `review digest`, and `claim:`
  is drafted from only for the drafter's own sentences. It is absent by
  default: a captured quote is a quote in the drafter's context, which
  is the thing this contract removes, so one is captured only when a
  quotation is intended.

**A `support:` field.** An older block may carry `support:` instead of
`claim:`/`quote:`, holding in practice a raw retrieval window
(`EVIDENCE_CHARS = 600` in `chitragupta/retrieval_cli.py`). `support:`
is **read but never written**, and nothing rewrites one to the newer
shape; `evidence_blocks()` returns a block verbatim, so old and new
coexist by construction. A skill meeting a `support:`-only block reads
it as `quote:`, the conservative reading.

**That rule covers what a drafter *may quote from*, and does not extend
to anything that *prints* the field.** The two questions have opposite
safe answers:

| | Reads a `support:`-only block as... | Why |
| --- | --- | --- |
| A drafting or revising skill | `quote:` | It is deciding whether the block may be quoted at all. Treating unknown provenance as quotable-only is the cautious answer, because it *restricts* what the skill may do with it |
| `chitragupta/evidence_appendix.py` | nothing at all | It is deciding what to put in a rendered document. A legacy `support:` holds a raw 600-character retrieval window (`EVIDENCE_CHARS`), and printing one as an attributed quotation would publish it |

So the evidence sidecar ([CLI.md](CLI.md#-chitragupta-draft-evidence))
reads `quote:` and only `quote:`, and a `support:`-only dossier renders
no sidecar. `claim:` is excluded for the mirror-image reason: it is the
drafter's own words, so quoting it back would attribute this project's
prose to the source. `tests/test_evidence_appendix.py` pins this.

### 📖 The evidence sidecar, decided per genre

Four of the six drafting skills also render an **evidence sidecar**,
`content/rendered/<topic>/<name>.evidence.{md,pdf}`, listing each cited
source and the verbatim spans its dossier marked quotable
([CLI.md](CLI.md#-chitragupta-draft-evidence)). It changes what a
finished document set looks like, so each genre decides for itself:

| Skill | Emits one? | Why |
| --- | --- | --- |
| `deep-research` | **yes**, the strongest case | Showing its work is the product |
| `survey-writer` | **yes** | Citation-dense, and its reader is mapping a field |
| `thesis-chapter-writer` | **yes** | An examiner is the ideal reader, and a standalone sidecar is never `\input` into the thesis |
| `textbook-chapter-writer` | **yes, and usually empty** | Citation-thin by design, so most chapters capture no `quote:` and nothing is written |
| `review-digest` | **no** | Every copied run is already cited source wording, so a sidecar would print the digest back |
| `tutorial-writer` | **no** | It cites only in "Where to go next", and a learner at a keyboard needs the next command, not an attributed quotation |

A sidecar is never committed: `.gitignore` excludes it even under the
example topic whose renders are tracked, because it carries verbatim
wording from copyrighted sources. [GENRE.md](GENRE.md#-the-six-drafting-genres)
says what each genre otherwise produces.

**The self-check.**
`python -m chitragupta.draft dossier check-evidence <draft>` first names
any citekey carrying more than one block, then compares each block's
`claim:` against its own `quote:` (`chitragupta/dossier/_evidence_check.py`,
reusing `chitragupta/overlap_skipgram.py`'s stemmed word stream) and
warns when the claim reads like the quote with its words moved. It is
advisory and prints no score by default:
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s R3 rules out a similarity
number a drafting step could optimise against. `--score` opts into the
number for a human reading by hand.

## 💡 Why several files rather than one

Several files let a revision load only what it needs. `scope.md` and
`sections.md` are small and almost always relevant; `rejected.md` is the
largest and is needed only when a change reopens a sub-theme. One file
would have to be read whole every time.

## 🔄 `sections.md` is derived, not maintained

A heading owns a line range, a citekey is cited on a line, and the
relation falls out of the intersection. Attributing keys by hand is a
mechanical step with a wrong answer available, and a `sections.md` that
disagrees with the draft hands `draft-reviser` the wrong section for a
citation.

```bash
python -m chitragupta.draft dossier sections content/drafts/<slug>.md --citekeys --write
```

builds it from both citation syntaxes, skipping fenced code and LaTeX
verbatim so a `# Step 1` comment in an example listing is neither a
heading nor a citation. A key cited above the first heading belongs to
no section and is reported on stderr.

`deep-research` is the exception, and only for timing: it writes *planned*
rows before the sections exist, and Phase 7(e) replaces them with what the
finished report cites.

## 💡 Why not merge the provenance JSON into the rest of the dossier

`thesis-chapter-writer` and `deep-research` also write a
`provenance.json`, **inside** the dossier directory at
`content/dossiers/<draft path minus suffix>/provenance.json`: it is that
run's drafting state, and the mirrored path keeps two drafts named
`survey.md` in different topics from sharing one file. It stays a
separate file because it answers a different question for a different
reader:

| | `provenance.json` | the dossier's Markdown |
| --- | --- | --- |
| Shape | JSON, machine-readable | Markdown, human-readable |
| Holds | section -> citekey, and why that source supports that claim | reader, scope, glossary, kept evidence, **rejected candidates and why**, steering |
| Read by | tooling, and a reviewer auditing one claim | `draft-reviser`, and a human months later |
| Lost if absent | an audit trail for a finished draft | the ability to revise without re-running the whole topic |

Merging them would put prose a human needs into JSON, or a machine
record into Markdown nothing parses.

## 📚 The corpus fingerprint

`scope.md` records how many parsed citekeys the ledger held when the
draft was written, plus a 12-character digest of that set. Only `parsed`
rows count, since an unparsed entry is not citable (a fingerprint
recorded before 6.160.0 counted every row, so it mismatches once):

```text
- corpus: 501 citekeys, digest `a1b2c3d4e5f6`
```

`python -m chitragupta.draft dossier status` recomputes it. If it differs,
the corpus has moved, and the command names the citekeys that appear
nowhere in the dossier (neither kept nor rejected). It opens the ledger
read-only, with no write lock and no migration, but waits out a writer's
commit rather than report drift against an empty corpus.

**Drift is not itself a reason to redraft.** A corpus that *grew* is a
reason to re-search only if the change being made touches a sub-theme
the new papers could bear on. A corpus that *lost* a paper the draft
cites has produced a broken citation, which is fixed whether or not
anyone asked. [DRAFT-ITERATION.md](DRAFT-ITERATION.md#-two-findings-and-they-are-not-the-same-kind-of-thing)
draws that line and acts on it in
["Re-grounding after the corpus moves"](DRAFT-ITERATION.md#-re-grounding-after-the-corpus-moves).

The fingerprint is written once, by `init`. Only a re-grounding pass
rewrites it, as the record that the draft was brought back into line
with that corpus.

## 🧭 The draft fingerprint (FEATURE-ROADMAP.md's E3)

The draft fingerprint stops a hand edit silently leaving `sections.md`,
`evidence.md` and `math.md` describing a document that no longer exists.
[WRITING-PROCESS.md](WRITING-PROCESS.md#-handing-a-hand-edited-draft-back-for-the-next-iteration)
covers handing a revised draft back from the user's side. `scope.md`
carries a text digest of the draft:

```text
- draft digest: `a1b2c3d4e5f6`
```

Before the first stamp it reads `not recorded`.

`init` does not write it, since a half-written draft would then read as
changed on its first real `status`. Each of
the six genre skills stamps at its finishing step, and
`draft-reviser`/`corpus-reviser` re-stamp after their own edits, always
after `python -m chitragupta.draft gate` passes:

```bash
python -m chitragupta.draft dossier stamp content/drafts/<path>
```

`agenda-reviser` may not touch `scope.md`, so a repair it makes leaves
the fingerprint stale on purpose: `CHANGED since last stamp` then
signals that an automated pass touched the draft since a person last
confirmed it.

`dossier status` reports `unchanged since last stamp` or
`CHANGED since last stamp`. A changed digest only says *that* the draft
moved, so only then does `status` check five specific classes:

| Class | What it means |
| --- | --- |
| a citekey cited in the draft with no `evidence.md` block | a hand-added citation, otherwise invisible to drift reporting, which reads the dossier |
| an `evidence.md` block whose citekey is no longer cited | the reverse: the citation was removed by hand |
| a heading with no row in `sections.md` | the draft's own outline moved |
| a `sections.md` row with no matching heading | the same drift, read the other way |
| a `math.md` row appearing nowhere in the draft | a revision reworded or deleted its equation (`render` warns of the same orphan) |

`draft-reviser` offers each finding to the user one at a time and acts
only on what they agree to. It **never applies a repair unasked, and
never blocks the revision on one going unanswered.** A digest never
stamped reports `not recorded`, which is not drift to chase.

The draft digest is `chitragupta.spec.digest`, a plain sha256[:12] of the
text, not the corpus fingerprint's order-independent digest over a set of
citekeys, which would not move for a reworded sentence.

### 🧹 The second row has a command, and a second reader

**An uncited `evidence.md` block is removable by a primitive instead of
a hand edit:**

```bash
python -m chitragupta.draft dossier prune content/drafts/<slug>.md              # dry run
python -m chitragupta.draft dossier prune content/drafts/<slug>.md --apply
python -m chitragupta.draft dossier prune content/drafts/<slug>.md --citekey sample_dt_factory_2022 --apply
```

It is a dry run by default because `recorded - cited` cannot tell a
citation the user cut from a candidate transcribed and never cited, and
the two want opposite repairs. It touches `evidence.md` only, never
`rejected.md`, and refuses a citekey with two blocks, one still cited, or
one recorded only in `sections.md`.

**And `status` is not the only surface that reports it.** Its classes
are gated on a changed digest, so a never-stamped dossier answers
nothing. `python -m chitragupta.review agenda` computes the same state
**ungated**, as a surfaced `recorded-but-uncited` item, over
`sections.md` as well as `evidence.md`. `status` keeps its gate because,
unconditional, these classes fire on almost any real dossier and become
a wall nobody reads.

### 🔁 The fingerprint as a retrieval trigger (FEATURE-ROADMAP.md's E4)

A `CHANGED` fingerprint is also ITER-RETGEN's `y_{t-1}` (Shao et al.,
*Findings of EMNLP 2023*, docs/RAG.md) with a person in the generation
slot: a hand-edited section's prose can drive one extra retrieval round
for that section. `draft-reviser` offers this, never unasked, once the
staleness findings are settled and only for a section `outline.md`
declares a query for.

```bash
python -m chitragupta.draft retrieve search "<query>" \
    --y-prev "<section's current prose>" --origin reground --log <draft>
```

Exactly two rounds (`chitragupta/retrieval_iterative.py`): round 1 is
the plain query, round 2 appends the prose (bounded to 1500 characters,
on a word boundary), and the results are merged by citekey and capped
back to `--k`. The prose never becomes draft content, an `evidence.md`
block, or anything persisted beyond the query string.
