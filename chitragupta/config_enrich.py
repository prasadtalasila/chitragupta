"""The enrichment and discovery layers' own settings: `[enrich]` and
`[discover]`.

Split from `chitragupta/config.py` (#848), which re-exports every name
here, so each is still read as `config.NAME` -- one spelling across the
codebase, and `tests/conftest.py`'s `isolated_config` patches keep
working. What lives here is the knobs: model ids, cluster sizes,
thresholds, caps. The paths these stages write stay in `config.py`
beside every other path under `CONTENT_DIR`, because they are derived
from it.

Imports only `config_load`, never `config`, so there is no cycle and
this module can be imported before `config.py` finishes. `config.py`
reloads it when it is itself reloaded; see the comment there.

Nothing here needs the `enrich` extra installed: these are strings and
numbers, read under bare `python` like every other setting, and a stage
that needs a model loads it itself.
"""

from chitragupta.config_load import (
    _get,
    _get_bool,
    _get_float,
    _get_int,
    _get_optional_positive_int,
    _get_positive_int,
)

# Whether docling_parse.py also extracts figure bitmaps (into
# content/docling/<doc>_artifacts/) plus a <doc>.figures.json index of
# page/caption/citation for each. Changing this invalidates the whole
# Docling cache -- it changes what every .md should contain, so the next
# run re-parses the corpus from scratch. See DEVELOPER.md's "Figures".
DOCLING_IMAGES = _get_bool("DOCLING_IMAGES", "enrich", "docling_images", default=False)

# Render scale for those bitmaps; 2.0 is ~144 DPI, legible for reading a
# figure back while checking a draft without storing print-resolution PNGs.
#
# Not validated or clamped, and since #600 it no longer needs to be: a
# high scale costs CPU rather than RAM, because _docling_crops renders one
# crop at a time. At 6.0 the old path reached 74.31 GiB and then failed
# outright on docling_core's 20 MiB decoded-image guard; the same document
# now costs +0.06 GiB over the images-off base and 439s instead of 159s.
# docs/PERFORMANCE.md has the measurements.
DOCLING_IMAGE_SCALE = _get_float(
    "DOCLING_IMAGE_SCALE", "enrich", "docling_image_scale", default=2.0
)

# Whether the enrichment layer's Docling parse also runs the formula
# recognition model, so a paper's equations land in the .md and the
# passage sidecar as decoded LaTeX instead of `formula-not-decoded`
# markers (#627). Off by default for the same economics as OCR: an
# extra model download and an extra pass per page. Changing this
# invalidates the whole Docling cache, like DOCLING_IMAGES -- it changes
# what every .md and sidecar should contain.
DOCLING_FORMULAS = _get_bool("DOCLING_FORMULAS", "enrich", "docling_formulas", default=False)

