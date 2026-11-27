"""What else still names a citekey that `sync --remove-stale` is about
to drop from the ledger -- reported, never repaired (issue #763).

Below the drafting layer, chroma vectors, the overlap index, the topic
graph and topic membership (#782) carry citekeys; drafts are reported by
`dossier status --all` (plans/1211), which this report points to.

Report, do not repair: cascading the deletion (as llm_wiki does) would
destroy hand-transcribed evidence (docs/AUTO-IMPROVEMENT.md); nothing
here opens a file for writing. Exact strings only, no fuzzy matching: a
guessing matcher would report residue that does not exist. Reads other
layers' artefacts without importing them; `overlap_chroma` is asked
nothing until `content/chroma/` exists, so the filesystem is left as found.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from chitragupta import chroma_paging, config, overlap_chroma
from chitragupta.citekey_safety import citekey_path, citekey_problem

# Fixed order, so two runs print identically; roughly cheapest first.
OVERLAP = "overlap index"
TOPIC_GRAPH = "topic graph"
TOPIC_MEMBERSHIP = "topic membership"
CHROMA = "chroma vectors"


@dataclass(frozen=True)
class Hit:
    """One artefact class still naming one citekey."""

    artefact: str
    count: int
    unit: str
    where: tuple[str, ...]


def _read_json(path: Path, artefact: str, notes: list[str]) -> dict:
    """`path`'s JSON, or `{}` when it is absent or cannot be read."""
    # Noted, not raised (#846): a killed enrichment run can leave a file
    # truncated, and a traceback here would hide the stale list.
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        notes.append(_unscanned(artefact, path, exc))
        return {}


def _unscanned(artefact: str, path: object, exc: Exception) -> str:
    return f"{artefact}: {path} could not be read ({exc}), so it was not scanned."


def _fingerprint_files(citekey: str) -> list[str]:
    """`citekey`'s per-document fingerprints that exist on disk."""
    # Every writer names files through `citekey_path`, so a key that cannot
    # name one has none; raising would follow committed upserts (#975).
    if citekey_problem(citekey):
        return []
    docs = config.OVERLAP_DIR / "docs"
    paths = (citekey_path(docs, citekey, suffix) for suffix in (".fpr", ".skipgram.fpr"))
    return [str(path) for path in paths if path.is_file()]


def _scan_overlap(citekeys: list[str], notes: list[str]) -> dict[str, Hit]:
    """Per-document fingerprints and the merged corpus index."""
    # Which index named it: the tiers are built independently, so a union
    # would misattribute paths and double-count.
    indexed: dict[str, list[str]] = {}
    for name in ("index.json", "skipgram_index.json"):
        path = config.OVERLAP_DIR / name
        for key in _read_json(path, OVERLAP, notes).get("citekeys", []):
            indexed.setdefault(key, []).append(str(path))
    hits = {}
    for citekey in citekeys:
        where = _fingerprint_files(citekey) + indexed.get(citekey, [])
        if where:
            hits[citekey] = Hit(OVERLAP, len(where), "file", tuple(where))
    return hits


def _graph_edge_citekeys(graph: dict) -> list[list[str]]:
    """Every edge's citekey list, across the topic graph's three edge
    kinds. Nodes carry none; membership is `_scan_topic_membership`'s."""
    edges = []
    for key, field in (
        ("edges_overlap", "shared"),
        ("edges_withheld", "shared"),
        ("edges_semantic", "bridge"),
    ):
        edges += [edge.get(field, []) for edge in graph.get(key, [])]
    return edges


def _scan_topic_graph(citekeys: list[str], notes: list[str]) -> dict[str, Hit]:
    """Edges whose shared-document or bridge list names the citekey."""
    path = config.TOPIC_GRAPH_PATH
    edges = _graph_edge_citekeys(_read_json(path, TOPIC_GRAPH, notes))
    hits = {}
    for citekey in citekeys:
        count = sum(1 for edge in edges if citekey in edge)
        if count:
            hits[citekey] = Hit(TOPIC_GRAPH, count, "edge", (str(path),))
    return hits


def _topic_set_citekeys(data: dict) -> list[str]:
    """Every citekey `topic_set.json` names, plus its `uncovered` list.
    A member with no `citekey` yields `None`, so a malformed record counts
    zero rather than raising before a destructive prompt.
    """
    named = [
        member.get("citekey")
        for topic in data.get("topics", [])
        for member in topic.get("members", [])
    ]
    return named + list(data.get("uncovered", []))


