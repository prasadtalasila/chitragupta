"""What `retrieval.md` was searched for: the distinct queries a draft
ran, paired with the collection or origin each was scoped to.

The read side of `_retrieval.py` (#467), which re-exports the public
names so no caller changes.
"""

from pathlib import Path

from chitragupta.dossier import RETRIEVAL_MD, _REVISION_MARKER_MODE, _ROW_SPLIT


def _retrieval_rows(dossier: Path) -> list[list[str]]:
    """The parseable rows of `retrieval.md`, normalised to eleven cells:
    date, mode, query, asked, results, chars, collection, origin, expanded,
    k1, b.

    An integer `chars` cell tells a logged call from the template's header
    rows; unparsable rows are skipped. Older widths (before #254, #455,
    #789, #788) are padded with empty cells, which is why every column is
    appended at the *end*. **Ten is deliberately not accepted**: nothing
    ever wrote a `k1` without `b`, so a ten-cell row is torn, and padding
    it would hide the unrecorded setting those columns exist to catch.
    """
    path = dossier / RETRIEVAL_MD
    if not path.is_file():
        return []
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        # Split on unescaped pipes only: a query pipe is logged as `\|`.
        cells = [cell.strip() for cell in _ROW_SPLIT.split(line.strip().strip("|"))]
        if len(cells) not in (6, 7, 8, 9, 11):
            continue
        try:
            int(cells[5])
        except ValueError:
            continue
        cells += [""] * (11 - len(cells))
        rows.append(cells)
    return rows


def recorded_queries(dossier: Path) -> list[str]:
    """The distinct queries this draft was retrieved with, first seen first.

    The only record of what the draft went looking for, so corpus growth
    can be ranked against it. Skips `mark_revision` boundary rows, whose
    third cell is a label, not a query. Ignores collection; drift reads
    `recorded_queries_with_collection` instead (#254).
    """
    seen: dict[str, None] = {}
    for cells in _retrieval_rows(dossier):
        if cells[1] == _REVISION_MARKER_MODE:
            continue
        # Unescape the pipe so the ranker sees the query as typed.
        query = cells[2].replace("\\|", "|").strip()
        if query:
            seen[query] = None
    return list(seen)


def recorded_queries_with_collection(dossier: Path) -> list[tuple[str, str]]:
    """The distinct (query, collection) pairs this draft was retrieved
    with, first seen first (#254).

    Empty collection means corpus-wide (also how old rows read).
    Deduplicated on the *pair*, or a scoped call would silently widen.
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
    first seen first (#455).

    `origin` is `"declared"`, `"extended"`, or `""`. An empty origin
    (including pre-`outline.md` rows) is neither declared nor extended,
    so callers must treat it as out of scope, not compliance.
    Deduplicated on the pair. A projection of
    `recorded_queries_with_evidence`, so the two cannot disagree.
    """
    return [(query, origin) for query, origin, _ in recorded_queries_with_evidence(dossier)]


def _returned_something(cell: str) -> bool:
    """Whether a row's `results` cell reports at least one result.

    An unreadable (hand-edited) cell reads as **True**: reading a typo as
    "returned nothing" would manufacture a finding.
    """
    try:
        return int(cell) > 0
    except ValueError:
        return True


def recorded_queries_with_evidence(dossier: Path) -> list[tuple[str, str, bool]]:
    """The distinct (query, origin, returned-anything) triples this draft
    was retrieved with, first seen first (#480).

    **Binary, not a count**: `docs/AUTO-IMPROVEMENT.md`'s R3 forbids an
    unattended check optimising a continuous score. **Folded before
    deduplicating**, so a query that returned nothing and then four after
    a reformulation reads as evidence retrieved.
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
