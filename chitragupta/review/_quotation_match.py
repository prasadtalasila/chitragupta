"""Does this span appear in that source? The whole of C3's decision, in
one place, so `quotation.py` holds the CLI and this holds the argument.

**One normalised character stream, not a word list**: both sides reduced
to `[a-z0-9]` after NFKD, compared with `str.find`, so every caveat of
#383 (line-break and soft hyphens, ligatures, whitespace, curly quotes)
vanishes by construction. NFKD, not NFKC: NFKC leaves `é` precomposed
and the filter deletes it (`café` -> `caf`), false-absenting European
names. Word lists (`verbatim_check/_corpus.py`, `overlap_index.py`) split
`environ-\nment` and cost 9 of 124 exact hits on the 189 spans of
`plans/c3-quotation-integrity.md`. The stated cost: `"the rapist"` and
`"therapist"` flatten alike, which never occurred and can only turn
absent into found.

Further normalisations, measured (70 raw findings to 33 on the 189 spans):
`strip_markers` drops `[30]`-style markers from the source, and
`fragments` splits the quote on an elision or editorial insertion, still
matched in order and exactly. An elision at either end of a quote leaves
one fragment (#775; see the guard in `locate`). Upstream,
`dossier/_evidence_check.normalise_quote` strips a trailing `(p. 24)`
and enclosing quotation marks (#1174). Declined: stripping an
abbreviation gloss like "(DT)" recovers 1 span and loses 12
(`plans/775-quotation-residual-absents.md`). #775's re-run over 206 spans
took residual absents 40 -> 38; both figures are upper bounds, since
extraction attributes a span to the nearest preceding citekey.

**Per passage, never over a concatenated document**: flattening fuses
passage seams, so a straddling span would match and report a wrong page,
and a false `found` is the outcome nobody re-reads. The one widening,
`ADJACENT` pairs, is bounded by construction.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from chitragupta.passages import Passage, distinctive

# Numeric-only: stripping `[sic]` would eat content a quote may carry, and
# author-year forms would need parsing.
_REFERENCE_MARKER = re.compile(r"\[[\d\s,;–—-]+\]")

# Both mean "the source differs here": cut out, surrounding pieces aligned.
_ELISION = re.compile(r"\s*(?:\[[^\]]*\]|\.\.\.|…)\s*")

# Flattened length below which a fragment is a sliver. Not tuned: over the
# 103 fragments of plans/c3-quotation-integrity.md the total is identical
# from 6 to 15. The low end is taken because a larger value drops short
# real anchors (`"operators [who] can start"` leaves 9 characters) and the
# corpus held no such span. Published with its sensitivity, per R3, as
# `dossier/_evidence_check.py`'s `_NGRAM`.
SLIVER = 8

# The bound *is* the safety property (see the module docstring).
ADJACENT = 2


def flatten(text: str) -> str:
    """`text` as a comparable character stream: NFKD, lowercased, and
    everything that is not `[a-z0-9]` removed."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text).lower())


def strip_markers(text: str) -> str:
    return _REFERENCE_MARKER.sub(" ", text)


def fragments(quote: str) -> list[str]:
    """`quote`'s flattened pieces either side of its elisions, slivers
    dropped. One piece can still be an elision at an end (#775); `locate`
    decides that.
    """
    pieces = [flatten(piece) for piece in _ELISION.split(quote)]
    return [piece for piece in pieces if len(piece) >= SLIVER]


def _ordered_in(pieces: list[str], haystack: str) -> bool:
    """Every piece present, in order, without overlapping."""
    at = 0
    for piece in pieces:
        found = haystack.find(piece, at)
        if found < 0:
            return False
        at = found + len(piece)
    return True


