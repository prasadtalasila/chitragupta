"""What each enrichment stage returns, shaped for the run report.

Each wrapper is thin: it decides only the `ok`/`skipped`/`partial`/
`error` vocabulary. `error` alone changes the exit code, so it is kept for
work a stage abandoned; an ordinary per-document failure stays `partial`
(docs/LADDERS.md owns the contract).
"""

import logging

from chitragupta import config, seed_topics
from chitragupta.enrich import (
    docling_parse,
    embed_index,
    keyword_extract,
    topic_converge,
    topic_graph,
    topic_model,
    topic_seeding,
)

logger = logging.getLogger("chitragupta.enrich")


def stage_docling(docs, args) -> dict:
    status = docling_parse.parse_corpus(docs)
    # `skipped` before `partial` (#509/m-40): docling missing means the
    # stage never ran, and the install step must not hide in a detail map.
    if status and all(value.startswith("skipped") for value in status.values()):
        return {"status": "skipped", "detail": next(iter(status.values()))}
    errors = {k: v for k, v in status.items() if v.startswith("error")}
    # `error` when a pool that kept dying abandoned documents (#584),
    # since only `error` exits nonzero for cron. An ordinary parse failure
    # stays `partial`, or one unreadable PDF would fail every nightly run.
    if docling_parse.POOL_DEATH_ERROR in errors.values():
        return {"status": "error", "detail": status}
    return {"status": "ok" if not errors else "partial", "detail": status}


def stage_embed(docs, args) -> dict:
    return {"status": "ok", "detail": embed_index.build_index(docs)}


def stage_bertopic(docs, args) -> dict:
    result = topic_model.run_topic_model(docs)
    return {
        "status": "ok",
        "detail": {"n_docs": result["n_docs"], "assignments": result["assignments"]},
    }


# Shaping lives in keyword_extract.run_stage(). Before seed-topics, whose
# seed list its phrases are unioned into (#605).
def stage_extract_keywords(docs, args) -> dict:
    return keyword_extract.run_stage(docs)


# The union is done here, not in seed_topics.load() (#605), which means
# "the author's own list". The author's file loads first, so its spelling
# wins the case-insensitive dedup.
def _seed_phrases() -> tuple:
    merged: list[str] = []
    seen: set[str] = set()
    for phrase in (*seed_topics.load(), *seed_topics.load(config.KEYWORDS_PATH)):
        if phrase.casefold() in seen:
            continue
        seen.add(phrase.casefold())
        merged.append(phrase)
    return tuple(merged)


# Shaping lives in topic_seeding.run_stage() (docs/TECHNICAL-DEBT.md,
# R14); the seed list is read here because it decides whether to run.
def stage_seed_topics(docs, args) -> dict:
    return topic_seeding.run_stage(docs, _seed_phrases())


# Joins the two stages above; earlier would read a stale topics.json.
def stage_converge(docs, args) -> dict:
    return topic_converge.run_stage(docs, _seed_phrases())


# Must stay last: it graphs the topics converge just joined.
def stage_topic_graph(docs, args) -> dict:
    return topic_graph.run_stage(docs)


STAGE_FUNCS = {
    "docling": stage_docling,
    "embed": stage_embed,
    "bertopic": stage_bertopic,
    "extract-keywords": stage_extract_keywords,
    "seed-topics": stage_seed_topics,
    "converge": stage_converge,
    "topic-graph": stage_topic_graph,
}
