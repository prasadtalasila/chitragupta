"""Where a topic's phrase came from, and the filter over it (#742).

The artefacts record only `seed` or `emergent`, because
`stages._seed_phrases()` unions seed_topics.toml and keywords.toml
before any stage runs. Reading the files again yields four origins:
`seed` (human only), `keyword` (extractor only), `corroborated` (both)
and `emergent` (neither).

**Selection is a union of predicates, not a partition**: `--origins
seed` still shows a corroborated topic, so agreement never hides a
hand-written one. `keep` filters the artefacts, not one view, so every
output agrees.
"""

import copy

from chitragupta import config, seed_topics

# Most human first; `--help`, the docs table and the app picker follow it.
CLASSES = ("seed", "keyword", "corroborated", "emergent")

# Which selected classes show each origin; the corroborated row is the
# whole "union of predicates" rule.
SHOWN_BY = {
    "seed": {"seed"},
    "keyword": {"keyword"},
    "corroborated": {"seed", "keyword", "corroborated"},
    "emergent": {"emergent"},
}


def parse(value: "str | None") -> set:
    """The `--origins` vocabulary. `None` (no flag) is every class.

    Raises ValueError for an unknown class or an empty selection, since
    an empty graph reads as an empty corpus rather than a filter.
    """
    if value is None:
        return set(CLASSES)
    chosen = {part.strip().casefold() for part in value.split(",")}
    chosen.discard("")
    unknown = sorted(chosen - set(CLASSES))
    if unknown:
        raise ValueError(
            f"unknown topic origin {', '.join(unknown)} -- "
            f"--origins takes any of: {', '.join(CLASSES)}"
        )
    if not chosen:
        raise ValueError(f"--origins names no class -- give one or more of: {', '.join(CLASSES)}")
    return chosen


def classify(topic: dict, hand: set, extracted: set) -> str:
    """This topic's origin. An emergent topic stays emergent (a label
    colliding with a keyword is coincidence). A seed topic in neither
    file degrades to "seed" rather than refusing. `.get`, since a node
    with no provenance must not crash views that never asked."""
    if topic.get("provenance") != "seed":
        return "emergent"
    key = topic["label"].casefold()
    if key in hand:
        return "corroborated" if key in extracted else "seed"
    return "keyword" if key in extracted else "seed"


def annotate(topics: list) -> list:
    """Add `origin` to each topic in place and return the list; the files
    are read once per run."""
    hand = {phrase.casefold() for phrase in seed_topics.load()}
    extracted = {phrase.casefold() for phrase in seed_topics.load(config.KEYWORDS_PATH)}
    for topic in topics:
        topic["origin"] = classify(topic, hand, extracted)
    return topics


def selected(origins: set) -> set:
    """Which origins a selection shows; exposed for the app payload."""
    return {origin for origin in CLASSES if SHOWN_BY[origin] & origins}


def keep(graph: dict, topic_set: dict, origins: set) -> tuple:
    """The two artefacts with every unselected topic removed, plus the
    edges that touched one (half an edge points at an invisible node).

    Both filtered in step, since views refuse on drift between them.
    `uncovered`, `edges_withheld` and the hierarchy are left as written:
    rescaling or recutting would publish numbers no stage produced.
    Copies, because `--app` writes twice from one load.
    """
    shown = selected(origins)
    graph = copy.deepcopy(graph)
    topic_set = copy.deepcopy(topic_set)
    dropped = {t["label"] for t in annotate(graph["topics"]) if t["origin"] not in shown}
    for topic in graph["topics"]:
        del topic["origin"]
    # Subtractive: a label the graph does not know is drift the views must
    # still see and refuse on.
    kept = [i for i, t in enumerate(graph["topics"]) if t["label"] not in dropped]
    graph["topics"] = [t for t in graph["topics"] if t["label"] not in dropped]
    for family in ("edges_overlap", "edges_semantic"):
        graph[family] = [e for e in graph[family] if not {e["a"], e["b"]} & dropped]
    topic_set["topics"] = [t for t in topic_set["topics"] if t["label"] not in dropped]
    if dropped:
        _refile_positional(graph, kept)
    return graph, topic_set


def _refile_positional(graph: dict, kept: list) -> None:
    """The two stored fields that are *positional* rather than named,
    and so cannot survive a filter untouched.

    `communities` is filtered to the kept positions, or every topic would
    silently take another's cluster id. `paths` (next-hop indices whose
    routes may cross removed topics) cannot be repaired without
    recomputing, so it is dropped; the terminal refuses and the app walks
    the graph itself.
    """
    for family in graph.get("communities", {}).values():
        for inflation, assignments in family.get("partitions", {}).items():
            family["partitions"][inflation] = [assignments[i] for i in kept]
    graph.pop("paths", None)
