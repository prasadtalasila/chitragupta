# 🔭 Per-citekey TL;DR: what's built, and the unattended generator that isn't

Status: **reference, plus a parked proposal.** Written 2026-08-24.

What `chitragupta draft tldr` does today -- a one-paragraph,
human-authored summary per citekey, cached beside a fingerprint of its
parsed text -- and the unattended-generation design from
[#401](https://github.com/prasadtalasila/chitragupta/issues/401), parked
rather than built.

**Written for** someone deciding whether to build #401, or wondering why
`tldr write` still reads from stdin instead of summarising a paper
itself. **Assumed:** [ARCHITECTURE.md](ARCHITECTURE.md)'s four layers and
the citekey invariant ([SOUL.md](../SOUL.md)). **Not covered here:** every
flag -- [CLI.md](CLI.md#-chitragupta-draft-tldr) is the exhaustive
reference; this is the design.

## 🧭 Table of contents

- [What's built: a cache, not a generator](#-whats-built-a-cache-not-a-generator)
- [Why it lives where it lives](#-why-it-lives-where-it-lives)
- [#401: generating it unattended](#-401-generating-it-unattended)
  - [The shape: two paths, split on whether the paper has an abstract](#-the-shape-two-paths-split-on-whether-the-paper-has-an-abstract)
  - [Measured: the abstract is detectable more often than a heading scan suggests](#-measured-the-abstract-is-detectable-more-often-than-a-heading-scan-suggests)
  - [Measured: the papers without abstracts are the long ones](#-measured-the-papers-without-abstracts-are-the-long-ones)
  - [Why whole text on path B, not an extractive reduction step](#-why-whole-text-on-path-b-not-an-extractive-reduction-step)
  - [Why nothing extractive is ever shown to a reader](#-why-nothing-extractive-is-ever-shown-to-a-reader)
  - [What this needs before it can be built](#-what-this-needs-before-it-can-be-built)
  - [Risks a reader should not have to rediscover](#-risks-a-reader-should-not-have-to-rediscover)
  - [Why this is parked, not next](#-why-this-is-parked-not-next)

## 📦 What's built: a cache, not a generator

`chitragupta/tldr.py` (#398) is deliberately small: a `write`/`show` pair
over a JSON sidecar at `content/tldr/<citekey>.json`, keyed to a
`sha256` of that citekey's *current parsed text*
(`content/parsed/<citekey>.txt`), not a stat of the PDF. That distinction
is the module's one piece of real design -- a backend switch or a
`--reparse` can change the parsed text without the PDF on disk moving at
all, which a PDF-stat fingerprint cannot see, so the fingerprint has to
be of the text a summary was actually written against.

```bash
echo "This paper proposes ..." | chitragupta draft tldr write smith2024
chitragupta draft tldr show smith2024
chitragupta draft tldr show smith2024 --json
```

`write` never generates the summary itself. It reads one on stdin --
from a person, or from a skill in the current Claude Code session -- and
persists it. **No LLM call happens inside this module, ever.**
`show` recomputes the fingerprint on every read and reports the summary
`[STALE]` rather than silently describing a paper that has since been
re-parsed; staleness is never cached, only re-derived. See
[CLI.md](CLI.md#-chitragupta-draft-tldr) for the full flag/exit-code
reference.

## 🏗 Why it lives where it lives

`content/tldr/`, not `content/dossiers/` or `content/ledger.sqlite`:

- **Not the corpus layer.** A summary is LLM output, and
  [SOUL.md](../SOUL.md) says the corpus layer "has no LLM and no
  judgment calls." `python -m chitragupta.corpus ledger` is untouched by
  any of this.
- **Not a dossier.** A summary belongs to a *citekey*, not to any one
  draft's working state -- unlike `content/dossiers/<slug>/`, which
  mirrors one draft's path, `content/tldr/` has no draft to mirror.
- **An eleventh `chitragupta/draft.py` verb**, because the drafting layer
  is where LLM output already lives, and because a skill session --
  which is what actually composes the words -- is drafting-layer by
  definition.

[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-four-constraints-every-item-respects)'s
constraint 1 ("no LLM output may reach the corpus plane") names this
placement as the whole design decision behind the module; nothing below
changes that.

## 🔭 #401: generating it unattended

Everything in this section is **proposed, not built**, and is tracked as
parked on the issue tracker
([#401](https://github.com/prasadtalasila/chitragupta/issues/401)).
`tldr.py`'s own docstring already anticipates a generator -- "someone
else composed" the summary, "a person, or a skill in the current Claude
Code session" -- and this is a design for who that someone else is when
nobody is watching a session at all. The measurements below were taken
against the real corpus at 497 parsed documents and are the durable part
of the proposal; whoever picks this up should not need to re-derive them.

### 📐 The shape: two paths, split on whether the paper has an abstract

**Path A -- the author's own abstract, stored verbatim.** No LLM, no
word limit, no summarisation. This is *extraction*, not summarisation:
the words are the authors' own, so there is no hallucination surface at
all.

**Path B -- no detectable abstract: the whole parsed text to an LLM, out
comes 100-120 words.**

The split pays for itself: path A covers 68% of the corpus for zero
tokens, and **self-heals for free on re-parse** -- when the fingerprint
goes stale, re-deriving an abstract costs nothing, so two thirds of the
corpus never needs regenerating.

### 📊 Measured: the abstract is detectable more often than a heading scan suggests

A Markdown-heading scan finds `Abstract` in only 133 of 497 documents
(27%). That undercounts badly, because Docling emits it as running text
as often as a heading -- one document reads `Abstract At the heart of a
digital twin is...` mid-paragraph. An inline-aware regex over the first
25% of each document, stopping at `Keywords`/`Index Terms`/`Introduction`:

| | count | share |
| --- | ---: | ---: |
| usable abstract body (60-400 words) | 337 | 68% |
| no usable abstract | 160 | 32% |

The length distribution of the 337 is why "no word limit" is safe rather
than reckless:

| percentile | words |
| --- | ---: |
| median | 162 |
| p90 | 243 |
| max | 321 |

Only 23 exceed 250 words and 2 exceed 300 -- no 800-word outlier hiding
in the tail.

### 📈 Measured: the papers without abstracts are the long ones

This is the measurement that shapes the whole design. The 160 documents
with no detected abstract are not a random 32% of the corpus -- they are
systematically the largest:

| | no-abstract set | whole corpus |
| --- | ---: | ---: |
| median | 10,696 w | 8,299 w |
| p90 | 27,961 w | -- |
| max | 135,149 w (~176k tokens) | 38,841 w |

That tracks: standards deliverables, project reports and theses are both
the documents that skip an abstract *and* the ones that run long.

Consequence: feeding whole text on path B costs **4.92M input tokens**,
not the ~130k a reduced-extract design would cost -- roughly $10 on
Sonnet 5 or $26 on Opus 5, one-time, re-incurred only for citekeys whose
fingerprint actually moved. Feeding whole text for *all* 497 documents
would be 11.7M tokens; path A is what keeps that off the table.

### ⚖ Why whole text on path B, not an extractive reduction step

The obvious cheaper design reduces each long document first -- rank
`embed_index` chunks by cosine similarity to the document centroid
`doc_vectors.pooled_embedding()` already caches, take the top-K, feed
~600 words to the LLM. Considered and rejected, in order of weight:

1. **It breaches the dependency boundary.** `chitragupta/tldr.py`
   currently imports only `config` and `ledger` -- stdlib plus
   `bibtexparser`. Centroid selection needs `sentence_transformers`,
   which [FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-four-constraints-every-item-respects)'s
   constraint 3 quarantines behind the `enrich` extra, and
   `pyproject.toml` deliberately keeps out of core. Whole text *deletes*
   that problem instead of engineering around it, and
   [SOUL.md](../SOUL.md) says the smaller change wins ties.
2. **The 160 long documents are precisely where a centroid is
   weakest.** A centroid selects the *typical* chunk, and in a
   28,000-word standards deliverable the typical chunk is boilerplate.
   It would drop a contribution stated once and keep procedural filler
   stated forty times.
3. **The long-document literature argues for seeing everything.** Koh
   et al.'s *An Empirical Survey on Long Document Summarization* (ACM
   Computing Surveys 55:8, 2022) -- already cited in prose at
   `chitragupta/enrich/doc_vectors.py`'s topic-model note, for the same
   reason -- reports that the layout bias making prefixes work for short
   documents is *absent* in long ones (uniformity 0.89-0.93 long against
   0.78-0.86 short). Salient content is scattered, so any sampling step
   risks missing it and full context does not. That paper is cited here
   as prose, not as a citekey: a ledger query confirms it is not in this
   corpus, and the one citekey invariant applies to a proposal's own
   text as much as to a draft.

### 🚫 Why nothing extractive is ever shown to a reader

Separately from path B's internals: an extractive summary must never be
the *stored* artefact. Stitching four sentences from different sections
of a paper into 110 words produces dangling anaphora -- "this approach",
"as shown in Fig. 3", "the proposed method" -- referring to things not in
the summary. That is incoherent by construction, not by tuning.
Extraction is acceptable as LLM *input*, where the reader never sees it;
it is not acceptable as output.

### 🧩 What this needs before it can be built

- **Provenance fields on the sidecar.** The payload today is
  `{citekey, summary, fingerprint}`. A human-authored TL;DR, an author's
  verbatim abstract and a machine-written summary would be
  indistinguishable on disk. [SOUL.md](../SOUL.md) says "anything
  abstractive waits for a human to accept it" -- that acceptance has
  nowhere to be recorded today. Needs `source: human|abstract|llm` and
  `accepted: bool`, with `show` marking an unaccepted machine summary the
  way it already marks `[STALE]`.
- **An enumerator.** Something like `tldr stale --json` listing citekeys
  whose sidecar is missing or whose fingerprint no longer matches, so a
  driver has a work list. `dossier status --all` is the existing shape
  to follow.
- **One subagent per paper, not one session loop.** A single session
  cannot carry 4.92M tokens; it would hit compaction partway through and
  later summaries would degrade silently. Each paper needs a fresh
  context that returns 100-120 words to a parent, which pipes them to
  `tldr write`. This is also what makes "no conversation history
  crosses between papers" true rather than aspirational.

### ⚠ Risks a reader should not have to rediscover

- **Abstract detection is a length gate, not a content gate.**
  `60 <= words <= 400` is what separates path A from path B, and it can
  be fooled: a table-of-contents entry, or an `Abstract` heading
  followed by unrelated prose, passes it and gets stored verbatim as
  authoritative -- on the path that skips both the LLM *and* human
  acceptance. The asymmetry is backwards: a false negative merely costs
  tokens on path B, a false positive publishes noise as trustworthy.
  **Sample and read ~20 of the 337 detected bodies before any of this
  ships.** If precision is not near-perfect, `accepted` should default to
  `false` on both paths, not just path B.
- **A verbatim abstract is still the authors' wording.** The sidecar
  itself is fine -- attributed to a citekey, a browsing aid rather than a
  draft. The hazard is downstream: a TL;DR *reads like* a finished
  summary, so a drafting session may echo its phrasing into prose in a
  way it would not when paraphrasing from `content/parsed/`.
  `python -m chitragupta.review verbatim scan` is a real safety net here
  -- it compares a draft against the parsed text the abstract came from --
  but only where its deterministic tiers can see it. The `source:
  "abstract"` field is what would warn a consumer these are borrowed
  words.
- **Two artefact shapes in one sidecar.** Author abstracts up to 321
  words alongside machine summaries at ~110. Acceptable for a browsing
  aid, but it should be a stated choice rather than something discovered
  later by a reader comparing two TL;DRs.
- **Two cheap wins already identified, for whoever builds this:**
  back-matter stripping (`chitragupta/enrich/doc_vectors.py`'s
  `BACK_MATTER` regex) saves 12% of path B's tokens (4.92M to 4.34M) but
  is recommended *against* importing for this, since pulling from
  `chitragupta.enrich` reintroduces exactly the drafting-to-enrichment
  coupling whole text was chosen to avoid, to save about $1.20 on an
  axis that is not the binding constraint. Byte-identical duplicate
  parsed files (7 pairs in the no-abstract set, 2% of path B's tokens)
  are worth a hash check in the enumerator instead.

### 🅿 Why this is parked, not next

- **The detection precision is unvalidated.** The 68% figure counts what
  the regex *matched*, not what it matched *correctly*. Until someone
  reads a sample, path A's headline benefit is unproven and the
  false-positive risk above is unquantified.
- **It is a schema change to a sidecar that just landed.** #398 merged
  days before #401 was filed. `source` and `accepted` are the right
  fields, but adding them before the current format has been used in
  anger is guessing at requirements.
- **The acceptance workflow has no home.** [SOUL.md](../SOUL.md)
  requires a human to accept abstractive output, and there is no `tldr
  accept`, no review surface, and no plausible answer yet to "who reads
  160 machine summaries, and on what occasion." Building the generator
  before the acceptance path produces 160 artefacts that are permanently
  unaccepted -- worse than not having them at all.
- **The cost is real and recurring**, not one-time. 4.92M tokens is
  cheap once, but it is re-incurred on every backend switch or
  `--reparse` that changes text for those 160 documents -- a running cost
  attached to a feature nobody has yet asked for.

Also explicitly **not** proposed by this or any related work: showing a
TL;DR in `corpus ledger` output. That would put LLM output in the
corpus-layer command's own view, inverting the layer order the same way
caching a summary in the ledger itself would --
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-what-is-deliberately-not-proposed)
records the decision.
