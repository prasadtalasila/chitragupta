"""Tier 1: exact contiguous n-gram matches against the corpus-wide index.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

from chitragupta import overlap_index
from chitragupta.review.verbatim_check._allowlist import _mask_allowlisted
from chitragupta.review.verbatim_check._masking import _DraftWord
from chitragupta.review.verbatim_check._merge import _merge_runs
from chitragupta.review.verbatim_check._shared import (
    _citekeys_at_positions, _cites_source, _line_at, _run_is_quoted, finding_id,
)


def _exact_tier_findings(
    words: list[_DraftWord],
    word_strs: list[str],
    paragraph_citekeys: list[set[str]],
    newlines: list[int],
    text: str,
    min_run: int,
    gap: int,
    allowlist: list[tuple[str, ...]],
) -> tuple[list[dict], int]:
    """Tier 1: exact contiguous n-gram matches against the corpus-wide
    index (`overlap_index.py`). One of possibly several tier finders
    `scan_findings` unions together -- see that function's docstring for
    the shared contract every tier finder follows: same finding-dict
    shape (`tier` naming which one produced it), same `(findings,
    suppressed)` return.

    A run can span a page break in the source: `chitragupta/overlap_index.py`'s
    `token_position` is a global offset into the document (#131), not
    reset per page, so `diagonal` (`src_pos - draft_pos`) stays constant
    across the boundary and the two halves merge into one run the same
    way a same-diagonal gap does. Each finding reports `page` and
    `end_page` -- equal for an ordinary single-page run, `end_page >
    page` for one that straddles a break -- rather than picking one side
    and losing the other.
    """
    index = overlap_index.build_corpus_index()
    if min_run < index.n:
        raise ValueError(
            f"--min-run must be >= {index.n} (the corpus index's own n-gram "
            "size, chitragupta.overlap_index.DEFAULT_N) -- a shorter run cannot be "
            "detected without rebuilding the whole corpus index at a "
            "different n. Change the index's n, not this flag, if that is "
            "really what's needed."
        )

    n = index.n
    draft_hashes = overlap_index.gram_hashes(word_strs, n)

    # (citekey, diagonal) -> {draft position: source page} for every
    # n-gram match on that diagonal (src_pos - draft_pos constant) -- two
    # matches on the same diagonal are still "in step" even with
    # non-matching words between them, which is exactly what makes a
    # gap-tolerant merge (below) a same-diagonal 1-D problem rather than a
    # general alignment one. `page` is not part of the group key: a run
    # that truly spans a source page break has postings attributed to two
    # different pages but the same diagonal (global token positions,
    # #131), and grouping on page too would split it right back apart.
    # One write per (group, j): a fixed j and diagonal pin src_pos
    # (`src_pos = diagonal + j`), and a document fingerprint has exactly
    # one posting per position, so no second write ever competes for the
    # same key.
    groups = {}
    for j, gh in enumerate(draft_hashes):
        for citekey, page, src_pos in overlap_index.postings_for_gram(index, gh):
            groups.setdefault((citekey, src_pos - j), {})[j] = page

    citekeys_at_position = _citekeys_at_positions(groups)
    return _exact_findings_from_groups(
        groups, gap, n, min_run, allowlist, words, word_strs,
        newlines, text, paragraph_citekeys, citekeys_at_position,
    )


def _exact_findings_from_groups(
    groups: dict[tuple[str, int], dict[int, int]],
    gap: int,
    n: int,
    min_run: int,
    allowlist: list[tuple[str, ...]],
    words: list[_DraftWord],
    word_strs: list[str],
    newlines: list[int],
    text: str,
    paragraph_citekeys: list[set[str]],
    citekeys_at_position: dict[int, set[str]],
) -> tuple[list[dict], int]:
    """Merge each `(citekey, diagonal)` group's positions into runs, drop
    anything the allowlist or `min_run` rules out, and build a finding for
    what's left. Extracted out of `_exact_tier_findings` so this loop's
    own nesting does not also count against that function's complexity.
    """
    findings = []
    suppressed = 0
    for (citekey, _diagonal), pos_pages in groups.items():
        for run in _merge_runs(list(pos_pages), gap, n):
            start, end = run[0], run[-1] + n
            span_words = end - start
            if span_words < min_run:
                continue
            if allowlist:
                mask = _mask_allowlisted(word_strs[start:end], allowlist)
                if span_words - sum(mask) < min_run:
                    suppressed += 1
                    continue
            findings.append(_exact_finding(
                run, citekey, pos_pages, span_words, n, words, word_strs,
                newlines, text, paragraph_citekeys, citekeys_at_position,
            ))
    return findings, suppressed


def _exact_finding(
    run: list[int],
    citekey: str,
    pos_pages: dict[int, int],
    span_words: int,
    n: int,
    words: list[_DraftWord],
    word_strs: list[str],
    newlines: list[int],
    text: str,
    paragraph_citekeys: list[set[str]],
    citekeys_at_position: dict[int, set[str]],
) -> dict:
    """The finding dict for one merged exact-tier `run`.

    Extracted out of `_exact_tier_findings` so its own comprehensions
    (each already nested inside that function's double loop) do not also
    count against that function's cognitive complexity -- this is a pure
    one-run-in, one-dict-out step with no other caller.
    """
    start, end = run[0], run[-1] + n
    matched_words = len({idx for p in run for idx in range(p, p + n)})
    run_words = words[start:end]
    char_start, char_end = run_words[0].char, run_words[-1].char_end
    fragment = " ".join(word_strs[start:end])
    run_paragraphs = {w.paragraph for w in run_words}
    cites_source = _cites_source(
        start, end, run_paragraphs, paragraph_citekeys, citekeys_at_position
    )
    run_pages = [pos_pages[p] for p in run]
    # Hoisted out of the dict rather than inlined as #131 wrote
    # it: `finding_id` needs the same start page the payload
    # reports, and computing `min(run_pages)` twice is how those
    # two quietly stop agreeing.
    page = min(run_pages)
    return {
        "id": finding_id(citekey, page, fragment),
        "citekey": citekey,
        "page": page,
        "end_page": max(run_pages),
        "span_words": span_words,
        "matched_words": matched_words,
        "start": start,
        # 1-based, counted in the original text: the only one of
        # these four a person reads directly.
        "line": _line_at(newlines, char_start),
        "char_start": char_start,
        "char_end": char_end,
        "draft_text": text[char_start:char_end],
        "fragment": fragment,
        "context": " ".join(word_strs[max(0, start - 6):min(len(word_strs), end + 6)]),
        "cites_source": cites_source,
        "quoted": _run_is_quoted(run_words),
        "tier": "exact",
        # `None`, not absent and not 0.0: every tier's finding has to
        # carry every published field (`published` projects
        # `_PAYLOAD_FIELDS` with a hard `KeyError`, deliberately), and a
        # deterministic tier has no similarity score to report. Zero
        # would read as "aligned, badly", which is a different claim
        # from "this tier does not measure that".
        "score": None,
    }
