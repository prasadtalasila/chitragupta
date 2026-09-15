"""What else still names a citekey that `sync --remove-stale` is about
to drop from the ledger -- reported, never repaired (issue #763).

The ledger row is not the only place a citekey lives. Five other
artefacts carry it: the enrichment layer's chunk vectors under
`content/chroma/`, the overlap index under `content/overlap/`, the topic
graph's edges in `content/topic_graph.json`, the topic membership records
in `content/topic_set.json` and `content/topics.json` (#782), and the
drafting layer's dossiers under `content/dossiers/`. Dropping the row
leaves every one of them pointing at a paper the corpus no longer holds --
`chitragupta/citation_gate.py` catches the draft-side symptom, but only
at the next gate run and without saying what caused it.

**Report, do not repair.** Cascading the deletion is what upstream
(llm_wiki) does and is rejected here: pruning a citekey out of a
dossier's `evidence.md` destroys evidence a human transcribed by hand,
and docs/AUTO-IMPROVEMENT.md already reasons through why that class of
repair must be human-confirmed. Nothing in this module opens a file for
writing. The confirmation posture `chitragupta/sync_decide.py` already
has does not change; what changes is that the person is told what they
are confirming.

**Exact strings only.** A citekey here comes from a human's own BibTeX
export and is matched literally, bounded by the characters a citekey may
itself contain. Upstream's three-method fuzzy matcher was deliberately
not copied: there is nothing to guess at, and a matcher that guessed
would be reporting residue for a paper that has none.

**Artefact-mediated, like every other edge in docs/ARCHITECTURE.md's
four-layer graph.** This is corpus-layer code reading files the
enrichment and drafting layers wrote; it imports neither
`chitragupta.dossier` nor `chitragupta.enrich`. The one exception is
`chitragupta/overlap_chroma.py`, which exists precisely so a caller
outside `chitragupta/enrich/` can ask whether the optional chroma stack
is installed without importing it -- and it is asked nothing at all
until `content/chroma/` is already on disk, because this module must
leave the filesystem exactly as it found it.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from chitragupta import chroma_paging, config, overlap_chroma

# Fixed order, so two runs over the same corpus print identically and a
# reader can diff them. Roughly cheapest-to-costliest to scan.
OVERLAP = "overlap index"
TOPIC_GRAPH = "topic graph"
TOPIC_MEMBERSHIP = "topic membership"
DOSSIERS = "dossiers"
CHROMA = "chroma vectors"

# The files in a dossier that carry citekeys as *citations of record*.
# `rejected.md` is deliberately not among them: a citekey there was
# considered and turned down, so the paper leaving the corpus confirms
# that decision rather than invalidating it.
DOSSIER_FILES = ("evidence.md", "sections.md")


@dataclass(frozen=True)
class Hit:
    """One artefact class still naming one citekey."""

    artefact: str
    count: int
    unit: str
    where: tuple[str, ...]


def _pattern(citekey: str) -> "re.Pattern[str]":
    """The literal citekey, bounded by the characters a citekey may
    contain, so `smith_2024` does not match inside `smith_2024b`."""
    edge = r"[A-Za-z0-9_:-]"
    return re.compile(rf"(?<!{edge}){re.escape(citekey)}(?!{edge})")


def _scan_overlap(citekeys: list[str]) -> dict[str, Hit]:
    """Per-document fingerprints and the merged corpus index."""
    # Which index named it, not merely that one did: the two tiers are
    # built independently, so unioning them would report a citekey that
    # is only in the skipgram index as living in `index.json` -- a path
    # that need not exist -- and would count a citekey in both as one.
    indexed: dict[str, list[str]] = {}
    for name in ("index.json", "skipgram_index.json"):
        path = config.OVERLAP_DIR / name
        if path.is_file():
            for key in json.loads(path.read_text(encoding="utf-8")).get("citekeys", []):
                indexed.setdefault(key, []).append(str(path))
    hits = {}
    for citekey in citekeys:
        where = [
            str(path)
            for path in (
                config.OVERLAP_DIR / "docs" / f"{citekey}.fpr",
                config.OVERLAP_DIR / "docs" / f"{citekey}.skipgram.fpr",
            )
            if path.is_file()
        ]
        where += indexed.get(citekey, [])
        if where:
            hits[citekey] = Hit(OVERLAP, len(where), "file", tuple(where))
    return hits


def _graph_edge_citekeys(graph: dict) -> list[list[str]]:
    """Every edge's citekey list, across the three kinds of edge the
    topic graph records. The topic *nodes* carry no citekeys at all --
    membership lives in `content/topic_set.json` and
    `content/topics.json`, which are a separate artefact class scanned by
    `_scan_topic_membership` rather than here."""
    edges = []
    for key, field in (
        ("edges_overlap", "shared"),
        ("edges_withheld", "shared"),
        ("edges_semantic", "bridge"),
    ):
        edges += [edge.get(field, []) for edge in graph.get(key, [])]
    return edges


def _scan_topic_graph(citekeys: list[str]) -> dict[str, Hit]:
    """Edges whose shared-document or bridge list names the citekey."""
    path = config.TOPIC_GRAPH_PATH
    if not path.is_file():
        return {}
    edges = _graph_edge_citekeys(json.loads(path.read_text(encoding="utf-8")))
    hits = {}
    for citekey in citekeys:
        count = sum(1 for edge in edges if citekey in edge)
        if count:
            hits[citekey] = Hit(TOPIC_GRAPH, count, "edge", (str(path),))
    return hits


def _topic_set_citekeys(data: dict) -> list[str]:
    """Every citekey `topic_set.json` names: one per membership record,
    plus the `uncovered` list of papers no topic claimed.

    A member carrying no `citekey` yields `None`, which no citekey ever
    equals -- so a malformed record counts zero instead of raising, which
    matters in a module that runs immediately before a destructive
    prompt.
    """
    named = [
        member.get("citekey")
        for topic in data.get("topics", [])
        for member in topic.get("members", [])
    ]
    return named + list(data.get("uncovered", []))


def _topics_citekeys(data: dict) -> list[str]:
    """`topics.json` keys both of its maps by citekey: `assignments`
    (the one topic each paper was assigned) and `memberships` (every
    topic it scored against)."""
    return list(data.get("assignments", {})) + list(data.get("memberships", {}))


def _scan_topic_membership(citekeys: list[str]) -> dict[str, Hit]:
    """Which topic each paper belongs to, across the two files that
    record it.

    Named per file with its own count, like `_scan_dossiers`, because the
    two are written by different stages and either may exist alone.
    Unlike a dossier, this residue is **self-healing**: both files are
    regenerated wholesale by the next enrichment run, so a hit here is a
    staleness that expires rather than one a human must go and remove.
    """
    named = []
    for path, extract in (
        (config.TOPIC_SET_PATH, _topic_set_citekeys),
        (config.TOPICS_PATH, _topics_citekeys),
    ):
        if path.is_file():
            named.append((path, extract(json.loads(path.read_text(encoding="utf-8")))))
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


def _dossier_files() -> list[Path]:
    """Every `evidence.md`/`sections.md` under `content/dossiers/`, in a
    stable order. Walked off disk rather than through
    `chitragupta.dossier`, which is the drafting layer's package."""
    found: list[Path] = []
    for name in DOSSIER_FILES:
        found += config.DOSSIERS_DIR.rglob(name)
    return sorted(found)