# Cosine similarity a document must reach, against a seed phrase's own
# embedding, to be listed under it -- and the same floor BERTopic's
# zero-shot assignment uses, since both measure the same thing in the
# same space with the same model. One key rather than two because two
# would invite them to drift apart and mean nothing together.
#
# Note what this threshold is not: a gate. docs/HOUSE-STYLE.md's R3 keeps
# continuous scores out of pass/fail decisions, and nothing here fails a
# run, blocks a draft or refuses a citekey. It decides how long a list a
# human reads, and they can move it and look again.
#
# A floor, not the selection rule -- and the distinction is what the real
# corpus taught. Selection is per-phrase ranking (SEED_TOPIC_MAX_PAPERS
# below); this only discards matches too weak to be worth ranking at all.
#
# It governs the seed-topic report, and nothing else. It briefly also
# drove BERTopic's zero-shot assignment, which was wrong twice over: the
# two measure the same quantity but make different decisions, and the
# zero-shot path itself is gone -- seeds no longer steer the clustering at
# all, so an author can name any number of them without costing a single
# emergent topic. See chitragupta/enrich/topic_model.py.
#
# Measured over 497 real documents and 14 real Zotero collection names,
# every phrase turned out to have its own score scale, so no single
# absolute cutoff can serve them: "Standards" peaked at 0.295 across the
# whole corpus while "Digital Twin" had a *median* of 0.338. A 0.35 cutoff
# therefore returned nothing at all for a genuine 25-paper topic and 238
# papers for a broad one. Ranking each phrase against itself is immune to
# that; a floor is not, which is why the floor is now low enough to bite
# only on noise.
#
# 0.15 specifically: of four deliberately shelf-like collection names in
# that run, the two with no semantic content at all -- "Others" and a
# person's name, "Karen Wilcox" -- peaked at 0.143 and 0.112, so this
# keeps a seed that means nothing returning nothing rather than its 25
# nearest neighbours.
#
# Stated precisely because the looser claim is tempting and false: the
# other two ("Reviews and Surveys", "opinions") do clear this floor and do
# return papers. A shelf label that is *also* a description of a paper is
# not distinguishable from a topic by score, and this floor does not try
# to. Which names go in the list stays the author's decision, which is the
# answer docs/HOUSE-STYLE.md gives and not a gap in this number.
SEED_TOPIC_MIN_SIMILARITY = _get_float(
    "SEED_TOPIC_MIN_SIMILARITY",
    "enrich",
    "seed_topic_min_similarity",
    default=0.15,
)

# How many papers a single seed topic may list, best-scoring first. The
# actual selection rule: each phrase is ranked against its own scores, so
# a generic word and a domain term both yield a readable list instead of
# nothing and half the corpus respectively.
#
# 25 is a reading length, not an accuracy claim -- this artefact exists to
# be read by a person deciding what to draft, and a topic answering with
# 238 papers has told them nothing. Raise it when a topic is genuinely
# broad and you want the tail.
SEED_TOPIC_MAX_PAPERS = _get_int(
    "SEED_TOPIC_MAX_PAPERS",
    "enrich",
    "seed_topic_max_papers",
    default=25,
)

# How many extracted phrases survive the cap, most-declared first (ties
# alphabetical). 40 is the value this feature's own exploratory run used
# to produce the list that was read by hand and judged useful --
# bench/RESULTS.md's 2026-09-03c entry.
KEYWORD_TOP_N = _get_int("KEYWORD_TOP_N", "enrich", "keyword_top_n", default=40)

# The floor under a phrase's distinct-document count. 2 drops a phrase
# declared by only one paper -- one author's idiosyncratic term, not
# corpus vocabulary -- matching the same exploratory run.
KEYWORD_MIN_DF = _get_int("KEYWORD_MIN_DF", "enrich", "keyword_min_df", default=2)

# Whether the words a topic is *named* by exclude the corpus's own
# authors. Names, not clusters: this never touches how documents are
# grouped, only how the resulting group is described.
#
# On by default because the failure it fixes was severe and measured --
# `werner kritzinger, fraunhofer austria` was a top-three topic by
# membership, which is a person and an institution rather than a subject.
# It is not fixable by dropping bibliographies: `kritzinger` is in 101 of
# 497 documents and 55 still carry it after the reference list goes,
# because the papers are discussing his taxonomy in prose.
#
# The cost, measured rather than assumed: of 1,277 distinct surnames in
# this corpus's bibliography, five are also ordinary English words
# (black, brown, can, park, wood) and leave the label vocabulary too.
# Turn this off for a corpus where that trade is wrong.
TOPIC_EXCLUDE_AUTHOR_NAMES = _get_bool(
    "TOPIC_EXCLUDE_AUTHOR_NAMES",
    "enrich",
    "topic_exclude_author_names",
    default=True,
)

