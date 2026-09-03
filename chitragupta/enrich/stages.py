"""What each enrichment stage returns, shaped for the run report.

Split out of `__main__.py` when a fifth stage pushed that module past
docs/CODE-STANDARDS.md's 250-line ceiling for the third time. The
boundary is real rather than arithmetic: everything here answers *what
one stage did*, everything left there answers *which stages to run, in
what order, and what to print* -- and the orchestrator had been growing
by one wrapper every time a stage was added, which is the shape of a
module holding two jobs.

Each wrapper is deliberately thin. The work belongs to the stage modules;
what these decide is only the `ok`/`skipped`/`partial`/`error` vocabulary
the run report speaks, and which parts of a stage's result are worth
printing against which are better read from the artefact it wrote.

`error` is the one of the four that changes the run's exit code, which
is the whole of what an unattended caller gets, so a wrapper escalates
to it only for work the stage abandoned rather than attempted -- an
ordinary per-document failure stays `partial`. docs/LADDERS.md owns
that contract; `stage_docling` below is the one case that has met it.
"""

import logging

from chitragupta import seed_topics
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
    # `skipped` before `partial` (#509/m-40). `parse_corpus` now returns
    # one shared `skipped:` line for every document when docling is not
    # installed; reading that as `partial` would say "some documents did
    # not parse" about a stage that never ran, and hide the install step
    # inside a per-document detail map.
    if status and all(value.startswith("skipped") for value in status.values()):
        return {"status": "skipped", "detail": next(iter(status.values()))}
    errors = {k: v for k, v in status.items() if v.startswith("error")}
    # `error`, not `partial`, when a document was abandoned by a pool
    # that kept dying (#584). `__main__._summarise` returns nonzero only
    # for `error`, so folding this into `partial` exited 0 -- and a run
    # that abandoned 460 of 642 documents then reported itself to cron,
    # the consumer that cannot read the summary, exactly as a clean run
    # does. Deliberately narrow: an ordinary parse failure is a
    # deterministic per-document result and stays `partial`, or one
    # unreadable PDF would fail every nightly run.
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


# Its ok/skipped shaping lives in keyword_extract.run_stage(), for the
# same ceiling reason stage_seed_topics states below. Before seed-topics
# in the order, because the extracted phrases exist to be unioned into
# that stage's seed list (#605).
def stage_extract_keywords(docs, args) -> dict:
    return keyword_extract.run_stage(docs)


# Unlike the three above, this stage's ok/skipped shaping lives in
# topic_seeding.run_stage() rather than here. Not a style break for its
# own sake: this module is four code lines under docs/CODE-STANDARDS.md's
# 250-line ceiling with three stages, so spelling a fourth out in the
# local idiom would push the orchestrator over a boundary that adding a
# stage is no reason to move. The seed list is read here, though, because
# "is there a seed file" is the question that decides whether the stage
# runs at all, and that is this file's decision to make.
def stage_seed_topics(docs, args) -> dict:
    return topic_seeding.run_stage(docs, seed_topics.load())


# It joins what the two stages above wrote and computes nothing itself.
# Running it earlier reads a stale content/topics.json, or none.
def stage_converge(docs, args) -> dict:
    return topic_converge.run_stage(docs, seed_topics.load())


# Last, and it must stay last: it derives relations between the topics
# converge just joined, so running it earlier graphs a stale
# content/topic_set.json, or none.
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
