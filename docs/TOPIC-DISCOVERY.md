# 🕸 Topic discovery: from a phrase to the papers, the graph, and an overview

Status: **reference for a feature landing in stages.** Written
2026-09-02. The `topic-graph` enrichment stage documented here is
built; the `corpus discover` reader, its precision tier, the gold-set
benchmark and the HTML graph view are G6-G9 in
[FEATURE-ROADMAP.md](FEATURE-ROADMAP.md), with the whole design in
`plans/g5-topic-discovery.md`. Sections below say which half they
describe. [TOPIC-MODELLING.md](TOPIC-MODELLING.md) covers how topics
come to exist at all; this document covers what happens next --
relating them, finding them, and reading them.

## 🎯 What the feature is for

Start from a phrase, find the corpus's real topics near it, see each
topic's papers with their bibliographic details, walk to the linked
topics, and take away an extractive overview grounded enough to seed a
draft. Scripted and interactive, and with no generative model anywhere:
embeddings, BM25, classic statistics and (in G7) a cross-encoder
scorer. Every citekey shown comes from the ledger via the topic
artefacts -- the same rule that binds every other part of this project.

Two relations, kept distinct on purpose:

- **topic -> papers** -- already recorded in `content/topic_set.json`'s
  members; discovery displays it, annotated with ledger detail.
- **topic <-> topic** -- derived by the `topic-graph` stage, with two
  typed edge families that are never merged into one score, because
  they answer different questions and their disagreement is itself a
  discovery cue: two topics can share many papers while saying
  different things, and can say the same thing while sharing none.

## 📦 The artefact: `content/topic_graph.json`

Written by `chitragupta enrich --stages topic-graph`, the sixth and
last stage, which -- like `converge` before it -- computes no topics
itself and refuses when `content/topic_set.json` is missing or was
built under a different embedding model.

```json
{
  "model": "...",
  "n_docs": 497, "n_topics": 53,
  "p_value": 0.01, "neighbors": 5,
  "corpus_mean": [0.0],
  "topics": [{"label": "digital twin", "provenance": "seed",
               "size": 12, "centroid": [0.0]}],
  "edges_overlap": [{"a": "...", "b": "...", "jaccard": 0.21,
                      "overlap_coeff": 0.83, "p_value": 0.0004,
                      "shared": ["citekey1", "citekey2"]}],
  "edges_semantic": [{"a": "...", "b": "...", "similarity": 0.74,
                       "bridge": ["citekeyA", "citekeyB"]}],
  "hierarchy": [{"id": "node-0", "a": "...", "b": "...",
                  "distance": 0.31}]
}
```

Keys are topic **labels**, never topic ids: ids are unstable across
runs, and the topic model's own documentation says anything downstream
must key on labels or citekeys.

## 🔗 Overlap edges: shared members, gated by surprise

An overlap edge exists between two topics when they share more papers
than chance would predict. Three decisions, each with its reason:

- **Both Jaccard and the overlap coefficient travel on every edge.**
  Jaccard (`|A∩B| / |A∪B|`) punishes size imbalance: a seed topic
  rank-truncated at `[enrich].seed_topic_max_papers` sitting entirely
  inside a 40-paper emergent cluster scores 0.15 despite full
  containment. The overlap coefficient (`|A∩B| / min(|A|,|B|)`) reads
  that case as what it is -- a sub-topic, scoring 1.0. Theme G's topic
  sizes are systematically unequal by construction, so the imbalance is
  routine, not exotic; but overlap alone loses the symmetric-similarity
  reading, so both are reported and neither is the edge's gate.
- **The gate is a hypergeometric tail test, not a weight floor.** The
  edge survives when the probability of sharing at least this many
  papers by chance -- drawing `|B|` papers from `n_docs` with `|A|` of
  them marked -- is below `[enrich].topic_graph_p_value`. A weight
  floor is a knob someone must re-tune per corpus; "more shared than
  chance, given both sizes and the corpus size" is not, and it also
  refuses the edge two large topics would otherwise get merely for both
  being large.
- **`shared` names the citekeys.** Every overlap edge is explainable by
  pointing at real papers. That is the difference between a discovery
  aid and a black box, and it is the property the tests pin first.

## 🧲 Semantic edges: best-match cosine, mutual top-k

Two topics can be about the same thing and share no papers -- a seed
topic that matched review articles and an emergent cluster of case
studies, say. Semantic edges catch that, and three decisions shape
them:

- **Average best-match, not centroid-to-centroid.** HDBSCAN clusters
  are non-convex, and a non-convex cluster's centroid can sit outside
  the cluster it summarises. Instead, each member of topic A is scored
  by its best cosine against B's members; the direction averages are
  symmetrised. At this corpus's scale (hundreds of documents, tens of
  topics) the exact computation costs nothing, so the approximation the
  centroid would be is all downside.
- **Mean-centred space**, the same space `topic_descriptors` uses and
  for the same measured reason: on a corpus that is all about one
  subject, every raw vector shares a large common component and cosines
  bunch together; centring removes it. The artefact stores
  `corpus_mean` so the G6 reader can move a query embedding into the
  same space without loading the embed cache.
- **Mutual top-k selection** (`[enrich].topic_graph_neighbors`): an
  edge survives only when each topic ranks the other within its top k.
  A global similarity floor either floods the dense region of the topic
  space or starves the sparse one; mutual k-NN adapts to both. And each
  edge carries `bridge` -- the single closest pair of papers across it
  -- so even semantic edges answer "show me why" with citekeys.

## 🌳 The hierarchy

An agglomerative merge tree over the topic centroids
(`scipy.cluster.hierarchy.linkage`, average linkage, cosine distance),
stored for the G9 tree view: which topics are siblings under a broader
theme. Not BERTopic's `hierarchical_topics()`, for two reasons: that
needs the fitted model object, which no stage persists -- re-fitting to
read a tree would repeat expensive work a derivation stage's contract
forbids -- and it covers emergent topics only, where a centroid exists
here for every topic, seed and emergent alike.

## 🚫 Alternatives considered

Recorded so each is not re-proposed as an oversight; the longer
versions are in `plans/g5-topic-discovery.md`.

| Rejected | Why |
| --- | --- |
| One fused topic-topic score | The two families answer different questions; merging destroys the disagreement signal |
| A weight floor on overlap edges | A per-corpus knob; the significance test needs none |
| Centroid-to-centroid semantic edges | Non-convex clusters; best-match respects shape at trivial cost |
| Soft-membership set similarity | The edge stops being explainable by naming papers |
| Earth-mover's distance between member sets | Cost and opacity with no added explanation, at this scale |
| UMAP-space distances | UMAP distorts global distances by design |
| Edges stored in the ledger | Derived corpus artefacts are JSON under `content/`; the CLI opens the ledger read-only on purpose |
| Abstractive topic summaries | The same failure class as a fabricated citekey; discovery output is extractive or it is not emitted |

## ▶ What lands next

G6 adds the reader (`corpus discover`): a resolution ladder from exact
label match through fuzzy matching and a rank-fused hybrid of BM25 and
centroid cosine, down to a clearly-labelled BM25 paper search; three
views (all topics, one topic with members and linked topics, one
paper's topics); `--json` throughout and an extractive Markdown
overview behind `--out`. G7 adds the cross-encoder precision tier and
personalised-PageRank neighbourhood ranking; G8 the gold-set benchmark;
G9 the self-contained HTML graph page. Each updates this document as it
lands.
