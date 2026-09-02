"""What `retrieval.md` was searched for: the distinct queries a draft
ran, paired with the collection or origin each was scoped to.

Split out of `_retrieval.py` (#467): that module writes `retrieval.md`
(`log_retrieval`, `mark_revision`) and turns it into cost accounting
(`retrieval_cost_by_revision`); this one only reads it
back as *what was searched for*, which is a distinct question with its
own three-function family (`recorded_queries` and two siblings). #455's
origin column pushed `_retrieval.py` back over C2's 250-line ceiling,
and unlike the write path and the cost accounting, nothing requires
these four to live in that file rather than merely be reachable through
it -- `_retrieval.py` re-exports the three public names where they used
to be defined, so no existing caller changes.
"""

from pathlib import Path

from chitragupta.dossier import RETRIEVAL_MD, _REVISION_MARKER_MODE, _ROW_SPLIT


def _retrieval_rows(dossier: Path) -> list[list[str]]:
    """The parseable rows of `retrieval.md`, normalised to eight cells:
    date, mode, query, asked, results, chars, collection, origin.

    An integer `chars` cell is what separates a logged call from the
    template's own header and separator rows, which otherwise parse to
    six, seven or eight cells like any other. Advisory like every other
    read here: a hand-edited row that doesn't parse is skipped rather
    than raising.

    A six-cell row -- every row written before #254 added the collection
    column -- or a seven-cell row -- every row written before #455 added
    the origin column -- is padded with trailing empty cells rather than
    rejected, so it reads back exactly as it always has: a call with no
    recorded collection and no recorded origin, indistinguishable from
    one explicitly logged corpus-wide with no declared/extended origin.
    """
    path = dossier / RETRIEVAL_MD
    if not path.is_file():
        return []
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        # Split on unescaped pipes only: `log_retrieval` writes a query
        # containing a pipe as `\|`, which is markdown's literal, and
        # splitting there would cut the row into extra cells.
        cells = [cell.strip() for cell in _ROW_SPLIT.split(line.strip().strip("|"))]
        if len(cells) not in (6, 7, 8):
            continue
        try:
            int(cells[5])
        except ValueError:
            continue
        cells += [""] * (8 - len(cells))
        rows.append(cells)
    return rows


def recorded_queries(dossier: Path) -> list[str]:
    """The distinct queries this draft was retrieved with, first seen first.

    `retrieval.md` was written to measure what a run cost, and this is
    the second thing it turns out to be good for: it is the only record
    of *what this draft went looking for*, which is what makes "the
    corpus grew" answerable as "and here is the part of the growth this
    draft would have wanted". Deduplicated because a reformulated search
    logs the same query more than once, and running it twice would just
    report the same candidate twice.

    Skips `mark_revision`'s boundary rows. Their third cell holds the
    `--label` text, not a query -- without this exclusion a label like
    "shorten intro" would be ranked against the corpus as if someone had
    searched for it, both here and in `recorded_queries_with_collection`,
    its sibling below, which skips them the same way.

    Says nothing about the collection a call was scoped to --
    `recorded_queries_with_collection` is the sibling that does, and is
    what `dossier status`'s drift check reads instead of this, so that a
    collection-scoped draft's candidates are ranked over the shelf it
    actually used (#254) rather than the whole corpus.
    """
    seen: dict[str, None] = {}
    for cells in _retrieval_rows(dossier):
        if cells[1] == _REVISION_MARKER_MODE:
            continue
        # `log_retrieval` escapes a pipe on the way in; unescape it so the
        # query goes to the ranker as the caller actually typed it.
        query = cells[2].replace("\\|", "|").strip()
        if query:
            seen[query] = None
    return list(seen)