# How fine the emergent topic structure is. The two knobs that decide it,
# in config rather than hardcoded, because the right depth is a property
# of the corpus and its owner rather than of this code.
#
# Defaults chosen by sweeping this project's own 497-document corpus,
# where the previous hardcoded values (10 and unset) were not a tuning
# choice but a ceiling: every clustering parameter saturated at n_docs>=20,
# so a 497-paper corpus and a 5000-paper one both got the settings written
# for a 20-paper one. Measured, holding everything else fixed:
#
#     min_cluster_size=10   13 topics, 27% outliers, median 19 papers
#     min_cluster_size=5    25 topics, 19% outliers, median 13
#     min_cluster_size=3    50 topics, 12% outliers, median 6
#     =3 with min_samples=2 75 topics, 10% outliers, median 5
#
# Note the outlier rate *falls* as the topics get finer: the coarse
# setting was both under-clustering and discarding more of the corpus,
# which is why this is a defect being fixed rather than a preference.
#
# Still clamped down for a small corpus at the point of use -- UMAP's
# spectral initialisation genuinely fails when n_neighbors >= n_samples,
# which is what the original formula existed for. What it never did was
# scale *up*.
TOPIC_MIN_CLUSTER_SIZE = _get_int(
    "TOPIC_MIN_CLUSTER_SIZE",
    "enrich",
    "topic_min_cluster_size",
    default=3,
)

# HDBSCAN's own default is min_cluster_size; lowering it makes the
# clustering less conservative and leaves fewer documents as outliers.
TOPIC_MIN_SAMPLES = _get_int(
    "TOPIC_MIN_SAMPLES",
    "enrich",
    "topic_min_samples",
    default=2,
)

# UMAP's neighbourhood size, the other half of granularity: smaller reads
# more local structure and yields more, finer topics.
#
# 5, not the 10 it started at, and the third column is what decided it.
# `bench/bench_topic_depth.py --repeats` scores how well a setting
# reproduces under resampling (adjusted Rand index over the
# document-to-topic assignment), and on this corpus:
#
#     n_neighbors=15, min_cluster_size=10    5 topics, 12% outliers, 0.14
#     n_neighbors=10, min_cluster_size=10   16 topics, 28% outliers, 0.26
#     n_neighbors=10, min_cluster_size=3     76 topics, 17% outliers, 0.71
#     n_neighbors=5,  min_cluster_size=3     83 topics,  9% outliers, 0.80
#
# 5 is better on all three axes at once -- more topics, fewer documents
# discarded, and a partition that actually reproduces. The old hardcoded
# 15/10 pairing scoring 0.14 is the finding worth carrying: it was not
# merely coarse, it was barely repeatable, which no amount of reading its
# output would have revealed.
TOPIC_NEIGHBORS = _get_int(
    "TOPIC_NEIGHBORS",
    "enrich",
    "topic_neighbors",
    default=5,
)

# Whether the bertopic stage also records, per document, every topic it
# belongs to rather than only the one id fit_transform returns. That
# scalar cannot express a paper genuinely about two things: on 497 real
# documents, 140 belong to more than one topic and the scalar discards
# 222 memberships outright.
#
# Recorded from HDBSCAN's own soft clustering, which is the only
# mechanism of four measured that agrees with the clustering it is
# describing -- its assignment appears in the memberships it produces for
# 100% of documents and leads for 99%, against 30-45% for every
# centroid-distance rule. See chitragupta/enrich/topic_model.py.
#
# Recorded for every run since the zero-shot path was removed: BERTopic
# only swaps its clusterer for a placeholder in that mode, so there is
# always a real one to ask.
TOPIC_DISTRIBUTION = _get_bool(
    "TOPIC_DISTRIBUTION",
    "enrich",
    "topic_distribution",
    default=True,
)

