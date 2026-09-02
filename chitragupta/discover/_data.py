"""What the discovery reader loads, and the refusals when it cannot.

Everything here reads artefacts other layers wrote -- the topic graph,
the converged topic set, the topic model's own info records, and the
ledger -- and computes nothing about topics itself. That boundary is the
whole reason `corpus discover` can sit in the corpus layer: the
expensive derivations happened once, in `chitragupta enrich`, and this
module's job is to open files and refuse clearly when one is missing.
"""

import json
import sqlite3

from chitragupta import config, references


class MissingArtefact(ValueError):
    """An artefact the reader needs has not been produced yet. The
    message names the command that produces it, because "file not found"
    tells a user what is absent and not what to do about it."""


def load_graph() -> dict:
    if not config.TOPIC_GRAPH_PATH.exists():
        raise MissingArtefact(
            f"No {config.TOPIC_GRAPH_PATH}. Run `python -m chitragupta.enrich "
            "--stages topic-graph` (after the earlier stages) to derive the topic graph."
        )
    return json.loads(config.TOPIC_GRAPH_PATH.read_text(encoding="utf-8"))


def load_topic_set() -> dict:
    if not config.TOPIC_SET_PATH.exists():
        raise MissingArtefact(
            f"No {config.TOPIC_SET_PATH}. Run `python -m chitragupta.enrich "
            "--stages converge` to join the topic artefacts first."
        )
    return json.loads(config.TOPIC_SET_PATH.read_text(encoding="utf-8"))


def top_terms(topic_set: dict) -> dict:
    """`{label: [term, ...]}` from the topic model's own info records.

    Keyed on labels, never topic ids -- ids are documented as unstable,
    and the join goes through `topic_set`'s label->id pairing so a
    seed-renamed topic keeps its human name. `topics.json` absent is not
    an error: seed-only projects never ran the bertopic stage, and the
    reader simply has no c-TF-IDF terms to show.
    """
    if not config.TOPICS_PATH.exists():
        return {}
    info = json.loads(config.TOPICS_PATH.read_text(encoding="utf-8")).get("topic_info", [])
    by_id = {record.get("Topic"): record.get("Representation") or [] for record in info}
    return {
        topic["label"]: by_id[topic["topic_id"]]
        for topic in topic_set["topics"]
        if topic.get("topic_id") in by_id
    }


def members_of(topic_set: dict) -> dict:
    return {topic["label"]: topic["members"] for topic in topic_set["topics"]}


def topics_of(topic_set: dict) -> dict:
    """The membership inverted: `{citekey: [{label, score}, ...]}`, in
    the topic set's own order, so every view that annotates a paper with
    its topics says the same thing in the same order."""
    inverted: dict = {}
    for topic in topic_set["topics"]:
        for member in topic["members"]:
            inverted.setdefault(member["citekey"], []).append(
                {"label": topic["label"], "score": member["score"]}
            )
    return inverted


def read_only_connection() -> sqlite3.Connection:
    """The ledger, opened read-only for the same reason `corpus ledger`
    does: inspecting must keep working during a sync, and
    `ledger.connect()` would run migrations under a write lock."""
    if not config.LEDGER_PATH.exists():
        raise MissingArtefact(
            f"No ledger at {config.LEDGER_PATH}. Run `python -m chitragupta.corpus sync`."
        )
    return sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=5.0)


def centred_cosine(vector: list, mean: list, centroid: list) -> float:
    """Cosine between a raw vector moved into centred space (by the
    graph artefact's stored corpus mean) and a stored centroid. The one
    piece of geometry the reader performs, written once: the resolution
    ladder scores query-vs-topic with it and the overview scores
    sentence-vs-topic with it, and two spellings would drift."""
    centred = [float(v) - m for v, m in zip(vector, mean)]
    norm = sum(v * v for v in centred) ** 0.5 or 1.0
    c_norm = sum(v * v for v in centroid) ** 0.5 or 1.0
    return sum(a * b for a, b in zip(centred, centroid)) / (norm * c_norm)


def entries_for(citekeys: list) -> dict:
    """citekey -> formatted IEEE entry, via the one formatter this
    project has (`references.entries`).

    A member citekey missing from the ledger is re-raised as this
    module's refusal: the topic artefacts were derived from an older
    sync, and "re-run the pipeline" is the fix, not a stack trace.
    """
    if not citekeys:
        return {}
    con = read_only_connection()
    try:
        return references.entries(list(citekeys), con)
    except references.MissingCitekey as missing:
        raise MissingArtefact(
            f"{missing} -- the topic artefacts name papers this ledger no longer "
            "holds; re-run `python -m chitragupta.corpus sync` and the enrich "
            "topic stages."
        ) from missing
    finally:
        con.close()
