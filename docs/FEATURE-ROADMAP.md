# 🗺 Feature roadmap: what is still open, and what was closed unbuilt

Status: **proposal.**

**Written for** someone picking up the next PR, or checking whether an
idea has already been weighed. **Assumed:**
[ARCHITECTURE.md](ARCHITECTURE.md) for the four layers,
[DRAFT-ITERATION.md](DRAFT-ITERATION.md) for the dossier, and
[PLAGIARISM.md](PLAGIARISM.md) for the three detection tiers. **Not
covered here:** how the existing detectors work
([PLAGIARISM-DESIGN.md](PLAGIARISM-DESIGN.md)), and figure work, which
[FIGURE-ROADMAP.md](FIGURE-ROADMAP.md) owns.

This page lists only work that is not built. A shipped item is deleted
from it rather than marked done; the PR that closed it and `plans/`
record how it was built. A roadmap that keeps its own history stops
being a list of what to do next.

## 🧭 Table of contents

- [What exists](#-what-exists)
- [Open items](#-open-items)
- [Closed without building](#-closed-without-building)
- [Five constraints every item respects](#-five-constraints-every-item-respects)
- [What is deliberately not proposed](#-what-is-deliberately-not-proposed)

## ✅ What exists

[FEATURES.md](FEATURES.md) is the capability surface as built, pinned
to the code by a test. Everything this roadmap's themes asked for is in
it: claim-first evidence (`claim:`/`quote:`) and the evidence sidecar,
multi-source synthesis and the pre-gate self-feedback step in the genre
skills, the review aids (`provenance`, `quotation`, `uncited`,
`support`, `union` and the rest), the TikZ scaffolds and figure checks,
outline-driven drafting and the draft fingerprint, the `agenda` loop,
and topic modelling and discovery
([TOPIC-MODELLING.md](TOPIC-MODELLING.md),
[TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md)).

The synthesis half drew on OpenScholar and the figure half on
PaperBanana, both as ideas only.
[INSPIRATION.md](INSPIRATION.md#-the-feature-roadmap) records what was
taken and what was refused.

## ▶ Open items

A new item goes here as one row once it has been proposed and costed.
"One PR" is the unit throughout.

| Item | Theme | Size | Depends on |
| --- | --- | --- | --- |
| Figure work: the remaining figure-drawer items and the parts not yet built | Figures | see there | [FIGURE-ROADMAP.md](FIGURE-ROADMAP.md) owns the list and the order |

Check a new proposal against two rules before costing it. An item that
makes something run without a person asking needs the amendment in
[constraint 2](#-five-constraints-every-item-respects). An item that has
a skill repair its own output is refused by the self-marking argument
in [AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md).

## 🚫 Closed without building

Each was weighed and closed. The reason is kept so the item is not
re-proposed as an oversight. "Revisit if" names the evidence that would
reopen it.

| Item | Closed as | Why | Revisit if |
| --- | --- | --- | --- |
| **A1b**: route `verbatim scan` findings into `agenda-reviser` automatically | Declined | A genre skill repairing its own output is marking its own homework, and `agenda-reviser` runs only when a person asks for it (R11 in [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#-the-requirements)). The scan runs and reports; the person decides whether to invoke the repair | Never on convenience alone; it needs a change to R11 |
| **B3**: open each section with a one-sentence thesis and a source count | Not a priority ([#379](https://github.com/prasadtalasila/chitragupta/issues/379)) | The design is in the issue | Someone wants it; start from the issue |
| **C4**: report a prose numeral with no traceable origin | Deferred as mis-specified | An adjacent citekey is the only traceable origin with instances, so the aid would mark the motivating case (a magnitude beside a real citation) as traced and report its complement. Every dossier here records `textbook-chapter`, where numerals are invented worked examples, so the base rate is zero. `plans/c4-numeral-as-claim.md` has the measurements | A survey, thesis chapter or deep-research draft with a dossier exists; or the finding is redefined as the *cited* case, with a passage narrow enough to check the number in |
| **C6**: measure negative rejection (how often a draft asserts what the corpus cannot support) | Skipped by evidence | On a single-subject corpus, neither construction of a negative query set works: unparsed bib entries and held-out shelves still match parsed papers on the same topic. No logged retrieval call has returned fewer results than asked, so the rate would be zero over zero | The corpus spans more than one subject, or a hand-authored negative query set is accepted as ground truth |
| **D4**: an optional vision critique of rendered figures | Skipped by evidence | A full visual pass over the 43 figures of this project's drafted book found nothing beyond what `review figure` already reports. Routing defects are measured by `figure check`'s connector rules | A denser figure set where the checks come back clean and a reader still disagrees |
| **D5**: two figure checks computed from source | Closed, not planned ([#624](https://github.com/prasadtalasila/chitragupta/issues/624)) | The point-size half is `figure check`'s `type-below-floor` rule. Whether two declared colours stay apart in a greyscale print is still a human judgement on [TIKZ-STYLE.md](TIKZ-STYLE.md)'s pre-flight list | Someone wants the greyscale half; the design is in the issue |
| **F4**: a blocking overlap gate | Declined | Measured on this project's own 178,000-word book, no span-length threshold separated the one genuine violation from correctly quoted passages several corpus papers share | A corpus of real rather than planted reuse, or a version-controlled seed allowlist |

## 🔑 Five constraints every item respects

Each one has already ruled out an obvious design.

**1. No LLM output may reach the corpus plane.** [SOUL.md](../SOUL.md):
the corpus layer "has no LLM and no judgment calls", and the enrichment
layer "reads the ledger and never writes it". Extracted claims live in
the **dossier**, and the per-citekey TL;DR (`chitragupta draft tldr`,
[FEATURES.md](FEATURES.md)) lives in the drafting layer, in neither
`corpus` nor `enrich`. Writing either into the ledger would break "same
bibliography in, same citekeys out".

**2. No second gate.** `chitragupta draft gate` means one thing: a
fabricated citekey fails. [WRITING-STANDARDS.md](WRITING-STANDARDS.md)
§10 says a second meaning "would blunt the first". Everything else is a
**mandatory step in a skill** or an **advisory review aid**, and the
review layer's rule is:

> a review finding may be read, may be invoked by a driver, and may never
> block a draft.

The line is advisory versus blocking, not manual versus automatic. The
rule is stated in the review layer and the documents describing it, not
in [SOUL.md](../SOUL.md). Making a review aid run without a person
asking is a user decision, not an engineering one.
[AUTO-IMPROVEMENT-RATIONALE.md](AUTO-IMPROVEMENT-RATIONALE.md#-the-amendment-this-needs)
has the reasoning.

**3. Anything with a torch/transformers dependency goes behind an
extra.** `pyproject.toml` makes `bibtexparser` the single core
dependency as a point of design, with all ML in the `enrich` group.
The cross-encoder reranker follows this rule.

**4. Attribution is owed for the idea, not for the text.** Nothing is
copied from an upstream, so no licence notice obligations attach.
[INSPIRATION.md](INSPIRATION.md) carries the credit. You may read an
upstream; you may not paste from it.

**5. `R1`-`R12` bind every new review aid and every unattended edit.**
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md#-the-requirements) states
them. Four are easy to breach by accident:

- **R2**: every finding carries an identity stable across runs, so "this
  finding is gone" is decidable.
- **R3**: *"An unattended item's check is **binary**. No continuous
  score is ever the thing being optimised."* Annotate every new aid
  **binary** (an agenda may consume it and a loop may act on it) or
  **continuous** (a human reads it; nothing acts on it unattended).
- **R4**: after an accepted edit, every aid re-runs and the result is
  compared by finding identity as well as by count. The repaired item is
  `resolved`, no objective-class finding is `new`, and the total has not
  risen, else the edit reverts.
- **R10**: a new aid is registered in both `review.AIDS` and
  `review._registry.AIDS`, and appears in AGENTS.md, CLI.md, the README
  tables and `mkdocs.yml`. `review/_registry.py` raises `RuntimeError`
  when the two dicts disagree, so a half-registered aid fails at import.
  A missing `mkdocs.yml` entry is the silent one: missing nav is INFO,
  not a `--strict` failure.

One naming rule comes with them: **the judgement register belongs to the
gate.** An advisory aid may not be called `audit`, `reckoning`,
`verdict` or `ruling`. `triage` is also taken:
[REJECTION.md](REJECTION.md) records a retrieval stage of that name
built and withdrawn.

## 🚫 What is deliberately not proposed

Recorded so each is not re-proposed as an oversight.

| Not proposed | Why |
| --- | --- |
| A blocking overlap gate | Declined on measured evidence (F4 above), and a second meaning would blunt the gate's one meaning ([WRITING-STANDARDS.md](WRITING-STANDARDS.md) §10) |
| Claim extraction cached in the corpus or enrichment layer | LLM output on the corpus plane; breaks "same bibliography in, same citekeys out" ([SOUL.md](../SOUL.md)) |
| TL;DR shown in `corpus ledger` output | Same, plus it inverts the layer order; see [FEATURES.md](FEATURES.md)'s per-citekey TL;DR section |
| An LLM-written TL;DR for a paper with no abstract | 4.92M input tokens for 160 documents, re-incurred on every re-parse, and [SOUL.md](../SOUL.md) requires a human to accept anything abstractive. There is no `tldr accept`, no review surface, and no answer to who reads 160 machine summaries. Such a paper reports "abstract not available" instead. [TLDR.md](TLDR.md) has the measurements |
| Abstractive topic summaries | Abstractive models carry factual inconsistencies in up to 30% of outputs. A topic summary asserting a claim no paper made is the same failure class as a fabricated citekey |
| An LLM transcribing document structure | Span *selection* (offsets to keep) is safe; span *transcription* is not, because a transcribed reference can be a fabricated one. [GROBID-CITATION-GRAPH.md](GROBID-CITATION-GRAPH.md) is the starting point if structural extraction is wanted |
| Image-generated figures | Non-deterministic, against the byte-identical output rule, and a raster cannot satisfy §10's two-form TikZ/ASCII contract. PaperBanana's own side-by-side shows the image route inverting a relationship, duplicating a category and drawing a bar taller than its gridline where the code route was correct |
| Any ML dependency in the core | `bibtexparser` as sole core dependency is a design decision in `pyproject.toml`, not an accident |
| Fetching papers from arXiv or anywhere else | Admission is the reference manager's job alone ([AGENTS.md](../AGENTS.md)) |
| Copying from zotero-arxiv-daily | AGPLv3, and excluded by the project owner |
| Positional `[n]` citation numbering | Upstream's scheme; reordering the passage list silently changes every citation's meaning. This project has real citekeys |
| OpenScholar's dead code paths | Its LLM reranker (`process_ranking_results`), `final_processing`, and `--use_abstract` are defined and never called; its `--norm_cite` adds a bounded `[0,1]` bonus to an unbounded cross-encoder logit |