def _scan_dossiers(citekeys: list[str]) -> dict[str, Hit]:
    """Mentions in the dossiers of drafts already written."""
    texts = [
        (path, path.read_text(encoding="utf-8", errors="replace")) for path in _dossier_files()
    ]
    hits = {}
    for citekey in citekeys:
        pattern = _pattern(citekey)
        counts = [(path, len(pattern.findall(text))) for path, text in texts]
        counts = [(path, n) for path, n in counts if n]
        if counts:
            where = tuple(f"{path} ({n})" for path, n in counts)
            hits[citekey] = Hit(DOSSIERS, sum(n for _path, n in counts), "mention", where)
    return hits


def _scan_chroma(citekeys: list[str]) -> tuple[dict[str, Hit], "str | None"]:
    """Chunk vectors, and -- second element -- why they could not be
    counted when they could not.

    `content/chroma/` is checked for existence *before* the stack is
    probed, and the collection is read through `overlap_chroma`, which
    never creates one. A corpus embedded under a different
    `[embedding].model` lives in a differently named collection and
    reads as zero here; that is a true statement about the collection
    this configuration would use, not a miscount.
    """
    if not config.CHROMA_DIR.is_dir():
        return {}, None
    stack = overlap_chroma.optional_stack()
    if stack is None:
        return {}, (
            f"{CHROMA}: {config.CHROMA_DIR} exists but the enrich group is not "
            f"installed, so vectors were not scanned."
        )
    collection = overlap_chroma.built_collection(stack[0])
    if collection is None:
        return {}, None
    rows = chroma_paging.all_rows(
        collection, where={"citekey": {"$in": sorted(citekeys)}}, include=["metadatas"]
    )
    hits = {}
    for citekey in citekeys:
        count = sum(1 for meta in rows["metadatas"] if meta.get("citekey") == citekey)
        if count:
            hits[citekey] = Hit(CHROMA, count, "vector", (str(config.CHROMA_DIR),))
    return hits, None


def scan(citekeys: list[str]) -> tuple[dict[str, list[Hit]], list[str]]:
    """`({citekey: [Hit, ...]}, [note, ...])` for every citekey given.

    A citekey with no residue is present with an empty list, because
    "nothing else references this" is the answer the caller most wants
    to be able to say out loud. The notes are the artefact classes that
    could not be scanned on this host.
    """
    chroma, note = _scan_chroma(citekeys)
    by_class = [
        _scan_overlap(citekeys),
        _scan_topic_graph(citekeys),
        _scan_topic_membership(citekeys),
        _scan_dossiers(citekeys),
        chroma,
    ]
    found = {
        citekey: [hits[citekey] for hits in by_class if citekey in hits] for citekey in citekeys
    }
    return found, [note] if note else []


def report(citekeys: list[str]) -> None:
    """Print what still references each citekey, grouped by artefact.

    Called with the citekeys a run is about to prune (or, in the default
    report-only mode, the ones it is inviting a human to prune). Prints
    nothing at all when there are none, so a routine sync pays neither
    the scan nor the noise.
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
            # "(s)" rather than a singular/plural branch, matching the
            # spelling the rest of sync's stdout already uses ("1 stale
            # item(s)") -- one shape, and one less branch to cover.
            print(f"      {hit.artefact:<16} {hit.count} {hit.unit}(s): {', '.join(hit.where)}")
    for note in notes:
        print(f"    NOTE: {note}")
    print("    Reported, not repaired -- nothing above is touched by this run.")
