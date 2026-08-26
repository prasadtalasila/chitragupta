# 🔭 Corpus search: how a query becomes passages

Status: **reference.** Written 2026-08-26.

[RETRIEVAL.md](RETRIEVAL.md) answers *which* search to build -- BM25,
embeddings, or the topic model -- and stops there. This document answers
what happens **inside** one `embed_index.search()` call: the four stages
a query passes through, why they are in that order, and which of them
you can change from `config.toml`.

Read this if you are turning `[enrich].rerank` on, choosing a
`rerank_model`, or wondering why a paper you know is in the corpus did
not come back.

## 🧭 Table of contents

- [The four stages](#-the-four-stages)
- [Why the rerank sits where it does](#-why-the-rerank-sits-where-it-does)
- [What reranking does and does not buy](#-what-reranking-does-and-does-not-buy)
- [What it costs](#-what-it-costs)
- [Choosing a reranker](#-choosing-a-reranker)
- [Turning it on](#-turning-it-on)
- [When a paper does not come back](#-when-a-paper-does-not-come-back)
- [What BM25 does instead](#-what-bm25-does-instead)

## 🪜 The four stages

`chitragupta/enrich/embed_index.py::search(query, k)` is four stages, of
which the second is optional and off by default.

```mermaid
flowchart TB

  Q(["<b>query</b><br/><i>“digital twin composability”</i>"])

  S1["<b>1 · OVER-FETCH</b><br/><small>Chroma returns k × <code>embed_overfetch_multiplier</code><br/>= 5 × 4 = 20 chunks, by cosine distance</small>"]
  S2["<b>2 · RERANK</b> — optional, <b>off by default</b><br/><small>a cross-encoder rescores all 20<br/>(query, passage) pairs <i>jointly</i><br/><code>[enrich].rerank = true</code></small>"]
  S3["<b>3 · CAP</b><br/><small>at most <code>embed_max_passages_per_source</code> (3)<br/>chunks from any one citekey</small>"]
  S4["<b>4 · TRUNCATE</b><br/><small>keep the first k — <code>embed_top_k</code> = 5</small>"]
  OUT[/"<b>5 passages</b><br/><small>each with citekey, title, snippet, distance</small>"/]

  Q --> S1 --> S2 --> S3 --> S4 --> OUT

  classDef optional fill:#fff4ce,stroke:#b8860b,stroke-width:3px
  class S2 optional
```

**Every size in that diagram is a `config.toml` key.** All three live
under `[enrich]`, all three are validated at load, and
[CONFIG.md](CONFIG.md#-the-three-that-size-a-search) is the reference:

| Stage | Key | Default | Reach for it when |
| --- | --- | --- | --- |
| 1 | `embed_overfetch_multiplier` | `4` | the right paper never comes back **at all** |
| 2 | `rerank` / `rerank_model` | `false` | the right paper comes back, but 4th or 5th |
| 3 | `embed_max_passages_per_source` | `3` | one paper is filling the whole result |
| 4 | `embed_top_k` | `5` | you want more or fewer passages per search |

**Why over-fetch at all.** Chroma ranks *chunks*, not documents, so a
single thoroughly-matched paper can otherwise occupy every one of the
`k` slots. Fetching `k × 4` gives the cap something to promote *from* --
see the next section. At a multiplier of `1` the cap can only ever
shorten the result, never improve it, which is the failure #305 existed
to fix.

**Why the cap is keyed on citekey, not title.** Two untitled or
same-titled documents are still different papers, and bucketing them
together would silently drop one.

**`snippet_chars` stops being cosmetic when stage 2 is on.** The
cross-encoder scores the *truncated snippet*, not the whole 200-word
chunk, so shrinking `snippet_chars` narrows what the reranker may judge
on as well as what you see. This is deliberate: the passage you are
shown is then exactly the evidence the ranking was based on. It is not a
`config.toml` key -- callers pass it -- but it is worth knowing before
tuning it alongside the four above.

## ⚖ Why the rerank sits where it does

This is the one ordering decision in the file, and it is worth stating
because the wrong order looks identical in a code review.

```mermaid
flowchart LR

  subgraph RIGHT["<b>WHAT SHIPS — over-fetch, rerank, then cap</b>"]
    direction TB
    R1["20 chunks<br/><small>A A A B C</small>"]
    R2["reranked<br/><small>C A A A B</small>"]
    R3["capped at 2/paper, k=3<br/><b>C A A</b><br/><small>the rerank promoted C past the cap</small>"]
    R1 --> R2 --> R3
  end

  subgraph WRONG["<b>THE MISTAKE — over-fetch, cap, then rerank</b>"]
    direction TB
    W1["20 chunks<br/><small>A A A B C</small>"]
    W2["capped at 2/paper, k=3<br/><small>A A B</small>"]
    W3["reranked<br/><b>A A B</b><br/><small>C was capped out before scoring —<br/>only a permutation is left</small>"]
    W1 --> W2 --> W3
  end

  classDef good fill:#e8f5e9,stroke:#2e7d32
  classDef bad fill:#ffe6e6,stroke:#c00
  class R3 good
  class W3 bad
```

The cap's purpose is that dropping a dominant paper's excess chunks
**promotes another paper's chunk into the window**. Run the rerank
first and a promotion can change *which document* survives. Run it
after, and it can only permute the papers the bi-encoder already chose
-- the cross-encoder's opinion arrives too late to matter.

This is not a theoretical distinction. Measured over 256 real queries,
the two orders return a **different set of papers on 217 of them
(85%)**, and the correct order scores better (nDCG@5 0.5281 against
0.4962). `tests/test_enrich_embed_index.py::TestSearchReranks` pins it
so a refactor cannot quietly swap the two.

## 📊 What reranking does and does not buy

Measured on this project's own corpus (642 ledger items, 497 parsed,
40,741 chunks) against 256 queries whose correct answer no retrieval
method chose -- full method and caveats in `bench/RESULTS.md`,
*"2026-08-26: where a cross-encoder rerank sits, relative to the
per-citekey cap"*.

| | off (today) | on (`ms-marco-MiniLM-L6-v2`) | change |
| --- | --- | --- | --- |
| recall@3 | 129 / 256 | **139 / 256** | **+10 queries** |
| recall@5 | 156 / 256 | 156 / 256 | **none** |
| nDCG@5 | 0.4949 | **0.5281** | +0.033 |
| distinct papers in top 5 | 3.590 | 3.574 | **none** |

Three things to take from that table:

- **It improves ordering, not recall.** The right paper is not found
  more often; it is found *higher*. If you read the top 3 and stop,
  that is worth something. If you read all 5, it is worth nothing.
- **recall@5 is unchanged because the swaps cancel**, not because
  nothing happened: the correct paper is lost 20 times and gained 20
  times across those 256 queries.
- **It does not improve source diversity, and cannot.** With a cap of 3
  and `k` of 5, the number of distinct papers in a result is bounded to
  {2, 3, 4, 5} by the **cap**, not by the ordering. Reranking reshuffles
  within that regime. If you want more sources per query, lower
  `embed_max_passages_per_source` or raise `k`; reranking is not that
  lever.

## 💸 What it costs

A reranker runs once per `search()` call, inside a drafting loop, so
what matters is the *added* latency per call. Measured in the same
process as the baseline it is compared against (`bench/RESULTS.md`,
*"2026-08-26b"*); pool 20 is the shipped setting.

| device | baseline `search()` | + `ms-marco-MiniLM-L6-v2` | + `bge-reranker-base` |
| --- | --- | --- | --- |
| GPU | 12.4 ms | 18.9 ms (**2.5x**) | 67.0 ms (**6.4x**) |
| CPU | 44.2 ms | 210 ms (**5.8x**) | 1001 ms (**23.6x**) |

Plus a one-off model construction of ~1.8-3.5 s on the first reranked
call of a process.

**The `enrich` extra does not require a GPU**, and a genre skill issues
many searches per draft. On CPU with `bge-reranker-base` that is a full
second of added latency on every one of them.

Deepening the pool is the expensive knob, not a free one: 5 → 20 → 50
chunks costs roughly 1x → 3.3x → 7.2x.

## 🧮 Choosing a reranker

`rerank_model` takes a **cross-encoder** -- a model that scores a
`(query, passage)` pair jointly in one forward pass and returns a single
relevance logit. That is a different architecture from `embedding_model`,
which takes a bi-encoder that embeds each side independently.

> **The bge-\*/e5-\* prefix warning does not carry over.**
> [CONFIG.md](CONFIG.md#-choosing-an-embedding-model) rules those
> families out of `embedding_model` because they expect literal
> `"query: "` / `"passage: "` prefixes that this code does not add.
> That applies to *bi-encoders*, which need a role marker because they
> never see the two texts together. `BAAI/bge-reranker-base` is
> `XLMRobertaForSequenceClassification` with `num_labels=1` -- a true
> cross-encoder, no prefix expected -- and is a genuine drop-in here.

### ✅ Measured candidates

All three scored on the same 256 queries, arm 2 (reranked before the
cap), against an un-reranked baseline of recall@3 129, recall@5 156,
nDCG@5 0.4949:

| Model | recall@3 | recall@5 | nDCG@5 | GPU cost | CPU cost | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| `cross-encoder/ms-marco-MiniLM-L6-v2` **(default)** | 139 | 156 | **0.5281** | **2.5x** | **5.8x** | Best nDCG, cheapest by a wide margin |
| `cross-encoder/ms-marco-MiniLM-L12-v2` | 138 | 152 | 0.5107 | 3.8x | 10.1x | **Rejected** -- worse than its smaller sibling on every metric, and twice the cost |
| `BAAI/bge-reranker-base` | **144** | **157** | 0.5175 | 6.4x | 23.6x | **Rejected as default** -- best recall, but by 5 queries in 256 for 3.5-4.8x the cost. Reasonable if you have a GPU and read only the top 3 |

The default is the cheapest, and it also won the ordering metric. The
recall winner costs several times more for a margin that one
document-level ground truth cannot resolve.

### 🚫 Not a drop-in

- **Any bi-encoder** -- `sentence-transformers/all-mpnet-base-v2` and
  friends. They embed one text at a time and have no notion of a pair;
  `CrossEncoder` will refuse them or produce nonsense.
- **LLM-as-reranker.** Out of scope here by design. This project's
  ranking stays deterministic and local.

## 🔧 Turning it on

`config.toml` is not in the repository -- you create it from
`config.toml.example`. Two keys, both under `[enrich]`:

```toml
[enrich]
rerank = true
rerank_model = "cross-encoder/ms-marco-MiniLM-L6-v2"

# The stage sizes, all optional -- these are the defaults.
embed_top_k = 5
embed_max_passages_per_source = 3
embed_overfetch_multiplier = 4
```

Or for a single run, without editing the file:

```bash
RERANK=true python -m chitragupta.retrieval search "digital twin composability"
```

Two keys rather than one, because `rerank_model = ""` cannot mean "off"
safely here: [CONFIG.md](CONFIG.md#-how-values-are-parsed) documents that
a string setting with the wrong TOML type falls back to its default
*silently*, so a typo would be indistinguishable from a deliberate
off-switch. The boolean says what was intended; the string says what to
load.

**Nothing needs rebuilding.** Unlike `embedding_model`, which
namespaces its own Chroma collection and requires a re-embed, `rerank`
changes ranking only. Turn it on and off freely.

**If the model cannot be loaded, `search()` raises**, naming both the
key and the model id. It does not fall back to un-reranked results: they
would look entirely normal, which is exactly the kind of silent
misconfiguration [CONFIG.md](CONFIG.md#-how-configuration-is-loaded)
refuses elsewhere.

## 🕵 When a paper does not come back

Reranking is often the wrong thing to reach for. In the measurement
above, **69 of 256 correct papers (27%) never entered the 20-chunk pool
at all** -- no reordering can retrieve what stage 1 did not fetch. That
puts a ceiling of 0.73 on dense recall@5 here that a reranker cannot
lift.

Work down this list instead:

| Symptom | Likely stage | What to change |
| --- | --- | --- |
| The paper has no parsed text | before stage 1 | It is findable by BM25 (title) but not here -- `build_index` skips documents with no text. Re-run `sync`, check the PDF parsed |
| One paper fills the result | stage 3 | Lower `embed_max_passages_per_source` (to `1` for maximal diversity) |
| The right paper is in the results but 4th or 5th | stage 2 | This is what reranking is for |
| The right paper is absent entirely | stage 1 | Raise `embed_overfetch_multiplier`, or `embed_top_k` -- the pool is their product. Reranking will not help |
| It uses different vocabulary than your query | stage 1 | This is what embeddings are *for*; if it still misses, the chunk may straddle a boundary |

## 🆚 What BM25 does instead

`chitragupta/retrieval.py::search()` has the same
`search(query, k, snippet_chars)` shape and none of these four stages.
It is **one result per citekey by construction** (#305) -- it scores
whole documents, so no cap is needed and none exists.

That also means it has **no cap-position question**, and no
`rerank` key. Reranking BM25's own over-fetched list was measured and
did not help: nDCG@5 fell from 0.7321 to 0.6886. See
`bench/RESULTS.md`.

On this project's corpus BM25 outscores the dense path on every ground
truth tried so far. [RETRIEVAL.md](RETRIEVAL.md#-which-should-i-build)
is where that choice belongs.
