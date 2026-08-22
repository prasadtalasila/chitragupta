"""What each enrichment stage returns, shaped for the run report.

Split out of `__main__.py` when a fifth stage pushed that module past
docs/CODE-STANDARDS.md's 250-line ceiling for the third time. The
boundary is real rather than arithmetic: everything here answers *what
one stage did*, everything left there answers *which stages to run, in
what order, and what to print* -- and the orchestrator had been growing
by one wrapper every time a stage was added, which is the shape of a
module holding two jobs.

Each wrapper is deliberately thin. The work belongs to the stage modules;
what these decide is only the `ok`/`skipped`/`partial` vocabulary the run
report speaks, and which parts of a stage's result are worth printing
against which are better read from the artefact it wrote.
"""

import logging

from chitragupta import seed_topics
from chitragupta.enrich import (docling_parse, embed_index, topic_converge,
                                topic_model, topic_seeding)

logger = logging.getLogger("chitragupta.enrich")


def stage_docling(docs, args) -> dict:
    status = docling_parse.parse_corpus(docs)
    errors = {k: v for k, v in status.items() if v.startswith("error")}
    return {"status": "ok" if not errors else "partial", "detail": status}


def stage_embed(docs, args) -> dict:
    return {"status": "ok", "detail": embed_index.build_index(docs)}


def stage_bertopic(docs, args) -> dict:
    result = topic_model.run_topic_model(docs)
    return {"status": "ok",
            "detail": {"n_docs": result["n_docs"],
                       "assignments": result["assignments"]}}


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


# Last, and it must stay last: it joins what the two stages above wrote
# and computes nothing itself. Running it earlier reads a stale
# content/topics.json, or none.
def stage_converge(docs, args) -> dict:
    return topic_converge.run_stage(docs, seed_topics.load())


STAGE_FUNCS = {
    "docling": stage_docling,
    "embed": stage_embed,
    "bertopic": stage_bertopic,
    "seed-topics": stage_seed_topics,
    "converge": stage_converge,
}
