"""Stage 6: one topic set, from the phrases you wrote and the topics the
corpus turned out to have.

`content/topic_set.json` joins `content/topic_seeds.json` (seed phrases,
deliberately kept out of clustering) and `content/topics.json` (emergent
topics). A topic here has one shape whatever it came from::

    {"label": ..., "provenance": "seed" | "emergent",
     "topic_id": ... | None, "members": [{"citekey": ..., "score": ...}]}

**Convergence is the human's name winning**: an emergent topic within
`config.TOPIC_CONVERGE_SIMILARITY` of a seed is renamed by it. Several
seeds on one topic: the closest wins, ties on phrase text. Several topics
on one seed: only the closest takes the name, since letting all of them
produced eight indistinguishable topics of one name. A seed matching no
topic still appears with `topic_id: None`: the corpus doesn't separate it.

**This stage re-runs nothing**: it recomputes only the descriptors from
cached vectors, so the two halves cannot drift.
"""

import json

from chitragupta import config, seed_topics
from chitragupta.enrich import doc_vectors, embed_index, topic_model, topic_seeding


def converge(descriptors: dict, seed_vectors: dict, min_similarity: "float | None" = None) -> dict:
    """`{emergent_topic_id: seed_phrase}` for every topic a seed names.

    Free of the corpus and the model, so tests can use hand-picked vectors.
    """
    floor = config.TOPIC_CONVERGE_SIMILARITY if min_similarity is None else min_similarity
    # Sorting all pairs, best first, lets each phrase be claimed once.
    candidates = sorted(
        (
            (topic_seeding.cosine(descriptor, vector), phrase, topic_id)
            for topic_id, descriptor in descriptors.items()
            for phrase, vector in seed_vectors.items()
        ),
        key=lambda triple: (-triple[0], triple[1], triple[2]),
    )

    named, spoken_for = {}, set()
    for score, phrase, topic_id in candidates:
        if score < floor or phrase in spoken_for or topic_id in named:
            continue
        named[topic_id] = phrase
        spoken_for.add(phrase)
    return named


def build(memberships: dict, citekeys: list, named: dict, seed_report: dict) -> dict:
    """The converged set: every topic, however it was found, in one shape.

    Uses `memberships`, so a paper appears under every topic it is about.
    """
    topics = []
    for topic_id in sorted({int(t) for row in memberships.values() for t in row}):
        members = sorted(
            (
                {"citekey": citekey, "score": row[str(topic_id)]}
                for citekey, row in memberships.items()
                if str(topic_id) in row
            ),
            key=lambda member: (-member["score"], member["citekey"]),
        )
        phrase = named.get(topic_id)
        topics.append(
            {
                "label": phrase or f"topic-{topic_id}",
                "provenance": "seed" if phrase else "emergent",
                "topic_id": topic_id,
                "members": members,
            }
        )

    for entry in seed_report.get("topics", []):
        if entry["phrase"] in set(named.values()):
            continue
        topics.append(
            {
                "label": entry["phrase"],
                "provenance": "seed",
                "topic_id": None,
                "members": [dict(match) for match in entry["matches"]],
            }
        )

    covered = {member["citekey"] for topic in topics for member in topic["members"]}
    return {
        "model": config.EMBEDDING_MODEL,
        # Stamped so the graph stage can refuse a mismatched space; the
        # model alone doesn't identify it when pooling changes (#557).
        "embedding_method": doc_vectors.EMBED_METHOD,
        "converge_similarity": config.TOPIC_CONVERGE_SIMILARITY,
        "n_docs": len(citekeys),
        "n_seed_named": sum(1 for t in topics if t["provenance"] == "seed"),
        "n_emergent": sum(1 for t in topics if t["provenance"] == "emergent"),
        "topics": topics,
        # The papers no topic covers: what an author planning a draft wants.
        "uncovered": sorted(set(citekeys) - covered),
    }


def _memberships_of(found: dict) -> "tuple[dict, str]":
    """`topics.json`'s many-to-many view, or a single-membership stand-in
    for it, plus which of the two this is.

    `memberships` is `None` with `[topics].topic_distribution` off, which
    made every paper look uncovered (#509/m-43). `assignments` is used
    instead and named via `membership_source`; the outlier topic (-1) is
    left out, as in `topic_descriptors`.
    """
    memberships = found.get("memberships")
    if memberships:
        return memberships, "memberships"
    synthesised = {
        citekey: {str(topic_id): 1.0}
        for citekey, topic_id in (found.get("assignments") or {}).items()
        if int(topic_id) >= 0
    }
    return synthesised, "assignments"


def run_topic_converge(docs, seed_phrases: tuple) -> dict:
    """Join the two topic artefacts and write `content/topic_set.json`.

    Raises when `content/topics.json` is absent: this stage re-runs nothing.
    """
    if not config.TOPICS_PATH.exists():
        raise ValueError(
            f"No {config.TOPICS_PATH} to converge. Run the bertopic stage first; "
            "this stage joins what the others found and computes no topics itself."
        )
    found = json.loads(config.TOPICS_PATH.read_text(encoding="utf-8"))
    memberships, membership_source = _memberships_of(found)

    # Refuse if the embedding space changed since bertopic ran (#504,
    # m-47): pairing topic ids with vectors they weren't clustered against
    # gives a plausible, meaningless result.
    if (
        found.get("embedding_model") != config.EMBEDDING_MODEL
        or found.get("embedding_method") != doc_vectors.EMBED_METHOD
    ):
        raise ValueError(
            f"{config.TOPICS_PATH} was built under a different embedding model or "
            "method than the one configured now. Re-run the bertopic stage before "
            "converging, or its assignments won't match these vectors."
        )

    doc_texts = doc_vectors.corpus_texts(docs)
    _client, model = embed_index.get_client_and_model()
    vectors = doc_vectors.document_embeddings(doc_texts, model)
    # In assignment order, so descriptors use the model's own pairing.
    citekeys = [c for c in found["assignments"] if c in vectors]
    embeddings = [vectors[c] for c in citekeys]
    assigned = [found["assignments"][c] for c in citekeys]

    seed_vectors = {}
    if seed_phrases:
        encoded = model.encode(list(seed_phrases), show_progress_bar=False)
        seed_vectors = dict(zip(seed_phrases, (row.tolist() for row in encoded)))

    ids, _centred, descriptors = topic_model.topic_descriptors(embeddings, assigned)
    named = converge(dict(zip(ids, (row.tolist() for row in descriptors))), seed_vectors)
    report = seed_topics.load_report()
    result = build(memberships, citekeys, named, report)
    result["membership_source"] = membership_source
    config.TOPIC_SET_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TOPIC_SET_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def run_stage(docs, seed_phrases: tuple) -> dict:
    """`run_topic_converge()` shaped as an enrichment-stage result.

    `skipped`, not an error, when the topic model has not run: a
    sequencing mistake, not a broken corpus.
    """
    if not config.TOPICS_PATH.exists():
        return {
            "status": "skipped",
            "detail": {"reason": f"no {config.TOPICS_PATH}; run bertopic first"},
        }
    result = run_topic_converge(docs, seed_phrases)
    return {
        "status": "ok",
        "detail": {
            "n_docs": result["n_docs"],
            "seed_named": result["n_seed_named"],
            "emergent": result["n_emergent"],
            "uncovered": len(result["uncovered"]),
        },
    }
