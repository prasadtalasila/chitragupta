# 🎯 Requirements

Status: **requirements record, revised against the codebase.** Written
2026-08-18. Updated 2026-08-24. The underlying discussion was held
August 2026; this revision was written 2026-08-18, against `main` at
v5.29.0.

What a grounded long-form AI writing system must do, how the closed- and
open-source landscape stacks up against that bar, the architectural
principles that follow from it, and where Chitragupta itself stands
against its own requirement set.

**Written for** someone deciding whether Chitragupta's architecture is
the right one, or picking up its remaining roadmap. **Assumed:** nothing
-- this file is self-contained. **Not covered here:** the day-to-day
mechanics of running the pipeline ([README.md](../README.md),
[CLI.md](CLI.md)); this is a requirements-and-status record, not a
how-to.

*A note on the landscape section's evidence quality (§2), unchanged
since the original discussion: nearly all "Best X in 2026" comparison
content in this product category is vendor-authored SEO material
(Paperguide, SciSpace, Anara, and Kenkyu each publish "neutral"
comparison pages ranking themselves first). Throughout, a claim a vendor
makes **about a competitor** (an against-interest admission, e.g. "Jenni
has no plagiarism checker") is treated as more reliable than a claim a
vendor makes about itself. This section was not re-researched for this
revision -- it is a point-in-time market snapshot, not a tracked claim,
and nothing in §5's status table depends on it. Everything said about
Chitragupta itself in §5 was checked against the current code and the
project's own closed GitHub issues, not carried over from the original
discussion.*

## 🧭 Table of contents

- [1. What a Good Grounded Writing Software Must Do](#-1-what-a-good-grounded-writing-software-must-do)
- [2. The Landscape: Closed and Open Source](#-2-the-landscape-closed-and-open-source)
- [3. Architectural Principles for Grounded Long-Form Drafting](#-3-architectural-principles-for-grounded-long-form-drafting)
- [4. How Chitragupta Was Built](#-4-how-chitragupta-was-built)
- [5. Where Chitragupta Stands, and What's Left](#-5-where-chitragupta-stands-and-whats-left)
- [6. One Experiment Worth Running Regardless](#-6-one-experiment-worth-running-regardless)

---

## 📋 1. What a Good Grounded Writing Software Must Do

The defining failure of LLM-assisted academic writing is **citation
fabrication**: models invent plausible-looking references, page numbers,
and quotes. A grounded writing system exists to make this failure
impossible or detectable. The full requirement set, in rough order of
importance:

### ✅ 1.1 Hard citation grounding (the gate property)

- Every citation key that appears in output must correspond to an entry
  in the user's own reference library (e.g. a Zotero-exported `.bib`
  file), **and** that entry must be backed by a real, parsed source
  document (PDF) the user actually holds.
- Crucially, this must be a **blocking gate**, not a warning: a draft
  containing an unknown citekey is rejected and sent back for
  regeneration, never rendered. The distinction between "makes
  fabrication less likely" (retrieval-augmented generation, RAG) and
  "makes fabrication architecturally impossible" (a gate on the only
  output path) is the central quality axis of this software category.
- The bibliography is the **single admission point** for sources.
  Nothing enters the citable universe except through it.

### 📖 1.2 Faithful use of sources, not just existence of sources

A citation can point to a real paper and still be wrong. Beyond
existence-gating, a mature system should verify:

- **Claim support**: does the cited source actually support the claim
  made? (Semantic entailment checking -- expensive, probabilistic, best
  kept advisory.)
- **Page-level anchoring**: page numbers in citations should be
  checkable against the parsed PDF.
- **Quotation integrity**: quoted spans must appear verbatim in the
  source at the cited location.

### 🔍 1.3 Plagiarism / verbatim-overlap detection against the cited corpus

The complement of citation grounding: the system must ensure the draft
does not silently **reuse the wording** of its sources. This means
source-vs-draft text alignment (iThenticate-style overlap regions)
against the *specific PDFs in the corpus* -- a different problem from
web-scale plagiarism checking.

Requirements: detect maximal verbatim n-gram runs; detect
paraphrase-shaped borrowing (high semantic similarity + low lexical
overlap); report overlap regions side-by-side with source location
(citekey, page); distinguish severity tiers; support an allowlist for
domain boilerplate.

### 🔁 1.4 Rephrasing / remediation loop

Detection without remediation leaves the human doing the tedious part.
The system should route each overlap finding back into a constrained
rewrite: preserve meaning and citation, avoid reusing >= N consecutive
source words -- or, where wording is canonical (definitions, theorem
statements), convert to an explicit quotation with quote marks and a
page-anchored citation. Rewrites must be re-verified before acceptance
(same gate-fail-retry loop as citations), and logged for audit.

### 🏗 1.5 Long-form structure and consistency

For thesis- and book-scale output: hierarchical decomposition (book ->
chapter -> section), outline-first workflows, and **cross-chapter
consistency** of terminology, notation, claims, and cross-references.
Consistency cannot live in model memory; it must live in explicit
artifacts (see §3.3).

### 🧾 1.6 Determinism, auditability, and reproducibility

- The corpus layer (parsing, hashing, indexing) must be deterministic
  and LLM-free.
- Every generated span should be traceable: which sources, which
  prompts, which model, which verification results produced it (a
  provenance ledger).
- Re-running the pipeline on unchanged inputs should cost nothing
  (content-addressed caching).

### 🔤 1.7 Language quality

Spelling, grammar, and style conformance to a house/genre standard --
ideally as a deterministic-where-possible check layer (spell-checking
against a project dictionary, style linting) plus LLM-assisted polish,
applied per-unit and re-verified. Distinct from §1.5's structural
consistency: this is about the prose surface, not the argument's shape.

### 🔒 1.8 Data control

For thesis and book manuscripts, many users need the corpus and drafts
to never leave their machine. Local-first operation is a requirement for
some, a nice-to-have for others -- and is the sharpest differentiator
between open-source and SaaS offerings.

---

## 🌐 2. The Landscape: Closed and Open Source

### 🏢 2.1 Closed-source (commercial SaaS)

The category has converged on one pitch -- *citations grounded in real
sources, no hallucinated references* -- because fabricated citations
became the signature embarrassment of LLM academic writing. All of these
are closed SaaS where the grounding mechanism is a **trust claim**, not
an inspectable mechanism. None publishes its enforcement code; none runs
locally.

| Tool | Core model | Grounding claim | Plagiarism check | Long-form ceiling |
| --- | --- | --- | --- | --- |
| **Paperguide** | Full research workspace: 200M+ paper search, reference manager (Zotero/Mendeley import), AI Paper Writer, PDF Q&A with page-level citations, systematic reviews (PRISMA), data extraction, team workspaces | "Citations applied automatically against the actual library"; "every cited paper verified against the actual reference" (own marketing) | Yes (paid plans) -- but **web/academic-scale**, Turnitin-style, not local-corpus | Thesis chapters; markets "multi-chapter consistency" |
| **SciSpace** | Paperguide's closest competitor: 280M paper search, PDF reading/Q&A, data extraction, literature review generation, reference management, AI Writer | Library + index grounded drafting | Not a differentiator | Paper/section scale |
| **Jenni AI** | Writing-first: upload your own PDFs (~50), grounded autocomplete and citation suggestions from that uploaded library; "Claim Confidence" flags unsupported claims | "Zero hallucinated references -- all autocomplete suggestions grounded in your actual source library" (marketing). Closest commercial tool in spirit to a bring-your-own-corpus model | **No** (conceded even by competitors' comparisons) | Chapter-by-chapter autocomplete |
| **ThesisAI** | Long-form first-draft generator: up to ~80-page documents from a single prompt; **LaTeX/Overleaf/Zotero integration**; 20+ languages | Draft-from-sources | **No** | The most aggressive long-form claimant (~80 pages) -- but single-prompt generation != coherent book |
| **Logically** (ex-Afforai) | Reference manager + chat-with-your-documents + light writing layer; RIS/BibTeX/CFF import | Answers grounded in your library | No | Interrogation, not drafting |
| **Anara** (ex-Unriddle) | Works only with uploaded PDFs; multi-paper comparison chat with passage-linked answers; light writing layer | Passage-linked answers from your corpus | No | Reading/annotation layer |
| **Paperpal** | Late-stage editing: academic language polish, journal submission checks | Not a drafter | Yes (paid) + AI detection | Editing, not generation |
| **Elicit / Consensus / Scite** | Research Q&A and evidence synthesis over large paper indexes (Scite: Smart Citations database) | Retrieval-grounded answers | No | Q&A/synthesis, not document drafting |
| **Yomu AI, AnswerThis, Writefull, QuillBot, Thesify** | Long tail: minimalist writers, proposal-stage synthesis, language polish, paraphrasing, rubric feedback | Varies | Mostly no | Essay/section scale |

**Key open question for all of them:** whether the grounding is a
genuinely *blocking* gate (a hallucinated citekey architecturally cannot
reach output; generation is rejected and retried) versus "the writer
draws from the selected set and this usually works." This cannot be
determined from outside a closed system. **The decisive empirical
test**: give the writer's library a deliberate gap -- prompt for a claim
whose natural source is absent -- and observe whether it fabricates,
omits, or refuses. §6 restates this as a standing experiment.

**Also notable:** SciSpace and Paperguide blend the user's library with
their large public index, which reintroduces ambiguity about what the
writer is allowed to draw from. Jenni and Anara are purer "your library
is the whole universe" designs.

### 🔓 2.2 Open-source

No open-source project replicates the full commercial feature set. What
exists:

- **Chitragupta** (this project) -- an automated pipeline over a
  Zotero-exported PDF library that drafts surveys, thesis chapters,
  textbook chapters, tutorials and multi-perspective deep-research
  reports, and assembles accepted units into a book (nine skills
  total, five of which draft; see
  [GENRE.md](GENRE.md)). Distinctive properties: bibliography file as
  the sole citekey admission point; deterministic, LLM-free
  parse-and-ledger corpus layer; a genuinely **blocking** citation gate
  (`chitragupta.draft gate`) on the only draft->render path, with failed drafts
  regenerated automatically; local-first (corpus never leaves the
  machine); auditable, readable enforcement code. Since the original
  discussion, closed-corpus verbatim-overlap detection (exact and
  paraphrase tiers), a rewrite-and-reverify remediation skill, and an
  automatic, non-blocking prose/dialect checker have all shipped too
  (§5). **This architecture -- bibliography-only entrance + deterministic
  ledger + blocking gate as sole exit -- still has no direct open- or
  closed-source equivalent**, and the gate remains the *only* blocking
  check anywhere in the pipeline by deliberate, measured decision (§5.1).
- **STORM / claude-storm** (Stanford OVAL; the `hadufer/claude-storm`
  fork is credited and adapted by Chitragupta's `deep-research` skill)
  -- grounded Wikipedia-style article generation from retrieved sources;
  pulls from the **live web**, not a closed user-curated bibliography;
  no hard citekey gate.
- **LitLLM** -- RAG-based related-work generation (research reference
  implementation); retrieval-before-writing reduces hallucination but no
  gate-or-reject pipeline.
- **LitRAG** -- open reference RAG implementation with a "groundedness
  layer" that LLM-judges whether a citation's supporting quote is
  actually entailed; closer in spirit (a verification step exists) but
  explicitly a small learning-oriented reference implementation, and the
  check is a judged pass/fail score, not an existence-gated block.
- **OpenScholar** (Apache-2.0) -- retrieval-augmented scientific answer
  generation over a pes2o datastore, with an optional self-feedback pass.
  Already credited in [INSPIRATION.md](INSPIRATION.md) as an influence on
  [FEATURE-ROADMAP.md](FEATURE-ROADMAP.md)'s synthesis half.
- **RAGFlow** (Apache-2.0) -- a full production RAG platform: layout-aware
  "deep document understanding", fifteen chunking templates, hybrid
  keyword+vector retrieval with a tunable fusion weight, and a
  citation-rendering UI. Server, database and web app; the opposite end
  of the deployment spectrum from this project.
- **papersgpt-for-zotero** -- a Zotero plugin, and therefore the closest
  thing to a direct competitor for this project's *input* side. Note the
  three-way licence split: the GitHub source tree is AGPL-3.0, the npm
  wrapper Apache-2.0, and **the shipped engine is a proprietary binary**
  whose source is not published, behind commercial tiers. The AGPL text
  is not the source of the shipped artefact.
- **local-deep-research** (MIT) -- multi-round "deep research" over web
  engines *or* a private document collection, behind one search-engine
  interface. Its fully-local egress scoping is genuinely enforced and
  fail-closed, which is the part most worth reading.
- **AutoRAG** -- AutoML for RAG: generate an evaluation set from your own
  corpus, then sweep retrieval/rerank/generation modules against it.
  **Mind the licence split** -- the root is MIT and covers a rewritten
  TypeScript agent, while the Python tool everything above describes now
  lives in `legacy/` under **Apache-2.0**. Its one genuinely valuable
  idea here is *label-by-construction*: sample a chunk, record its id as
  the ground truth, and only then generate a question from it, so the
  label needs no judge. Its filters are worth the same look --
  particularly the one that drops passage-dependent questions ("what does
  the table show?") that no retriever can resolve.
- **MiniRAG** (MIT, and a LightRAG fork -- roughly 330 lines are its own)
  -- a heterogeneous graph index plus topology-enhanced retrieval, aimed
  at small on-device models. The transferable idea is the framing:
  *reduce what the model is asked to do to one structured extraction and
  make the ranking arithmetic*.
- **Zotero** -- the open-source reference manager itself; the natural
  upstream of any bring-your-own-corpus pipeline (and Chitragupta's
  actual upstream), but not a writing tool.

### 📉 What a 2026-08-28 source read of those four found

Read for architecture only, as [INSPIRATION.md](INSPIRATION.md) requires.
The result was largely negative, and the negative result is the useful
part -- it says these are not the places to look for the two capabilities
this project keeps being asked about.

| | Query manufacture | Is a citation verified? |
| --- | --- | --- |
| **OpenScholar** | **None.** No decomposition, no rewriting, no HyDE. Its one LLM generator caps at 3 by `split(", ")` at temperature 0.9 | **No.** Positional `[n]` into a *reranked* list, so a marker denotes a rank slot rather than a document. Posthoc attribution is a pure LLM prompt that silently returns the original text when its markers are missing |
| **RAGFlow** | Three LLM rewrites, **all off by default**; decomposition exists but sits behind `thinking_mode` | **No.** If the model emitted any marker, the only check is `i < len(chunks)` -- an array-bounds test. Its fallback attributor lowers a 0.63 threshold by ×0.8 in a loop *until something matches* |
| **papersgpt** | **None**, in both versions -- the raw user string goes straight to embedding | **No.** One regex turns a `REFID:` marker into an anchor; the "click to jump" lands on a line the model itself wrote. Its prompt contract points citations at the *source papers' own bibliographies* -- works never parsed, and not necessarily in the library |
| **local-deep-research** | Fixed round counts. One genuinely deterministic templated generator (entity coverage) | **No.** An out-of-range `[42]` survives as inert literal text. Its own benchmark **strips citation markers before grading**, so citation correctness is never measured at all |

Three consequences worth recording, because each one is a design
decision this project already took differently:

1. **"Grounded" in these tools means retrieval happened, not that the
   citation was checked.** None of the four validates that a cited source
   supports -- or even exists for -- the sentence citing it. §1.1's gate
   property remains without an equivalent here.
2. **Every one of them is built to always produce a citation.** RAGFlow
   relaxes its threshold until one sticks; OpenScholar's attribution
   prompt tells the model that one citation suffices even where several
   sources support a claim. Against a closed, human-curated bibliography
   the opposite disposition is available and better: **an empty result
   means the claim cannot be grounded, so the sentence is cut rather than
   cited.**
3. **Marking coverage on the query rather than on the evidence is a real
   and repeated bug.** local-deep-research marks a topic covered when it
   appears in an *issued* query, so a search that returned nothing marks
   its topic covered permanently.

### ♻ How those four handle revision: they don't

The same read asked a second question -- once output exists, what happens
if you want it *changed*? Taking **revision** to mean a path that accepts
a prior artifact as input, emits a modified version of *that* artifact,
and persists it so the prior is superseded or versioned:

**None of the four supports it. Regeneration is the only model, zero for
four.** Three come close enough to look like exceptions, and each fails
differently:

| System | Looks like revision | Why it is not |
| --- | --- | --- |
| OpenScholar | the `--feedback` edit loop | it runs **before** the artifact exists -- intra-generation refinement, not a post-hoc path |
| RAGFlow | a **regenerate** button in the UI | it truncates the history and re-asks: the prior answer is *destroyed*, never read as input, and no version is kept. `refine_multiturn` rewrites the **question**, not the answer -- and `PATCH .../sessions/<id>` **explicitly refuses** to change stored messages, so this is a deliberate design refusal rather than a missing feature |
| papersgpt | "writes findings into Zotero Notes" | it **appends at the cursor** of an editor you already had open, and never looks a note up. Its chat state is one global in-memory conversation that dies on restart |
| local-deep-research | follow-up carrying a `parent_research_id` | it creates a **new child row**; the parent's report is untouched |

Three properties follow, and each is a requirement this project already
meets:

- **No hand-edit detection anywhere.** Not one has a digest, mtime or
  version check on its output. Two are structurally immune rather than
  merely missing the check -- LDR reads reports only from its database,
  so its optional file backup is write-only; papersgpt has no persistent
  artifact at all. OpenScholar is the worst case: it *does* read its
  output file back, but only for a row count, so edited content is
  silently honoured.
- **No section-scoped editing anywhere.** The unit of change is always
  the whole document. OpenScholar comes closest and still replaces the
  entire answer per feedback item.
- **Evidence reuse in two of four, and forced re-search in both.** LDR
  pre-injects filtered prior sources so they stay citable without
  re-fetching, then runs a fresh search unconditionally; OpenScholar
  reuses prior passages as the base and retrieves only conditionally.

**The pattern worth naming: all four persist far more than they
consume.** OpenScholar writes a complete refinement audit trail -- the
pre-edit draft, the feedback, every accepted edit -- and reads back only
`len()`. RAGFlow stores per-turn retrieved chunks in a parallel array no
revision path exists to use. The state a revision feature would need
largely already exists on disk in three of the four; what is missing is
any entry point that reads it.

### 📚 Two surveys, and what they say this pipeline is

Read 2026-08-29, and useful mainly for placing this project in the
field's own vocabulary rather than its own:

- **Gao et al.**, *"Retrieval-Augmented Generation for Large Language
  Models: A Survey"* (arXiv:2312.10997v5, 2024) -- the Naive / Advanced /
  Modular paradigms, a retrieval-process taxonomy (Once / Iterative /
  Recursive / Adaptive), a granularity ladder from Token to Doc, and an
  evaluation framework of three quality scores and four required
  abilities.
- **Fan et al.**, *"A Survey on RAG Meeting LLMs"* (KDD '24,
  pp. 6491-6501) -- organised by architecture, training strategy and
  application, and the source of the integration-layer distinction
  (input / intermediate / output).

Placed against those, this pipeline is **Advanced** (not Modular),
**Once** (not iterative), **Doc**-granularity on its lexical path,
**input-layer** by necessity, and **train-free** by design.
[RAG.md](RAG.md#-where-this-sits-in-the-standard-taxonomy) carries the
table and what each choice costs.

**Three things the surveys supply that §1's requirement list did not.**
The first is that intermediate- and output-layer integration are
*unavailable* to any pipeline driving a model through an inference API,
so a large part of the published technique space is inapplicable rather
than merely unbuilt. The second is **negative rejection** -- declining
to answer when the retrieved material does not support one -- named as a
first-class evaluable ability, which is the behaviour this project is
built around and the one it has never measured (now
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md)'s C6). The third is a defence
of retrieval that does not depend on context length: Gao §VII-A argues
that RAG's durable advantage over a long-context model is that "the
entire retrieval and reasoning process is observable, while generation
solely relying on long context remains a black box". That is §1.1's
gate property argued from the outside.

**[RAG.md](RAG.md) is the stage-by-stage version of everything below**
-- the eleven stages of a RAG pipeline, the algorithm each of these
systems uses at each, and the trade-off it buys.

### 🧪 Two more, read for retrieval and evaluation

A follow-up read of **AutoRAG** and **MiniRAG** (2026-08-28) added two
findings and one warning.

**The warning is about measuring retrieval at all, and it is the most
useful thing either produced.** AutoRAG generates its evaluation
questions *from* the gold chunk's own text. The query therefore inherits
that chunk's vocabulary, so the set **structurally favours lexical
retrieval** -- a BM25 change scored on it looks better than it is, and
nothing upstream flags this. It also has no near-duplicate question
dedup, and no train/test tooling at all: its own documentation warns
about overfitting while its code does nothing to prevent it. **A
generated evaluation set is not neutral ground for a retrieval change.**
This project's `bench_retrieval_keyword_selfretrieval.py` avoids the
circularity by construction -- author-assigned keywords were written
without reference to any retriever, or to the paper's body text.

**Worth adapting.** *Label-by-construction* (AutoRAG): fix the ground
truth before generating anything, so no judge is needed. *Cross-route
agreement* (MiniRAG): a passage that two independent retrieval routes
reach is worth multiplicatively more than one either route merely ranks
highly -- implementable over BM25 in stdlib, needing no graph, no
embeddings and no LLM.

**Not worth taking.** MiniRAG's index needs an LLM pass per chunk --
about 8,400 calls and tens of millions of tokens for a 500-paper corpus
-- to build entity nodes typed `organization` / `person` / `location` /
`event`, a news ontology with no override hook and little purchase on
academic content. Its retrieval value ultimately flows through a
chunk-id adjacency list, which a SQLite ledger already stores exactly
and without hallucination risk. **Its paper also never benchmarks
against BM25** -- "beats NaiveRAG" means beats embedding-only retrieval
-- so there is no published evidence it would beat what already runs
here. And its generator is handed anonymous text: chunk identity is
replaced by a loop index before the prompt is built, which is the
inverse of this project's requirement.

That is the gap [DRAFT-ITERATION.md](DRAFT-ITERATION.md)'s dossier and
the `draft-reviser` / `corpus-reviser` split were built to fill, and this
read found no open- or closed-source equivalent for either. It also
sharpens what is still missing here: nothing yet fingerprints the draft,
so a *hand*-edited draft is as invisible to this pipeline as to the other
four -- Theme E3 in
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-e3-notice-that-the-draft-moved).

### 🔍 2.3 Plagiarism detection for a closed corpus (source-vs-draft overlap, iThenticate-style)

A distinct sub-landscape. No open-source tool matches iThenticate's
web-scale index (billions of crawled pages + publisher partnerships) --
but for the closed-corpus use case that index is unnecessary; every open
option compares only against sources **you supply**, which is exactly
right when the corpus is already local PDFs.

**Verified (project site read directly, active as of the original
discussion):**

- **WCopyfind / Copyfind** (Lou Bloomfield, U. Virginia) -- open source
  (GPL). Compares a suspect document against a local collection of
  source documents, matches word sequences above a configurable minimum
  length, produces an HTML report with copied text underlined -- the
  closest lightweight analogue to iThenticate's side-by-side view for a
  local corpus. **WCopyfind is Windows-only with a GUI** (runs on
  Mac/Linux via Wine); **Copyfind** is the command-line sibling. For a
  Linux pipeline, running either under Wine is awkward -- which is why
  Chitragupta built a native reimplementation instead (§5.1) rather than
  wrapping either.

**Research lineage (published methods + evaluation corpora, competition
code rather than products):**

- **PAN text-alignment systems** -- the PAN shared tasks (CLEF) define
  exactly this problem: given a suspicious document and source
  documents, identify and align reused passages, scored by
  character-overlap precision/recall/granularity. Public benchmark
  corpora (PAN-11/12/13; a 2025 revival targets LLM-paraphrased reuse).
  Effective published approaches: word/character n-gram fingerprinting
  with greedy string tiling; sentence/paragraph **SBERT embeddings +
  Smith-Waterman local alignment** (handles paraphrase far better than
  exact n-grams); DB-SCAN merging of matched features.
- **Hamtajoo** -- open academic plagiarism checker (Persian) with the
  standard two-stage architecture: candidate retrieval -> text-alignment
  module reporting exact overlap positions (n-gram / VSM / LSA). Useful
  as a design reference.
- **Dolos** -- excellent, actively maintained, but **source-code only**
  (programming courses), not prose.
- **PlagChek** and similar -- tiny personal projects (Tkinter apps,
  essentially unmaintained); they exist but should not be relied on.

**Key gaps in open tools:** exact/near-exact matching is well covered;
paraphrase detection requires the embedding-based approaches; nothing
was turnkey. `docs/PLAGIARISM-DESIGN.md`'s "Where this sits in a bigger
plan" table records exactly which of these methods Chitragupta chose for
each of its three detection tiers, and why -- see §5.1 below.

---

## 🏗 3. Architectural Principles for Grounded Long-Form Drafting

The fundamental constraint: **a book does not fit in a context window,
and generation quality degrades long before the limit.** Every sound
architecture is a response to that fact plus the grounding requirement.
These are the principles Chitragupta's own architecture follows --
[DESIGN.md](DESIGN.md) is the fuller rationale document for the same
choices, where the two overlap.

### 🧩 3.1 Two-plane separation: deterministic substrate, stochastic generation

The corpus layer -- PDF parsing, text extraction, bibliography parsing,
content hashing, chunk indexing -- must be fully deterministic,
LLM-free, and idempotent. The generation layer sits on top and is
treated as **untrusted**: everything it produces gets verified against
the substrate. Mixing LLM judgment into the corpus layer destroys
reproducibility and makes downstream verification circular.

> **Constraint: no LLM call may ever write to the corpus plane.**

### 🚧 3.2 Closed-world enforcement at a structural boundary, not in the prompt

"Only cite these sources" as a prompt instruction fails probabilistically;
it must fail deterministically. This requires (a) a single admission
point for sources (the bibliography), and (b) a gate on the **only**
path from draft to output. The principle mirrors capability-based
security: the generator is not *asked* not to fabricate; it is *unable*
to get a fabrication past the boundary. The same pattern generalizes to
page numbers, quoted spans, and (with more work) numeric claims.

### 🗄 3.3 Externalized state: the model remembers nothing

Cross-chapter consistency cannot live in model memory across calls. It
lives in explicit artifacts:

- an **outline/spec** document (approved before prose);
- a **terminology and notation registry**;
- a **claim register** (what has been asserted, where, with which
  citation);
- a **cross-reference graph**;
- per-chapter **dossiers**.

Each generation call receives *only* the artifacts relevant to its unit
of work. This is the book-vs-thesis dividing line: at thesis scale one
can partially cheat with large contexts; at book scale, consistency is
entirely an artifact-management problem. (Commercial chat-centric SaaS
externalizes very little -- which is why their "multi-chapter
consistency" claims are weak and their ceiling is thesis chapters.)
Chitragupta already externalizes per-draft state this way, via the
dossier (`docs/DRAFT-ITERATION.md`); the book-scale registries above are
the still-open piece (§5.2).

### 🌳 3.4 Hierarchical decomposition with a fixed unit of generation

Book -> part -> chapter -> section, **planned top-down** (outline
approved first), **generated bottom-up** in units small enough that
grounding retrieval + genre instructions + local context fit comfortably
in the context budget -- typically a *section*, not a chapter. Each unit
has a contract: inputs (spec slice, registry excerpts, retrieved source
chunks) -> outputs (draft + citations + claims to register). Units are
independently regenerable, enabling parallelism and cheap iteration.

### ✅ 3.5 A verification ladder, ordered by cost, with blocking vs. advisory tiers

Cheapest first:

1. **Citekey existence** (regex/parse vs. the bib file) -- deterministic,
   blocks.
2. **Verbatim overlap** (n-gram scan vs. parsed sources) --
   deterministic, but see §5.1: measured and deliberately **not**
   promoted to blocking in Chitragupta, because no threshold separated
   true from false positives on real prose.
3. **Structural checks** (cross-references resolve; notation matches
   registry) -- deterministic, but advisory, not blocking: book-scale is
   built (§5.2), and `python -m chitragupta.draft registry check` always
   exits 0, a review aid rather than a gate.
4. **Semantic checks** (does the cited source support the claim --
   NLI/embedding-based) -- probabilistic, **advisory only**.
5. **Human review** -- outline sign-off and final sign-off.

> **Constraint: only deterministic checks may block, and not every
> deterministic check should.** A fallible checker in a blocking
> position creates infinite rewrite loops on false positives; a
> deterministic checker with no threshold that separates its two
> populations creates the same failure by a different route (§5.1's
> `overlap_gate` measurement). Blocking failures trigger bounded
> regeneration retries and then fail loudly to the human; they never
> silently pass.

### 💾 3.6 Content-addressed caching and resumability everywhere

At book scale, one section is regenerated fifty times while 200 pages
sit untouched. Every stage is keyed by the content hash of its inputs so
a full-pipeline re-run costs only what changed. The same machinery
yields the audit trail: a ledger recording which sources, prompts,
model, and verification results produced every span.

### ⚙ 3.7 Conventions as data, not code

Genre rules (thesis chapter vs. tutorial vs. survey vs. deep research),
house style, citation format, and structural templates live in editable
skill/config files consumed by the generation layer -- making the
pipeline retargetable (thesis -> book -> tutorial series) without
touching enforcement machinery.

### ⚠ 3.8 The constraints, stated bluntly

- Single source-admission point (the bibliography).
- LLM never touches the deterministic plane.
- Generation unit sized to context budget with room to spare.
- All cross-unit state in artifacts, none in model memory.
- Only deterministic checks block, and only where a false-positive rate
  makes that tolerable -- neither is sufficient alone; bounded retries;
  loud failure.
- Everything content-hashed and resumable.
- Human sign-off at outline and final stages -- no automated check
  verifies the argument is *good*, only that it is *grounded*.

---

## 🔨 4. How Chitragupta Was Built

The build sequence Chitragupta actually followed, in the dependency
order the principles above imply. Each step below is marked with what
shipped it; §5 has the full status table.

### 📚 4.1 Corpus substrate first — built

1. **Ingestion**: parse the reference manager's export (BibTeX).
   `chitragupta/bib_reader.py` handles the real format quirks -- Zotero's `file`
   field is `Description:path:mimetype`, `;`-separated per attachment,
   with relative paths anchored to the `.bib` file's own directory
   (`docs/ZOTERO.md` documents the trap this avoids); brace-matches
   entries to their true end rather than naive `\n}` matching, which
   truncates entries with multi-line fields.
2. **Parsing**: `chitragupta/pdf_text/` extracts text per PDF (`pdftotext
   -layout` or `docling`), preserving page boundaries (form-feed splits)
   so every downstream check can report page numbers.
3. **Ledger**: `content/ledger.sqlite` content-hashes every artifact
   (PDF, parsed text, bib entry) and is the ground truth for "what
   exists" and the cache key for everything downstream.

### ✅ 4.2 The gate — built

1. `python -m chitragupta.draft gate` validates every citekey a draft uses
   against the bib parse **and** the ledger (entry exists *and* has a
   parsed source behind it), on the only draft->render path. On
   failure: the drafting skill discards the bad claim, drafts again, and
   loops until it passes -- the human sees a finished, gated draft, not
   the failed attempts. A PostToolUse hook
   (`.claude/hooks/citation_gate_hook.py`) enforces the same check
   mechanically on every write under `content/drafts/`.

### 🔍 4.3 Overlap detection (the plagiarism layer) — built

1. **Whole-draft x whole-corpus verbatim scan** (`python -m chitragupta.review
   verbatim scan`, #110/#127/#128/#131): every parsed source is
   fingerprinted once into a disk-cached, ledger-keyed index; the whole
   draft -- not just citing paragraphs -- is scanned against it; findings
   report run length, source, page, fragment and draft context, bucketed
   by severity with a per-phrase boilerplate allowlist.
2. **Paraphrase tiers** (#133, #134): a deterministic stemmed-skip-gram
   tier, and an embedding tier (SBERT-style, over the existing
   enrichment-layer index) flagging high-semantic-similarity /
   low-lexical-overlap sentence pairs. Both advisory, cumulative with
   tier 1, never blocking -- see §5.1 for why the embedding tier
   specifically cannot be anything else in this pipeline's kind of
   corpus.
3. **Gating policy** (#130): measured, not assumed. `bench/RESULTS.md`
   and `docs/PLAGIARISM-DESIGN.md` record the finding: on this project's
   own 178,000-word book, no span-length threshold separated the one
   genuine planted violation from the false positives (correctly quoted,
   correctly attributed passages that several corpus papers also quote).
   **Declined.** `chitragupta.draft gate` remains the only blocking check in the
   pipeline.

### 🔁 4.4 The remediation loop — built

1. Overlap findings are machine-readable (`--json`, draft span, source
   span, citekey, run length) and feed the `agenda-reviser` skill: a
   constrained rewrite per finding, restating the draft's own register
   while preserving citation and meaning -- or, for long runs, stopping
   to ask the human paraphrase-or-quote rather than deciding silently.
2. Every rewrite is re-scanned and re-passed through `chitragupta.draft gate`
   before acceptance, and logged in the draft's dossier
   (`revisions.md`), so edit provenance is as auditable as citation
   provenance.

### 🔤 4.5 Language quality layer — built for English, explicitly parked for others

1. Deterministic-first: `python -m chitragupta.draft style` wraps a vendored
    Vale configuration (`assets/vale/`) checking §2's defect markers, an
    unexpanded acronym, and dialect conformance against the draft's own
    recorded `language:` line (`content/dossiers/<slug>/scope.md`). A
    review aid, never a gate, and deliberately so -- unlike a citekey, a
    recorded dialect can be wrong, stale, or a quoted title, so blocking
    on it would refuse a *correct* draft on a *bad target*. A
    non-blocking PostToolUse hook
    (`.claude/hooks/style_check_hook.py`) and a step in every genre
    skill invoke it automatically; `draft-reviser`'s copy-edit mode is
    the sanctioned path when a finding should actually be acted on.
    LLM-assisted polish is exactly that copy-edit mode: a constrained,
    meaning- and citation-preserving rewrite that must re-pass every
    gate.
2. **Multi-language plumbing was scoped and then explicitly
    deprioritized**, not left undiscovered: `render_output` language
    metadata / non-English hyphenation and CSL (#105), locale-aware
    reference connectives such as "and" vs. "und" vs. "et" (#106), and
    non-English retrieval -- tokenizer, embeddings, OCR language (#108) --
    were each designed in full in their issue before being closed "not a
    priority." None of the three is built: verified directly, there is no
    babel/polyglossia or other language-metadata plumbing anywhere in
    `chitragupta/render_output/`. A draft in a language other than English today
    gets nothing automatic -- pandoc renders it with English hyphenation
    rules and an English-locale CSL regardless of the draft's own content,
    its reference list joins authors with English "and", and its
    retrieval assumes an ASCII-ish, English-tuned index. The one
    exception is manual, not automatic: the References section's own
    heading text can be overridden per invocation with `--heading` (e.g.
    `--heading "Bibliographie"`), which #106 itself calls "already
    soft-solved" -- everything else in that paragraph is what #106
    would have built and didn't.

### 📕 4.6 Scaling to books — built (#135-#139, see §5.2 and BOOKS.md)

1. **Spec/outline artifact** with human sign-off before any prose
   (#136).
2. **Unit decomposition**: generation contract at section granularity;
   sections independently regenerable and parallelizable (#137).
3. **Consistency registries** (terminology/notation, claim register,
   cross-reference graph) written by a deterministic post-pass over
   accepted units and injected (as relevant excerpts) into subsequent
   unit generations; a global consistency pass runs after chapter-level
   parallel generation (#138).
4. **Global checks**: cross-reference resolution, notation-registry
   conformance, and a claim register across chapters -- all
   deterministic (`python -m chitragupta.draft registry check`), and all advisory,
   not blocking: it always exits 0, a review aid rather than a gate (#138).
5. **LaTeX book assembly** as a genre skill -- data, not code, per §3.7
   (#139).

### 🧪 4.7 Testing and operations — built, and structural to the repo

- The deterministic plane gets ordinary unit/CI tests (fixtures of bib
  files, PDFs, drafts with planted violations). This repository holds
  itself to 100% line and branch coverage on the Linux CI leg
  (`DEVELOPER-AGENTS.md`).
- The gates get adversarial fixtures: drafts with fabricated citekeys,
  planted verbatim runs, planted paraphrases -- the pipeline catches
  every planted violation, or the test fails.
- Everything runs locally; nothing in the corpus or drafts leaves the
  machine.

---

## 📍 5. Where Chitragupta Stands, and What's Left

### 🔭 5.1 Current position

Every principle in §3 that does not depend on book scale is built and in
production, not just designed. As of v5.29.0:

| Principle | Status |
| --- | --- |
| Two-plane separation (deterministic parse-and-ledger corpus layer, LLM-free) | Built |
| Closed-world gate (`chitragupta.draft gate` on the only draft->render path; failed drafts regenerate; PostToolUse hook enforces it mechanically too) | Built -- and, per #130 below, still the *only* blocking check anywhere in the pipeline, by measured decision rather than by omission |
| Bibliography as sole source-admission point | Built |
| Local-first, auditable, open source | Built, by construction |
| Genre conventions as data (skills) | Built -- nine skills, five of which draft ([GENRE.md](GENRE.md)) |
| Content-hash caching / "second run costs nothing" | Built, and load-bearing for the overlap index (#110) specifically |
| Verbatim overlap checking, exact tier | Built (#110, #127, #128, #131): corpus-wide n-gram index, disk-cached and ledger-keyed; whole-draft scan, not just citing paragraphs; severity buckets; boilerplate allowlist; `--json` output |
| Overlap remediation loop | Built (#129): the `agenda-reviser` skill -- rewrite, re-scan, re-gate, log |
| Paraphrase detection, deterministic tier | Built (#133): stemmed skip-grams, advisory |
| Paraphrase detection, embedding tier | Built (#134), but **narrower than §1.3 asks for**: SBERT-style local alignment, advisory, and only where the optional enrichment layer, Docling passage sidecars and the draft's own dossier are all present. Per `docs/PLAGIARISM.md`, it compares a section only against the sources *that section already cites* -- a restatement of a source the draft never cited at all is still tiers 1 and 2's business alone, invisible to this tier by design, not just by the weak-discriminator argument below. And per `docs/PLAGIARISM-DESIGN.md`, even within that scope it is a weak discriminator specifically *because* this pipeline's retrieval step already selects a draft's grounding by semantic similarity, so "similar because copied" and "similar because correctly grounded" are hard to separate by cosine distance alone in a single-field corpus |
| Blocking `overlap_gate` | **Declined** (#130): measured against this project's own 178,000-word book -- no span-length threshold separated the one genuine violation from false positives that were correctly quoted, correctly attributed passages several corpus papers also quote. Not a gap; a closed, evidence-based decision, revisitable only given new evidence (a corpus of real rather than planted reuse, or a version-controlled seed allowlist) |
| Language quality: dialect recording, deterministic style/defect-marker check, automatic invocation, copy-edit revision path | Built (#104, #107, #182-#186): `python -m chitragupta.draft style`, a vendored-Vale review aid; a non-blocking hook and a step in every skill invoke it automatically; `draft-reviser`'s copy-edit mode is the sanctioned edit path. Advisory, never a gate, by the same reasoning as the overlap gate -- a recorded target can be wrong in a way a ledger entry cannot |
| Multi-language plumbing (render metadata, non-English reference connectives, non-English retrieval/OCR) | **Explicitly parked**, not merely absent (#105, #106, #108: each fully designed, then closed "not a priority") |
| Book-scale: spec/outline sign-off, unit decomposition, consistency registries, book assembly | Built (#135-#139) -- see [BOOKS.md](BOOKS.md) |

Competitive position in one sentence: **commercial tools (Paperguide,
SciSpace, Jenni, ThesisAI, ...) remain feature supersets as products, but
Chitragupta's architecture is further ahead of them than it was at the
time of the original discussion** -- it now also does closed-corpus
overlap detection across all three PAN-literature tiers, with a
measured, on-the-record decision about where a second blocking gate
would and would not help, which none of the commercial tools publish
enough to even ask about.

### 📕 5.2 Book scale

What raises the ceiling from chapter/report scale to book scale is
built, tracked under
[#135](https://github.com/prasadtalasila/chitragupta/issues/135) and
described in full in [BOOKS.md](BOOKS.md). It depended on none of the
tracks above, but benefits from all of them, since every gate and every
review aid built there applies per-unit at book scale, which is what
makes a 300-page grounded document tractable at all. In the order it was
built:

1. **[#136](https://github.com/prasadtalasila/chitragupta/issues/136) --
   a spec/outline artifact with human sign-off before any prose.** The
   smallest piece, and independently useful at chapter scale today: an
   on-disk outline (book -> part -> chapter -> section), approved by a
   human before generation starts, living beside the dossier under the
   same path-mirroring convention as `content/dossiers/`.
2. **[#137](https://github.com/prasadtalasila/chitragupta/issues/137) --
   section-sized generation units with explicit input/output
   contracts.** Fixes the unit of generation at the section rather than
   the chapter, small enough that retrieval + genre instructions + local
   context fit the budget with room to spare; makes units independently
   regenerable, which is what enables chapter-level parallelism and
   cheap iteration; every existing gate applies per-unit.
3. **[#138](https://github.com/prasadtalasila/chitragupta/issues/138) --
   consistency registries.** The genuinely hard part: a
   terminology/notation registry, a claim register, and a
   cross-reference graph, each written by a deterministic post-pass over
   accepted units (never by an LLM writing to the corpus plane) and
   enforced by deterministic, blocking global checks after chapter-level
   parallel generation completes.
4. **[#139](https://github.com/prasadtalasila/chitragupta/issues/139) --
   LaTeX book assembly as a genre skill.** Deliberately the smallest
   step of the four: parts/chapters/front-and-back-matter assembly of
   already gate-passed units, as data-not-code per §3.7, touching no
   enforcement machinery because everything it assembles has already
   passed every gate per-unit.

All four are closed, in the order listed above; [BOOKS.md](BOOKS.md) is
the record of what each shipped as, not just what it was scoped to be.

---

## 🔬 6. One Experiment Worth Running Regardless

Test the commercial tools' gate claims empirically: in Paperguide's (or
Jenni's) writer, select a library with a deliberate gap and prompt for a
claim whose natural source is absent. Fabricate / omit / refuse -- the
observed behavior settles, per tool, whether "citation-grounded" means a
gate or a tendency, and calibrates how unique Chitragupta's blocking
property actually is in practice. Nothing in this pipeline's own design
depends on the answer; it is offered here because it is the fastest way
for anyone comparing tools in this category to stop taking a vendor's
grounding claim on faith.
