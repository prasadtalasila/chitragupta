# 🔭 Per-citekey TL;DR: the written summary, and the abstract behind it

Status: **reference.**

`chitragupta draft tldr` keeps a one-paragraph summary per citekey,
written by a person and cached beside a fingerprint of its parsed text,
and falls back to the authors' own abstract where nobody has written
one. This page also records the half of the
[unattended-generation design](https://github.com/prasadtalasila/chitragupta/issues/401)
that was declined: sending a whole paper with no abstract to a model.

**Written for** someone wondering why `tldr write` reads from stdin
instead of summarising a paper, or why a paper with no abstract gets
none generated. **Assumed:** [ARCHITECTURE.md](ARCHITECTURE.md)'s four
layers and the citekey invariant ([SOUL.md](../SOUL.md)). **Not covered
here:** the flags ([CLI.md](CLI.md#-chitragupta-draft-tldr)).

## 📦 What's built

`chitragupta/tldr.py` is a `write`/`show` pair over a JSON sidecar at
`content/tldr/<citekey>.json`, keyed to a `sha256` of the citekey's
*current parsed text* (`content/parsed/<citekey>.txt`), not a stat of
the PDF: a backend switch or `--reparse` can change the text without
the PDF moving, so the fingerprint must be of the text the summary was
written against.

```bash
echo "This paper proposes ..." | chitragupta draft tldr write smith2024
chitragupta draft tldr show smith2024
chitragupta draft tldr show smith2024 --json
```

`write` reads a summary on stdin, from a person or a skill in the
current session, and stores it. **No LLM call happens inside this
module, ever.** `show` recomputes the fingerprint on every read and
marks a summary `[STALE]` once the paper is re-parsed; staleness is
never cached. It answers with one of four `source` values:

| `source` | Meaning |
| --- | --- |
| `human` | somebody wrote a TL;DR; `stale` reports it against the current parse |
| `abstract` | nobody did, so the authors' own abstract stands in; never stale |
| `none` | nobody did, and this paper has no abstract: "abstract not available" |
| `unknown` | nobody did, and there is no passage sidecar, so nothing can tell |

`none` is about the paper; `unknown` is about how it was parsed. The
pdftotext backend (`_extract_pdftotext` in `pdf_text/_backends.py`)
resolves no reading order and writes no passage sidecar;
`[parser].backend = "docling"` fixes it. Merging the two would report
"no abstract" for a document nothing had read, which is worse than no
answer.

## 🏗 Why it lives where it lives

`content/tldr/`, not `content/dossiers/` or `content/ledger.sqlite`:

- **Not the corpus layer.** A written summary may be LLM output, and
  [SOUL.md](../SOUL.md) says the corpus layer "has no LLM and no
  judgment calls." `corpus ledger` is untouched.
- **Not a dossier.** A summary belongs to a citekey, not to one draft,
  so there is no draft path to mirror.
- **A `chitragupta/draft.py` verb**, because the drafting layer is where
  LLM output already lives, and the skill session that composes the
  words is drafting-layer by definition.

[FEATURE-ROADMAP.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/FEATURE-ROADMAP.md#-five-constraints-every-item-respects)'s
constraint 1 ("no LLM output may reach the corpus plane") makes this
placement the module's whole design decision. The abstract fallback
makes no LLM call and writes nothing, so it does not touch it.

## 🔍 The abstract fallback

`chitragupta/_abstract.py` finds the authors' own abstract in the
citekey's passage sidecar and returns it verbatim. Nothing is
summarised or rewritten, so nothing can be hallucinated. It resolves an
abstract for **318 of this project's 498 parsed documents (63.9%)**;
the other 180 report `none` or `unknown`
([what is declined](#-what-is-declined-whole-paper-summarisation)).

### 📐 Why the passage sidecar and not the flattened text

Docling resolves reading order and labels every item, and
`content/docling/<citekey>.passages.json` already carries both.
`structural_passages()` in `chitragupta/passages.py` is the one
resolver, so this module never re-derives the "enrichment sidecar
before corpus sidecar" order itself. A regex over the flattened
`content/parsed/<citekey>.txt` has the same recall (337 of 498 against
342), but "stop at the next `section_header`" is a structural fact
where "stop after N words" is a guess. That precision is the whole
value, and why the shipped 318 is *lower* than the regex's 337: the gap
is the withheld set.

### 🏷 Docling has no abstract label

`DocItemLabel` has no `abstract`: it runs `caption`, `chart`, `code`,
`document_index`, `footnote`, `form`, `formula`, `list_item`, `marker`,
`page_footer`, `page_header`, `paragraph`, `picture`, `reference`,
`section_header`, `table`, `text`, `title`, plus field and checkbox
variants. "Structure" means reading order and heading boundaries only.
The openers are matched on *text*: `Abstract` alone as a
`section_header`, or opening a paragraph that runs into the abstract
(`Abstract At the heart of a digital twin is...`). The second form is
210 of the 342 found, which is why a heading-only scan finds just 133.

### ⚖ The three guards, and what each one cost

The guards withhold rather than trim, because the errors are unequal: a
false negative costs a reader one `less content/parsed/<citekey>.txt`;
a false positive publishes something as though the authors wrote it.
Each guard is set by measurement on the real 498, against an observed
failure:

| Guard | Set at | The failure it answers |
| --- | --- | --- |
| `MAX_LEAD_ITEMS` | 40 | `slavic_python_2025` matched an inline `Abstract` at item #155 and `akiki_resources_2025` at #93, both capturing class-diagram text. Genuine openers sit at median item #5 (inline) or #7 (heading), p90 #21 |
| `MAX_BODY_ITEMS` | 3 | Five documents opened with a correct abstract and ran on, because no `section_header` and no `Keywords` line arrived to stop them; `humlum_large_2025` swallowed 1442 words |
| `MIN_BODY_WORDS` / `MAX_BODY_WORDS` | 40 / 400 | A length sanity check on the result. The longest genuine abstract here is 321 words and the p90 is 243, so anything past the ceiling means the stop rule failed |

Three of these are decisions, not tuning:

- **The body cap counts items, not words.** A word cap would discard
  `humlum_large_2025`'s correct abstract, which comes first with the
  runaway behind it.
- **The floor is 40, not 60.** `lin_utwin_2023` is a real abstract at
  58 words. `deslauriers_everyday_2022`'s title-and-affiliations false
  positive falls under 40 anyway (35); the floor is a length check, not
  a precision device.
- **One real detection is knowingly lost.**
  `fitzgerald_engineering_2024-1` is a chapter abstract at item #407 of
  a whole-book PDF, outside the lead window. Chapter-in-book PDFs are
  the known cost.

The precision claim rests on 19 detected bodies read by hand: every one
between roughly 60 and 300 words was a genuine, correctly bounded
abstract, and all four false positives and five runaways fell outside
that band.

### ♻ Why it is derived on every read and never stored

An extracted abstract is not written to `content/tldr/`: caching it
would *create* the staleness the fingerprint exists to detect, where a
derived one is current by construction. `stale` is always `false` for
`source: "abstract"`. So:

- **No schema change.** The sidecar stays
  `{citekey, summary, fingerprint}`. Only `write` creates it, so its
  contents are human-authored by construction; `source` lives only in
  the dict `resolve()` returns.
- **A written summary wins.** Extraction runs only when `read` finds
  nothing. A person's summary cannot be recovered once stale; an
  abstract can always be read again.

### 🧷 Why a verbatim abstract is not the extractive summary this rejects

An extractive summary must never be the stored artefact: stitching
sentences from different sections produces dangling anaphora ("this
approach", "as shown in Fig. 3") that no tuning fixes. The abstract is
one **contiguous** span in reading order, written by its authors to
stand alone: up to three consecutive paragraphs, ending at the next
heading. Nothing is selected or recombined, so no dangling reference
can arise.

## 🚫 What is declined: whole-paper summarisation

The other half of the proposal sent a paper with no detectable abstract
whole to an LLM for 100-120 words. That is **declined**, not deferred
([FEATURE-ROADMAP.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/FEATURE-ROADMAP.md#-what-is-deliberately-not-proposed)
carries the row): a paper with no abstract reports that it has none. The
reasons follow, so whoever reopens it need not re-derive them.

### 📈 Measured: the papers without abstracts are the long ones

| | no-abstract set | whole corpus |
| --- | ---: | ---: |
| median | 10,696 w | 8,299 w |
| p90 | 27,961 w | -- |
| max | 135,149 w (~176k tokens) | 38,841 w |

Standards deliverables, project reports and theses both skip an
abstract *and* run long. Their whole text is **4.92M input tokens**,
roughly $10 on Sonnet 5 or $26 on Opus 5, recurring whenever a
citekey's parsed text moves (11.7M for all 498 documents).

### ⚙ Why no reduction step would have rescued it

The cheaper design ranks `embed_index` chunks by cosine similarity to
the centroid `doc_vectors.pooled_embedding()` caches and feeds the
top ~600 words. It was rejected, heaviest reason first:

1. **It breaches the dependency boundary.** Centroid selection needs
   `sentence_transformers`, which
   [FEATURE-ROADMAP.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/FEATURE-ROADMAP.md#-five-constraints-every-item-respects)'s
   constraint 3 keeps behind the `enrich` extra, and `tldr` is a tier-1
   command that must run under bare `python3`
   ([ARCHITECTURE.md](ARCHITECTURE.md#-which-interpreter-and-why)).
   `_abstract.py` imports only the stdlib-only `chitragupta.passages`.
2. **A centroid is weakest on long documents.** It picks the *typical*
   chunk, which in a 28,000-word standards deliverable is boilerplate:
   a contribution stated once loses to filler stated forty times.
3. **The long-document literature argues for seeing everything.** Koh
   et al.'s *An Empirical Survey on Long Document Summarization* (ACM
   Computing Surveys 55:8, 2022), also cited in prose in
   `chitragupta/enrich/doc_vectors.py`, reports that the layout bias
   that makes prefixes work is *absent* in long documents (uniformity
   0.89-0.93 long against 0.78-0.86 short), so sampling risks missing
   scattered content. It is cited as prose, not a citekey, because a
   ledger query confirms it is not in this corpus.

So the choice was whole text or nothing, at the cost above.

### 🧩 The three things it would have needed first

- **A home for acceptance.** [SOUL.md](../SOUL.md) requires a human to
  accept anything abstractive. There is no `tldr accept`, no review
  surface, and no answer to who reads 160 machine summaries; 160
  permanently unaccepted artefacts are worse than none. Verbatim
  extraction is not abstractive, so the fallback needs no acceptance.
- **Provenance on the sidecar.** An LLM path needs `source: human|llm`
  and `accepted: bool` *stored*; the fallback stores nothing
  ([why](#-why-it-is-derived-on-every-read-and-never-stored)).
- **One subagent per paper.** One session cannot carry 4.92M tokens
  without compaction silently degrading later summaries; each paper
  needs a fresh context returning 100-120 words to a parent that pipes
  them to `tldr write`.

Also **not** proposed: showing a TL;DR in `corpus ledger` output, which
would put LLM output in a corpus-layer view, inverting the layer order
as caching it in the ledger would
([FEATURE-ROADMAP.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/FEATURE-ROADMAP.md#-what-is-deliberately-not-proposed)).
