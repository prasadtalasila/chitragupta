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


def entries_for(citekeys: list) -> dict:
    """citekey -> formatted IEEE entry, via the one formatter this
    project has (`references.entries`). Opened read-only for the same
    reason `corpus ledger` does: inspecting must keep working during a
    sync, and `ledger.connect()` would run migrations under a write
    lock."""
    if not citekeys:
        return {}
    if not config.LEDGER_PATH.exists():
        raise MissingArtefact(
            f"No ledger at {config.LEDGER_PATH}. Run `python -m chitragupta.corpus sync`."
        )
    con = sqlite3.connect(f"file:{config.LEDGER_PATH}?mode=ro", uri=True, timeout=5.0)
    try:
        return references.entries(list(citekeys), con)
    finally:
        con.close()
