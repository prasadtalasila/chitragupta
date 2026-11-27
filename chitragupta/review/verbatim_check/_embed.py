"""Tier 3: embedding-based paraphrase detection by local alignment over
sentence embeddings.
"""

from pathlib import Path

from chitragupta import overlap_chroma, overlap_embed, overlap_segments
from chitragupta.review.verbatim_check._allowlist import _mask_allowlisted
from chitragupta.review.verbatim_check._masking import _DraftWord
from chitragupta.review.verbatim_check._shared import (
    _cites_source,
    _line_at,
    _run_is_quoted,
    finding_id,
)


def _embed_tier_findings(
    draft: str | Path,
    words: list[_DraftWord],
    word_strs: list[str],
    paragraph_citekeys: list[set[str]],
    newlines: list[int],
    text: str,
    min_run: int,
    allowlist: list[tuple[str, ...]],
    lexical_findings: list[dict],
) -> tuple[list[dict], int, list[dict]]:
    """Tier 3 (`chitragupta/overlap_embed.py`, #134/#164): the tier
    finders' shared contract plus a third return value, **what this run
    does not cover**: `[{"reason": str, "partial": bool}, ...]`.

    Tiers 1 and 2 always run; this one needs the enrich stack,
    `content/chroma/`, passage sidecars and the dossier, any of which may
    be absent (`partial: False`), and renamed headings or a grown corpus
    can leave part of a draft uncompared (`partial: True`, #499).
    `lexical_findings` (tiers 1 and 2) must be applied before
    `report()`'s cap (#499). No `gap`: the alignment's
    `overlap_align.GAP_PENALTY` is a cost in sentences, not a word count.
    """
    scope, reason = overlap_embed.open_scope(Path(draft))
    if scope is None:
        return [], 0, [{"reason": reason, "partial": False}]
    try:
        return _findings_within(
            scope,
            words,
            word_strs,
            paragraph_citekeys,
            newlines,
            text,
            min_run,
            allowlist,
            lexical_findings,
        )
    finally:
        # Whoever acquired the scope releases it, on every path (#516/m-79).
        scope.close()


def _findings_within(
    scope,
    words: list[_DraftWord],
    word_strs: list[str],
    paragraph_citekeys: list[set[str]],
    newlines: list[int],
    text: str,
    min_run: int,
    allowlist: list[tuple[str, ...]],
    lexical_findings: list[dict],
) -> tuple[list[dict], int, list[dict]]:
    """`_embed_tier_findings`'s body, split so the caller owns the scope."""
    sections, unmatched = overlap_segments.draft_sections(
        text, [(w.char, w.char_end) for w in words], scope.citekeys_by_section
    )
    if not sections:
        # The dossier's sections match no heading here (renamed, or an
        # older convention): say so rather than report a clean scan.
        return (
            [],
            0,
            [
                {
                    "reason": (
                        "the draft's headings and its dossier's sections.md do not agree "
                        "on a single section -- regenerate it with `python -m "
                        "chitragupta.dossier sections <draft> --citekeys --write`"
                    ),
                    "partial": False,
                }
            ],
        )

    reasons = _partial_coverage_reasons(scope, sections, unmatched)

    alignments = overlap_embed.align_draft(scope, sections)
    # Map from *every* alignment, before `report` drops the weaker sources
    # matching the same passage, or a correctly cited paragraph would show
    # `UNCITED SOURCE` whenever the strongest match is a paper it omits.
    citekeys_at_position = _embed_citekeys_at_positions(alignments)

    # Drop tier 1/2 duplicates *before* `report()`'s per-section cap
    # (#499), or a verbatim quote takes the cap slot and the paraphrase
    # elsewhere is lost. Overlap, not containment: a tier-3 passage
    # normally contains the lexical span.
    alignments = [
        a
        for a in alignments
        if not any(
            other["citekey"] == a.citekey
            and other["start"] < a.word_end
            and a.word_start < other["start"] + other["span_words"]
            for other in lexical_findings
        )
    ]

    findings = []
    suppressed = 0
    for alignment in overlap_embed.report(alignments):
        span_words = alignment.word_end - alignment.word_start
        if span_words < min_run:
            continue
        if allowlist:
            mask = _mask_allowlisted(
                word_strs[alignment.word_start : alignment.word_end], allowlist
            )
            if span_words - sum(mask) < min_run:
                suppressed += 1
                continue
        findings.append(
            _embed_finding(
                alignment,
                span_words,
                words,
                word_strs,
                newlines,
                text,
                paragraph_citekeys,
                citekeys_at_position,
            )
        )
    return findings, suppressed, reasons