# How strong a topic must be *relative to the document's own strongest*
# to be recorded under it, and how many may be kept at all.
#
# Relative, not an absolute weight, and for the second time in this
# feature the real corpus is what settled it. An absolute 0.05 floor
# recorded 6.99 topics per document out of 7 -- every paper under every
# topic, the dense matrix an absolute floor was supposed to prevent. The
# reason is the same one that broke a fixed cosine cutoff for seed
# phrases: the scale moves. Weights sum to about 1 across however many
# topics BERTopic found, so a fixed floor means something entirely
# different at 7 topics than at 70, and nothing at all at 200.
#
# A document's own strongest weight is the scale that travels. 0.5 keeps
# a genuine second topic -- on a planted two-topic document the winner
# took 0.570 and the real second 0.319, well over half -- while dropping
# the long tail of a document that is diffuse rather than plural.
TOPIC_MEMBERSHIP_RATIO = _get_float(
    "TOPIC_MEMBERSHIP_RATIO",
    "enrich",
    "topic_membership_ratio",
    default=0.5,
)

# The cap, for a document similar to almost everything: without one,
# "belongs to all 76 topics" is noise wearing the shape of an answer.
#
# 8, not the 3 it started at. 3 was chosen when this corpus produced 7
# topics and was plainly wrong once it produced 76: measured, 387 of 497
# documents sat at exactly 3, so the cap rather than the similarity was
# deciding what a paper is about, and the ratio never got to speak. At 8
# the ratio binds for most documents and the cap catches only the
# genuinely diffuse ones -- which is the division of labour the two
# settings are for.
TOPIC_MEMBERSHIP_MAX = _get_int(
    "TOPIC_MEMBERSHIP_MAX",
    "enrich",
    "topic_membership_max",
    default=8,
)

# How close an emergent topic's descriptor must sit to a seed phrase for
# that phrase to *name* it rather than sit beside it as a separate topic.
#
# Deliberately higher than the seed report's own floor. That floor decides
# which papers are worth listing under a phrase and is loose on purpose;
# this decides whether two topics are the same topic, and being wrong here
# merges things a reader expected to see apart. 0.45 measured on this
# corpus as the point where a phrase claims the cluster a human would
# agree it names, without reaching across to its neighbours.
TOPIC_CONVERGE_SIMILARITY = _get_float(
    "TOPIC_CONVERGE_SIMILARITY",
    "enrich",
    "topic_converge_similarity",
    default=0.45,
)

# How surprising a shared-member count must be for two topics to get an
# overlap edge. A significance level rather than a weight floor: "more
# shared papers than chance, given both sizes and the corpus size" needs
# no per-corpus tuning, where any fixed Jaccard cutoff does -- and it
# refuses the edge two large topics would otherwise get merely for both
# being large.
TOPIC_GRAPH_P_VALUE = _get_float(
    "TOPIC_GRAPH_P_VALUE",
    "enrich",
    "topic_graph_p_value",
    default=0.01,
)

# Semantic edges are kept only between mutual top-k neighbours. Mutual,
# because a global similarity floor either floods the dense region of
# the topic space or starves the sparse one; k-nearest adapts to both.
TOPIC_GRAPH_NEIGHBORS = _get_int(
    "TOPIC_GRAPH_NEIGHBORS",
    "enrich",
    "topic_graph_neighbors",
    default=5,
)

# How semantically close the best topic centroid must be before the
# discover ladder's hybrid rung claims a free phrase resolved to a topic
# rather than falling back to paper search. Gates only the semantic
# evidence -- a BM25 hit on the topic's own vocabulary is direct evidence
# regardless of geometry. 0.35 is a starting point, not a measurement;
# the G8 gold set is what will tune it, and recording that here is what
# stops the number acquiring false authority.
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

# The three numbers that size chitragupta/enrich/embed_index.py::search()'s
# stages. They are one setting in three parts and are easiest to read as
# the pipeline they describe -- docs/CORPUS-SEARCH.md draws it:
#
#   over-fetch k * MULTIPLIER  ->  [rerank]  ->  cap per citekey  ->  keep k
#
# so the pool the cap and the reranker both work from is
# EMBED_TOP_K * EMBED_OVERFETCH_MULTIPLIER, and the useful invariant is
# that the multiplier is what gives the cap something to promote *from*.
# At a multiplier of 1 the cap can only shorten the result, never
# improve it, which is the failure #305 existed to fix.

