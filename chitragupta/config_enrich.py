"""The enrichment and discovery layers' own settings: `[enrich]` and
`[discover]`.

`chitragupta/config.py` re-exports every name here, so each is read as
`config.NAME` (#848). Imports only `config_load`, never `config`, so
there is no cycle. Nothing here needs the `enrich` extra installed.
"""

from chitragupta.config_load import (
    _get,
    _get_bool,
    _get_float,
    _get_int,
    _get_optional_positive_int,
    _get_positive_int,
)

# Also extract figure bitmaps and a <doc>.figures.json index. Changing it
# invalidates the whole Docling cache (DEVELOPER.md, "Figures").
DOCLING_IMAGES = _get_bool("DOCLING_IMAGES", "enrich", "docling_images", default=False)

# 2.0 is ~144 DPI. Not clamped: since #600 crops render one at a time, so
# a high scale costs CPU, not RAM (docs/PERFORMANCE.md).
DOCLING_IMAGE_SCALE = _get_float(
    "DOCLING_IMAGE_SCALE", "enrich", "docling_image_scale", default=2.0
)

# Decode equations to LaTeX instead of `formula-not-decoded` (#627). Off
# for the same economics as OCR; changing it invalidates the Docling cache.
DOCLING_FORMULAS = _get_bool("DOCLING_FORMULAS", "enrich", "docling_formulas", default=False)

# Cosine floor for listing a document under a seed phrase. Not a gate
# (docs/HOUSE-STYLE.md R3): it only discards matches too weak to rank;
# selection is per-phrase ranking (SEED_TOPIC_MAX_PAPERS), because every
# phrase has its own score scale and no absolute cutoff serves them all.
# 0.15 keeps meaningless seeds ("Others", a person's name: peaks 0.143,
# 0.112) returning nothing; it cannot tell a shelf label that also
# describes papers from a topic, and does not try to.
SEED_TOPIC_MIN_SIMILARITY = _get_float(
    "SEED_TOPIC_MIN_SIMILARITY",
    "enrich",
    "seed_topic_min_similarity",
    default=0.15,
)

# The actual selection rule, ranked per phrase. 25 is a reading length, not
# an accuracy claim.
SEED_TOPIC_MAX_PAPERS = _get_int(
    "SEED_TOPIC_MAX_PAPERS",
    "enrich",
    "seed_topic_max_papers",
    default=25,
)

# 40 is what the exploratory run read by hand and judged useful
# (bench/RESULTS.md 2026-09-03c).
KEYWORD_TOP_N = _get_int("KEYWORD_TOP_N", "enrich", "keyword_top_n", default=40)

# 2 drops one author's idiosyncratic term.
KEYWORD_MIN_DF = _get_int("KEYWORD_MIN_DF", "enrich", "keyword_min_df", default=2)

# Exclude the corpus's own authors from topic *names* (never from
# clustering). On because one author-and-affiliation string was a
# top-three topic, and dropping bibliographies does not fix it; the cost
# is five surnames that are also English words (black, brown, can, park,
# wood). Turn off where that trade is wrong.
TOPIC_EXCLUDE_AUTHOR_NAMES = _get_bool(
    "TOPIC_EXCLUDE_AUTHOR_NAMES",
    "enrich",
    "topic_exclude_author_names",
    default=True,
)

# Granularity, in config because the right depth is the corpus owner's.
# Defaults from sweeping a 497-document corpus; finer settings also cut
# the outlier rate (27% at 10, 12% at 3), so coarse was a defect, not a
# preference. Still clamped for a small corpus at the point of use: UMAP
# fails when n_neighbors >= n_samples.
TOPIC_MIN_CLUSTER_SIZE = _get_int(
    "TOPIC_MIN_CLUSTER_SIZE",
    "enrich",
    "topic_min_cluster_size",
    default=3,
)

# Lower than min_cluster_size leaves fewer documents as outliers.
TOPIC_MIN_SAMPLES = _get_int(
    "TOPIC_MIN_SAMPLES",
    "enrich",
    "topic_min_samples",
    default=2,
)

# UMAP neighbourhood size. 5 beats 10 and 15 on topics, outliers and
# reproducibility under resampling (ARI 0.80 vs 0.14 for the old 15/10;
# `bench/bench_topic_depth.py --repeats`).
TOPIC_NEIGHBORS = _get_int(
    "TOPIC_NEIGHBORS",
    "enrich",
    "topic_neighbors",
    default=5,
)

# Record every topic a document belongs to, not only fit_transform's one
# id: 140 of 497 documents belong to more than one. Measured as cosine to
# each topic's centroid; HDBSCAN soft clustering was rejected as nearly
# binary (`MEMBERSHIP_MECHANISM` in enrich/topic_model.py, docs/CONFIG.md).
TOPIC_DISTRIBUTION = _get_bool(
    "TOPIC_DISTRIBUTION",
    "enrich",
    "topic_distribution",
    default=True,
)

