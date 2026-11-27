"""Tier 2: deterministic light-paraphrase detection via stemmed
skip-grams.
"""

from chitragupta import overlap_skipgram, overlap_source_text
from chitragupta.review.verbatim_check._allowlist import _mask_allowlisted_stemmed
from chitragupta.review.verbatim_check._masking import _DraftWord
from chitragupta.review.verbatim_check._merge import _merge_spans
from chitragupta.review.verbatim_check._shared import (
    _cites_source,
    _line_at,
    _run_is_quoted,
    finding_id,
)


def _skipgram_tier_findings(
    words: list[_DraftWord],
    word_strs: list[str],
    paragraph_citekeys: list[set[str]],
    newlines: list[int],
    text: str,
    min_run: int,
    gap: int,
    allowlist: list[tuple[str, ...]],
) -> tuple[list[dict], int]:
    """Tier 2: stemmed skip-grams (`chitragupta/overlap_skipgram.py`, #133,
    docs/PLAGIARISM-DESIGN.md), under `_exact_tier_findings`' contract
    against its own corpus index.

    A posting is a whole `(start, end)` window, so the diagonal comes from
    each window's start and `_merge_spans` merges them. `matched_words`
    counts only family members a matched window touched. Advisory only:
    gate-eligibility is a separate decision (#130, discussion #115).
    """
    index = overlap_skipgram.build_corpus_index()
    n = index.n

    groups = {}
    for gh, start_j, end_j in overlap_skipgram.skipgram_postings(word_strs, n):
        for citekey, page, src_pos in overlap_skipgram.postings_for_gram(index, gh):
            groups.setdefault((citekey, src_pos - start_j), []).append((start_j, end_j, page))

    citekeys_at_position = _skipgram_citekeys_at_positions(groups)
    return _skipgram_findings_from_groups(
        groups,
        gap,
        min_run,
        allowlist,
        words,
        word_strs,
        newlines,
        text,
        paragraph_citekeys,
        citekeys_at_position,
    )


def _skipgram_findings_from_groups(
    groups: dict[tuple[str, int], list[tuple[int, int, int]]],
    gap: int,
    min_run: int,
    allowlist: list[tuple[str, ...]],
    words: list[_DraftWord],
    word_strs: list[str],
    newlines: list[int],
    text: str,
    paragraph_citekeys: list[set[str]],
    citekeys_at_position: dict[int, set[str]],
) -> tuple[list[dict], int]:
    """Merge each `(citekey, diagonal)` group's spans, drop what the
    allowlist or `min_run` rules out, and build the rest.

    **One finding per id** (#180): a repeating source table puts the same
    window on several diagonals, yielding findings identical in every
    published field, which inflated benchmark precision. Keeping the
    first discards nothing.
    """
    findings = []
    seen_ids = set()
    suppressed = 0
    for (citekey, diagonal), spans in groups.items():
        for start, end, members in _merge_spans(spans, gap):
            span_words = end - start
            if span_words < min_run:
                continue
            if allowlist:
                mask = _mask_allowlisted_stemmed(word_strs[start:end], allowlist)
                if span_words - sum(mask) < min_run:
                    suppressed += 1
                    continue
            finding = _skipgram_finding(
                start,
                end,
                members,
                span_words,
                citekey,
                diagonal,
                words,
                word_strs,
                newlines,
                text,
                paragraph_citekeys,
                citekeys_at_position,
            )
            if finding["id"] in seen_ids:
                continue
            seen_ids.add(finding["id"])
            findings.append(finding)
    return findings, suppressed


def _skipgram_citekeys_at_positions(
    groups: dict[tuple[str, int], list[tuple[int, int, int]]],
) -> dict[int, set[str]]:
    """Tier 2's `_citekeys_at_positions`, over `(start, end, page)` span
    postings."""
    citekeys_at_position = {}
    for (citekey, _diagonal), spans in groups.items():
        for start_j, end_j, _page in spans:
            for j in range(start_j, end_j):
                citekeys_at_position.setdefault(j, set()).add(citekey)
    return citekeys_at_position


def _skipgram_matched_positions(
    members: list[tuple[int, int, int]], word_strs: list[str]
) -> set[int]:
    """Same-parity, non-stopword positions a matched window touched: the
    evidence `matched_words` counts, not everything merged in between."""
    matched_positions = set()
    for m_start, m_end, _page in members:
        parity = m_start % 2
        for p in range(m_start, m_end):
            if p % 2 == parity and word_strs[p] not in overlap_skipgram.STOPWORDS:
                matched_positions.add(p)
    return matched_positions


def _skipgram_finding(
    start: int,
    end: int,
    members: list[tuple[int, int, int]],
    span_words: int,
    citekey: str,
    diagonal: int,
    words: list[_DraftWord],
    word_strs: list[str],
    newlines: list[int],
    text: str,
    paragraph_citekeys: list[set[str]],
    citekeys_at_position: dict[int, set[str]],
) -> dict:
    """The finding dict for one merged skip-gram-tier span."""
    matched_positions = _skipgram_matched_positions(members, word_strs)
    run_words = words[start:end]
    char_start, char_end = run_words[0].char, run_words[-1].char_end
    fragment = " ".join(word_strs[start:end])
    run_paragraphs = {w.paragraph for w in run_words}
    cites_source = _cites_source(
        start, end, run_paragraphs, paragraph_citekeys, citekeys_at_position
    )
    pages = [m[2] for m in members]
    page = min(pages)
    return {
        "id": finding_id(citekey, page, fragment),
        "citekey": citekey,
        "page": page,
        "end_page": max(pages),
        "span_words": span_words,
        "matched_words": len(matched_positions),
        "start": start,
        "line": _line_at(newlines, char_start),
        "char_start": char_start,
        "char_end": char_end,
        "draft_text": text[char_start:char_end],
        "fragment": fragment,
        "context": " ".join(word_strs[max(0, start - 6) : min(len(word_strs), end + 6)]),
        "cites_source": cites_source,
        "quoted": _run_is_quoted(run_words),
        "tier": "skip-gram",
        # 1-based; survives edits above the run that move `line`.
        "paragraph": min(run_paragraphs) + 1,
        "end_paragraph": max(run_paragraphs) + 1,
        # `None`, not 0.0: this deterministic tier has no similarity score.
        "score": None,
        # Unlike tier 1, a stemmed match means the wording differs, so the
        # source side is recovered via the constant diagonal; `None` when
        # the parsed text is gone.
        "source_text": overlap_source_text.source_span(citekey, start + diagonal, end + diagonal),
    }
