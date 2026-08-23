"""Tier 2: deterministic light-paraphrase detection via stemmed
skip-grams.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

from chitragupta import overlap_skipgram
from chitragupta.review.verbatim_check._allowlist import _mask_allowlisted_stemmed
from chitragupta.review.verbatim_check._masking import _DraftWord
from chitragupta.review.verbatim_check._merge import _merge_spans
from chitragupta.review.verbatim_check._shared import (
    _cites_source, _line_at, _run_is_quoted, finding_id,
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
    """Tier 2: deterministic light-paraphrase detection via stemmed
    skip-grams (`chitragupta/overlap_skipgram.py`, #133, the CoReMo design --
    discussion #115, docs/PLAGIARISM-DESIGN.md). Same shared contract as
    `_exact_tier_findings` -- `(citekey, diagonal)` grouping, allowlist,
    `_cites_source` -- against `overlap_skipgram`'s own corpus-wide
    index instead of the exact tier's.

    Grouping mirrors `_exact_tier_findings`, but a posting here is a
    whole `(start, end)` skip-gram window, not a single anchor position:
    `diagonal` is still `src_pos - draft_start`, computed from each
    window's own start, and `_merge_spans` (not `_merge_runs`) merges
    same-diagonal windows, since a skip-gram window's width in original
    positions varies rather than being fixed at `n`.

    `matched_words` counts only the *family members* an actual matched
    window touched -- same-parity, non-stopword original positions --
    not every position `_merge_spans` merged in between, which can
    include the other family's words and any interposed stopwords
    (`span_words` already counts those, matching tier 1's own
    span/matched_words split).

    Advisory only: nothing here or in `overlap_skipgram.py` decides
    gate-eligibility (a later, separate call, issue #130); this tier
    ships now because discussion #115 says start advisory and promote
    with evidence, not because it has been judged safe to block on.
    """
    index = overlap_skipgram.build_corpus_index()
    n = index.n

    groups = {}
    for gh, start_j, end_j in overlap_skipgram.skipgram_postings(word_strs, n):
        for citekey, page, src_pos in overlap_skipgram.postings_for_gram(index, gh):
            groups.setdefault((citekey, src_pos - start_j), []).append((start_j, end_j, page))

    citekeys_at_position = _skipgram_citekeys_at_positions(groups)
    return _skipgram_findings_from_groups(
        groups, gap, min_run, allowlist, words, word_strs,
        newlines, text, paragraph_citekeys, citekeys_at_position,
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
    """Merge each `(citekey, diagonal)` group's spans, drop anything the
    allowlist or `min_run` rules out, and build a finding for what's
    left. Extracted out of `_skipgram_tier_findings` for the same reason
    as `_exact_findings_from_groups`.

    **One finding per id** (#180). Grouping is by `(citekey, diagonal)`,
    but a finding's identity is `(citekey, page, fragment)` -- no
    diagonal in it -- and the two do not agree: a source table whose
    values repeat puts the *same* draft window at several `src_pos`, so
    the same window lands in several `(citekey, diagonal)` groups, each
    of which then merges to the same draft span against the same source
    page and builds a finding with the same id. #180 measured 190 raw
    findings resolving to 125 unique ids on one real run, and the
    duplicates inflated the benchmark's own precision arithmetic, which
    sums labels over the raw list. Traced against a repeating source
    block, the colliding findings were identical in every published
    field, not merely in their id, so keeping the first one seen
    discards nothing.
    """
    findings = []
    seen_ids = set()
    suppressed = 0
    for (citekey, _diagonal), spans in groups.items():
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
                start, end, members, span_words, citekey, words, word_strs,
                newlines, text, paragraph_citekeys, citekeys_at_position,
            )
            if finding["id"] in seen_ids:
                continue
            seen_ids.add(finding["id"])
            findings.append(finding)
    return findings, suppressed


def _skipgram_citekeys_at_positions(
    groups: dict[tuple[str, int], list[tuple[int, int, int]]]
) -> dict[int, set[str]]:
    """Same purpose as `_citekeys_at_positions` (tier 1), reshaped for
    tier 2's `(start, end, page)` span postings instead of single
    positions: every original position some matched skip-gram window
    covers maps to the citekeys with a matching window there.

    Extracted out of `_skipgram_tier_findings` so this loop's own
    nesting does not also count against that function's complexity.
    """
    citekeys_at_position = {}
    for (citekey, _diagonal), spans in groups.items():
        for start_j, end_j, _page in spans:
            for j in range(start_j, end_j):
                citekeys_at_position.setdefault(j, set()).add(citekey)
    return citekeys_at_position


def _skipgram_matched_positions(
    members: list[tuple[int, int, int]], word_strs: list[str]
) -> set[int]:
    """Same-parity, non-stopword original positions an actual matched
    skip-gram window touched -- the real evidence `matched_words` counts,
    as opposed to every position `_merge_spans` merged in between (which
    can include the other family's words and any interposed stopwords).

    Extracted out of `_skipgram_tier_findings` for the same reason as
    `_skipgram_citekeys_at_positions`.
    """
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
    words: list[_DraftWord],
    word_strs: list[str],
    newlines: list[int],
    text: str,
    paragraph_citekeys: list[set[str]],
    citekeys_at_position: dict[int, set[str]],
) -> dict:
    """The finding dict for one merged skip-gram-tier span. Mirrors
    `_exact_finding`'s role for tier 1 -- extracted for the same reason.
    """
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
        "context": " ".join(word_strs[max(0, start - 6):min(len(word_strs), end + 6)]),
        "cites_source": cites_source,
        "quoted": _run_is_quoted(run_words),
        "tier": "skip-gram",
        # `None`, not absent and not 0.0: every tier's finding has to
        # carry every published field (`published` projects
        # `_PAYLOAD_FIELDS` with a hard `KeyError`, deliberately), and a
        # deterministic tier has no similarity score to report. Zero
        # would read as "aligned, badly", which is a different claim
        # from "this tier does not measure that".
        "score": None,
    }