# Relative to the document's own strongest topic, not absolute: weights
# sum to ~1 across however many topics exist, so an absolute 0.05 floor
# kept nearly every paper under every topic. 0.5 keeps a genuine second
# topic (0.319 against 0.570 in a planted test).
TOPIC_MEMBERSHIP_RATIO = _get_float(
    "TOPIC_MEMBERSHIP_RATIO",
    "enrich",
    "topic_membership_ratio",
    default=0.5,
)

# 8, not 3: at 76 topics, 387 of 497 documents sat at a cap of 3, so the
# cap rather than the ratio decided membership.
TOPIC_MEMBERSHIP_MAX = _get_int(
    "TOPIC_MEMBERSHIP_MAX",
    "enrich",
    "topic_membership_max",
    default=8,
)

# Higher than the seed report's floor on purpose: being wrong here merges
# topics a reader expected apart. 0.45 measured on this corpus.
TOPIC_CONVERGE_SIMILARITY = _get_float(
    "TOPIC_CONVERGE_SIMILARITY",
    "enrich",
    "topic_converge_similarity",
    default=0.45,
)

# A significance level, not a Jaccard cutoff: needs no per-corpus tuning
# and refuses edges two large topics would get merely for being large.
TOPIC_GRAPH_P_VALUE = _get_float(
    "TOPIC_GRAPH_P_VALUE",
    "enrich",
    "topic_graph_p_value",
    default=0.01,
)

# Mutual top-k: a global floor floods dense regions or starves sparse ones.
TOPIC_GRAPH_NEIGHBORS = _get_int(
    "TOPIC_GRAPH_NEIGHBORS",
    "enrich",
    "topic_graph_neighbors",
    default=5,
)

# Gates only semantic evidence for the discover ladder's hybrid rung. 0.35
# is a starting point, not a measurement; the G8 gold set will tune it.
DISCOVER_MIN_SIMILARITY = _get_float(
    "DISCOVER_MIN_SIMILARITY",
    "discover",
    "min_similarity",
    default=0.35,
)

EMBEDDING_MODEL = _get(
    "EMBEDDING_MODEL",
    "enrich",
    "embedding_model",
    default="sentence-transformers/all-MiniLM-L6-v2",
)

# Search pipeline sizes (docs/CORPUS-SEARCH.md):
#   over-fetch k * MULTIPLIER  ->  [rerank]  ->  cap per citekey  ->  keep k
# A multiplier of 1 leaves the cap nothing to promote from (#305).

# A default, not a ceiling: callers and --k may pass `k`.
EMBED_TOP_K = _get_positive_int("EMBED_TOP_K", "enrich", "embed_top_k", default=5)

# 3 lets one paper still dominate a small k while giving a second source a
# chance; 1 forces maximal diversity.
EMBED_MAX_PASSAGES_PER_SOURCE = _get_positive_int(
    "EMBED_MAX_PASSAGES_PER_SOURCE",
    "enrich",
    "embed_max_passages_per_source",
    default=3,
)

# A multiple of k, not of collection size, so the fetch stays bounded;
# Chroma clamps n_results itself (chromadb 1.5.9). The lever for a paper
# that never enters the pool, and costly when reranking scores the pool.
EMBED_OVERFETCH_MULTIPLIER = _get_positive_int(
    "EMBED_OVERFETCH_MULTIPLIER",
    "enrich",
    "embed_overfetch_multiplier",
    default=4,
)

# Off by measurement (#380): recall@5 unchanged (156/256) at 2.5x GPU and
# 5.75x CPU cost; it only improves ordering (recall@3 129 -> 139).
RERANK = _get_bool("RERANK", "enrich", "rerank", default=False)

# A cross-encoder, so the bi-encoder prefix warning on EMBEDDING_MODEL does
# not apply. Cheapest of three measured and best on nDCG@5
# (docs/CORPUS-SEARCH.md, "Choosing a reranker").
RERANK_MODEL = _get(
    "RERANK_MODEL",
    "enrich",
    "rerank_model",
    default="cross-encoder/ms-marco-MiniLM-L6-v2",
)

ENTAILMENT_MODEL = _get(
    "ENTAILMENT_MODEL",
    "enrich",
    "entailment_model",
    default="cross-encoder/nli-deberta-v3-small",
)

# None means every premise, which every recorded score was measured under.
# Uncapped because a cap was measured harmful: it turns well-supported
# claims into false alarms at every k from 8 to 128 (#693;
# bench/RESULTS.md 2026-09-09, `claim_support._ranked`). No recommended value.
SUPPORT_PREMISE_TOPK = _get_optional_positive_int(
    "SUPPORT_PREMISE_TOPK", "enrich", "support_premise_topk"
)
