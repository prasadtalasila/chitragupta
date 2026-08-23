"""Smith-Waterman local alignment over a sentence-similarity matrix.

The half of tier 3 that has no dependencies and no I/O: given a matrix of
already-computed, already-shifted similarity scores, find the contiguous
passage pairs inside it. `chitragupta/overlap_embed.py` is the half that decides
which sentences to compare and where the numbers come from, and it is the
only caller.

Separate modules because the two halves fail differently and are checked
differently. This one is arithmetic -- deterministic, exhaustively
testable against a hand-written matrix, and correct or not on its own
terms. That one depends on an optional embedding stack, a built chroma
collection, Docling sidecars and a draft's dossier, any of which can be
absent, and most of what it does is decide what to do when they are.
Keeping them together would mean the alignment could only be exercised
through a fake model.

**Why Smith-Waterman and not a threshold.** #164 makes the argument:
`scan_findings` already walks the draft in order, matches grams into the
corpus index and merges consecutive hits into a maximal run -- that is a
one-dimensional local alignment whose match test is equality, and `--gap`
is its gap tolerance. This is the same walk with a scoring matrix in
place of that test. A bi-encoder gives one number per sentence pair; a
finding needs a span, and the alignment is what turns the first into the
second.

Stdlib only, and it stays that way: matrix arithmetic belongs to whatever
produced the vectors (`sentence-transformers` hands back numpy arrays and
`@` on two of those is the fast path), and by the time a matrix reaches
here it is a list of lists of floats.
"""

from dataclasses import dataclass

# --------------------------------------------------------------------------
# Tuning constants
#
# Named module constants rather than a new `[overlap]` TOML table,
# following tier 2's own precedent (`MAX_NUMERIC_SHARE`,
# `LONG_RUN_WORDS`): these are project-wide detection policy, not a
# per-host choice, and DEVELOPER-AGENTS.md's no-speculative-abstraction
# rule says not to invent config surface nothing has asked for. Every
# value below was measured, not guessed -- see `bench/RESULTS.md`'s
# embedding-tier section and `bench/bench_overlap_embed.py`.
# --------------------------------------------------------------------------

# Subtracted from every cosine before it enters the alignment, which is
# what makes the alignment *local*: a pair scoring below this contributes
# negatively and terminates the run rather than letting it drift across
# unrelated prose. It is not a "these two sentences are the same"
# threshold and must not be read as one -- in a single-field corpus,
# two unrelated sentences about digital twins routinely cosine at 0.4-0.5
# on all-mpnet-base-v2, which is exactly why the value sits above that
# band rather than at some absolute notion of similarity.
TAU = 0.62

# Charged for a sentence skipped on one side. Low, deliberately: a
# paraphrase that splices two source sentences into one, or splits one
# into two, is the normal case rather than the exception, and a penalty
# steep enough to forbid it would restrict this tier to the
# one-sentence-to-one-sentence rewrites tier 2 can already almost see.
GAP_PENALTY = 0.25

# The floor a completed alignment must clear to be traced at all.
# Structural rather than editorial: it is what stops the traceback loop
# once the table holds nothing positive left, and it is *not* a
# report/don't-report decision. `chitragupta/overlap_embed.py` ranks and caps
# instead of thresholding, because a threshold provably cannot work in
# this corpus -- see `overlap_embed.report`. Anything above zero would
# make this a policy knob by the back door, so it is exactly zero.
MIN_ALIGNMENT_SCORE = 0.0

# Alignments taken per (section, source) pair. One section can lean on
# one paper in two separate places, and reporting only the strongest
# would hide the second; a cap keeps a pathological pair from filling a
# report with progressively weaker tails of the same passage.
MAX_ALIGNMENTS_PER_PAIR = 3


@dataclass(frozen=True)
class Alignment:
    """One local alignment: half-open sentence-index ranges on each side,
    the score that traced back to it, and which draft sentences inside
    that range were actually *matched* rather than absorbed by a gap.

    `matched` is the counterpart of tier 1's `matched_words` and tier 2's
    same-parity-position count: the span is what a reader is pointed at,
    and this is the evidence inside it. A paraphrase that splices two
    source sentences into one leaves the second draft sentence on a gap
    step, inside the reported span but not itself matched.
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
    pointer for each cell.

    `scores[i][j]` is already `cosine - TAU` -- shifted, so unrelated
    pairs are negative and an alignment terminates rather than running
    off the ends. That shift is the only thing separating this from tier
    1's own merge: `scan_findings` walks the draft in order, matches into
    the corpus index and merges consecutive hits into a maximal run,
    which is a one-dimensional local alignment whose match test is
    equality. This is the same walk with a scoring matrix in place of
    that test (#164).
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

    The walk stops at the first cell scoring zero -- that cell is *not*
    part of the alignment, which is what makes the returned ranges
    half-open 0-based sentence indices: table row `r` is sentence `r-1`,
    so stopping on row `i` means the alignment starts at sentence `i`.

    Row 0 and column 0 stop it too. They are the table's zero border and
    carry no pointer, and an alignment that reaches the very first
    sentence on either side arrives there with a diagonal step rather
    than by finding a zero cell first.
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

    Rows, not cells: an alignment claims a run of *draft* sentences, and
    the second-best alignment over the same draft sentences is the same
    finding pointing at a slightly different part of the source. Barring
    the rows is what makes `MAX_ALIGNMENTS_PER_PAIR` mean "two places in
    this section", not "two tracebacks off one peak".
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
    two sharing a draft sentence.

    `scores` is `cosine - TAU`; an empty matrix (no draft sentences, or a
    source with no usable passages) has nothing to align and returns
    nothing rather than raising -- an unalignable pair is an ordinary
    outcome here, not a malformed request.
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
            # The best remaining alignment is already below the floor, so
            # every weaker one is too -- stop rather than keep tracing.
            break
        # A traceback can still *run back into* rows an earlier alignment
        # claimed, even though `_max_cell` would not have started in one.
        # Such a peak is dropped rather than reported, and its rows are
        # retired anyway -- which is what makes this loop terminate (the
        # used set grows every iteration) and what makes `limit` mean
        # "this many separate places in this section" rather than "this
        # many tracebacks off one passage".
        used_rows |= set(range(alignment.draft_start + 1, alignment.draft_end + 1))
        if not _overlaps(alignment, found):
            found.append(alignment)
    return found


def _overlaps(alignment: Alignment, found: list[Alignment]) -> bool:
    return any(
        alignment.draft_start < other.draft_end and other.draft_start < alignment.draft_end
        for other in found
    )
