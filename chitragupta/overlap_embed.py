"""Tier 3 of the overlap scan: embedding-based paraphrase detection, by
local alignment over sentence embeddings (docs/PLAGIARISM-DESIGN.md,
#134, #164).

Tiers 1 and 2 match on token position, so a moved qualifier or spliced
sentence escapes both; cosine similarity does not care about position.

**Advisory only, permanently.** Vectors change with
`[enrich].embedding_model`, so a finding is not reproducible and may
never block; `bench/bench_overlap_gate.py::eligible()` admits only
`exact` and its self-test asserts an embedding finding is ineligible.

Never searches the corpus: each section is scoped to the citekeys its
dossier records, shortlisted (`overlap_chroma.shortlist`) and aligned.
A corpus-wide threshold would re-detect the pipeline's own retrieval.
`report` ranks rather than thresholds. When the stack, chroma, ledger
or dossier is missing, `unavailable_reason()` says which, since an
unbuilt tier and a clean one would otherwise look identical.
"""

from dataclasses import dataclass

from chitragupta import overlap_align, overlap_chroma, overlap_segments

# Re-exported so existing `overlap_embed.Scope` callers keep resolving.
from chitragupta.overlap_embed_scope import Scope, open_scope, unavailable_reason

__all__ = [
    "SECTION_LIMIT",
    "SHORTLIST_SOURCES",
    "Scope",
    "SectionAlignment",
    "align_draft",
    "open_scope",
    "report",
    "unavailable_reason",
]

# Cited sources aligned per section after the shortlist ranks them; a
# constant, not config, as overlap_align explains.
SHORTLIST_SOURCES = 5

# Alignments reported per *section*, a cap not a threshold. Per section
# because scores are not comparable across sections: a draft-wide cap of
# 12 dropped the one hand-verified paraphrase in a real chapter.
SECTION_LIMIT = 1


@dataclass(frozen=True)
class SectionAlignment:
    """One aligned passage pair. `section` is the draft heading it was
    found under, which `report` ranks within."""

    section: str
    citekey: str
    page: int
    end_page: int
    score: float
    word_start: int
    word_end: int
    matched_words: int
    source_text: str


def align_draft(
    scope: Scope, sections: list[overlap_segments.DraftSection]
) -> list[SectionAlignment]:
    """Every alignment across `sections`, strongest first.

    Each source is encoded once per draft, each section once for all its
    sources. Returned unnarrowed, because verbatim_check's
    `_cites_source` needs every citekey that matched before `report`
    drops any.
    """
    # No lexical-overlap ceiling, though #134 asks for one: `scan_findings`
    # drops alignments a real exact/skip-gram finding overlaps instead.
    # A 0.55 ceiling discarded the strongest alignment in
    # bench/fixtures/graded-paraphrase-of-singh-offload-2022.md (0.83).
    sources: dict[str, tuple[list[overlap_segments.SourceSentence], object]] = {}
    found = []
    for section in sections:
        vectors = scope.embedder.encode([s.text for s in section.sentences])
        for citekey in overlap_chroma.shortlist(
            scope.collection,
            scope.embedder,
            section.citekeys,
            " ".join(s.text for s in section.sentences),
            SHORTLIST_SOURCES,
        ):
            if citekey not in sources:
                sources[citekey] = _encoded_source(scope, citekey)
            found += _align_section(scope, section, vectors, citekey, sources[citekey])
    found.sort(key=lambda a: (-a.score, a.citekey, a.word_start))
    return found


def _encoded_source(
    scope: Scope, citekey: str
) -> tuple[list[overlap_segments.SourceSentence], object]:
    segments = overlap_segments.source_sentences(scope.connection, citekey)
    return segments, scope.embedder.encode([s.text for s in segments]) if segments else None


def report(alignments: list[SectionAlignment]) -> list[SectionAlignment]:
    """The alignments a report shows: strongest first, one per draft
    span, capped at `SECTION_LIMIT`.

    A ranking, not a verdict (#134): on a real hand-verified pair the
    restatement scored 0.62 while an incidental clause scored 0.74, so no
    cutoff means anything. One per span, since one passage matching four
    sources is one place to look.
    """
    kept: list[SectionAlignment] = []
    per_section: dict[str, int] = {}
    for alignment in alignments:
        if per_section.get(alignment.section, 0) >= SECTION_LIMIT:
            continue
        if any(
            other.word_start < alignment.word_end and alignment.word_start < other.word_end
            for other in kept
        ):
            continue
        kept.append(alignment)
        per_section[alignment.section] = per_section.get(alignment.section, 0) + 1
    return kept


def _align_section(
    scope: Scope,
    section: overlap_segments.DraftSection,
    draft_vectors,
    citekey: str,
    encoded: tuple[list[overlap_segments.SourceSentence], object],
) -> list[SectionAlignment]:
    """`section` against one source, as reportable alignments."""
    source, source_vectors = encoded
    if not source:
        return []
    cosines = scope.embedder.similarity(draft_vectors, source_vectors)
    scores = [[value - overlap_align.TAU for value in row] for row in cosines]
    found = []
    for alignment in overlap_align.align(scores):
        draft_span = section.sentences[alignment.draft_start : alignment.draft_end]
        source_span = source[alignment.source_start : alignment.source_end]
        source_text = " ".join(s.text for s in source_span)
        matched = overlap_segments.matched_words(section, alignment.matched)
        found.append(
            SectionAlignment(
                section=section.title,
                citekey=citekey,
                page=min(s.page for s in source_span),
                end_page=max(s.page for s in source_span),
                score=alignment.score,
                word_start=draft_span[0].word_start,
                word_end=draft_span[-1].word_end,
                matched_words=matched,
                source_text=source_text,
            )
        )
    return found
