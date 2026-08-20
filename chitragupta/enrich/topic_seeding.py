"""Stage 5: match the author's own topic phrases against the corpus.

The other half of seeding, and the half that keeps the relation the
author actually asserted. `topic_model.py` runs BERTopic, which returns
one topic id per document; a Zotero library does not work that way. In
this project's own corpus 637 of 642 papers carry collection labels
across 95 collections, and a paper on digital twins in manufacturing sits
under both -- so the moment a seed list is derived from those labels, an
artefact that permits one topic per paper is throwing away the thing the
labels were consulted for.

So this stage writes a many-to-many artefact: for each seed phrase,
every citekey whose document embedding reaches
`config.SEED_TOPIC_MIN_SIMILARITY` against that phrase's own embedding,
with its score. One paper appears under as many phrases as it clears,
none, or all of them.

**A phrase is embedded whole.** That is the entire reason this stage
exists in the shape it does. BERTopic's older `seed_topic_list` steers
topics by matching seed terms against a `CountVectorizer`'s vocabulary,
which tokenises on whitespace -- so "structural health monitoring" enters
as three unrelated unigrams that individually mean something else
("monitoring" matches every paper with a monitoring section). Passing the
phrase to `model.encode()` instead produces one vector for the phrase as
written: self-attention runs over the whole string and pooling collapses
it, so the multi-word phrase is one point in the same space the documents
live in, and there is no tokenisation boundary for it to fall apart at.

This is also #192's missing reader. `content/topics.json` has had no
consumer since it was written -- the topic model produced clusters and
nothing looked at them. `content/topic_seeds.json` is written to be
looked at: `chitragupta/seed_topics.py`'s `report()` prints it without
the venv, and its `unmatched` list is the question an author planning a
draft actually has, which is not "what did the clustering find" but
"which of my papers does my own topic list fail to describe".

Needs the "enrich" Poetry group, like every other stage here: it calls
the same sentence-transformers model `embed_index.py` and
`topic_model.py` do, deliberately, since a similarity computed against a
different model than the one that embedded the documents is not a
similarity at all.
"""

import json

from chitragupta import config
from chitragupta.enrich import embed_index, topic_model
from chitragupta.enrich.corpus import CorpusDoc


def cosine(left, right) -> float:
    """Cosine similarity of two vectors, as a plain float.

    Written out rather than pulled from sentence-transformers' own
    `util.cos_sim`: this module already holds every vector as a list of
    floats (that is what the embedding cache stores), and going through a
    torch tensor to get one number back would make the whole stage depend
    on how the cache happens to be serialised.
    """
    import numpy as np

    left_vec = np.asarray(left, dtype=float)
    right_vec = np.asarray(right, dtype=float)
    denominator = float(np.linalg.norm(left_vec) * np.linalg.norm(right_vec))
    # A zero-norm vector has no direction, so no angle to any other
    # vector. 0.0 keeps it below every threshold rather than raising:
    # it means "this matches nothing", which is the truth about a
    # document whose embedding degenerated, and is not worth failing a
    # whole corpus run over.
    if denominator == 0.0:
        return 0.0
    return float(np.dot(left_vec, right_vec) / denominator)