def _partial_coverage_reasons(
    scope: overlap_embed.Scope, sections: list[overlap_segments.DraftSection], unmatched: int
) -> list[dict]:
    """The `partial: True` coverage gaps (#499), as separate entries
    because a renamed heading and a grown corpus have different fixes.
    """
    reasons = []
    if unmatched:
        # Some sections matched, so the tier still ran. The denominator is
        # `scope.citekeys_by_section`: `sections` omits matched headings
        # with no usable prose.
        reasons.append(
            {
                "reason": (
                    f"{unmatched} of {len(scope.citekeys_by_section)} section(s) the "
                    "dossier's sections.md records citekeys for could not be matched to "
                    "this draft's own headings -- probably renamed since `python -m "
                    "chitragupta.dossier sections <draft> --citekeys --write` last ran; "
                    "only the matched section(s) below were scanned"
                ),
                "partial": True,
            }
        )
    cited = {key for section in sections for key in section.citekeys}
    stale = overlap_chroma.absent_citekeys(scope.collection, cited)
    if stale:
        reasons.append(
            {
                "reason": (
                    f"{len(stale)} cited source(s) have no chunks in the embedded corpus "
                    "-- run `python -m chitragupta.enrich` to catch reuse from them"
                ),
                "partial": True,
            }
        )
    return reasons


def _embed_citekeys_at_positions(
    alignments: list[overlap_embed.SectionAlignment],
) -> dict[int, set[str]]:
    """Tier 3's `_citekeys_at_positions`: each covered word position
    mapped to the citekeys aligned there, so a paragraph citing any one
    of several sources stating the same thing is correctly attributed.
    """
    at_position: dict[int, set[str]] = {}
    for alignment in alignments:
        for j in range(alignment.word_start, alignment.word_end):
            at_position.setdefault(j, set()).add(alignment.citekey)
    return at_position


def _embed_finding(
    alignment: overlap_embed.SectionAlignment,
    span_words: int,
    words: list[_DraftWord],
    word_strs: list[str],
    newlines: list[int],
    text: str,
    paragraph_citekeys: list[set[str]],
    citekeys_at_position: dict[int, set[str]],
) -> dict:
    """The finding dict for one alignment, as `_exact_finding`, plus
    `score`, the alignment's strength."""
    start, end = alignment.word_start, alignment.word_end
    run_words = words[start:end]
    char_start, char_end = run_words[0].char, run_words[-1].char_end
    fragment = " ".join(word_strs[start:end])
    run_paragraphs = {w.paragraph for w in run_words}
    return {
        "id": finding_id(alignment.citekey, alignment.page, fragment),
        "citekey": alignment.citekey,
        "page": alignment.page,
        "end_page": alignment.end_page,
        "span_words": span_words,
        "matched_words": alignment.matched_words,
        "start": start,
        "line": _line_at(newlines, char_start),
        "char_start": char_start,
        "char_end": char_end,
        "draft_text": text[char_start:char_end],
        "fragment": fragment,
        "context": " ".join(word_strs[max(0, start - 6) : min(len(word_strs), end + 6)]),
        "cites_source": _cites_source(
            start, end, run_paragraphs, paragraph_citekeys, citekeys_at_position
        ),
        "quoted": _run_is_quoted(run_words),
        "tier": "embedding",
        # 1-based, for people; a paragraph number survives edits above the
        # run that move `line` and `char_start`.
        "paragraph": min(run_paragraphs) + 1,
        "end_paragraph": max(run_paragraphs) + 1,
        # The source side: unlike tiers 1 and 2, `fragment` (the draft's
        # words) differs from the source here, and showing both is what
        # makes a restatement legible as one.
        "source_text": alignment.source_text,
        # Rounded where built, so the JSON and Markdown agree.
        "score": round(alignment.score, 3),
    }
