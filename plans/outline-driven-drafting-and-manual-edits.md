# 🧭 Outline-driven drafting, and picking a hand-edited draft back up

Status: **designed, unbuilt, unapproved.** Written 2026-08-28.

Two workflows the drafting layer does not support today:

1. **The human supplies the structure.** Today all five genre skills
   manufacture their own retrieval queries from a one-line topic --
   `survey-writer` step 1 is the prose instruction *"break the requested
   topic into 2-4 sub-themes"*. There is no way to hand the pipeline an
   outline, a per-section brief, or the queries you actually want run.
2. **The human edits the draft by hand, then asks for a revision.**
   Nothing detects that the draft moved. `scope.md` fingerprints the
   *corpus*; nothing fingerprints the draft. So `sections.md`,
   `evidence.md` and `math.md` silently describe a document that no
   longer exists, and `draft-reviser` reads them as current.

**Written for** whoever builds this. **It assumes**
[docs/DRAFT-ITERATION.md](../docs/DRAFT-ITERATION.md) for the dossier,
[docs/BOOKS.md](../docs/BOOKS.md) for the book track's outline and unit
contract, [docs/RETRIEVAL.md](../docs/RETRIEVAL.md) and
[docs/CORPUS-SEARCH.md](../docs/CORPUS-SEARCH.md) for the search path,
and [DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the cycle each PR
runs.

**Not covered here:** the pre-gate self-feedback loop. Findings from this
research that bear on it are amendments to
[FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s **B5**, recorded in
[§B5 amendments](#-amendments-owed-to-b5-not-a-new-item) rather than
respecified under a new name.

Every number below names the command that produced it.

## 🧭 Table of contents

- [What was measured](#-what-was-measured)
- [The finding that reframes the work](#-the-finding-that-reframes-the-work)
- [What the four upstreams actually do](#-what-the-four-upstreams-actually-do)
- [PR 1: strip interrogatives from the query](#-pr-1-strip-interrogatives-from-the-query-side)
- [PR 2: an outline the human writes](#-pr-2-an-outline-the-human-writes)
- [PR 3: notice that the draft moved](#-pr-3-notice-that-the-draft-moved)
- [B5 amendments](#-amendments-owed-to-b5-not-a-new-item)
- [Adjacent, deliberately not bundled](#-adjacent-deliberately-not-bundled)
- [What is deliberately not proposed](#-what-is-deliberately-not-proposed)

## 🔬 What was measured

Three measurements against the real corpus at `/workspace` (642 ledger
items, 497 parsed), 2026-08-28. All read-only; `search()` takes no lock.

### 1. Question-form queries retrieve different papers than keyword-form

Six paired queries, each asked as a natural-language question and as the
equivalent keyword string, `k=10`, BM25:

| | mean overlap@10 | top-1 identical |
| --- | --- | --- |
| question form vs keyword form | **4.7 / 10** | 2 of 6 |

Asking the same question in prose returns **less than half the same
papers**. The mechanism is visible in the tokenizer -- `_STOPWORDS`
(`chitragupta/retrieval.py:54`) holds twenty function words and **no
interrogatives**, and the `len(w) > 2` filter passes `how`, `why`, `who`,
`can`:

```text
'what are the failure modes of co-simulation' -> ['what', 'failure', 'modes', 'simulation']
'why does model calibration matter'           -> ['why', 'does', 'model', 'calibration', 'matter']
```

`what`, `why`, `does` and `matter` are scored as BM25 terms. Because they
are *rare in academic PDFs* they carry high IDF, so they do not merely add
noise -- they compete for the ranking.

**Stripping them from the query alone closes it, and rebuilds nothing:**

| | mean overlap@10 | index rebuilt |
| --- | --- | --- |
| raw question form | 4.7 / 10 | -- |
| query-side strip only | **9.2 / 10** | **no** |

The query-side-only result is the whole of the effect. That matters for
scope: see [PR 1](#-pr-1-strip-interrogatives-from-the-query-side).

**This is a convergence measurement, not a correctness one.** The keyword
form is the reference, not ground truth. The claim it supports is
*"phrasing a query as a question no longer changes which papers you
get"* -- which is exactly the property [PR 2](#-pr-2-an-outline-the-human-writes)
needs, and not a claim that ranking improved. See PR 1 for what has to be
measured before it ships.

### 2. Retrieved snippets carry their sources' own citation markers

180 snippets (12 queries x `k=15`, 500 chars each):

| Marker family | Snippets | Share |
| --- | --- | --- |
| numeric bracket -- `[12]`, `[1, 2]`, `[1-3]` | 39 | 21.7% |
| author-year -- `(Smith et al., 2019)` | 2 | 1.1% |
| **any of the above** | **41** | **22.8%** |

Nothing in `chitragupta/retrieval.py` or `chitragupta/passages.py` strips
them, so roughly one snippet in four puts a foreign citation marker into
a context whose job is to emit `[@citekey]`.

### 3. …and that has never actually leaked into a draft

The obvious follow-up, run over all seven real drafts under
`/workspace/content/drafts/`: **zero** source markers in any draft body.
Every apparent hit was a legitimate numbered reference list. (The first
pass reported 38 in `da/anvendelser-af-digitale-tvillinger.md`; that file
ends `## Referencer`, which the English-only heading filter missed. Two
further files use `## 7. References` and `## 7.14 References`, which a
`^#+\s*References` pattern also misses.)

**So measurement 2 is context hygiene, not a fabrication vector**, and
this plan does not claim otherwise. Its real payoff is elsewhere: reference
markers are already known here to dominate quote-versus-parsed-text
matching failures, which is `verbatim scan`'s problem and C3's.

## 🔭 The finding that reframes the work

Both workflows are already solved in this repository -- **at book scale
only** -- and a third, partial solution is locked inside one genre skill.

| Capability | `spec`/`unit` (book) | `deep-research` (one draft) | Other four genres |
| --- | --- | --- | --- |
| Structure on disk | `spec.md`, four heading levels, `{#id}` required | `sections.md` rows, written at Phase 4 | -- |
| Authored by | **the human** | **the model** | -- |
| Approved before prose | `spec sign`, digest sign-off | -- | -- |
| Per-section brief | text under each heading -> `unit contract` | outline fragment in the dispatch | -- |
| Per-section grounding | `--source <citekey>`, in the input digest | `sections.md` citekeys -> `dossier brief --section` | -- |
| Dispatch without pasting evidence | -- | **`dossier brief --section`** | -- |
| Detects the prose moved | **`unit status` -> `stale: draft changed since accepted`** | -- | -- |

Two consequences:

- **The mechanism for PR 2 mostly exists.**
  `chitragupta/dossier/_brief.py` already resolves a section name through
  `sections.md` to its evidence blocks, and `--check` validates the rows
  resolve *without printing them*. What is missing is that a human cannot
  author those rows, and four of five genres never use them.
- **The mechanism for PR 3 exists verbatim, one scope away.** The book
  track re-derives a prose digest and reports
  `stale: draft changed since accepted`. Reuse the vocabulary.

**Why not simply widen `spec`/`unit` to single drafts.** `content/specs/`
mirrors a *directory*, because a book is a directory of drafts in which a
section is the generation unit. A survey is one file, and the whole file
is the unit -- there is nothing for `unit contract` to slice, and
`book > part > chapter > section` has no single-draft reading. The two
human sign-offs are right for a 178,000-word book and wrong for a
2,400-word survey. The dossier already mirrors exactly one draft and
already holds the reader, the scope and the glossary; an outline is its
missing sibling, not a second spec system.

## 📚 What the four upstreams actually do

Read for architecture only, under
[INSPIRATION.md](../docs/INSPIRATION.md)'s standing rule -- *"Attribute
the idea, and never copy the text."* Nothing here is ported as text.

**The headline result is negative, and it is the useful part: three of
the four have no query manufacture at all.**

| Project | Licence | Query manufacture | Citation verified? |
| --- | --- | --- | --- |
| [OpenScholar](https://github.com/AkariAsai/OpenScholar) | Apache-2.0 | **None.** No decomposition, no rewriting, no HyDE. Its one LLM generator caps at 3 by `split(", ")`, at temperature 0.9 under a comment reading `# greedy decoding` | No. Positional `[n]` into a reranked list; posthoc attribution is a pure LLM prompt that silently returns the original on missing markers |
| [RAGFlow](https://github.com/infiniflow/ragflow) | Apache-2.0 (verified unmodified; single commit to `LICENSE`, 2023-12-12) | Three LLM rewrites, **all off by default**. Decomposition exists behind `thinking_mode` | No. If the model emitted any marker, the only check is `i < len(chunks)` -- an array-bounds check |
| [papersgpt-for-zotero](https://github.com/papersgpt/papersgpt-for-zotero) | repo AGPL-3.0; shipped engine proprietary | **None**, verified in both versions. Raw user string straight to embedding | No. One regex rewrites `REFID:` into an anchor; links scroll within the answer pane |
| [local-deep-research](https://github.com/LearningCircuit/local-deep-research) | MIT | Fixed round counts. One deterministic templated generator (entity coverage) | No. Its own benchmark **strips citation markers before grading**, so citation correctness is never measured |

### The three ideas worth taking

1. **Deterministic interrogative/stopword stripping before lexical
   search** (RAGFlow's `rmWWW`, `common/query_base.py:39` -- five
   regexes, query-side, no model). Measured here at 4.7 -> 9.2. This is
   [PR 1](#-pr-1-strip-interrogatives-from-the-query-side).
2. **Coverage must be marked on evidence retrieved, never on query
   issued.** LDR's `progressive_explorer.py` marks an entity covered when
   it *appears in an issued query*, so a search that returned nothing
   marks its topic covered forever. Taken as an inverted lesson; belongs
   to [B5](#-amendments-owed-to-b5-not-a-new-item).
3. **Strip a source's own citation markers from a passage before it
   enters a prompt** (OpenScholar's `remove_citations`,
   `open_scholar.py:37`). Take the idea, not the regex -- theirs also does
   a global `.replace("]", "")` and mangles every legitimate bracket.
   Justified by measurement 2, scoped by measurement 3.

### What is rejected, and why

- **Length-ratio edit acceptance** (OpenScholar, `len(edited)/len(orig) > 0.9`).
  Accepts any edit that grows the answer and rejects every correct
  tightening. FEATURE-ROADMAP already rejects it on **R3**; this research
  confirms it from source, which is evidence for a standing decision, not
  a new one.
- **Threshold relaxation until something cites.** RAGFlow's
  `insert_citations` multiplies its 0.63 threshold by 0.8 in a `while`
  loop until at least one sentence attaches a citation. Engineered to
  always produce *a* citation -- the exact failure this project exists to
  prevent.
- **Citing from source papers' own bibliographies** (papersgpt injects
  each PDF's reference list as `[BIBLIOGRAPHY]` and points the numbered
  citations at it). Those works were never parsed and need not be in the
  library. This manufactures the one failure CLAUDE.md forbids.
- **Any LLM in the pre-retrieval path.** Non-deterministic, and off by
  default even upstream.
- **Fixed round counts dressed as convergence.** LDR's early termination
  is disabled at every call site and its one gap-analysis function has
  zero production callers.

### None of the four can revise a draft, which is what PR 3 is about

The same read asked what happens once output exists and you want it
*changed*. Taking revision to mean *a path that accepts a prior artifact
as input, emits a modified version of that artifact, and persists it so
the prior is superseded*: **none of the four supports it. Regeneration is
the only model, zero for four.** Three near-misses, each failing
differently:

| System | Looks like revision | Why it is not |
| --- | --- | --- |
| OpenScholar | the `--feedback` edit loop | runs **before** the artifact exists |
| RAGFlow | a **regenerate** button | truncate-and-resend: the prior answer is destroyed, never read as input, no version kept. `PATCH .../sessions/<id>` **explicitly refuses** to change stored messages -- a deliberate refusal, not a gap |
| papersgpt | "writes findings into Zotero Notes" | **appends at the cursor** of an already-open editor; never looks a note up |
| local-deep-research | follow-up with a `parent_research_id` | creates a **new child row**; the parent is untouched |

Three properties, each one a requirement this project already meets:

- **No hand-edit detection anywhere** -- no digest, mtime or version
  check on output in any of the four. OpenScholar is the worst case: it
  reads its output file back, but only for a row count, so edited content
  is silently honoured.
- **No section-scoped editing anywhere.** The unit of change is always
  the whole document.
- **Evidence reuse in two of four, forced re-search in both.**

**All four persist far more than they consume** -- OpenScholar writes a
complete refinement audit trail and reads back only `len()`; RAGFlow
stores per-turn chunks in a parallel array no revision path uses. The
state a revision feature would need already exists on disk in three of
them; what is missing is any entry point that reads it.

That is exactly what the dossier and the `draft-reviser` /
`corpus-reviser` split already are here, and this read found no
equivalent anywhere. It also sharpens PR 3's scope: **on hand-edit
detection this pipeline is currently no better than the four.** Nothing
fingerprints the draft, so that gap is real rather than comparative.

### Where this pipeline is already ahead

Worth recording so nobody "fixes" it toward an upstream: a per-citekey cap
(BM25 is one-result-per-citekey by construction; the dense path has
`embed_max_passages_per_source`, applied *before* truncation -- RAGFlow has
no per-document cap at all), a rerank that sits **before** the cap rather
than after, and a citation check that is set membership against a real
ledger rather than an array-bounds test.

## ▶ PR 1: strip interrogatives from the query side

**Prerequisite for PR 2, and independently valuable.** PR 2 invites the
human to author queries; humans write questions; this pipeline currently
mis-ranks questions.

**Query-side only.** BM25 scores query terms against document term
frequencies, so a term absent from the query contributes nothing whatever
the documents hold. Stripping in the query path alone therefore buys the
entire measured effect while leaving `_tokenize`, every document's
`term_freqs`, every IDF and `_INDEX_SCHEMA_VERSION` untouched -- and
leaves `bench/RESULTS.md`'s standing BM25 baseline (nDCG@5 0.7321)
undisturbed. A symmetric change to `_STOPWORDS` would re-rank every query
in the corpus and put that baseline in play for no additional gain.
Verified: the 9.2/10 run above rebuilt no index.

**What to measure before it ships.** The six pairs above are a probe, not
a result, and this repository does not ship a ranking change on a probe.
Two honest complications:

- `bench/bench_retrieval_compare.py` takes `--ground-truth`, and
  `bench/bench_retrieval_ground_truth.py` builds 48 real
  `(query, citekey)` pairs -- but those queries are **claim text from the
  drafted book**, i.e. declarative sentences. A ground truth containing no
  questions cannot measure a fix aimed at questions.
- So this PR owes a question-form query set with known-correct citekeys,
  and must report recall@3 / recall@5 / nDCG@5 in the shape B4's table
  uses. It must also report the **claim-form** figures, to show the change
  is inert where it should be inert.

Two house rules attach: a `bench/` script that publishes a number must
fabricate a difference and assert it sees it, and adding any `bench/*.py`
reddens a test that counts them. Check whether the existing comparator can
take a variant before adding a script.

Also in this PR, justified by measurement 2 and scoped by measurement 3:
strip a source's own citation markers from `search()` snippets and
`evidence()` windows. **A scoped pattern, unit-tested against passages
carrying brackets in mathematics and code** -- not a global `]` delete.

## ▶ PR 2: an outline the human writes

A new dossier file, `outline.md`, created by
`dossier init --outline` and edited by the human before drafting. Per
section: the heading, a **brief**, and the **declared queries**.

### Two paragraphs under a heading: the ambiguity is the defect

The question this section has to answer: **you hand the pipeline an
outline and one of its sections contains two paragraphs of your own
prose. What are they?** A brief, to be read and written from -- or text
you want to appear? The two are indistinguishable as prose, so a skill
must guess, and either guess is wrong half the time.

#### Recording who wrote it is the wrong fix

The obvious answer is a provenance span marking your paragraphs as yours,
which the advisory aids then skip. **Rejected, and the reason generalises
past this feature.**

A draft gets revised. `draft-reviser` rewrites, shortens, re-scopes and
copy-edits the prose inside such a span, legitimately -- that is what it
is for. After one revision the span is part your wording and part the
model's; after two nobody can say which part; and the marker still
asserts a single author. **The record does not decay gracefully, it
becomes false while continuing to look authoritative** -- and an aid told
to skip it would then be skipping the model's prose on a stale claim.

This repository already treats that as the serious failure. `sections.md`
is regenerated immediately before a scan rather than trusted, and
`math.md` desyncing on a reworded span is called out as a hazard, both
because **recorded state a later edit can silently falsify is worse than
no record**. Authorship is the least recoverable case: a citekey can be
re-derived from the draft and a section map rebuilt from its headings,
but nothing can recompute who wrote a sentence after the fact.

So there is **no author provenance and no aid exemption resting on one**,
and this plan does not propose one.

#### What is declared instead

Intent is declared **about the input**, checked once and then discharged
-- not attached to the output, where it would have to survive every later
edit:

| Declared as | In the draft? | What the pipeline owes you |
| --- | --- | --- |
| `brief` | no | write the section from it; your wording is not preserved |
| `claim` | no -- rewritten | find a citekey supporting each assertion, and **report every sentence that could not be grounded** rather than shipping it |

Neither leaves a marker, because neither needs one: a brief is consumed
by the time the draft exists, and a claim's grounding is re-checkable at
any point against the ledger. That is the property authorship lacks, and
why this split survives revision.

`claim` is the one worth building deliberately -- it turns your
paragraphs into an obligation the pipeline can discharge honestly, and
*"I could not ground your third sentence in this corpus"* is precisely
the output this project exists to produce.

**If you want your exact words in the draft, put them in the draft.**
They are then draft prose like any other. That is not a gap; it is what
is true of every sentence in a revised document.

**Declared queries bind by default.** The skill runs them verbatim instead
of inventing sub-themes. `--extend` permits additions where a sub-theme
comes up thin, and an added query is logged distinctly -- so
`retrieval.md` can be diffed against the declared list and *"did this
draft follow my structure?"* becomes decidable rather than trusted.

**`retrieval.md` gains an `origin` column** (`declared` / `extended`),
exactly as #254 added `collection` for the same reason: a scoped call and
a corpus-wide one wrote byte-identical rows and nothing downstream could
tell which had run.

> ⚠ **`_retrieval_rows` will silently swallow the new column.** Its guard
> is `if len(cells) not in (6, 7): continue`. An eighth cell makes every
> new row **skipped, not rejected** -- `retrieval_cost` undercounts and
> `recorded_queries` loses the queries entirely. Extend the tuple to
> `(6, 7, 8)` and pad a short row exactly as #254's column is padded.

**Generalise the corpus-grounded step, which is the best idea already
here.** `deep-research` Phase 1 runs 1-2 broad calls *before* naming its
perspectives, so the structure is derived from what the corpus actually
holds rather than what the topic suggests. An outline written blind is an
outline whose sections the corpus may not support. `dossier init
--outline` should therefore print what a broad call returns, and the
skills should read `outline.md` through the existing
`dossier brief --section`.

**No sign-off gate.** That ceremony stays book-scale. `spec sign` guards a
178,000-word generation run; an outline for one survey does not earn a
second gate, and [FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s
constraint 2 says the gate means exactly one thing.

Touches all five genre skills' step 1 (`survey-writer`,
`thesis-chapter-writer`, `textbook-chapter-writer`, `tutorial-writer`,
`deep-research`). Note that `survey-writer`'s SKILL.md currently states
that `retrieval.md` records *"not the collection (#254)"*, which is stale
against the code; a schema change to that file corrects that prose too.

## ▶ PR 3: notice that the draft moved

`scope.md` gains a **draft fingerprint** beside its corpus fingerprint,
and `dossier status` re-derives it and reports
`stale: draft changed since accepted` -- the book track's own wording.

> ⚠ **Do not reuse `dossier.digest()`.** It is order-independent over a
> *set of citekeys* (`dossier/__init__.py:202`) and is meaningless over
> prose. The text digest is the one in `chitragupta/spec/_cli.py`.

**Say who stamps, in the docstring.** Drafts are written by a skill's
`Edit` calls, so there is no Python chokepoint to hook. A skill therefore
stamps after editing, and the recorded value means *"the last digest the
pipeline recorded"* -- so a pipeline that forgets to stamp reads as a
human edit. That is the right direction to fail (a false *"you edited
this"* costs one confirmation; a missed one silently corrupts a
revision), and it should be written down rather than left implicit.

**A digest says only that the draft moved.** `status` therefore also
reports four staleness classes, each already derivable:

| Class | Why it matters |
| --- | --- |
| a citekey in the draft with no `evidence.md` block | `dossier status`'s `missing` is computed from the dossier, **not** the draft body, so a hand-added citation is invisible to drift reporting forever |
| an `evidence.md` block whose citation was deleted | the reverse blind spot |
| `sections.md` no longer matching the headings | the embedding tier of `verbatim scan` compares each section against that row |
| `math.md` desynced | it is keyed on exact span text, so any manual reword breaks it |

**`draft-reviser` step 1 branches on this and offers each repair one at a
time.** It never applies them unasked and never blocks -- constraint 2, no
second gate. `dossier sections --citekeys --write` is already the repair
primitive for the third class.

## 🔁 Amendments owed to B5, not a new item

*"Route a critique to wording-or-evidence, and let only the second cost a
retrieval"* is [FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s **B5**,
already specified with dependencies and an acceptance discipline.
Restating it under a new name is what that roadmap exists to prevent, so
these are amendments to B5:

- **Its rejection of the length ratio is confirmed from source.**
  OpenScholar accepts an edit iff it is ≥90% as long as the original, so a
  longer and wronger answer is always accepted and a correct compression
  always rejected. Evidence for the standing **R3** decision.
- **New, and the sharpest lesson of the four:** *coverage is marked on
  evidence retrieved, never on query issued.* LDR marks a topic covered
  when it appears in an issued query, so a search returning nothing marks
  it covered forever. Stated as a **binary** -- evidence came back or it
  did not -- so it does not become a continuous score under R3.
- **A fixed corpus makes a declared query list exhaustible**, so a real
  termination condition is available here where it is not for a
  web-search tool. All four upstreams use fixed round counts because
  their corpus has no edge. This is the one place this design beats every
  one of them, and it is B5's sentence to write.
- **An empty result set is informative.** Against a closed, human-curated
  bibliography, "nothing came back" means the claim cannot be grounded in
  this corpus -- so the sentence is cut, not cited. Every upstream is
  built to always produce a citation; this inverts that.

## 🔗 Adjacent, deliberately not bundled

- **`co-simulation` tokenizes to `simulation`.** The `co` is dropped by
  `len(w) > 2`, on a domain-central term. Real, and not part of PR 1's
  stopword change -- it needs its own measurement.
- **Per-paper reference-list extraction.** papersgpt harvests each PDF's
  own bibliography; a `.bib` export never gives you the reference lists
  *inside* each paper. Inverted -- stored as a set to **check against,
  never cite from** -- it answers *"which work do thirty of my papers
  cite that I do not have?"*, a deterministic corpus-growth signal. A
  corpus-layer item, not a drafting one.
- **Chunk-level bounding boxes at index time.** papersgpt v0.0.16 stored
  `{page, left, right, top, bottom}` per chunk and could scroll to the
  exact rectangle; v1.1.0 moved to page-level chunks with no boxes and its
  click-to-jump now lands on a line the model wrote. Their regression is
  the argument for C3.
- **Zotero annotations as a steering signal.** Verified *not* used by
  papersgpt -- highlights are a manual context injector, never indexed.
  A `.bib` export discards them, so this would need a new corpus-layer
  input.

## 🚫 What is deliberately not proposed

- **A second outline system.** PR 2 is a dossier file, not a rival to
  `spec.md`. The reason is stated above and should be a sentence in
  BOOKS.md so the next reader finds it.
- **A sign-off gate for a single draft.** No second gate.
- **Human prose pasted into the draft.** Named and excluded in PR 2.
- **Auto-reconciliation of a hand-edited draft.** PR 3 offers; it never
  applies unasked.
- **An LLM anywhere in the pre-retrieval path.**
