# 🧠 Topic modelling: what the literature said, and what this corpus said back

Status: **discussion, not a specification.** Written 2026-08-21. Updated
2026-08-23. It records where the topic
stage's current shape came from -- which published findings argued for
it, which measurements on this project's own corpus confirmed or
contradicted them, and which decisions are still open. `docs/CONFIG.md`
is the reference for the settings themselves;
[TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md) covers what happens after the
model runs -- the topic graph and the discovery feature reading it.
The discovery half borrows from a different set of sources than the
modelling half below (OpenScholar's retrieval cascade, MiniRAG's
heterogeneous graph, Reciprocal Rank Fusion, FlashRAG's extractive
refiner, legacy AutoRAG's gold-set methodology); those are quoted where
each mechanism is described in TOPIC-DISCOVERY.md and itemised --
borrowings and refusals both -- in
[INSPIRATION.md](INSPIRATION.md#-topic-discovery), so this document's
own reference list stays what it was: the evidence behind the *model*.

> **On the references below.** The four sources here are *not* in
> `content/ledger.sqlite` and therefore have no citekeys, so they are
> cited in full at the end and by author-year in the text. That is
> deliberate and it is the rule from [AGENTS.md](../AGENTS.md): a citekey
> exists only when the human's own `.bib` export and a real parse of a
> real PDF put it in the ledger. Inventing one here -- in a document that
> ships, for sources that are genuinely real -- is exactly the habit this
> project exists to make impossible. If these papers are later added to a
> library and synced, this document should be updated to cite them
> properly rather than left as prose.

## ❗ The problem, in one sentence

`content/topics.json` existed for several releases with no consumer
([#192](https://github.com/prasadtalasila/chitragupta/issues/192)), and
the topic model had no way to know that the corpus's owner had already
grouped the same papers by hand in Zotero
([#206](https://github.com/prasadtalasila/chitragupta/issues/206)).

## 📚 What the sources argued, and what happened when it was tried

### 🌱 1. Seed the model, but do not let seeding replace discovery

Asta's *Topic Extraction and Document-Topic Linking in Scientific and
Domain-Specific Corpora* is unambiguous that a narrow corpus wants
guidance: fully unsupervised models "often produce overlapping or vague
topics unless they are anchored by concepts, seed words, or expert
knowledge", and seed-guided models are "useful when you have partial
prior knowledge and still want the model to discover unknown topics
rather than only match a fixed taxonomy". It notes in passing that keyATM
"allows each document to belong to multiple keyword topics".

That is the design this stage now has, but the *first* implementation got
it wrong in a way the survey's phrasing predicts. Routing seed phrases
through BERTopic's `zeroshot_topic_list` makes seeding and discovery
compete for the same documents: measured on this corpus, nine seed
phrases took the emergent topic count from **81 to 53**, roughly three
discovered topics traded away per named one. Pushed further it stops
trading and breaks -- enough zero-shot assignment leaves HDBSCAN fewer
points than its own `min_samples` needs and the fit dies inside sklearn.

**Resolution:** seeds never touch the clustering. They are matched
against the same document vectors afterwards. A seed list is therefore
unlimited and costs nothing, which is the property the survey asks for
and the zero-shot path could not give.

### 🧹 2. Preprocessing is a modelling step, not a cleanup step

Asta's first best practice for narrow scientific domains, and its warning
is specific: "generic preprocessing is often too destructive", because
in-domain corpora carry "abbreviations, identifiers, formulas, and rare
phrases" that hold most of the meaning. It cites industrial work
(Nikulski et al., 2025) reporting a 22% gain from domain preprocessing
plus a domain-adapted encoder, and stresses that preprocessing is "a
complex, high-effort part of the system, not a trivial step".

`doc_vectors.content_text()` follows that literally. It removes the
reference list, bare emails, URLs, DOIs, copyright lines and page
numbers, and **nothing else** -- no stop-word removal, no lowercasing, no
low-frequency filtering, each of which would destroy exactly the
multiword domain terms this corpus is discriminated by. A test asserts
`IEC 62304`, `MQTT v5` and `DTaaS` survive untouched.

**What it fixed, measured:** a `References` heading is detectable in 451
of 497 documents (91%); the text after it is a median 15% of the
document. Two artefact clusters left the top twenty --
`www nature, program officer, national academies` and `a116, a115, a114`.

**What it did not fix, and this is the interesting part.** The author
cluster survived. `werner kritzinger, fraunhofer austria` was still a
top-three topic afterwards, because the name is in the *body*, not the
bibliography: `kritzinger` appears in 101 documents and **55 still
contain it after the reference list is removed**. Those papers genuinely
are a topic -- they survey the digital-twin/shadow/model taxonomy -- so
the clustering is right and only the *label* is wrong. No amount of
further preprocessing fixes that without deleting content that belongs to
the topic. It is a labelling problem, and §3 is its answer.

### 🏷 3. Label topics from recognised domain terms -- [#297](https://github.com/prasadtalasila/chitragupta/issues/297)

Asta's third best practice: "use domain term recognition as a backbone
for both topics and labels", citing TLATR (Truica et al., 2021), which
extracts domain-specific terms first and then chooses each topic's label
from the recognised terms by C-Value scoring, and Silvello et al. (2016),
which ranks candidates by both corpus-level and document-level TF-IDF.

**Built**, in [#303](https://github.com/prasadtalasila/chitragupta/pull/303) --
`chitragupta/enrich/topic_labels.py`. It fixed two things at once: the
author-name labels above, and BERTopic's own topic names, which on this
corpus were stopwords (`0_the_and_of_to`) because no
`CountVectorizer(stop_words=...)` was configured. A person's name is not
a domain term and is excluded by construction: every surname in the
corpus's own bibliography (1,277 of them) is dropped from the label
vocabulary, behind `[enrich].topic_exclude_author_names` for a corpus
where that trade is not worth it.

### 📄 4. A prefix is the wrong part of a long document

Koh et al. (2022) measure the layout bias that makes truncation
tolerable for short documents -- roughly 60% of salient sentences in the
first 30% -- and find it **absent** in long ones, where salient content
is scattered: uniformity 0.89-0.93 for long-document benchmarks against
0.78-0.86 for short. Models that truncate "suffer significant
performance degradation" there.

This corpus is squarely long-document: measured, two representative
papers run to 22,048 and 24,132 tokens against a 512 word-piece model
limit, so `model.encode(text)` was embedding **about 2%** of each paper --
its chapter heading, author list and abstract opening. Documents are now
chunked with `embed_index.chunk_text()` and the chunk vectors mean-pooled.

**Measured effect:** at identical clustering settings, 75 topics with
median size 5 (prefix) against 81 with median 4 (pooled), and labels that
stop being front matter -- `californium, coap, mqtt v5, sparkplug`
separating from `mbdo, twinops, moddevops, aadl` from `gitops, dataops,
iec 62304`. The cost is a higher outlier share (10% to 17%), which is
expected: averaging 82 chunks pulls every vector toward the corpus
centroid and reduces separation.

### 🔭 5. Multi-document summarisation is the shape of a topic

Ma et al. (2022) define multi-document summarisation as generating a
summary "from a cluster of topic-related documents", and name
cross-document redundancy as its defining problem. That is exactly the
shape of a topic here, which makes per-topic summarisation the natural
consumer for this artefact -- and `chitragupta/overlap_index.py` already
computes shared n-grams corpus-wide, so the redundancy detector exists.

One constraint from Koh et al. bears directly on it and is a
[SOUL.md](../SOUL.md) argument rather than a quality one: abstractive
models carry factual inconsistencies in up to 30% of outputs, while
extractive summarisation "will faithfully preserve the original
content". A topic summary asserting a claim no paper made is the same
failure class as a fabricated citekey, one level up. **Extractive first;
abstractive only behind a human accept-gate, if at all.**

### 🏗 6. Structural labels would let content be selected, if they existed

DocBank (Li et al., 2020) annotates 500,000 document pages at token level
with twelve semantic labels -- Abstract, Author, Caption, Date, Equation,
Figure, Footer, List, Paragraph, Reference, Section, Table -- built by
weak supervision over arXiv LaTeX, with a LayoutLM baseline at 0.935
macro-average, under Apache-2.0.

That taxonomy is the vocabulary §2 needed and could not express, because
Docling emits only three labels on this corpus: `text` (77% of
characters), `list_item` (21%) and `section_header` (2%). References,
captions, equations and author blocks are one undifferentiated category,
which is why `content_text()` has to find the bibliography by *heading
regex* rather than by label. Adopting DocBank-grade structure means a
LayoutLM-class model and Detectron2 -- a real dependency and its own
piece of work, not a configuration change.

**This was filed as [#301](https://github.com/prasadtalasila/chitragupta/issues/301)
and is now closed as not planned**, because §3 removed the evidence for
it. The artefact clusters that motivated it -- an author block, a
publisher's front matter, a run of clause numbers -- all left the top
twenty once topic *labels* stopped being drawn from author names and
citation scaffolding, and that cost no new dependency at all. What
survives is a DOI fragment and a broken `fi` ligature, and the ligature
is a text-extraction defect rather than a layout one: it corrupts
`identification` and `classification` into `identi fi cation`, which
damages the clustering input and not merely the display. DocBank would
not touch it.

If structural extraction is wanted later, the better starting point is
[GROBID-CITATION-GRAPH.md](GROBID-CITATION-GRAPH.md) rather than that
issue. GROBID is purpose-built for the two spans `content_text()` finds
by heading regex -- the author/affiliation block and the reference list
-- returns them as structured records at roughly 0.87-0.90 F1 rather than
as a class label per token, and does sequence labelling rather than
layout inference, so it costs a fraction of a Docling parse per document.
That proposal is itself unbuilt and argues a case for a *citation graph*,
with structural extraction a by-product; it is the document to start
from, not a queued piece of work.

### ✅ 7. Validate stability, not just fit -- [#300](https://github.com/prasadtalasila/chitragupta/issues/300)

Asta again: hyperparameter choice in this family is usually driven by
coherence alone, but "a model that looks good once can still be unstable
across runs or topic counts", so good evaluation combines coherence with
topic diversity, stability, and whether experts can name the topics. It
cites work using repeated resampling and model selection (Yengejeh et
al., 2026, which lands on 83-88 topics for 3,689 forensic-science
abstracts).

**Built**, in [#304](https://github.com/prasadtalasila/chitragupta/pull/304) --
`bench/bench_topic_depth.py --repeats` refits each setting on 90%
bootstrap resamples and scores agreement with the full fit by adjusted
Rand index. The old hardcoded defaults (`n_neighbors=15`,
`min_cluster_size=10`) scored **0.14** -- barely more stable than
chance; the shipped defaults (`5`/`3`/`2`) score **0.80**.
`chitragupta/enrich/topic_model.py`'s own docstring still admits topic
ids are not stable *between* runs -- membership has to be read by label
or citekey, not id -- but which *settings* reproduce is now measured
rather than assumed.

## 📊 Where the numbers come from

- `bench/bench_topic_depth.py` -- the granularity sweep behind
  `topic_min_cluster_size` and its siblings.
- `bench/bench_topic_membership.py` -- the five-mechanism comparison
  behind HDBSCAN soft clustering.

  **A correction worth carrying, because it bit twice.** An early version
  of this comparison scored HDBSCAN's own soft clustering at 1%
  agreement, which is nonsense: it indexed HDBSCAN's *cluster* ids with
  BERTopic's *topic* ids, and BERTopic renumbers topics by size (cluster
  0 was topic 6 on the run this was written against). Separately, an
  earlier ad-hoc measurement reported centroid rules agreeing only 30-45%
  of the time -- true at 7 topics on a seeded run, and **not** true at 76,
  where every non-degenerate mechanism agrees 100%. Agreement discriminates
  in the first regime and not the second; concentration does both. Quote
  the committed script's numbers, not either of those.

Both are recorded in `bench/RESULTS.md`. Every
figure quoted above is from this project's own 497-document corpus on one
host, which is one corpus and one host -- the same limitation every
section of `bench/RESULTS.md` carries.

## 📖 References

These are cited in full because none is in the ledger; see the note at
the top.

- Koh, H. Y., Ju, J., Liu, M., and Pan, S. (2022). *An Empirical Survey
  on Long Document Summarization: Datasets, Models, and Metrics.* ACM
  Computing Surveys 55(8), Article 154. <https://doi.org/10.1145/3545176>
- Ma, C., Zhang, W. E., Guo, M., Wang, H., and Sheng, Q. Z. (2022).
  *Multi-document Summarization via Deep Learning Techniques: A Survey.*
  ACM Computing Surveys 55(5), Article 102.
  <https://doi.org/10.1145/3529754>
- Asta (Allen Institute for AI). *Topic Extraction and Document-Topic
  Linking in Scientific and Domain-Specific Corpora.* Generated research
  synthesis, supplied 2026-08-21. Not a peer-reviewed publication; the
  primary sources it cites and which are named above -- Nikulski et al.
  (2025), Truica et al. (2021), Silvello et al. (2016), Yengejeh et al.
  (2026) -- are reported at second hand and have not been read directly.
- DocBank. Li, M., Xu, Y., Cui, L., Huang, S., Wei, F., Li, Z., and Zhou,
  M. (2020). *DocBank: A Benchmark Dataset for Document Layout Analysis.*
  <https://github.com/doc-analysis/DocBank>, Apache-2.0.
