"""Smith-Waterman local alignment over a sentence-similarity matrix.

The dependency-free, I/O-free half of tier 3; `overlap_embed.py` decides
what to compare and is the only caller. Kept apart so the arithmetic is
testable against a hand-written matrix rather than through a fake model.

A bi-encoder gives one number per sentence pair and a finding needs a
span; the alignment turns one into the other (#164). Stdlib only: by
the time a matrix reaches here it is lists of floats.
"""

from dataclasses import dataclass

# --------------------------------------------------------------------------
# Tuning constants: module constants, not config, as tier 2's are (policy,
# not a per-host choice). Each was measured: bench/RESULTS.md's embedding
# tier section and bench/bench_overlap_embed.py.
# --------------------------------------------------------------------------

# Subtracted from every cosine so the alignment is local. Not a sameness
# threshold: unrelated sentences in one field cosine 0.4-0.5 on
# all-mpnet-base-v2, so it sits above that band.
TAU = 0.62

# Low on purpose: splicing or splitting sentences is the normal paraphrase.
GAP_PENALTY = 0.25

# Structural, not editorial: it only stops the traceback. overlap_embed
# ranks instead of thresholding, so anything above zero would be a policy
# knob by the back door.
MIN_ALIGNMENT_SCORE = 0.0

# One section may lean on one paper in two places; the cap stops a
# pathological pair filling a report with weaker tails.
MAX_ALIGNMENTS_PER_PAIR = 3


@dataclass(frozen=True)
class Alignment:
    """One local alignment: half-open sentence-index ranges on each side,
    the score, and which draft sentences were *matched* rather than
    absorbed by a gap (the evidence inside the span, like tier 1's
    `matched_words`).
    """

    draft_start: int
    draft_end: int
    source_start: int
    source_end: int
    score: float
    matched: tuple[int, ...] = ()


# Traceback directions, as (row step, column step). `_STOP` is the zero
# cell every local alignment terminates on.
_STOP = (0, 0)
_DIAGONAL = (1, 1)
_UP = (1, 0)
_LEFT = (0, 1)


def _fill(scores: list[list[float]], gap_penalty: float) -> tuple[list[list[float]], dict]:
    """The Smith-Waterman DP table over `scores`, plus the traceback
    pointer for each cell. `scores[i][j]` is already `cosine - TAU`.
    """
    rows, columns = len(scores), len(scores[0])
    table = [[0.0] * (columns + 1) for _ in range(rows + 1)]
    pointers = {}
    for i in range(1, rows + 1):
        for j in range(1, columns + 1):
            candidates = (
                (table[i - 1][j - 1] + scores[i - 1][j - 1], _DIAGONAL),
                (table[i - 1][j] - gap_penalty, _UP),
                (table[i][j - 1] - gap_penalty, _LEFT),
                (0.0, _STOP),
            )
            best, direction = max(candidates)
            table[i][j] = best
            pointers[(i, j)] = direction
    return table, pointers


def _trace(table: list[list[float]], pointers: dict, cell: tuple[int, int]) -> Alignment:
    """Walk back from `cell` to the zero cell that opened this alignment.

    That cell is not part of it, which makes the ranges half-open 0-based
    sentence indices. Row and column 0 also stop the walk: they carry no
    pointer.
    """
    i, j = cell
    matched = []
    while i and j and pointers[(i, j)] != _STOP:
        di, dj = pointers[(i, j)]
        if (di, dj) == _DIAGONAL:
            matched.append(i - 1)
        i, j = i - di, j - dj
    return Alignment(
        draft_start=i,
        draft_end=cell[0],
        source_start=j,
        source_end=cell[1],
        score=table[cell[0]][cell[1]],
        matched=tuple(reversed(matched)),
    )


def _max_cell(table: list[list[float]], used_rows: set[int]) -> tuple[int, int] | None:
    """The highest-scoring cell whose row is not already spoken for, or
    `None` when nothing positive is left.

    Rows, not cells, so `MAX_ALIGNMENTS_PER_PAIR` means separate places in
    the section, not tracebacks off one peak.
    """
    best = None
    best_score = 0.0
    for i in range(1, len(table)):
        if i in used_rows:
            continue
        row = table[i]
        for j in range(1, len(row)):
            if row[j] > best_score:
                best, best_score = (i, j), row[j]
    return best


def align(
    scores: list[list[float]],
    gap_penalty: float = GAP_PENALTY,
    minimum_score: float = MIN_ALIGNMENT_SCORE,
    limit: int = MAX_ALIGNMENTS_PER_PAIR,
) -> list[Alignment]:
    """Up to `limit` local alignments over `scores`, strongest first, no
    two sharing a draft sentence. An empty matrix returns nothing: an
    unalignable pair is ordinary, not malformed.
    """
    if not scores or not scores[0]:
        return []
    table, pointers = _fill(scores, gap_penalty)
    found = []
    used_rows: set[int] = set()
    while len(found) < limit:
        cell = _max_cell(table, used_rows)
        if cell is None:
            break
        alignment = _trace(table, pointers, cell)
        if alignment.score < minimum_score:
            # Every weaker alignment is below the floor too.
            break
        # A traceback that runs into claimed rows is dropped, but its rows
        # are retired anyway, which guarantees the loop terminates.
        used_rows |= set(range(alignment.draft_start + 1, alignment.draft_end + 1))
        if not _overlaps(alignment, found):
            found.append(alignment)
    return found


def _overlaps(alignment: Alignment, found: list[Alignment]) -> bool:
    return any(
        alignment.draft_start < other.draft_end and other.draft_start < alignment.draft_end
        for other in found
    )
