# G5-G9: topic discovery -- from a phrase to the papers, the graph, and an overview

Status: **plan, unbuilt.** Written 2026-09-02. Implements
[docs/FEATURE-ROADMAP.md](../docs/FEATURE-ROADMAP.md)'s G5-G9, the first
Theme G work since G1-G4 closed, and the first consumer of
`content/topic_set.json` -- the artefact
[docs/TOPIC-MODELLING.md](../docs/TOPIC-MODELLING.md) records as having
shipped without a reader (issue #192's finding).

**Written for** whoever builds it, one PR per item, in order.
**Assumed:** [docs/TOPIC-MODELLING.md](../docs/TOPIC-MODELLING.md) for
how the topic artefacts are produced and why they look the way they do;
[docs/RETRIEVAL.md](../docs/RETRIEVAL.md) for the BM25 layer;
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the tier split the
reader must respect. **Not covered here:** the topic *model* itself --
clustering, seeding and convergence are G1-G4's settled ground, and
nothing in G5-G9 changes how a topic comes to exist.

## What this is for

Start from a phrase, find the corpus's real topics near it, see each
topic's papers with their bibliographic details, walk to the linked
topics, and take away an extractive overview grounded enough to seed a
draft. Scripted (`--json` everywhere) and interactive (successive
invocations, then a self-contained HTML page). No generative model
anywhere: embeddings, BM25, a cross-encoder scorer and classic
statistics only, and every citekey shown comes from the ledger via the
topic artefacts -- the same rule as everywhere else in this repository.

Two graphs, kept distinct on purpose:

- **topic -> papers**: already recorded in `topic_set.json`'s members.
- **topic <-> topic**: derived, with two typed edge families that are
  never merged into one score, because they answer different questions
  ("which topics share papers?" versus "which topics say similar
  things?") and their disagreement is itself a discovery cue.

## G5: the `topic-graph` enrich stage

A new final stage, appended after `converge` in
`chitragupta/enrich/__main__.py`'s `STAGE_ORDER`, writing
`content/topic_graph.json`. Like `converge`, it computes nothing about
topics themselves; it derives relations between topics that already
exist, and refuses when `topic_set.json` is absent or was built under a
different embedding model or pooling method.

### The artefact

```json
{
  "model": "...", "embedding_method": "chunk-mean-content-v2",
  "n_docs": 497, "n_topics": 53,
  "corpus_mean": [0.0],
  "topics": [{"label": "...", "provenance": "seed", "size": 12,
               "centroid": [0.0]}],
  "edges_overlap": [{"a": "...", "b": "...", "jaccard": 0.21,
                      "overlap_coeff": 0.83, "p_value": 0.0004,
                      "shared": ["citekey1", "citekey2"]}],
  "edges_semantic": [{"a": "...", "b": "...", "similarity": 0.74,
                       "bridge": ["citekeyA", "citekeyB"]}],
  "hierarchy": []
}
```

Keys are topic **labels**, never topic ids -- ids are documented as
unstable (Theme G's own table says so), and labels are what `converge`
already deduplicates.

### Overlap edges: co-membership, gated by significance

For every topic pair with at least one shared member, record both
Jaccard (`|A∩B| / |A∪B|`) and the overlap coefficient
(`|A∩B| / min(|A|,|B|)`), and keep the edge only when the shared count
is statistically surprising: a hypergeometric tail test
(`scipy.stats.hypergeom.sf`) against the null of drawing `|B|` papers
from `n_docs`, at p < `topic_graph_p_value` (default 0.01).

Three decisions, each with its reason:

- **Both coefficients, one edge.** Jaccard punishes size imbalance:
  a seed topic truncated at `seed_topic_max_papers` nested inside a
  large emergent cluster scores low despite full containment. The
  overlap coefficient reads that case as what it is -- a sub-topic --
  and Theme G's sizes are systematically unequal by construction. But
  overlap alone loses the symmetric-similarity reading, so both travel
  on the edge and the reader shows both.
- **Significance instead of a weight floor.** A weight threshold is a
  knob someone must tune per corpus; "more shared papers than chance,
  given both sizes and the corpus size" is not. It also kills the
  failure mode where two large topics get an edge merely for being
  large.
- **`shared` carries the citekeys.** Every overlap edge must be
  explainable by naming real papers; that is the difference between a
  discovery aid and a black box.

### Semantic edges: average best-match cosine, mutual top-k

Centroid-to-centroid cosine is the obvious choice and the wrong one:
HDBSCAN clusters are non-convex, and a non-convex cluster's centroid
can sit outside it. Instead, for topics A and B: for each member of A
take its best cosine against B's members, average, symmetrise (mean of
the two directions), using the pooled document vectors from
`content/topic_embed_cache.json`. Keep an edge only when each topic is
in the other's top `topic_graph_neighbors` (default 5) -- mutual k-NN
adapts to density where a global floor either floods dense regions or
starves sparse ones. `bridge` names the single highest-cosine pair
across the edge, so semantic edges are paper-explainable too.

Per-topic `centroid` is still stored -- not for edges, but so G6 can
resolve a free-text query against topics without loading the whole
embed cache.

### Hierarchy

An agglomerative merge tree over topic centroids
(`scipy.cluster.hierarchy.linkage`, average linkage, cosine distance),
stashed for G9's tree view. Not `bertopic.hierarchical_topics()`, for
two reasons: that needs the fitted model object, which no stage
persists -- re-fitting to read a tree would repeat an hour of work this
stage's contract forbids -- and it covers emergent topics only, where
the linkage tree covers seed topics in the same pass because a centroid
exists for every topic regardless of provenance.

Centroids -- and the semantic edges above -- are computed in
**mean-centred** embedding space, the same space `topic_descriptors`
uses and for the same measured reason (raw cosines bunch on a
one-subject corpus). The artefact stores the corpus mean so G6 can move
a query embedding into the same space without loading the embed cache.

### Config

`topic_graph_p_value` (default 0.01), `topic_graph_neighbors`
(default 5), both under `[enrich]`, the section every existing topic
knob lives in. `scipy` becomes an explicitly declared enrich-group
dependency (and mirrored extra) -- it was always installed transitively
via bertopic; importing it directly means declaring it.

## G6: the `corpus discover` reader

A new corpus-layer verb, `python -m chitragupta.corpus discover`,
module `chitragupta/discover/`. Reads `topic_graph.json`,
`topic_set.json`, `topics.json` (for top terms) and the ledger
(read-only, for `bib_fields` details). Three invocations:

```text
corpus discover                      # every topic: label, provenance, size, top terms
corpus discover "digital twin"       # the main view, below
corpus discover --paper <citekey>    # the paper's topics, with each topic's neighbours
```

All three take `--json`; the main view also takes `--out FILE` to write
the overview as Markdown. Nothing is written without `--out`.

### Resolution ladder

A free phrase resolves through four rungs, and the output names which
rung fired (`resolved_via: exact | fuzzy | hybrid | search`):

1. **exact** -- case-insensitive equality against topic labels and seed
   phrases.
2. **fuzzy** -- `difflib.get_close_matches` against the same
   vocabulary, for typos and near-forms.
3. **hybrid** -- two rankings fused by Reciprocal Rank Fusion
   (`score = Σ 1/(60 + rank)`): BM25 over each topic's vocabulary
   (label + seed phrase + top c-TF-IDF terms, as one small document per
   topic) beside cosine of the query's embedding against stored topic
   centroids, embedded with the model the artefact stamps. RRF is
   rank-based, so BM25 and cosine scores never need calibrating against
   each other. Then the cross-encoder tier (G7) rescores the fused
   top candidates.
4. **search** -- below the hybrid floor, fall back to
   `chitragupta.retrieval.search()` over papers, clearly labelled a
   search result rather than a topic membership, each hit still
   annotated with its topics.

Rungs 1, 2 and 4 are stdlib-plus-core only. Rung 3 needs the enrich
extra; without it the reader says so in one line and falls through --
same degradation posture as every enrich stage's self-probe. An
unresolvable phrase exits 1 naming the near misses, matching
`corpus topics`' convention.

### The main view

1. Header: label, provenance, size, top terms.
2. Members: citekey, title, year, authors, venue (ledger
   `bib_fields`), membership score -- and the *other* topics each paper
   belongs to, so a paper is always shown inside its neighbourhood.
3. Linked topics, two labelled lists, never merged: overlap neighbours
   ("via: citekey1, citekey2 -- jaccard 0.21, overlap 0.83") and
   semantic neighbours ("bridge: citekeyA <-> citekeyB -- 0.74").

### The overview file (`--out`)

The same view as Markdown, plus representative snippets: the top
`n` sentences from member papers' parsed text ranked by cosine to the
topic centroid, **quoted verbatim with their citekeys** -- extraction,
never paraphrase, for the same reason Theme G declines abstractive
summaries: a summary asserting a claim no paper made is the fabricated
citekey's failure class wearing different clothes.

## G7: the precision tier

Two additions to G6's machinery, both enrich-tier:

- **Cross-encoder rescoring** of the hybrid rung's fused top ~20
  candidates via `sentence_transformers.CrossEncoder` with a small
  MS-MARCO checkpoint -- already installed, no new dependency. The
  cross-encoder sees query and candidate jointly and catches
  term-overlap-without-relevance failures a bi-encoder cannot. Scoring
  pairs are capped at ~256 tokens (label + top terms + best title), so
  20 candidates cost tens of milliseconds on CPU.
- **Personalised PageRank** over the topic graph, seeded from every
  topic the query matched, when resolution is plural -- ranking the
  merged neighbourhood by topology instead of concatenating per-topic
  lists. Pure arithmetic on a graph of at most a few hundred edges;
  no new dependency.

## G8: the gold set

`bench/topic_discovery_eval.py` plus a hand-authored
`content/topic_gold.toml` (`[[query]]` records: phrase, expected
topics, expected citekeys). Reports Recall@k, MRR and NDCG for
query->topic and topic->paper, per resolution rung. Every future knob
change becomes a measured decision instead of a vibe -- the same
posture as G1-G4, where every default cites a measurement in
`bench/RESULTS.md`. Follows the bench self-check convention: fabricate
a difference, assert the script sees it.

## G9: the HTML page

`corpus discover graph --out topics.html`: one self-contained file --
inline JS and CSS, graph data embedded as JSON, no CDN, no server, so
the repository stays print-and-exit and the page works offline
forever. Overlap edges solid, semantic edges dashed; click a topic for
its ego view (members with their other-topic links); the G5 hierarchy
as a collapsible tree beside the graph. A pure renderer of the same
JSON `--json` emits, so the page cannot disagree with the terminal.

## Alternatives considered, and where they went

| Rejected | Why |
| --- | --- |
| One fused topic-topic score | The two edge families answer different questions; merging destroys the disagreement signal |
| A weight floor on overlap edges | A per-corpus knob; the hypergeometric test needs none |
| Centroid-centroid semantic edges | Non-convex HDBSCAN clusters; best-match average respects shape at trivial cost here |
| Soft-membership set similarity (Ružička) | The edge stops being explainable by naming papers |
| Score-interpolation fusion in the ladder | Needs calibration across incommensurable scales; RRF does not |
| Earth-mover's distance between member sets | Cost and opacity, no added explanation, at this scale |
| UMAP-space distances | UMAP distorts global distances by design |
| Edges in the ledger (sqlite) | The corpus plane's derived artefacts are JSON under `content/`; the CLI opens the ledger read-only on purpose |
| A REPL/TUI | Successive invocations plus the HTML page cover interaction without a new UI surface |
| Citation-count priors on members | Needs an external API; the `.bib` is a closed universe by design |
| RM3 pseudo-relevance feedback on the search rung | The classic-IR upgrade path if the fallback proves weak; deferred until the gold set says it is |

## Order and shape

One PR per item, G5 through G9, each with its version bump, docs sweep
(CLI.md, CONFIG.md, FEATURES.md, and a new
[docs/TOPIC-DISCOVERY.md](../docs/TOPIC-DISCOVERY.md) started in G5),
and a tagged release after merge. G6 depends on G5's artefact; G7-G9
each depend on G6; G8 and G9 are independent of each other.
