"""Tier 3: embedding-based paraphrase detection by local alignment over
sentence embeddings.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
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
    """Tier 3: embedding-based paraphrase detection by local alignment
    over sentence embeddings (`chitragupta/overlap_embed.py`, #134/#164). Same
    shared contract as the other two tier finders, plus a third return
    value the other two have no use for: **what this run does not cover**.

    `lexical_findings` is tier 1's and tier 2's own findings (already
    computed by the caller), needed *before* `overlap_embed.report()`
    narrows the alignments -- see the comment at the filter below for
    why the order matters (#499).

    That third value -- `[{"reason": str, "partial": bool}, ...]` -- is
    the point of the tier being wired in at all on a host that cannot run
    it, or that cannot run it against everything a draft cites. Tier 1
    and tier 2 are always available -- they read an index this repo
    builds from parsed text with no optional dependency -- so "found
    nothing" is the only thing either can say. This tier needs the
    enrichment layer's embedding stack, a built `content/chroma/`,
    Docling passage sidecars and the draft's own dossier, any of which
    can be absent on a perfectly healthy checkout (`partial: False`,
    nothing else ran); and even when it can run, a heading renamed since
    the dossier was last written or a cited source the corpus grew since
    `enrich` last ran can each leave part of a draft uncompared while the
    tier still reports real findings elsewhere (`partial: True`, #499).
    A caller that only asked "did this tier run at all" could not tell
    either partial case from a clean, complete run.

    No `gap` parameter, unlike the other two. Tier 1 and tier 2 merge
    same-diagonal matches with a word-level gap tolerance; the alignment
    here has its own, in sentences, as `overlap_align.GAP_PENALTY` --
    a *cost* rather than a limit, so there is no equivalent flag for
    `--gap` to set and pretending otherwise would put a word count in
    charge of a sentence-level decision.
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
        # This function opened the scope, so it closes it -- on every
        # path, including the two mid-function returns below (#516/m-79).
        # The body moved into `_findings_within` rather than growing a
        # `try` around forty lines: the release belongs to whoever
        # acquired, and that is here.
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
    """`findings`'s body, once tier 3 is known to be runnable.

    Split only so the caller above can own the scope's lifetime; every
    comment about *what* this does is on the caller's docstring.
    """
    sections, unmatched = overlap_segments.draft_sections(
        text, [(w.char, w.char_end) for w in words], scope.citekeys_by_section
    )
    if not sections:
        # The dossier records citekeys against section headings that this
        # draft no longer has -- a heading renamed since `sections
        # --citekeys` last wrote the table, or a `sections.md` written by
        # a release whose heading convention differed. Nothing to scope
        # to, and the tier says so rather than reporting a clean scan of
        # a draft it never compared against anything.
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
    # The position map is built from *every* alignment and the report
    # from the narrowed list -- in that order, and not the other way
    # round. `_cites_source` asks whether a paragraph cites any citekey
    # that matched somewhere in the span, and `report` has by then
    # dropped the four weaker sources that matched the same passage. Read
    # off the narrowed list, a correctly-cited paragraph would report as
    # `UNCITED SOURCE` whenever the strongest match happened to be a
    # paper it does not name.
    citekeys_at_position = _embed_citekeys_at_positions(alignments)

    # Filtered against tier 1's and tier 2's spans *before* `report()`
    # applies its per-section cap, not after (#499). A section that
    # quotes a source verbatim -- the strongest alignment there -- and
    # also paraphrases it elsewhere used to lose the paraphrase: the
    # verbatim alignment consumed the section's one cap slot, and only
    # afterwards was it discovered to duplicate the exact-tier finding
    # and dropped. Filtering first lets the cap fall on what tiers 1
    # and 2 could not already see, which is the point of this tier.
    # Overlap, not containment -- a tier-3 alignment is a whole passage
    # and normally *contains* the exact or skip-gram span rather than
    # the other way round, so containment would never fire and the same
    # passage would be reported twice.
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
    """The `partial: True` entries `_embed_tier_findings` returns
    alongside real findings -- coverage gaps that do not stop the tier
    from running, unlike the two `partial: False` cases above (#499).

    Two independent gaps, kept as two independent entries rather than
    merged into one message: a renamed heading and a corpus grown since
    `enrich` last ran have different fixes, and a reviewer needs to tell
    them apart.
    """
    reasons = []
    if unmatched:
        # Some, not zero, of the recorded sections matched -- the tier
        # still runs and still reports real findings, so this is not the
        # "nothing to scope to" case above. A draft with 9 of 10 headings
        # renamed would otherwise scan the one matched section and say
        # nothing about the other nine.
        #
        # The denominator is `scope.citekeys_by_section`, not `unmatched
        # + len(sections)` -- `sections` only holds sections that also
        # survived prose/sentence extraction, so a matched heading with
        # no usable prose (an empty section, or one that is only code or
        # fences) would silently disappear from that count too.
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
    """The tier-3 analogue of `_citekeys_at_positions`: every draft word
    position an alignment covers, mapped to the citekeys aligned there.

    Same purpose as tier 1's and tier 2's -- a passage that restates a
    definition several corpus papers each state will align against all of
    them, and a paragraph correctly citing any one of them is correctly
    attributed. Without this, the other matches would each report
    `UNCITED SOURCE` against a paragraph that cites its source properly
    (the Kritzinger case `_cites_source` documents, which a
    similarity-based tier hits harder than either lexical one).
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
    """The finding dict for one alignment. Mirrors `_exact_finding` and
    `_skipgram_finding`, and carries the one field they cannot: `score`,
    the alignment's own strength.
    """
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
        # Rounded where it is built, not where it is printed: the JSON
        # payload and the Markdown report both read this field, and a
        # float that renders differently in the two is the kind of
        # difference nobody notices until a diff of two reports is
        # noise. Three places is well inside what separates two
        # alignments in practice.
        "score": round(alignment.score, 3),
    }