def recorded_queries_with_collection(dossier: Path) -> list[tuple[str, str]]:
    """The distinct (query, collection) pairs this draft was retrieved
    with, first seen first -- `recorded_queries`'s sibling (#254).

    An empty collection means the call was corpus-wide, which is also
    what a row logged before this column existed means -- `_retrieval_rows`
    pads it in, so an old dossier reads back exactly as it always has.

    Deduplicated on the *pair*, not the query alone: the same query asked
    once corpus-wide and once scoped to a shelf is two different calls,
    and collapsing them the way `recorded_queries` does would silently
    widen the scoped one back to corpus-wide.
    """
    seen: dict[tuple[str, str], None] = {}
    for cells in _retrieval_rows(dossier):
        if cells[1] == _REVISION_MARKER_MODE:
            continue
        query = cells[2].replace("\\|", "|").strip()
        if not query:
            continue
        collection = cells[6].replace("\\|", "|").strip()
        seen[(query, collection)] = None
    return list(seen)


def recorded_queries_with_origin(dossier: Path) -> list[tuple[str, str]]:
    """The distinct (query, origin) pairs this draft was retrieved with,
    first seen first -- `recorded_queries`'s other sibling (#455).

    `origin` is `"declared"`, `"extended"`, or `""` for a call that named
    neither -- which is also what a row logged before this column existed
    reads as, padded in by `_retrieval_rows`. Unlike
    `recorded_queries_with_collection`'s empty `collection`, an empty
    `origin` is not read as any particular thing by this function; a
    caller comparing this against `outline.md`'s declared list (the
    reader `_outline.declared_vs_actual` is) has to treat it as out of
    scope, not as compliance, because a pre-`outline.md` call was
    neither declared nor extended.

    Deduplicated on the pair, the same way `recorded_queries_with_collection`
    is: the same query logged once declared and once extended is two
    different facts about the run, and collapsing them would hide that a
    declared query also had to be extended.

    Says nothing about what a call *returned* --
    `recorded_queries_with_evidence` is the sibling that does, and this
    function is now a projection of it, so the two cannot disagree about
    which pairs exist.
    """
    return [(query, origin) for query, origin, _ in recorded_queries_with_evidence(dossier)]


def _returned_something(cell: str) -> bool:
    """Whether a row's `results` cell reports at least one result.

    An unreadable cell -- a hand edit, since nothing else writes this
    file -- reads as **True**, not as zero. The asymmetry is deliberate:
    a caller uses this to report a declared query the corpus could not
    answer, and reading a typo as "returned nothing" would manufacture
    that finding out of the typo. Silence is the safe direction here,
    the same way `_retrieval_rows` skips a row it cannot parse rather
    than raising on it.
    """
    try:
        return int(cell) > 0
    except ValueError:
        return True


def recorded_queries_with_evidence(dossier: Path) -> list[tuple[str, str, bool]]:
    """The distinct (query, origin, returned-anything) triples this draft
    was retrieved with, first seen first -- the family's fourth member
    (#480).

    **Binary, not a count.** The question a caller has is whether a
    declared query can be said to have covered its sub-theme, and that is
    "evidence came back or it did not" -- `docs/AUTO-IMPROVEMENT.md`'s R3
    forbids an unattended check from optimising a continuous score, and a
    result *count* handed out here is exactly the thing someone would
    later average into one.

    **Folded before the pair is deduplicated, which is the whole reason
    this exists rather than a `results` column bolted onto
    `recorded_queries_with_origin`.** A query searched twice -- nothing,
    then four after a reformulation -- must read as evidence retrieved;
    deduplicating first would keep whichever row happened to come first
    and report the reformulation as a gap the draft had in fact closed.
    """
    seen: dict[tuple[str, str], bool] = {}
    for cells in _retrieval_rows(dossier):
        if cells[1] == _REVISION_MARKER_MODE:
            continue
        query = cells[2].replace("\\|", "|").strip()
        if not query:
            continue
        origin = cells[7].replace("\\|", "|").strip()
        key = (query, origin)
        seen[key] = seen.get(key, False) or _returned_something(cells[4])
    return [(query, origin, evidence) for (query, origin), evidence in seen.items()]
