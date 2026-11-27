"""Tier 1: exact contiguous n-gram matches against the corpus-wide index."""

from chitragupta import overlap_index
from chitragupta.review.verbatim_check._allowlist import _mask_allowlisted
from chitragupta.review.verbatim_check._masking import _DraftWord
from chitragupta.review.verbatim_check._merge import _merge_runs
from chitragupta.review.verbatim_check._shared import (
    _citekeys_at_positions,
    _cites_source,
    _line_at,
    _run_is_quoted,
    finding_id,
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
    """Tier 1: exact n-gram matches against `overlap_index.py`, under the
    tier contract `scan_findings` documents.

    Source positions are global (#131), so a run across a page break keeps
    one diagonal and merges; `page`/`end_page` report both sides.
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

    # (citekey, diagonal) -> {draft position: source page}: same-diagonal
    # matches stay in step across gaps, making the merge 1-D. Not keyed
    # on page, which would split runs across a page break (#131).
    groups = {}
    for j, gh in enumerate(draft_hashes):
        for citekey, page, src_pos in overlap_index.postings_for_gram(index, gh):
            groups.setdefault((citekey, src_pos - j), {})[j] = page

    citekeys_at_position = _citekeys_at_positions(groups)
    return _exact_findings_from_groups(
        groups,
        gap,
        n,
        min_run,
        allowlist,
        words,
        word_strs,
        newlines,
        text,
        paragraph_citekeys,
        citekeys_at_position,
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
    """Merge each `(citekey, diagonal)` group into runs, drop what the
    allowlist or `min_run` rules out, and build the rest (split out for
    complexity)."""
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
            findings.append(
                _exact_finding(
                    run,
                    citekey,
                    pos_pages,
                    span_words,
                    n,
                    words,
                    word_strs,
                    newlines,
                    text,
                    paragraph_citekeys,
                    citekeys_at_position,
                )
            )
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
    """The finding dict for one merged exact-tier `run`."""
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
    # One value, so `finding_id` and the payload cannot disagree.
    page = min(run_pages)
    return {
        "id": finding_id(citekey, page, fragment),
        "citekey": citekey,
        "page": page,
        "end_page": max(run_pages),
        "span_words": span_words,
        "matched_words": matched_words,
        "start": start,
        # 1-based, in the original text.
        "line": _line_at(newlines, char_start),
        "char_start": char_start,
        "char_end": char_end,
        "draft_text": text[char_start:char_end],
        "fragment": fragment,
        "context": " ".join(word_strs[max(0, start - 6) : min(len(word_strs), end + 6)]),
        "cites_source": cites_source,
        "quoted": _run_is_quoted(run_words),
        "tier": "exact",
        # 1-based; survives edits above the run that move `line`.
        "paragraph": min(run_paragraphs) + 1,
        "end_paragraph": max(run_paragraphs) + 1,
        # `None`, not 0.0 ("aligned, badly"): every finding carries every
        # published field, and this tier has no similarity score.
        "score": None,
        # `None`: `fragment` already is the source text here.
        "source_text": None,
    }
