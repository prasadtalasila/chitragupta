"""Stage: match the run's seed phrases against the corpus -- the
author's own topic list unioned with the extracted keywords (#605;
chitragupta/enrich/stages.py owns the union).

Writes a many-to-many artefact: for each phrase, every citekey whose
document embedding reaches `config.SEED_TOPIC_MIN_SIMILARITY`, since a
library files papers under several collections and one topic per paper
throws that away. **A phrase is embedded whole** with `model.encode()`:
BERTopic's `seed_topic_list` tokenises on whitespace, so a multi-word
phrase fell apart into unrelated unigrams. `chitragupta/seed_topics.py`'s
`report()` reads the result (#192), and its `unmatched` list says which
papers the author's own list fails to describe. Uses the same model as
the documents, or the similarity means nothing.
"""

import json

from chitragupta import config
from chitragupta.enrich import doc_vectors, embed_index
from chitragupta.enrich.corpus import CorpusDoc


def cosine(left, right) -> float:
    """Cosine similarity of two vectors, as a plain float.

    Not `util.cos_sim`: vectors are plain lists from the cache, and a
    torch round trip would tie the stage to its serialisation.
    """
    import numpy as np

    left_vec = np.asarray(left, dtype=float)
    right_vec = np.asarray(right, dtype=float)
    denominator = float(np.linalg.norm(left_vec) * np.linalg.norm(right_vec))
    # Zero-norm: no direction, so 0.0 ("matches nothing") rather than
    # failing a whole corpus run.
    if denominator == 0.0:
        return 0.0
    return float(np.dot(left_vec, right_vec) / denominator)


def assign(
    doc_embeddings: dict,
    phrase_embeddings: dict,
    min_similarity: "float | None" = None,
    max_papers: "int | None" = None,
) -> dict:
    """The many-to-many map, as `content/topic_seeds.json`'s payload.

    **Each phrase is ranked against its own scores, then truncated**; the
    absolute floor is only a noise gate. Per-phrase score scales barely
    overlap (one real collection peaked at 0.295, another's median was
    0.338), so no global cutoff serves both. The floor keeps a meaningless
    seed (a stray name) from returning its nearest neighbours. Free of the
    model and corpus for hand-picked test vectors. Ties break on citekey,
    so the report doesn't shuffle between runs.
    """
    floor = config.SEED_TOPIC_MIN_SIMILARITY if min_similarity is None else min_similarity
    limit = config.SEED_TOPIC_MAX_PAPERS if max_papers is None else max_papers

    topics = []
    matched: set[str] = set()
    for phrase, phrase_vec in phrase_embeddings.items():
        scored = [
            {"citekey": citekey, "score": round(cosine(phrase_vec, doc_vec), 6)}
            for citekey, doc_vec in doc_embeddings.items()
        ]
        scored = [match for match in scored if match["score"] >= floor]
        scored.sort(key=lambda match: (-match["score"], match["citekey"]))
        matches = scored[:limit]
        matched.update(match["citekey"] for match in matches)
        # `considered` is what the floor left before the limit: "25 shown"
        # reads the same whether the 26th was close or absent.
        topics.append({"phrase": phrase, "considered": len(scored), "matches": matches})

    return {
        "model": config.EMBEDDING_MODEL,
        "min_similarity": floor,
        "max_papers": limit,
        "n_docs": len(doc_embeddings),
        "topics": topics,
        # Sorted so a person can compare one run with the next.
        "unmatched": sorted(set(doc_embeddings) - matched),
    }


def run_topic_seeding(docs: list[CorpusDoc], seed_phrases: tuple) -> dict:
    """Embed the seed phrases, score every document against each, write
    `content/topic_seeds.json`.

    Raises on an empty phrase list: an empty report looks like every
    phrase matched nothing, which calls for the opposite response.
    """
    if not seed_phrases:
        raise ValueError(
            f"No seed topics to match. Write {config.SEED_TOPICS_PATH} with a "
            "topics = [...] array of phrases first."
        )

    doc_texts = doc_vectors.corpus_texts(docs)
    if not doc_texts:
        raise ValueError("No documents with text to match seed topics against")

    _client, model = embed_index.get_client_and_model()
    doc_embeddings = doc_vectors.document_embeddings(doc_texts, model)

    # One encode() for all phrases, no cache: tens of short strings are
    # the cheap side.
    phrase_vecs = model.encode(list(seed_phrases), show_progress_bar=False)
    # .tolist() unguarded, as topic_model.py's cache-write assumes too.
    phrase_embeddings = {phrase: vec.tolist() for phrase, vec in zip(seed_phrases, phrase_vecs)}

    result = assign(doc_embeddings, phrase_embeddings)
    config.TOPIC_SEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPIC_SEEDS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_stage(docs: list[CorpusDoc], seed_phrases: tuple) -> dict:
    """`run_topic_seeding()` shaped as an enrichment-stage result.

    Shaping lives here, not stages.py (docs/TECHNICAL-DEBT.md, R14).
    `skipped`, not an error, for no phrases: most libraries have no seed
    file, and a clean run must not look broken.
    """
    if not seed_phrases:
        # Both sources by name (#605), so an empty keywords.toml isn't
        # blamed on the author's file.
        return {
            "status": "skipped",
            "detail": {
                "reason": f"no seed topics in {config.SEED_TOPICS_PATH} or {config.KEYWORDS_PATH}"
            },
        }
    result = run_topic_seeding(docs, seed_phrases)
    # Counts only: the papers live in content/topic_seeds.json.
    return {
        "status": "ok",
        "detail": {
            "n_docs": result["n_docs"],
            "matched": {topic["phrase"]: len(topic["matches"]) for topic in result["topics"]},
            "unmatched": len(result["unmatched"]),
        },
    }
