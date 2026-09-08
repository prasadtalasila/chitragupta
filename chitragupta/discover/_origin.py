"""Where a topic's phrase came from, and the filter over it (#742).

The topic artefacts record `provenance`: `seed` or `emergent`, and
nothing finer. That is not an omission -- `stages._seed_phrases()`
unions `content/seed_topics.toml` (what the human wrote) with
`content/keywords.toml` (what the keyword extractor proposed) *before*
any stage runs, so by the time a topic exists the two are one set. The
files themselves are the only record left, and reading them is what
turns two provenances into four origins:

    seed          in seed_topics.toml only -- the human named it
    keyword       in keywords.toml only -- the corpus proposed it
    corroborated  in both -- two independent sources agree
    emergent      in neither, and provenance says so

`corroborated` rather than `both`: the reader is looking at a fact
about the topic, not at a set operation over two files.

**Selection is a union of predicates, not a partition.** A corroborated
topic satisfies the seed predicate *and* the keyword predicate, so
`--origins seed` shows it: someone asking for hand-written topics must
not have their hand-written topics hidden because the extractor happened
to agree. `--origins corroborated` asks for the intersection alone.

`keep` filters the artefacts rather than one view's output, so the
terminal list, `--json`, `--html` and `--app` cannot disagree about what
is in the graph -- and a phrase naming a filtered-out topic falls
through the resolution ladder like any other unknown phrase.
"""

import copy

from chitragupta import config, seed_topics

# Order is the reader's, not the machine's: how much of a human is in
# the topic, most first. `--help`, the docs table and the app's origin
# picker all follow it.
CLASSES = ("seed", "keyword", "corroborated", "emergent")

# Which selected classes show a topic of each origin. Only the
# corroborated row has more than one key, and that is the whole of the
# "union of predicates" rule above, in one place.
SHOWN_BY = {
    "seed": {"seed"},
    "keyword": {"keyword"},
    "corroborated": {"seed", "keyword", "corroborated"},
    "emergent": {"emergent"},
}


def parse(value: "str | None") -> set:
    """The `--origins` vocabulary. `None` (no flag) is every class, so
    an unflagged run is the graph exactly as it was.

    Raises ValueError -- the CLI turns it into a refusal on stderr --
    for an unknown class and for a selection that names none, because
    an empty graph reads as an empty corpus rather than as a filter.
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
    """This topic's origin. An emergent topic keeps its provenance
    whatever the files say -- a BERTopic label colliding with a keyword
    is a coincidence, not a seeding. A seed topic in neither file (the
    files moved after the stages ran) degrades to "seed": the artefact's
    own provenance is still true, and refusing would make this stricter
    than every other view of the same data.

    `.get` because this now runs on every `discover` invocation, over
    whatever the artefact holds: a node recording no provenance at all
    cannot be called seeded, and a KeyError here would take down views
    that never asked about origin."""
    if topic.get("provenance") != "seed":
        return "emergent"
    key = topic["label"].casefold()
    if key in hand:
        return "corroborated" if key in extracted else "seed"
    return "keyword" if key in extracted else "seed"


def annotate(topics: list) -> list:
    """Add `origin` to each topic in place, and hand the list back so a
    caller can use it in an expression. One pair of file reads for the
    whole list: the files are the same for every topic in a run."""
    hand = {phrase.casefold() for phrase in seed_topics.load()}
    extracted = {phrase.casefold() for phrase in seed_topics.load(config.KEYWORDS_PATH)}
    for topic in topics:
        topic["origin"] = classify(topic, hand, extracted)
    return topics


def selected(origins: set) -> set:
    """The labels-independent half of `keep`, exposed because the app
    payload records it: which origins a selection shows."""
    return {origin for origin in CLASSES if SHOWN_BY[origin] & origins}


def keep(graph: dict, topic_set: dict, origins: set) -> tuple:
    """The two artefacts with every unselected topic removed, plus the
    edges that touched one -- an edge is a claim about a pair, and half
    a pair is a line to a node the reader cannot see.

    Both artefacts, filtered in step: the views compare them and refuse
    for drift when one knows a topic the other does not.

    `uncovered` and `edges_withheld` are left as the stages wrote them.
    They are statements about the corpus, not about the reader's current
    view, and rescaling them to a subset would publish a number no stage
    ever produced.

    The stored hierarchy is left whole for the same reason -- it is the
    merge tree over the topics that had a vector, and recutting it over
    a subset would invent a grouping nothing computed. Both the page and
    the app already draw only the leaves they can see, which is how the
    hop filter has always worked.

    Copies rather than edits: a caller's artefact is not this function's
    to rewrite, and `--app` writes twice from one load.
    """
    shown = selected(origins)
    graph = copy.deepcopy(graph)
    topic_set = copy.deepcopy(topic_set)
    dropped = {t["label"] for t in annotate(graph["topics"]) if t["origin"] not in shown}
    for topic in graph["topics"]:
        del topic["origin"]
    # Subtractive, deliberately: a topic_set label the *graph* does not
    # know is artefact drift, and the views raise a refusal naming the
    # stage to re-run. Keeping only what the graph selected would drop
    # that label here instead, and the drift would leave with it.
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

    `communities` is one cluster id per topic, in `graph["topics"]`
    order: filtering the topics without filtering these in step hands
    every surviving topic the cluster id of whichever topic now sits at
    its index -- silently wrong, which is worse than a crash. Filtered
    to the kept positions, each topic keeps the id the stage gave it,
    and a partly hidden cluster is still that topic's cluster.

    `paths` cannot be repaired the same way. It stores next-hop indices
    into the edge lists, and a stored route is free to run *through* a
    topic the filter removed; truncating the matrices would leave routes
    pointing at edges that are gone. Recomputing is not this layer's to
    do -- the reader derives nothing -- so the field goes, and both
    consumers already have an honest answer for an artefact without it:
    the terminal refuses by name (`__init__` refuses earlier still, on
    the flag combination) and the app walks the graph in the browser.
    """
    for family in graph.get("communities", {}).values():
        for inflation, assignments in family.get("partitions", {}).items():
            family["partitions"][inflation] = [assignments[i] for i in kept]
    graph.pop("paths", None)
