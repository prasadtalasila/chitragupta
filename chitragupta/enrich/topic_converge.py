"""Stage 6: one topic set, from the phrases you wrote and the topics the
corpus turned out to have.

Two artefacts described the same corpus and never met.
`content/topic_seeds.json` holds phrases the author wrote with the papers
each matched; `content/topics.json` holds the topics clustering found,
with per-document memberships. Both are computed from the same document
vectors, and their independence is deliberate -- it is what makes a seed
list unlimited, since seeds never enter the clustering -- but nothing
joined them afterwards. A seed phrase and an emergent topic covering the
same papers appeared as two unrelated things, and the reader reconciled
them by eye.

`content/topic_set.json` is that join. A topic here has one shape
whatever it came from::

    {"label": ..., "provenance": "seed" | "emergent",
     "topic_id": ... | None, "members": [{"citekey": ..., "score": ...}]}

**Convergence is the human's name winning.** An emergent topic whose
descriptor sits within `config.TOPIC_CONVERGE_SIMILARITY` of a seed
phrase is *renamed* by that phrase rather than listed beside it. That is
what "seeds are a starting point" has to mean in the artefact: an author
who wrote "structural health monitoring" should not have to notice that
emergent topic 41 is the same thing under a c-TF-IDF name.

Two shapes of collision, resolved deliberately rather than by accident:

- **Several seeds match one topic.** The closest wins, ties broken on the
  phrase text so a run is diffable against the last one.
- **Several topics match one seed.** Only the closest takes the name; the
  rest stay emergent and keep their derived labels.

  This is the reverse of what was built first, and the real corpus is
  what changed it. Letting every close cluster take the phrase read well
  in the abstract -- a phrase *can* name a family of neighbouring
  clusters -- and produced eight topics all called `digital twin` on a
  digital-twins corpus, plus three called `dt architecture`. Nineteen
  seed-named topics from nine phrases, and no way for a reader to tell
  any of them apart. A label that does not distinguish is not a label.

  The clusters that lose the name are not lost: they keep their own
  identity and their own members, and the phrase's broader view is still
  in `content/topic_seeds.json`, which is exactly where "every paper
  matching this phrase" belongs.

A seed phrase matching no emergent topic still appears, carrying the
papers it matched and `topic_id: None`. That is the useful case rather
than a leftover: it is the author naming something the clustering did not
separate out, and seeing it with no cluster behind it is the signal that
the corpus does not organise the way they assumed.

**This stage re-runs nothing.** It reads `content/topics.json` and
`content/topic_seeds.json`, recomputes only the topic descriptors --
cheap arithmetic over vectors already cached, no clustering -- and joins.
Re-deriving either half here would be a second answer to a question
already answered, and the two would drift.
"""

import json

from chitragupta import config, seed_topics
from chitragupta.enrich import doc_vectors, embed_index, topic_model, topic_seeding


def converge(descriptors: dict, seed_vectors: dict, min_similarity: "float | None" = None) -> dict:
    """`{emergent_topic_id: seed_phrase}` for every topic a seed names.

    Free of the corpus and the model so it can be driven with vectors
    chosen by hand: everything above decides what to embed, this is
    arithmetic on the result.
    """
    floor = config.TOPIC_CONVERGE_SIMILARITY if min_similarity is None else min_similarity
    # Every (phrase, topic) pair above the floor, best first. Sorting the
    # whole set rather than deciding per topic is what lets a phrase be
    # claimed once: the walk below hands each phrase to its closest topic
    # and each topic to its closest unclaimed phrase.
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

    `memberships` is the many-to-many view, not the single id in
    `assignments` -- a paper appears under every topic it is about, which
    is the whole reason that field exists.
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
        # Stamped so a later stage can refuse a mismatched space without
        # re-reading topics.json -- the graph stage's check needs both
        # halves, and the model alone does not identify the space when
        # the pooling method changes (#557's review caught the gap).
        "embedding_method": doc_vectors.EMBED_METHOD,
        "converge_similarity": config.TOPIC_CONVERGE_SIMILARITY,
        "n_docs": len(citekeys),
        "n_seed_named": sum(1 for t in topics if t["provenance"] == "seed"),
        "n_emergent": sum(1 for t in topics if t["provenance"] == "emergent"),
        "topics": topics,
        # The papers no topic of either kind covers. The one number an
        # author planning a draft actually wants from this file.
        "uncovered": sorted(set(citekeys) - covered),
    }


def _memberships_of(found: dict) -> "tuple[dict, str]":
    """`topics.json`'s many-to-many view, or a single-membership stand-in
    for it, plus which of the two this is.

    `memberships` is `None` whenever `[topics].topic_distribution` is off,
    and `build` reads *only* that field -- so converging on such a corpus
    silently produced zero emergent topics and listed every paper as
    uncovered (#509/m-43). That is a report about the setting, dressed up
    as a finding about the library.

    `assignments` still holds the one thing the clustering is sure of:
    which cluster each document landed in. Synthesised into
    single-membership rows here, and named in the result through
    `membership_source`, so the output says which view it is rather than
    letting the narrow one pass for the full one. The outlier topic (-1)
    is not a topic and is left out, exactly as `topic_descriptors` leaves
    it out.
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

    Raises when `content/topics.json` is absent rather than clustering to
    produce one: this stage's contract is that it re-runs nothing, and a
    stage that silently did an hour of GPU work would be a different
    stage wearing this one's name.
    """
    if not config.TOPICS_PATH.exists():
        raise ValueError(
            f"No {config.TOPICS_PATH} to converge. Run the bertopic stage first; "
            "this stage joins what the others found and computes no topics itself."
        )
    found = json.loads(config.TOPICS_PATH.read_text(encoding="utf-8"))
    memberships, membership_source = _memberships_of(found)

    # `found["assignments"]` is a clustering computed against a specific
    # embedding space; `vectors` below is re-embedded under *today's*
    # config, silently a different space if `embedding_model`/`method`
    # changed since the bertopic stage last ran. Zipping the two together
    # anyway would pair a topic id with a vector it was never clustered
    # against and hand back a plausible-looking, meaningless result
    # (#504, m-47) -- caught here, in the same "re-run the earlier stage"
    # shape the missing-file check above already uses, rather than left
    # for a reader to notice the descriptors don't make sense.
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
    # Ordered by the assignments the topic model recorded, so descriptors
    # are built from the same document-to-topic pairing that produced them.
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

    `skipped` rather than an error when the topic model has not run,
    because a `--stages converge` on a corpus with no topics yet is a
    sequencing mistake and not a broken corpus -- the same status the
    docling stage reports for a binary that is not installed.
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
