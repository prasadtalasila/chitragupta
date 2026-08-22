"""How a document becomes one vector, and the cache that keeps it.

Split out of topic_model.py because it answers a different question:
everything here is *what a document is*, everything left there is *what
the corpus divides into*. Two consumers need the first without the
second -- topic_model.py clusters these vectors, topic_seeding.py scores
seed phrases against them -- and they must be the same vectors, or a
similarity in the seed report would not explain the topic assignment
printed beside it.

Needs the "enrich" Poetry group, like everything else in this package.
"""

import json
import re

from chitragupta import config
from chitragupta.enrich import embed_index
from chitragupta.enrich.corpus import CorpusDoc


def _load_embed_cache() -> dict:
    if config.TOPIC_EMBED_CACHE_PATH.exists():
        return json.loads(config.TOPIC_EMBED_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_embed_cache(cache: dict) -> None:
    config.TOPIC_EMBED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPIC_EMBED_CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def corpus_texts(docs: list[CorpusDoc]) -> dict:
    """Every doc that has text at all, by citekey. Docs with none are
    dropped rather than embedded as empty strings, which would cluster
    together on their emptiness and invent a topic out of missing PDFs."""
    doc_texts = {}
    for doc in docs:
        text = embed_index.get_text(doc)
        if text:
            doc_texts[doc.citekey] = text
    return doc_texts


# The headings that mean "the paper is over". Matched at the *last*
# occurrence, not the first: a paper's own related-work section may say
# "References" in prose, and an appendix can follow the bibliography.
BACK_MATTER = re.compile(
    r"(?im)^\s*#{1,6}\s*\**\s*(references|bibliography|works cited)\b")

# Lines that carry no topical content at whatever depth they appear:
# contact details, retrieval boilerplate, bare page numbers, and the
# running heads a PDF extractor repeats on every page.
NOISE_LINE = re.compile(
    r"(?im)^\s*(?:"
    r"\S+@\S+\.\S+"                       # an email address on its own
    r"|(?:https?://|www\.|doi:|10\.\d{4}/)\S*"   # a bare URL or DOI
    r"|(?:downloaded from|licensed under|all rights reserved|"
    r"copyright|\(c\)\s*\d{4}|©).*"
    r"|\d{1,4}"                             # a bare page number
    r")\s*$")


def content_text(text: str) -> str:
    """A document with its back matter and boilerplate removed.

    Preprocessing as a modelling step rather than a cleanup step, which is
    the first best practice in Asta's *Topic Extraction and Document-Topic
    Linking in Scientific and Domain-Specific Corpora*: "generic
    preprocessing is often too destructive... in-domain datasets contain
    abbreviations, identifiers, formulas, and rare phrases that carry most
    of the meaning". This therefore removes only what is provably not
    about the paper, and keeps every technical token -- no stop-word
    stripping, no lowercasing, no low-frequency filtering, all of which
    that survey warns destroy exactly the multiword domain terms a
    scientific corpus is discriminated by.

    **Why the reference list has to go.** It is a paper's densest block of
    *other people's* names and titles, so pooling it in makes two papers
    similar for citing the same work rather than for being about the same
    thing. Measured on this corpus before this function existed, the ninth
    largest topic was `werner kritzinger, fraunhofer austria` -- an author
    cluster, formed because those papers cite one famous digital-twin
    paper. A reference list is also large: a References heading is
    detectable in 451 of 497 documents (91%), and the text after it is a
    median 15% of the document and 26% at the 90th percentile.

    A document with no detectable heading keeps its whole text. That is
    the honest outcome for the remaining 9% rather than guessing at a
    boundary, and it degrades to today's behaviour rather than to
    something worse.
    """
    match = None
    for match in BACK_MATTER.finditer(text):
        pass  # the last one wins -- see BACK_MATTER
    if match is not None:
        text = text[:match.start()]
    return "\n".join(line for line in text.splitlines()
                      if not NOISE_LINE.match(line))


# Bumped when the arithmetic that turns a document into one vector
# changes, and stored beside every cached vector. Without it, switching
# from the old prefix embedding to pooling would keep serving prefix
# vectors for every unchanged document -- the text hash and the model id
# are both identical across that change, so neither notices it.
EMBED_METHOD = "chunk-mean-content-v2"


def pooled_embedding(text: str, model) -> list[float] | None:
    """One vector for a whole document: the mean of its chunk vectors.

    **Not `model.encode(text)`, and the difference is most of the
    document.** A sentence-transformer truncates at its own input limit --
    512 word pieces for the mpnet models -- and this corpus's documents
    run to 22,000-24,000 tokens, so encoding the raw text embedded
    **about 2% of each paper**: the chapter heading, the author list and
    the opening of the abstract. Topics were being formed largely from
    front matter, which is why they came out shallow and why author names
    and publisher boilerplate surfaced as topic terms.

    Koh et al., *An Empirical Survey on Long Document Summarization*
    (ACM Computing Surveys 55:8, 2022) measures why a prefix is the wrong
    2% specifically for documents like these. Its Finding 4 reports the
    layout bias that makes prefixes work for short documents -- roughly
    60% of salient sentences inside the first 30% -- as **absent** in long
    ones, where salient content is scattered: uniformity 0.89-0.93 for
    long-document benchmarks against 0.78-0.86 for short ones. A model
    that truncates therefore "suffers significant performance
    degradation" on long documents in that survey's words, and a
    scientific paper is squarely a long document.

    Chunked at `embed_index.chunk_text`'s own 200 words with 40 overlap
    rather than a second chunking of this module's own, so a document is
    split identically here and in the Chroma index -- docs/CODE-STANDARDS
    forbids the second way of doing something the codebase already does.

    Mean pooling, unweighted: chunks are near-uniform in length by
    construction, so a length weighting would be arithmetic with no effect
    to justify it.
    """
    import numpy as np

    chunks = embed_index.chunk_text(content_text(text))
    if not chunks:
        return None
    return np.asarray(model.encode(chunks, show_progress_bar=False)).mean(axis=0).tolist()


def document_embeddings(doc_texts: dict, model) -> dict:
    """One whole-document vector per citekey, re-encoding only what changed.

    Split out of run_topic_model() so chitragupta/enrich/topic_seeding.py
    can match seed phrases against the same vectors this stage clusters.
    That sharing is the point rather than a convenience: a phrase scored
    against one embedding of a document and clustered against another
    would be two different opinions about the same corpus, and the
    similarity numbers the report prints would not explain the topic
    assignments sitting beside them.

    See `pooled_embedding` for what "the document's vector" now means and
    for the measurement that changed it.
    """
    cache = _load_embed_cache()
    doc_hashes = {citekey: embed_index.hash_text(text) for citekey, text in doc_texts.items()}
    # Track which model produced each cached vector, not just the text hash
    # that produced it: swapping config.toml's embedding_model changes every
    # vector's dimensionality without changing any doc's text, and mixing
    # dimensions in the same `embeddings` array below breaks BERTopic outright.
    # EMBED_METHOD is the same argument for the pooling arithmetic, which
    # changes a vector while leaving both the text and the model id alone.
    stale_citekeys = [
        citekey for citekey in doc_texts
        if citekey not in cache
        or cache[citekey]["hash"] != doc_hashes[citekey]
        or cache[citekey].get("model") != config.EMBEDDING_MODEL
        or cache[citekey].get("method") != EMBED_METHOD
    ]
    for citekey in stale_citekeys:
        vector = pooled_embedding(doc_texts[citekey], model)
        if vector is None:
            continue
        cache[citekey] = {
            "hash": doc_hashes[citekey],
            "model": config.EMBEDDING_MODEL,
            "method": EMBED_METHOD,
            "embedding": vector,
        }
    if stale_citekeys:
        _save_embed_cache(cache)
    # A document whose text chunked to nothing has no vector and is
    # dropped rather than carried as a zero row, which would cluster with
    # every other empty document and invent a topic out of parse failures.
    return {citekey: cache[citekey]["embedding"]
            for citekey in doc_texts if citekey in cache}
