"""Line lookup, finding identity, and the citing/quoting checks all three
detection tiers share.
"""

import bisect
import hashlib
import re

from chitragupta.review.verbatim_check._masking import _DraftWord


def _newline_offsets(text: str) -> list[int]:
    """Every newline's index in `text`, ascending: one sweep reused by
    every finding, not an O(len(text)) count per finding."""
    return [m.start() for m in re.finditer("\n", text)]


def _line_at(newlines: list[int], pos: int) -> int:
    """The 1-based line `pos` falls on, given `_newline_offsets`; a newline
    ends the line it sits on (`bisect_left`)."""
    return bisect.bisect_left(newlines, pos) + 1


def finding_id(citekey: str, page: int, fragment: str) -> str:
    """A finding's name, stable across runs and across edits elsewhere in
    the draft. `page` is the run's start page, so a run that merges
    differently really is a different finding.

    Position-free, or repairing one finding would rename the rest and
    nothing could tell what survived a revision (R2). Identical runs from
    one page share an id; `recheck` then understates progress.
    """
    digest = hashlib.sha256(f"{citekey}\x00{page}\x00{fragment}".encode())
    return digest.hexdigest()[:12]


def _citekeys_at_positions(groups: dict[tuple[str, int], dict[int, int]]) -> dict[int, set[str]]:
    """Draft position -> every citekey with a posting there, across every
    `(citekey, diagonal)` group a tier produced, for `_cites_source`.
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
    matches somewhere in `[start, end)`, not only this finding's own.

    A definition several papers reproduce is correctly attributed to any
    one of them; checking only the finding's citekey reported the others
    as `UNCITED SOURCE` and kept a cited quotation out of `_bucket`'s
    exemption (#162). Paragraphs and positions are both unioned, since a
    run can cross a paragraph break.
    """
    span_citekeys = set()
    for j in range(start, end):
        span_citekeys |= citekeys_at_position.get(j, set())
    return any(span_citekeys & paragraph_citekeys[p] for p in run_paragraphs)


def _run_is_quoted(run_words: list[_DraftWord]) -> bool:
    """Whether this run touches a quotation at all -- `any`, not `all`.

    A matched span routinely opens a word or two before the quote mark,
    so `all` silently reported attributed quotations as unquoted (#189).
    Replayed over the 43 labels behind two benchmarks (#130 gate labels,
    `bench/results/2026-08-14-skipgram-precision/labels.json`), `any`
    recovers all four such cases, majority-of-span only two, and no `tp`
    changes bucket; thresholds 3-8 add nothing. The span is not narrowed,
    which would change every labelled `finding_id`.
    """
    return any(w.quoted for w in run_words)