def _topics_citekeys(data: dict) -> list[str]:
    """`topics.json`'s `assignments` and `memberships`, both keyed by
    citekey."""
    return list(data.get("assignments", {})) + list(data.get("memberships", {}))


def _scan_topic_membership(citekeys: list[str], notes: list[str]) -> dict[str, Hit]:
    """Which topic each paper belongs to, per file with its own count, as
    either may exist alone. Self-healing: the next enrichment run
    regenerates both.
    """
    named = [
        (path, extract(_read_json(path, TOPIC_MEMBERSHIP, notes)))
        for path, extract in (
            (config.TOPIC_SET_PATH, _topic_set_citekeys),
            (config.TOPICS_PATH, _topics_citekeys),
        )
    ]
    hits = {}
    for citekey in citekeys:
        counts = [(path, keys.count(citekey)) for path, keys in named]
        counts = [(path, n) for path, n in counts if n]
        if counts:
            where = tuple(f"{path} ({n})" for path, n in counts)
            hits[citekey] = Hit(
                TOPIC_MEMBERSHIP, sum(n for _path, n in counts), "membership", where
            )
    return hits


def _scan_chroma(citekeys: list[str]) -> tuple[dict[str, Hit], "str | None"]:
    """Chunk vectors, and why they could not be counted when they could not."""
    # `content/chroma/` is checked before probing, and `overlap_chroma` never
    # creates a collection. A different `[enrich].embedding_model` reads as
    # zero, which is true of the collection this config would use.
    if not config.CHROMA_DIR.is_dir():
        return {}, None
    stack = overlap_chroma.optional_stack()
    if stack is None:
        return {}, (
            f"{CHROMA}: {config.CHROMA_DIR} exists but the enrich group is not "
            f"installed, so vectors were not scanned."
        )
    try:
        collection = overlap_chroma.built_collection(stack[0])
        where = {"citekey": {"$in": sorted(citekeys)}}
        rows = collection and chroma_paging.all_rows(collection, where=where, include=["metadatas"])
    # Any chroma or sqlite error is noted, as in `_read_json` (#970).
    except Exception as exc:  # noqa: BLE001 -- see the comment above
        return {}, _unscanned(CHROMA, config.CHROMA_DIR, exc)
    if rows is None:
        return {}, None
    hits = {}
    for citekey in citekeys:
        count = sum(1 for meta in rows["metadatas"] if meta.get("citekey") == citekey)
        if count:
            hits[citekey] = Hit(CHROMA, count, "vector", (str(config.CHROMA_DIR),))
    return hits, None


def scan(citekeys: list[str]) -> tuple[dict[str, list[Hit]], list[str]]:
    """`({citekey: [Hit, ...]}, [note, ...])` for every citekey given. A
    citekey with no residue maps to `[]`; notes name what could not be
    scanned or read.
    """
    notes: list[str] = []
    chroma, note = _scan_chroma(citekeys)
    by_class = [
        _scan_overlap(citekeys, notes),
        _scan_topic_graph(citekeys, notes),
        _scan_topic_membership(citekeys, notes),
        chroma,
    ]
    found = {
        citekey: [hits[citekey] for hits in by_class if citekey in hits] for citekey in citekeys
    }
    return found, notes + ([note] if note else [])


def report(citekeys: list[str]) -> None:
    """Print what still references each citekey, grouped by artefact.
    Prints nothing for no citekeys, so a routine sync pays nothing.
    """
    if not citekeys:
        return
    found, notes = scan(citekeys)
    print(f"  Checking what else still references the {len(citekeys)} stale citekey(s) ...")
    for citekey in citekeys:
        hits = found[citekey]
        if not hits:
            print(f"    {citekey}: no other artefact references it")
            continue
        print(f"    {citekey}: still referenced by {len(hits)} artefact class(es)")
        for hit in hits:
            # "(s)", as elsewhere in sync's stdout ("1 stale item(s)").
            print(f"      {hit.artefact:<16} {hit.count} {hit.unit}(s): {', '.join(hit.where)}")
    for note in notes:
        print(f"    NOTE: {note}")
    print("    Reported, not repaired -- nothing above is touched by this run.")
    print("    Drafts and dossiers citing these: chitragupta draft dossier status --all")