# How many passages search() returns when a caller does not say. A
# default, not a ceiling: every caller may still pass `k` explicitly,
# and the CLI's --k does.
EMBED_TOP_K = _get_positive_int("EMBED_TOP_K", "enrich", "embed_top_k", default=5)

# The most chunks search() will return from a single citekey, applied to
# the over-fetched ranked list before it is truncated to k -- see that
# function's docstring for why the ordering matters. 3 leaves room for a
# paper's chunks to still dominate a small k (e.g. k=5), while
# guaranteeing a second source a chance at the result once at least two
# papers are relevant. Lower it to 1 to force maximal source diversity.
EMBED_MAX_PASSAGES_PER_SOURCE = _get_positive_int(
    "EMBED_MAX_PASSAGES_PER_SOURCE",
    "enrich",
    "embed_max_passages_per_source",
    default=3,
)

# How much deeper than k search() asks Chroma for, so that dropping a
# dominant paper's excess chunks promotes another paper's chunk into the
# window rather than merely shortening the list. A multiple of k, not of
# the collection size: growing with the request keeps the fetch bounded
# by what was asked for rather than by corpus size, and Chroma returns
# min(n_results, chunk_count) rather than erroring when n_results
# exceeds what the collection holds (verified against chromadb 1.5.9),
# so there is no need to clamp against a count() call. Raising it is the
# lever for a correct paper that never enters the pool at all -- and the
# expensive one when reranking is on, since the reranker scores the
# whole pool.
EMBED_OVERFETCH_MULTIPLIER = _get_positive_int(
    "EMBED_OVERFETCH_MULTIPLIER",
    "enrich",
    "embed_overfetch_multiplier",
    default=4,
)

# Whether embed_index.search() reorders its over-fetched passages with a
# cross-encoder before the per-citekey cap is applied (#380). Off by
# default, and that is a measurement rather than caution:
# bench/bench_rerank_position.py found reranking leaves recall@5
# unchanged (156 of 256 either way, the correct paper lost 20x and
# gained 20x) and moves source diversity not at all, while
# bench/bench_rerank_cost.py found the cheapest candidate makes a search
# call 2.5x dearer on a GPU and 5.75x on a CPU. What it does buy is
# ordering: recall@3 rises from 129 to 139 of 256.
RERANK = _get_bool("RERANK", "enrich", "rerank", default=False)

# Which cross-encoder scores (query, passage) pairs when RERANK is on.
# Read only when it is. Unlike EMBEDDING_MODEL this takes a
# *cross-encoder* -- a model that scores the two texts jointly in one
# forward pass -- so the "query: "/"passage: " prefix warning that rules
# the bge-*/e5-* bi-encoders out of EMBEDDING_MODEL does not apply here:
# BAAI/bge-reranker-base is a sequence-classification cross-encoder and
# is a genuine drop-in. The default is the cheapest of the three
# candidates measured, which is also the one that won on nDCG@5; the
# candidate that won on recall cost 3.5-4.8x more for five extra correct
# answers in 256. See docs/CORPUS-SEARCH.md, "Choosing a reranker".
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

# How many premises `review support` scores per citation -- None (the
# default, and the shipped config.toml.example's value) meaning all of
# them, which is the behaviour every recorded score in
# docs/PERFORMANCE.md and bench/RESULTS.md was measured under.
#
# Uncapped by default because the cap was measured and found harmful,
# not because it is unproven. It buys what the arithmetic promised
# (#693: 725-887 pairs per citation, `support` ~97% of the nine-aid
# total on a dossier-less draft, cut 5.3-102x here) and it turns
# strongly-supported claims into top-of-agenda false alarms at every k
# from 8 to 128 -- bench/RESULTS.md's 2026-09-09 entry has the numbers
# and `claim_support._ranked` the reason. There is no recommended value.
SUPPORT_PREMISE_TOPK = _get_optional_positive_int(
    "SUPPORT_PREMISE_TOPK", "enrich", "support_premise_topk"
)