def _windows(streams: list[tuple[int | None, str]], size: int) -> list[tuple[list[int], str]]:
    """(pages, joined stream) for each run of `size` consecutive passages,
    each page once. Takes pre-flattened streams so NFKD, the expensive
    part, runs once per passage rather than per window size.
    """
    found = []
    for start in range(len(streams) - size + 1):
        run = streams[start : start + size]
        pages: list[int] = []
        for page, _ in run:
            if page is not None and page not in pages:
                pages.append(page)
        found.append((pages, "".join(stream for _, stream in run)))
    return found


def locate(quote: str, passages: list[Passage]) -> tuple[str, list[int]] | None:
    """(tier, pages) for `quote` in `passages`, or None if it is nowhere.

    Tiers: exact in one passage, exact across a pair, elided in one, elided
    across a pair; returned so a reader sees an `elided` match. Every exact
    tier precedes every elided one: a span contiguous across two passages
    must not be reported as an alignment around an ellipsis.
    """
    needle = flatten(quote)
    if not needle:
        return None
    streams = [(p.page, flatten(strip_markers(p.text or ""))) for p in passages]
    windows = {size: _windows(streams, size) for size in (1, ADJACENT)}
    for size, tier in ((1, "exact"), (ADJACENT, "exact-pair")):
        for pages, haystack in windows[size]:
            if needle in haystack:
                return tier, pages
    pieces = fragments(quote)
    # One fragment is still an elided match when the quote has an elision
    # at an end (#775): "the topic is [unresolved]." leaves an empty tail,
    # and the survivor matches exactly. `_ELISION.search`, not
    # `len(pieces) == 1` alone, so an elision-free quote stays `absent`
    # rather than being relabelled `elided`. On #775's 206 spans: 2
    # recoveries, 0 lost. Least evidenced near `SLIVER`: both survivors were
    # long, so a short lone fragment is untested rather than shown safe.
    least = 1 if _ELISION.search(quote) else 2
    if len(pieces) < least:
        return None
    for size, tier in ((1, "elided"), (ADJACENT, "elided-pair")):
        for pages, haystack in windows[size]:
            if _ordered_in(pieces, haystack):
                return tier, pages
    return None


def near_miss(quote: str, passages: list[Passage]) -> tuple[float, int | None]:
    """The page whose own words cover most of `quote`'s, and that share,
    so a lightly edited quote is told apart from a fabricated one.

    Scored on unstripped words: `passages.distinctive` drops words of two
    characters, so a marker like `30` cannot inflate it (verified on the
    189-span corpus, not re-checked on #775's).
    """
    keys = distinctive(quote)
    if not keys:
        return 0.0, None
    best = (0.0, None)
    for passage in passages:
        share = len(keys & passage.words) / len(keys)
        if share > best[0]:
            best = (share, passage.page)
    return best


@dataclass
class Checked:
    """One `quote:`, and what became of it."""

    citekey: str
    quote: str
    verdict: str
    tier: str | None = None
    pages: list[int] = field(default_factory=list)
    near_miss_page: int | None = None
    near_miss_score: float = 0.0
    reason: str | None = None
    # Its place among its block's distinct `quote:` lines (#1174).
    index: int = 1
    of: int = 1


def check_one(citekey: str, quote: str, found: list, reason: str | None) -> Checked:
    """`quote`'s verdict against one source's passages. A source without
    reading-ordered text is `unverifiable` before comparing, not `absent`
    after; the near-miss page is still reported, so a human knows which
    page to open.
    """
    quotable = [p for p in found if p.quotable]
    if not quotable:
        score, page = near_miss(quote, found)
        return Checked(
            citekey,
            quote,
            "unverifiable",
            near_miss_page=page,
            near_miss_score=round(score, 3),
            reason=reason or "no reading-ordered passages -- only page-level text",
        )
    located = locate(quote, quotable)
    if located is not None:
        tier, pages = located
        return Checked(citekey, quote, "found", tier=tier, pages=pages)
    score, page = near_miss(quote, quotable)
    return Checked(citekey, quote, "absent", near_miss_page=page, near_miss_score=round(score, 3))