def assign(doc_embeddings: dict, phrase_embeddings: dict,
           min_similarity: "float | None" = None) -> dict:
    """The many-to-many map, as `content/topic_seeds.json`'s payload.

    Kept free of both the model and the corpus so it can be tested
    against vectors chosen by hand: everything above it decides what to
    embed, everything below it is arithmetic on the result.

    Matches are sorted by descending score, so the first paper under a
    phrase is the one that phrase describes best. Ties break on citekey,
    because Python's sort is stable and dict order is insertion order --
    without the second key, two papers with identical scores would swap
    places between runs depending on what order the ledger happened to
    return them in, and a report that shuffles is a report nobody trusts.
    """
    floor = config.SEED_TOPIC_MIN_SIMILARITY if min_similarity is None else min_similarity

    topics = []
    matched: set[str] = set()
    for phrase, phrase_vec in phrase_embeddings.items():
        matches = []
        for citekey, doc_vec in doc_embeddings.items():
            score = cosine(phrase_vec, doc_vec)
            if score >= floor:
                matches.append({"citekey": citekey, "score": round(score, 6)})
                matched.add(citekey)
        matches.sort(key=lambda match: (-match["score"], match["citekey"]))
        topics.append({"phrase": phrase, "matches": matches})

    return {
        "model": config.EMBEDDING_MODEL,
        "min_similarity": floor,
        "n_docs": len(doc_embeddings),
        "topics": topics,
        # Sorted for the same reason the matches are: this list is read
        # by a person comparing one run against the next to see whether a
        # phrase they just added covered what they meant it to.
        "unmatched": sorted(set(doc_embeddings) - matched),
    }


def run_topic_seeding(docs: list[CorpusDoc], seed_phrases: tuple) -> dict:
    """Embed the seed phrases, score every document against each, write
    `content/topic_seeds.json`.

    Raises on an empty phrase list rather than writing an artefact with
    no topics in it: an empty report is indistinguishable from a report
    whose every phrase matched nothing, and the two call for opposite
    responses from the author. The caller in
    `chitragupta/enrich/__main__.py` skips this stage outright when there
    is no seed file, which is the case this refuses to paper over.
    """
    if not seed_phrases:
        raise ValueError(
            f"No seed topics to match. Write {config.SEED_TOPICS_PATH} with a "
            "topics = [...] array of phrases first."
        )

    doc_texts = topic_model.corpus_texts(docs)
    if not doc_texts:
        raise ValueError("No documents with text to match seed topics against")

    _client, model = embed_index.get_client_and_model()
    doc_embeddings = topic_model.document_embeddings(doc_texts, model)

    # One encode() call for every phrase rather than one per phrase, and
    # no cache: a seed list is tens of short strings against a corpus of
    # hundreds of full documents, so this is the cheap side of the stage
    # by orders of magnitude and a cache would be more code than it saves.
    phrase_vecs = model.encode(list(seed_phrases), show_progress_bar=False)
    # .tolist() unguarded, the same assumption topic_model.py's own
    # cache-write makes of the same call: sentence-transformers returns
    # numpy rows, and a fallback for a shape this seam never receives
    # would be untestable except by faking the model into producing it.
    phrase_embeddings = {phrase: vec.tolist()
                         for phrase, vec in zip(seed_phrases, phrase_vecs)}

    result = assign(doc_embeddings, phrase_embeddings)
    config.TOPIC_SEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPIC_SEEDS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_stage(docs: list[CorpusDoc], seed_phrases: tuple) -> dict:
    """`run_topic_seeding()` shaped as an enrichment-stage result.

    The status vocabulary lives here rather than in
    chitragupta/enrich/__main__.py, where the other three stages shape
    their own: that module sits four code lines under docs/CODE-STANDARDS.md's
    250-line ceiling with three stages, so a fourth cannot be spelled out
    there without pushing the orchestrator past a boundary this feature
    has no business moving. The wrapper it keeps is two lines.

    `skipped` rather than an error for an empty phrase list, because that
    is the ordinary state of this stage: most libraries have no seed
    file, the same way most have no Zotero collections (docs/ZOTERO.md),
    and a clean run must not look broken. It is the same status the
    docling stage reports for a binary that is not installed.
    """
    if not seed_phrases:
        return {"status": "skipped",
                "detail": {"reason": f"no seed topics in {config.SEED_TOPICS_PATH}"}}
    result = run_topic_seeding(docs, seed_phrases)
    # Counts, not the matches: this is the one-line-per-stage run report,
    # and content/topic_seeds.json is where the papers themselves live.
    return {"status": "ok",
            "detail": {"n_docs": result["n_docs"],
                       "matched": {topic["phrase"]: len(topic["matches"])
                                   for topic in result["topics"]},
                       "unmatched": len(result["unmatched"])}}
