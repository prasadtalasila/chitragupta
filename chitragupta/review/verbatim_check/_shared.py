"""Line lookup, finding identity, and the citing/quoting checks all three
detection tiers share.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

import bisect
import hashlib
import re

from chitragupta.review.verbatim_check._masking import _DraftWord


def _newline_offsets(text: str) -> list[int]:
    """Every newline's index in `text`, ascending -- one sweep, reused by
    every finding.

    `text.count("\\n", 0, char_start)` per finding is O(len(text)) each
    time, so a long draft with many findings pays for the whole file once
    per finding. `citation_gate.extract_citekeys` already computes its
    line numbers in a single forward pass rather than per match, for
    exactly this reason; this is that discipline applied here.
    """
    return [m.start() for m in re.finditer("\n", text)]


def _line_at(newlines: list[int], pos: int) -> int:
    """The 1-based line `pos` falls on, given `_newline_offsets`.

    `bisect_left`, so a newline character counts as ending the line it
    sits on rather than starting the next one -- the same convention
    `str.count("\\n", 0, pos)` had.
    """
    return bisect.bisect_left(newlines, pos) + 1


def finding_id(citekey: str, page: int, fragment: str) -> str:
    """A finding's name, stable across runs and across edits elsewhere in
    the draft. `page` is the run's start page (`scan_findings` passes
    `min(run_pages)`, not `end_page`) -- a run that merges differently on
    a later scan can land on a different start page and so get a
    different id, which is correct: the finding really did change.

    Deliberately position-free. `start` moves whenever anything above a
    finding is edited, so an identity built on it would rename every
    remaining finding the moment the first one was repaired, and nothing
    could then decide whether a given finding had survived a revision --
    which is the whole job (R2, docs/AUTO-IMPROVEMENT.md).

    Two identical runs from the same source page therefore share an id.
    `recheck` is written to understate progress in that case rather than
    overstate it: with two copies in the baseline and one repaired, the
    id is still present and the finding still reports as persisting.
    """
    digest = hashlib.sha256(f"{citekey}\x00{page}\x00{fragment}".encode())
    return digest.hexdigest()[:12]


def _citekeys_at_positions(
    groups: dict[tuple[str, int], dict[int, int]]
) -> dict[int, set[str]]:
    """Draft position -> every citekey with a posting there, across
    *every* `(citekey, diagonal)` group a tier produced -- not just the
    one a given finding is reported against. Built once per tier and
    handed to `_cites_source`, below.
    """
    at_position = {}
    for (citekey, _diagonal), pos_pages in groups.items():
        for j in pos_pages:
            at_position.setdefault(j, set()).add(citekey)
    return at_position


def _cites_source(
    start: int,
    end: int,
    run_paragraphs: set[int],
    paragraph_citekeys: list[set[str]],
    citekeys_at_position: dict[int, set[str]],
) -> bool:
    """Whether a paragraph this run crosses cites *any* citekey that
    matches somewhere in `[start, end)` -- not only the one citekey this
    particular finding happens to be grouped under.

    A definition several corpus papers reproduce verbatim can be cited
    to any one of them: the paragraph that quotes and cites paper A is
    correctly attributed even though `scan` also finds the same span
    matching papers B through N, which the paragraph never mentions.
    Checking only "does this citekey appear in the paragraph" reported
    the other N-1 matches as `UNCITED SOURCE` regardless -- including a
    correctly quoted, correctly credited block quote, which then never
    reached the `quoted`-and-cited exemption `_bucket` gives an
    attributed quotation, because that exemption also keyed off this
    same single-citekey check (docs/PLAGIARISM-DESIGN.md's Kritzinger case,
    surfaced by PR #162's benchmark: a taxonomy quoted and cited to
    `kritzinger_digital_2018` also matches `barbie_toward_2024`, which
    reproduces the same taxonomy and is never mentioned in the
    paragraph -- correct scholarship, misreported as uncited).

    Paragraphs *plural*, and positions *plural*: a run can cross a
    paragraph break (the flat word stream `_tokenize_draft` produces),
    and different words within one run can each match a different set
    of other-citekey postings, so both dimensions have to be unioned
    before checking for overlap with what any of those paragraphs cite.
    """
    span_citekeys = set()
    for j in range(start, end):
        span_citekeys |= citekeys_at_position.get(j, set())
    return any(span_citekeys & paragraph_citekeys[p] for p in run_paragraphs)


def _run_is_quoted(run_words: list[_DraftWord]) -> bool:
    """Whether this run touches a quotation at all -- `any`, not `all`.

    `all` was the first reading of "sits inside quote delimiters", on the
    argument that one incidentally-quoted word should not excuse a long
    run -- and it reads false on the case the flag exists for. A matched
    span is wider than the quotation that evidences it and routinely
    opens a word or two *before* the mark, in the draft's own framing
    prose, so a correctly quoted and correctly credited passage reported
    `quoted: false`, silently, to the reader relying on the flag to skip
    attributed material (#189). Four hand-labelled
    `attributed-quotation` findings have that shape: `f0f4fd3982b7` in
    the #130 gate labels (10 of 24 words quoted), and `06373f5eb33f`,
    `77a6a3a6ac03`, `b1f7848c8965` in
    `bench/results/2026-08-14-skipgram-precision/labels.json` (21/22,
    8/19, 8/15).

    **Those proportions are why this is `any` and nothing gentler.** In
    two of the four the quoted material is a *minority suffix* of the
    span, out of reach of any majority-of-span rule: replayed over all 43
    labels behind the two benchmarks, majority recovers two of the four,
    while `any` and every longest-quoted-stretch threshold from 3 to 8
    words score identically. A threshold buys nothing the corpus can see
    and adds a constant to tune. The same replay answers the `all`-era
    worry: no finding labelled `tp` changes bucket under `any`.

    The span is deliberately left alone. Narrowing a finding to stop at
    the quote boundary would change `fragment` and so every `finding_id`
    those labels are keyed by; the exact tier has lived with straddling
    spans since #162, and this keeps the flag honest about them rather
    than reopening that.
    """
    return any(w.quoted for w in run_words)
