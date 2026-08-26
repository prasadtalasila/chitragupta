"""Does this span appear in that source? The whole of C3's decision, in
one place, so `quotation.py` holds the CLI and this holds the argument.

**One normalised character stream, not a word list.** Both sides are
reduced to `[a-z0-9]` after NFKD, and the comparison is `str.find`.
Every caveat issue #383 names then vanishes by construction rather than
by a list of special cases: a line-break hyphen, a soft hyphen, a
ligature, collapsed whitespace and a curly quotation mark are all simply
not `[a-z0-9]`.

**NFKD rather than NFKC**, which the plan wrote and which is wrong here.
Both expand a ligature, but NFKC leaves a precomposed `é` precomposed,
so the filter *deletes* it: `café` flattens to `caf` and `Müller` to
`mller`. NFKD decomposes the letter first, the combining mark is dropped
as non-alphanumeric, and the base letter survives -- `cafe`, `muller`.
Deleting a letter is not a normalisation, it is a corruption that both
sides only sometimes share, and it would false-absent any quotation
carrying a European name or loanword. `verbatim_check/_corpus.py`'s `norm` and
`overlap_index.py`'s `_norm` are *word lists*, and a word list splits
`environ-\nment` into two tokens where the quote has one -- the exact
false "not found" #383 warns about. Measured over the 189 real quoted
spans in `plans/c3-quotation-integrity.md`, that difference alone costs
9 of 124 exact-tier hits.

The cost is real and stated rather than discovered later: discarding
word boundaries makes `"the rapist"` and `"therapist"` flatten alike.
For a span of quotation length that is theoretical -- it did not occur
once in 189 -- and it fails in the safe direction, since it can only
turn an absent into a found, never invent a finding.

**Two normalisations #383 does not name, which measured larger than the
ones it does.** Without both, the matcher reports 70 findings on that
corpus where the answer is 33.

1. `strip_markers` drops an inline reference marker from the *source*.
   A passage reads "...circumstances and hypotheses [30]." and a correct
   quotation drops the marker; flattened, a bare `30` sits inside the
   span and a perfect quotation reads as fabricated.
2. `fragments` splits the *quote* on an elision or an editorial
   insertion. `"PE refers to the physical entity ... CN is the
   connection"` is not contiguous in the source and is not a defect.
   Order is still required, so this stays exact -- ordered subsequence
   matching, with no similarity score anywhere in it.

**Per passage, never over a concatenated document.** Flattening strips
every separator, so joining the whole source fuses passage seams: `...end
of para` + `Beginning of...` becomes one stream, and a span straddling
the seam matches and reports a page it is not on. A false `found` is
worse here than a false `absent` -- it is the outcome nobody re-reads.
The one widening is `ADJACENT` pairs, which is bounded by construction.

Stdlib only, like everything else this layer runs at interpreter tier 1.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from chitragupta.passages import Passage, distinctive

# A numeric bracket group: `[30]`, `[1, 2]`, `[1-3]`. Deliberately
# numeric-only -- stripping `[sic]` would eat content a quote may
# legitimately carry, and `(Smith 2020)` would need author-year parsing.
_REFERENCE_MARKER = re.compile(r"\[[\d\s,;–—-]+\]")

# An elision or an editorial substitution. Both mean "the source differs
# here", so both are cut out and the surrounding fragments aligned.
_ELISION = re.compile(r"\s*(?:\[[^\]]*\]|\.\.\.|…)\s*")

# Flattened characters below which a fragment is a sliver rather than
# something to align on. **Not tuned**: across the 103 fragments the 189
# measured spans in plans/c3-quotation-integrity.md produce, the
# confirmed total is identical at every value from 6 to 15 and falls
# only at 20. The one thing it must exclude is the empty string a
# leading or trailing elision leaves behind -- 10 of the 11 sub-12
# fragments there are length zero.
#
# Given a flat region, take its *low* end rather than its middle. The
# corpus gives no reason to prefer a larger value, and a larger one
# silently discards a short but real anchor: `"operators [who] can start
# developing"` leaves a 9-character first fragment, which at 12 is
# dropped, leaving one fragment, which is not an elision at all -- so a
# correct quotation reports absent. The measurement could not see that
# because it happened to contain no such span, which is the argument for
# the low end rather than the comfortable middle.
#
# R3 bars a continuous *score* from being optimised, and nothing here
# is: this is published with its sensitivity, the same discipline
# `dossier/_evidence_check.py` applies to its own `_NGRAM`.
SLIVER = 8

# How many consecutive passages may be joined before matching. Two, and
# the reason for the constant rather than a literal is that the bound
# *is* the safety property -- see the module docstring.
ADJACENT = 2


def flatten(text: str) -> str:
    """`text` as a comparable character stream: NFKD, lowercased, and
    everything that is not `[a-z0-9]` removed."""
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", text).lower())


def strip_markers(text: str) -> str:
    """`text` with inline numeric reference markers replaced by a space."""
    return _REFERENCE_MARKER.sub(" ", text)


def fragments(quote: str) -> list[str]:
    """`quote`'s flattened pieces either side of its elisions, slivers
    dropped. Fewer than two means there was nothing to elide."""
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
    """(pages, joined stream) for each run of `size` consecutive
    passages. A page appears once even where consecutive passages share
    it, so a hit inside one page does not report `[4, 4]`.

    Takes already-flattened streams rather than `Passage`es so each
    passage is normalised once per `locate` instead of once per window
    size -- NFKD over a whole paper is the expensive part of this
    module, and it does not depend on the window.
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

    Four tiers, tried in order: exact within one passage, exact across an
    adjacent pair, elided within one passage, elided across a pair. The
    tier is returned rather than discarded because a reader deciding
    whether to trust a rendered quotation should be able to see that
    `elided` matched fragments around an ellipsis instead of a
    contiguous span.

    **Every exact tier is tried before any elided one**, rather than
    exact-then-elided within each window size. Exact is the stronger
    claim, and it should not lose to a wider window: a span that really
    is contiguous across two passages must not be reported as an
    alignment around an ellipsis merely because a single passage also
    happens to contain its fragments in order.
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
    if len(pieces) < 2:
        return None
    for size, tier in ((1, "elided"), (ADJACENT, "elided-pair")):
        for pages, haystack in windows[size]:
            if _ordered_in(pieces, haystack):
                return tier, pages
    return None


def near_miss(quote: str, passages: list[Passage]) -> tuple[float, int | None]:
    """The page whose own words cover most of `quote`'s, and that share.

    What turns "not found" into something a reviewer can act on: a
    fabricated quotation and a lightly-edited one look identical without
    it, and alarm fatigue is the stated risk for this whole class of aid.

    Scored on the passage's *unstripped* words. A reference marker
    cannot inflate it, because `passages.distinctive` drops words of two
    characters or fewer and `30` is two -- verified rather than assumed:
    none of the 33 residual absents in the measurement changes its score
    when markers are stripped first.
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


def check_one(citekey: str, quote: str, found: list, reason: str | None) -> Checked:
    """`quote`'s verdict against one source's passages.

    A source with no reading-ordered text is `unverifiable` before
    anything is compared -- not `absent` after a failed comparison. The
    near-miss page is reported on both of the non-`found` outcomes: on
    `absent` it is what makes the finding actionable, and on
    `unverifiable` it is not evidence of anything but it does tell a
    human which page to open.
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
