# 🔭 Per-citekey TL;DR: the written summary, and the abstract behind it

Status: **reference.** Written 2026-08-24. Updated 2026-09-09.

What `chitragupta draft tldr` does: a one-paragraph summary per citekey,
written by a person and cached beside a fingerprint of its parsed text,
falling back to the authors' own abstract for the citekeys nobody has got
to. Plus the half of the
[unattended-generation design](https://github.com/prasadtalasila/chitragupta/issues/401)
that was **declined** rather than built -- sending the whole text of a
paper with no abstract to a model.

**Written for** someone wondering why `tldr write` reads from stdin
instead of summarising a paper itself, or why a paper with no abstract
reports nothing rather than getting one generated. **Assumed:**
[ARCHITECTURE.md](ARCHITECTURE.md)'s four layers and the citekey
invariant ([SOUL.md](../SOUL.md)). **Not covered here:** every flag --
[CLI.md](CLI.md#-chitragupta-draft-tldr) is the exhaustive reference;
this is the design.

## 🧭 Table of contents

- [What's built](#-whats-built)
- [Why it lives where it lives](#-why-it-lives-where-it-lives)
- [The abstract fallback](#-the-abstract-fallback)
  - [Why the passage sidecar and not the flattened text](#-why-the-passage-sidecar-and-not-the-flattened-text)
  - [Docling has no abstract label](#-docling-has-no-abstract-label)
  - [The three guards, and what each one cost](#-the-three-guards-and-what-each-one-cost)
  - [Why it is derived on every read and never stored](#-why-it-is-derived-on-every-read-and-never-stored)
  - [Why a verbatim abstract is not the extractive summary this rejects](#-why-a-verbatim-abstract-is-not-the-extractive-summary-this-rejects)
- [What is declined: whole-paper summarisation](#-what-is-declined-whole-paper-summarisation)
  - [Measured: the papers without abstracts are the long ones](#-measured-the-papers-without-abstracts-are-the-long-ones)
  - [Why no reduction step would have rescued it](#-why-no-reduction-step-would-have-rescued-it)
  - [The three things it would have needed first](#-the-three-things-it-would-have-needed-first)

## 📦 What's built

`chitragupta/tldr.py` is deliberately small: a `write`/`show` pair
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
re-parsed; staleness is never cached, only re-derived.

`show` answers with one of four `source` values, and the last two are
deliberately not one:

| `source` | Meaning |
| --- | --- |
| `human` | somebody wrote a TL;DR; `stale` reports it against the current parse |
| `abstract` | nobody did, so the authors' own abstract stands in; never stale |
| `none` | nobody did, and this paper has no abstract -- "abstract not available" |
| `unknown` | nobody did, and there is no passage sidecar, so nothing can tell |

`none` is a statement about the paper. `unknown` is a statement about how
the paper was parsed: `pdf_text/_backends.py`'s `_extract_pdftotext`
returns `None` rather than an empty list -- "this backend resolves no
reading order" -- so nothing writes a passage sidecar for it, and
`[parser].backend = "docling"` is what fixes it. Collapsing the two would
report "no abstract" about a document nothing had read, which is the one
answer worse than no answer.

## 🏗 Why it lives where it lives

`content/tldr/`, not `content/dossiers/` or `content/ledger.sqlite`:

- **Not the corpus layer.** A written summary may be LLM output -- a
  skill in the current session is one of the two things that compose one
  -- and [SOUL.md](../SOUL.md) says the corpus layer "has no LLM and no
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
changes that. The abstract fallback does not touch that constraint from
either side: it makes no LLM call, and it writes nothing at all.

## 🔍 The abstract fallback

`chitragupta/_abstract.py` answers "what does this paper say it is
about?" without asking a model, by finding the authors' own abstract in
the citekey's passage sidecar and returning it verbatim. Nothing is
summarised, paraphrased or rewritten, so there is no hallucination
surface: the words are the authors' or there is no answer.

It resolves an abstract for **318 of this project's 498 parsed
documents (63.9%)**. The remaining 180 report `none` or `unknown` rather
than getting anything generated -- see
[what is declined](#-what-is-declined-whole-paper-summarisation).

### 📐 Why the passage sidecar and not the flattened text

The obvious implementation is a regex over `content/parsed/<citekey>.txt`,
and it is the one issue #401 and an earlier revision of this document
described. It was measured and then replaced, because the flattened file
has thrown away the thing the job needs.

Docling resolves reading order and labels every item it emits, and
`content/docling/<citekey>.passages.json` already carries both -- 498 of
them, written by a stage that has already run. `chitragupta/passages.py`
is that sidecar's reader, so `structural_passages()` there is the one
resolver both rungs go through, and this module never re-derives the
"enrichment sidecar before corpus sidecar" order for itself.

Recall is the same either way -- a flat-text regex finds 337 of 498 and
the structural pass finds 342 -- so the sidecar buys nothing in coverage.
What it buys is **precision**: "stop at the next `section_header`" is a
structural fact, where "stop after N words" is a guess. That difference
is the entire value, and it is why the shipped figure (318) is *lower*
than the regex's 337 rather than higher. The gap is the withheld set.

### 🏷 Docling has no abstract label

Worth stating plainly, because it is the first thing a reader assumes:
there is no `abstract` in `DocItemLabel`. The enum runs
`caption`, `chart`, `code`, `document_index`, `footnote`, `form`,
`formula`, `list_item`, `marker`, `page_footer`, `page_header`,
`paragraph`, `picture`, `reference`, `section_header`, `table`, `text`,
`title`, plus field and checkbox variants -- and nothing in it marks an
abstract semantically.

"Structure" here therefore means reading order and heading boundaries,
nothing more. The two openers are matched on their *text*: `Abstract`
alone on a line as a `section_header`, or the same word opening a
paragraph that runs straight into the abstract. The second is not an edge
case -- Docling emits it that way for 210 of the 342 documents where an
abstract is found at all, as in `Abstract At the heart of a digital twin
is...`, which is why a heading-only scan finds just 133.

### ⚖ The three guards, and what each one cost

The guards **withhold** rather than trim, and the asymmetry is the whole
reason. A false negative reports "abstract not available" for a paper
that has one, and costs a reader one `less
content/parsed/<citekey>.txt`. A false positive publishes something that
is not an abstract as though the authors wrote it. Each guard is set
where measurement put it, against the real 498, and each answers a
failure that was read rather than imagined:

| Guard | Set at | The failure it answers |
| --- | --- | --- |
| `MAX_LEAD_ITEMS` | 40 | `slavic_python_2025` matched an inline `Abstract` at item #155 and `akiki_resources_2025` at #93, both capturing class-diagram text. Genuine openers sit at median item #5 (inline) or #7 (heading), p90 #21 |
| `MAX_BODY_ITEMS` | 3 | Five documents opened with a correct abstract and ran on, because no `section_header` and no `Keywords` line arrived to stop them -- `humlum_large_2025` swallowed 1442 words |
| `MIN_BODY_WORDS` / `MAX_BODY_WORDS` | 40 / 400 | A length sanity check on the result. The longest genuine abstract here is 321 words and the p90 is 243, so anything past the ceiling means the stop rule failed |

Three things about that table are decisions rather than tuning, and are
the parts worth not re-deriving:

- **The body cap counts items, not words.** A word cap discards a
  correct abstract whose real text sits in its first 200 words, which is
  exactly `humlum_large_2025`: its abstract is right there and the
  runaway is behind it.
- **The floor is 40, not the 60 issue #401 proposed.** `lin_utwin_2023`
  is a real, correctly-bounded abstract at 58 words, and a floor of 60
  drops it.
  `deslauriers_everyday_2022`'s title-and-affiliations false positive
  falls under 40 anyway, at 35 -- caught by a length check rather than by
  any rule about title blocks, which is worth knowing before someone
  reads the floor as a precision device. It is not one.
- **One real detection is knowingly lost.**
  `fitzgerald_engineering_2024-1` is a genuine chapter abstract sitting
  at item #407 of a whole-book PDF, and the lead window withholds it.
  That is the stated price of the lead window rather than an
  unnoticed bug: chapter-in-book PDFs are the shape it costs.

The precision claim behind all of this is a read sample, not a count of
what a regex matched: 19 detected bodies were read by hand, which is what
issue #401 asked for before any of it shipped. Every one between roughly
60 and 300 words was a genuine, correctly-bounded abstract; all four
false positives and all five runaways were outside that band, and the
guards above are where they were drawn from.

### ♻ Why it is derived on every read and never stored

An extracted abstract is not written to `content/tldr/`, and that is the
design rather than an omission. Caching it would *create* the staleness
the sidecar's fingerprint exists to detect: a stored abstract goes stale
on the next re-parse and needs re-deriving, where a derived one is
current by construction. `stale` is therefore structurally `false` for
`source: "abstract"`, not merely usually false.

Two things follow, and both are why this shape is small:

- **No schema change.** The payload on disk stays
  `{citekey, summary, fingerprint}`. Because nothing but `write` ever
  creates that file, everything in it is human-authored by construction,
  so provenance is answered by *where the text came from* rather than by
  a stored field: a sidecar exists, or extraction ran. `source` lives
  only in the dict `resolve()` returns.
- **A written summary wins.** Extraction runs only when `read` finds
  nothing. Somebody who wrote a TL;DR chose to, and the fingerprint
  machinery exists for exactly that text -- a summary a person composed
  cannot be recovered once it is stale, and an abstract can always just
  be read again.

### 🧷 Why a verbatim abstract is not the extractive summary this rejects

An earlier revision of this document said, of the declined generator's
internals, that "an extractive summary must never be the stored
artefact": stitching four sentences from different sections into 110
words produces dangling anaphora -- "this approach", "as shown in Fig.
3", "the proposed method" -- referring to things that are not in the
summary. That is incoherent by construction rather than by tuning, and it
still stands.

It is not what the fallback does, and the distinction is structural
rather than a matter of degree. The abstract is one **contiguous** span
in reading order that its authors wrote to be read standalone; up to
three consecutive paragraphs are joined, and the span ends at the next
heading. Nothing is selected from elsewhere in the paper and nothing is
recombined, so there is no dangling reference to construct. That is why
issue #401 put the author's abstract on a path of its own from the start,
rather than treating it as the cheap end of summarisation.

## 🚫 What is declined: whole-paper summarisation

The other half of the proposal was: no detectable abstract, so send the
whole parsed text to an LLM and take 100-120 words back. That is
**declined**, not deferred, and
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-what-is-deliberately-not-proposed)
carries the row. A paper with no abstract reports that it has none.

The measurements below are why, and they are the durable part of the
original proposal; whoever reopens this should not need to re-derive
them.

### 📈 Measured: the papers without abstracts are the long ones

This is the measurement that decides it. The documents with no detected
abstract are not a random third of the corpus -- they are systematically
the largest:

| | no-abstract set | whole corpus |
| --- | ---: | ---: |
| median | 10,696 w | 8,299 w |
| p90 | 27,961 w | -- |
| max | 135,149 w (~176k tokens) | 38,841 w |

That tracks: standards deliverables, project reports and theses are both
the documents that skip an abstract *and* the ones that run long.

Consequence: feeding whole text costs **4.92M input tokens** -- roughly
$10 on Sonnet 5 or $26 on Opus 5, and re-incurred for every citekey whose
parsed text moves, so it is a *running* cost attached to a feature nobody
asked for rather than a one-off. Feeding whole text for all 498 documents
would be 11.7M; the abstract path is what keeps that off the table.

### ⚙ Why no reduction step would have rescued it

The obvious cheaper design reduces each long document first -- rank
`embed_index` chunks by cosine similarity to the document centroid
`doc_vectors.pooled_embedding()` already caches, take the top-K, feed
~600 words to the model. Rejected, in order of weight:

1. **It breaches the dependency boundary.** Centroid selection needs
   `sentence_transformers`, which
   [FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-four-constraints-every-item-respects)'s
   constraint 3 quarantines behind the `enrich` extra and
   `pyproject.toml` deliberately keeps out of core -- and `tldr` is a
   tier-1 command that must run under bare `python3`
   ([ARCHITECTURE.md](ARCHITECTURE.md#-which-interpreter-and-why)). Worth
   noting what shipped instead: `_abstract.py` imports only
   `chitragupta.passages`, itself stdlib-only, so the extractor stays
   inside that boundary rather than engineering around it.
2. **The long documents are precisely where a centroid is weakest.** A
   centroid selects the *typical* chunk, and in a 28,000-word standards
   deliverable the typical chunk is boilerplate. It would drop a
   contribution stated once and keep procedural filler stated forty
   times.
3. **The long-document literature argues for seeing everything.** Koh
   et al.'s *An Empirical Survey on Long Document Summarization* (ACM
   Computing Surveys 55:8, 2022) -- already cited in prose at
   `chitragupta/enrich/doc_vectors.py`'s topic-model note, for the same
   reason -- reports that the layout bias making prefixes work for short
   documents is *absent* in long ones (uniformity 0.89-0.93 long against
   0.78-0.86 short). Salient content is scattered, so any sampling step
   risks missing it. That paper is cited here as prose, not as a
   citekey: a ledger query confirms it is not in this corpus, and the one
   citekey invariant applies to a document's own text as much as to a
   draft.

So the choice was whole text or nothing, and whole text is what the cost
above prices.

### 🧩 The three things it would have needed first

Recorded because they are what a reopening would have to answer, and none
of them is a matter of effort:

- **A home for acceptance.** [SOUL.md](../SOUL.md) requires a human to
  accept anything abstractive. There is no `tldr accept`, no review
  surface, and no plausible answer to "who reads 160 machine summaries,
  and on what occasion" -- and building the generator first produces 160
  artefacts that are permanently unaccepted, which is worse than not
  having them. Note that this clause is exactly what the abstract
  fallback does *not* trip: verbatim extraction is not abstractive, so
  there is nothing to accept, which is why it needs no `accepted` field
  and could ship without one.
- **Provenance on the sidecar.** A human TL;DR and a machine summary
  would be indistinguishable on disk, so an LLM path needs
  `source: human|llm` and `accepted: bool` *stored*. The abstract
  fallback needs neither, because it stores nothing -- see
  [why it is derived on every read](#-why-it-is-derived-on-every-read-and-never-stored).
- **One subagent per paper, not one session loop.** A single session
  cannot carry 4.92M tokens; it would hit compaction partway through and
  the later summaries would degrade silently. Each paper needs a fresh
  context returning 100-120 words to a parent that pipes them to `tldr
  write`.

Also explicitly **not** proposed by this or any related work: showing a
TL;DR in `corpus ledger` output. That would put LLM output in the
corpus-layer command's own view, inverting the layer order the same way
caching a summary in the ledger itself would --
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md#-what-is-deliberately-not-proposed)
records the decision.
