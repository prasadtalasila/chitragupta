"""Tier 3 of the overlap scan: embedding-based paraphrase detection, by
local alignment over sentence embeddings.

The third and last of the detection tiers `docs/PLAGIARISM-DESIGN.md` names
(#134, #164, closing #132). Tiers 1 and 2 -- `chitragupta/overlap_index.py`'s
exact word-8-grams and `chitragupta/overlap_skipgram.py`'s stemmed odd/even
skip-grams -- both match on *token position*, so both break the moment a
paraphrase moves a qualifier or splices two sentences. That is the
family-split design working as specified, and it is why a hand read of
one real 15-chapter book found 59 close-paraphrase candidates of which 34
fired neither tier (#134's 2026-08-14 comments). Cosine similarity does
not care about token position, which is why this tier exists.

**Advisory only, permanently.** `content/chroma/` is namespaced per
`[enrich].embedding_model` precisely because vectors change when that
setting does, so a finding here is not reproducible across a config edit
and can never satisfy `docs/PLAGIARISM-DESIGN.md`'s "only deterministic checks
may block" line. There is no gate-eligibility check *here* to enforce
that, because nothing in `chitragupta/` decides gate-eligibility for any tier
today (#130, undecided) and inventing a gate path to exclude this tier
from would be the speculative abstraction DEVELOPER-AGENTS.md forbids.
The structural guarantee lives where the only gate-shaped predicate in
this repo lives: `bench/bench_overlap_gate.py::eligible()` admits
`exact` and nothing else, and its own self-test asserts a `tier:
"embedding"` finding is ineligible.

## Shortlist, then align

Alignment costs `O(|draft segments| x |source segments|)` per candidate
pair, which is fine over a handful of sources and impossible corpus-wide
(#164). So the tier never searches the corpus. It **scopes** each section
to the citekeys its dossier records that section as written from,
**shortlists** those against the collection the enrichment layer already
built (`overlap_chroma.shortlist`), and **aligns** the section's segments
against those sources' segments (`overlap_segments`,
`overlap_align.align`).

Scoping to the dossier is not only cheaper, it is the only shape that
works here. This pipeline aims at a deep single-field corpus and the
drafts are written *from* it via `chitragupta.retrieval`, so a draft segment's
nearest corpus neighbours are, by construction, the passages it was
legitimately grounded in: a corpus-wide cosine threshold would re-detect
the pipeline's own retrieval step. `docs/PLAGIARISM-DESIGN.md` carries the
argument and the measurement (`bench/bench_overlap_df.py`) behind it.

## What it reports

A `SectionAlignment` per aligned passage pair, carrying the draft word
span (#131's coordinate system, shared with tiers 1 and 2, so the three
can be deduplicated against each other), the page range and the score.
`report` narrows those to what a reader sees, and it **ranks rather than
thresholds** -- see that function for the measurement saying why a
threshold cannot work in this corpus.

Needs the optional `enrich` Poetry group, a built `content/chroma/` and
a synced ledger to read source passages from. When any of that is
missing -- or the draft has no dossier, or no source has a passage
sidecar -- `unavailable_reason()` (in `chitragupta/overlap_embed_scope.py`
since #516, re-exported here) says *which*, and `scan`
prints it: an unbuilt tier that says nothing and a built tier that found
nothing look identical in a report, and only one means the draft was
checked.
"""

from dataclasses import dataclass

from chitragupta import overlap_align, overlap_chroma, overlap_segments

# Re-exported so every existing `overlap_embed.Scope` /
# `.open_scope` / `.unavailable_reason` caller keeps resolving -- see
# chitragupta/overlap_embed_scope.py for why they moved. `__all__` names
# them so the import is not read as unused.
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

# How many of a section's cited sources are aligned against, after the
# chroma shortlist ranks them. A section citing more than this is
# ordinarily citing a couple of sources for its argument and the rest in
# passing; the shortlist is what decides which is which. A named module
# constant rather than config, for the reason `chitragupta/overlap_align.py`
# gives about the alignment's own constants.
SHORTLIST_SOURCES = 5

# How many alignments a scan reports per *section*. A cap, not a
# threshold -- see `report`.
#
# Per section rather than per draft, and this is load-bearing rather
# than cosmetic. A draft-wide cap ranks every section's findings against
# each other, and alignment scores are not comparable across sections:
# a section whose sources happen to be written in the draft's own
# register scores higher throughout than one whose sources are
# equations and tables, so a draft-wide top-N fills up with the former
# and never reports the latter at all. Measured on chapter 1 of the real
# book: a draft-wide cap of 12 dropped the one hand-verified organic
# paraphrase in the chapter (`singh_digital_2023`), which is the
# strongest alignment *in its own section*. Per section, it is reported.
SECTION_LIMIT = 1


# --------------------------------------------------------------------------
# The tier itself
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SectionAlignment:
    """One aligned passage pair, in the terms a finding needs.

    `section` is the draft heading it was found under -- not published in
    the finding, but what `report` ranks within."""

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

    Each source is segmented and embedded once for the whole draft and
    each section once for all its sources: a book chapter's sections
    routinely cite the same three papers, and encoding is essentially the
    whole cost of this tier.

    Everything is returned, unranked and undeduplicated -- `report`
    below is what turns this into what a reader sees. The two are
    separate because `chitragupta/review/verbatim_check.py` needs the full list
    to work out which citekeys matched where before it narrows
    (`_cites_source`: a passage several corpus papers each state can be
    cited to any one of them, and a narrowed list has already thrown
    away the evidence for that).
    """
    # No lexical-overlap ceiling here, deliberately, and it is worth
    # saying why because #134 asks for one: "high cosine + *low lexical
    # overlap*", so that a passage tiers 1 or 2 already caught verbatim
    # is not reported twice. That is the right goal and the wrong
    # mechanism -- a ceiling is an a-priori guess that high wording
    # overlap implies a deterministic tier caught it, and
    # `scan_findings` can simply *check*, by dropping any alignment a
    # real exact or skip-gram finding overlaps. The guess is not
    # harmless: measured on `bench/fixtures/graded-paraphrase-of-
    # singh-offload-2022.md`, a ceiling of 0.55 threw away the
    # strongest alignment in the whole fixture (0.83, the
    # word-substitution grade) -- which neither deterministic tier
    # caught, because substituting words also moved them. The check
    # replaces the guess; the goal is unchanged.
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

    **A ranking, not a verdict**, which is the shape #134's own redesign
    asks for ("report a ranked top-N, always, with scores -- no cutoff to
    tune and no pretence of a verdict") and the shape this corpus
    forces. A cutoff was tried and cannot work here: on the one
    hand-verified organic pair in the real book, the draft's restatement
    of `singh_digital_2023`'s ROI claim scores 0.62 against the source
    sentence it restates, while the same draft sentence's opening clause
    scores 0.74 against that paper's own description of its case study.
    Both are that sentence leaning on that paper, and no threshold
    between them means anything -- but a ranking puts the sentence near
    the top of its section either way, which is all a reviewer needs to
    go and read it.

    One per draft span, because the same passage aligning against four of
    a section's five cited sources is one place to look, not four. The
    strongest survives and the rest are dropped after
    `_citekeys_at_positions` has already recorded that they matched.
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
