"""What the discovery reader loads, and the refusals when it cannot.

It reads artefacts other layers wrote and computes nothing about
topics, which is why `corpus discover` sits in the corpus layer.
"""

import json
import sqlite3

from chitragupta import config, ledger, reference_entries


class MissingArtefact(ValueError):
    """An artefact the reader needs has not been produced yet. The
    message names the command that produces it, not just what is absent."""


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

    Keyed on labels via `topic_set`'s pairing (ids are unstable), so a
    seed-renamed topic keeps its name. A missing `topics.json` is fine:
    seed-only projects never ran bertopic.
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
    the topic set's order, so every view agrees."""
    inverted: dict = {}
    for topic in topic_set["topics"]:
        for member in topic["members"]:
            inverted.setdefault(member["citekey"], []).append(
                {"label": topic["label"], "score": member["score"]}
            )
    return inverted


def read_only_connection() -> sqlite3.Connection:
    """The ledger through `ledger.read_connection`, its refusal re-raised
    as this package's own."""
    try:
        return ledger.read_connection()
    except ledger.NoLedger as exc:
        raise MissingArtefact(" ".join(str(exc).split("\n"))) from exc


def centred_cosine(vector: list, mean: list, centroid: list) -> float:
    """Cosine between a raw vector moved into centred space (by the
    graph's stored corpus mean) and a stored centroid. Written once, as
    the ladder and the overview both use it."""
    centred = [float(v) - m for v, m in zip(vector, mean)]
    norm = sum(v * v for v in centred) ** 0.5 or 1.0
    c_norm = sum(v * v for v in centroid) ** 0.5 or 1.0
    return sum(a * b for a, b in zip(centred, centroid)) / (norm * c_norm)


def entries_for(citekeys: list) -> dict:
    """citekey -> formatted IEEE entry, via `reference_entries.entries`.

    A member missing from the ledger means stale topic artefacts, so it
    is re-raised as a refusal ("re-run the pipeline").
    """
    if not citekeys:
        return {}
    con = read_only_connection()
    try:
        return reference_entries.entries(list(citekeys), con)
    except reference_entries.MissingCitekey as missing:
        raise MissingArtefact(
            f"{missing} -- the topic artefacts name papers this ledger no longer "
            "holds; re-run `python -m chitragupta.corpus sync` and the enrich "
            "topic stages."
        ) from missing
    finally:
        con.close()
