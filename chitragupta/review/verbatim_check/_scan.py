"""`scan`'s orchestrator: union every detection tier, dedupe, bucket by
severity, and the published finding shape both `scan` and `recheck` read.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

from pathlib import Path

from chitragupta import overlap_index
from chitragupta.review.verbatim_check._allowlist import _load_allowlist_phrases
from chitragupta.review.verbatim_check._embed import _embed_tier_findings
from chitragupta.review.verbatim_check._exact import _exact_tier_findings
from chitragupta.review.verbatim_check._masking import _tokenize_draft
from chitragupta.review.verbatim_check._shared import _newline_offsets
from chitragupta.review.verbatim_check._skipgram import _skipgram_tier_findings


def scan_findings(
    draft: str | Path, min_run: int | None = None, gap: int = 1, limit: int | None = None
) -> tuple[list[dict], int, int, list[dict]]:
    """Slide `draft`'s whole normalized text across every built detection
    tier (`_exact_tier_findings`, `_skipgram_tier_findings`,
    `_embed_tier_findings`), the first two grouping their own matches by
    `(citekey, diagonal)` and merging into maximal same-diagonal runs,
    the third aligning sentence embeddings within the scope its dossier
    records. Returns `(findings, min_run, suppressed, not_run)`:
    `findings` is every tier's findings unioned (minus anything a
    stronger tier already covers -- see below) and sorted longest-first,
    each dict naming which tier produced it (`"tier"`); `suppressed` is
    the total the allowlist (see `_load_allowlist_phrases`) dropped,
    summed across tiers; `not_run` is one `{"tier", "reason", "partial"}`
    entry per gap in what a tier covered -- either it did not run at all
    (`"partial": False`) or it ran but not against everything the draft
    cites (`"partial": True`, #499) -- and a tier can contribute more
    than one entry, e.g. a renamed heading and a stale embedded corpus
    are independent gaps with independent fixes.

    `not_run` is the fourth return value rather than a silent empty
    contribution because the two are not the same claim. Tiers 1 and 2
    are always available, so an empty result from either means "checked,
    nothing found". Tier 3 depends on the optional enrichment layer, a
    built `content/chroma/`, Docling sidecars and the draft's dossier;
    an empty result from it means either "checked, nothing found",
    "never ran", or "ran, but only against part of what this draft
    cites" -- and a report that cannot tell a reader which is
    overstating what was checked.

    Every tier finder shares this function's tokenization, allowlist and
    newline bookkeeping -- computed once here, not once per tier -- and
    returns `(tier_findings, tier_suppressed)` in the same finding-dict
    shape `_PAYLOAD_FIELDS` publishes; nothing downstream of this
    function (bucketing, rendering, the JSON payload) needs to know how
    many tiers ran or which one produced any given finding beyond
    reading `"tier"`.

    This function never raises for "nothing found" and returns an empty
    list in that case -- this is a review aid, not a gate, and it is not
    wired into anything that treats a nonzero exit as a failure. It does
    raise `ValueError` for a request it cannot honor at all -- `min_run`
    below a tier's own n-gram size, or a malformed allowlist file -- that
    is not "no findings", it is "this input can't be scanned as asked",
    and the `scan` CLI (below) turns it into the same stderr-plus-exit-2
    usage error as its other malformed invocations, e.g. `--gap` with no
    value.

    A finding is dropped, not just flagged, when the allowlist accounts
    for enough of it that what's left would not itself have cleared
    `min_run` -- e.g. a run that is entirely one allowlisted standard's
    name. A run that merely *contains* a short allowlisted phrase inside
    a much longer otherwise-unexplained lift is kept: suppressing the
    whole thing would hide the real overlap the allowlist was never
    meant to excuse.
    """
    if min_run is None:
        min_run = overlap_index.DEFAULT_N

    text = Path(draft).read_text(encoding="utf-8")
    words, paragraph_citekeys = _tokenize_draft(text)
    word_strs = [w.text for w in words]
    newlines = _newline_offsets(text)
    allowlist = _load_allowlist_phrases()

    exact_findings, exact_suppressed = _exact_tier_findings(
        words, word_strs, paragraph_citekeys, newlines, text, min_run, gap, allowlist
    )
    skipgram_findings, skipgram_suppressed = _skipgram_tier_findings(
        words, word_strs, paragraph_citekeys, newlines, text, min_run, gap, allowlist
    )
    # Pure verbatim reuse trivially satisfies skip-gram matching too --
    # nothing in the text changed, so both families' stems line up
    # exactly -- which means tier 2 would otherwise re-report every tier
    # 1 finding a second time under `"tier": "skip-gram"`, adding no new
    # information. Drop a skip-gram finding whenever an exact-tier
    # finding for the *same citekey* already covers an overlapping span:
    # tier 2 exists to surface what tier 1 structurally cannot, not to
    # duplicate what it already did.
    # Drop a skip-gram finding only when an exact finding fully CONTAINS its
    # span -- the pure-verbatim-reuse case where tier 2 trivially re-finds
    # what tier 1 already reported. A merely-overlapping exact finding (a
    # short verbatim island inside a longer paraphrased passage) must not
    # suppress the skip-gram finding: the wider paraphrase span is exactly
    # the signal this tier exists to surface, and containment is the
    # narrowest test that still avoids the redundant report.
    skipgram_findings = [
        f
        for f in skipgram_findings
        if not any(
            e["citekey"] == f["citekey"]
            and e["start"] <= f["start"]
            and f["start"] + f["span_words"] <= e["start"] + e["span_words"]
            for e in exact_findings
        )
    ]

    # Tier 3 is filtered against these two tiers' spans *before* it ever
    # applies its own per-section cap -- see `_embed_tier_findings` for
    # why the order matters (#499) -- so nothing further needs doing
    # with `embed_findings` here.
    lexical_findings = exact_findings + skipgram_findings
    embed_findings, embed_suppressed, embed_reasons = _embed_tier_findings(
        draft,
        words,
        word_strs,
        paragraph_citekeys,
        newlines,
        text,
        min_run,
        allowlist,
        lexical_findings,
    )

    findings = lexical_findings + embed_findings
    suppressed = exact_suppressed + skipgram_suppressed + embed_suppressed
    not_run = [{"tier": "embedding", **entry} for entry in embed_reasons]

    # Longest run first, no silent truncation -- every finding above the
    # floor prints unless --limit narrows it, matching the issue's explicit
    # break from `overlap`'s hardcoded top-25.
    findings.sort(key=lambda f: (-f["span_words"], f["citekey"], f["start"]))
    if limit is not None:
        findings = findings[:limit]
    return findings, min_run, suppressed, not_run


def _flags(finding: dict) -> list[str]:
    flags = []
    if not finding["cites_source"]:
        flags.append("UNCITED SOURCE")
    if finding["quoted"]:
        flags.append("quoted")
    return flags


def _matched_note(finding: dict) -> str:
    if finding["matched_words"] == finding["span_words"]:
        return ""
    return f", {finding['matched_words']} matched"


def _tier_note(finding: dict) -> str:
    """`tier=exact`, or `tier=embedding, score=0.41` where there is a
    score to report.

    The score rides inside the tier's own parenthesis rather than beside
    the word count, because it is only meaningful *given* the tier: it is
    an alignment strength in `overlap_embed`'s shifted-cosine units, not
    a probability and not comparable to anything tier 1 or tier 2
    reports.
    """
    if finding["score"] is None:
        return f"tier={finding['tier']}"
    return f"tier={finding['tier']}, score={finding['score']}"


def _page_range(finding: dict) -> str:
    """`p.N` for an ordinary single-page run, `p.N-M` for one whose
    postings start on more than one page (#131).

    Not a guarantee that `p.N` never means multi-page content: `page`/
    `end_page` are the pages an n-gram in the run actually *starts* on, so
    a remainder shorter than the index's own n-gram size -- recovered
    into the run's word content because nothing that short can start a
    gram of its own -- can leave `end_page` unmoved even though the run's
    text reaches that page. See `scan_findings`'s docstring."""
    page, end_page = finding["page"], finding["end_page"]
    return f"p.{page}" if page == end_page else f"p.{page}-{end_page}"


# A run at or above this many words is "long" for bucketing purposes
# (see `_bucket`) -- a fixed policy constant, not a flag: the threshold
# is project-wide reading guidance, not a per-invocation choice.
LONG_RUN_WORDS = 15

# Most-damning-first: an uncited long run first, then an uncited short
# one, and only then a quoted-and-cited run, which is the likeliest to be
# a deliberate, legitimate quotation.
BUCKET_ORDER = ("long", "short", "quoted")


def _bucket(finding: dict) -> str:
    """Which severity bucket the written report groups `finding` under.

    `quoted` only demotes a run to the low-priority `quoted` bucket when
    it *also* cites its source -- a quoted-but-uncited run is still the
    finding `overlap` structurally cannot make and `_flags` calls "the
    one most worth reading first" (see below); burying it under `quoted`
    just because it happens to sit inside quote marks would contradict
    that. It buckets by length like any other uncited run instead.

    Length is judged on `matched_words`, not `span_words`. For the exact
    tier the two are nearly identical (`--gap` only ever interpolates a
    handful of edited words). For the skip-gram tier they are not:
    `span_words` is the raw width of a family window and can run to
    dozens of words on the evidence of a handful of matched stemmed
    content words. Bucketing on `span_words` would let a weakly-evidenced
    skip-gram finding outrank a strongly-evidenced one solely because its
    window happened to stretch across more stopwords.
    """
    if finding["quoted"] and finding["cites_source"]:
        return "quoted"
    return "long" if finding["matched_words"] >= LONG_RUN_WORDS else "short"


def _bucket_title(bucket: str) -> str:
    if bucket == "long":
        return f"Long runs (>= {LONG_RUN_WORDS} matched words)"
    if bucket == "short":
        return "Short runs"
    return "Quoted runs"


def _not_run_lines(not_run: list[dict]) -> list[str]:
    """One line per tier that did not run, naming it and why.

    Shared by the printed and written forms so the two cannot end up
    saying different things about the same scan -- the same reason
    `scan_command` is built once and handed to both.
    """
    return [f"tier {entry['tier']} did not run: {entry['reason']}" for entry in not_run]


# The finding fields the JSON payload publishes, in the order they are
# written. Spelled out rather than serialising `scan_findings`' dicts
# directly: those are this module's working representation and a key
# added there for some later internal purpose would otherwise silently
# become part of a published contract that #128's severity buckets and
# #129's remediation loop consume.
_PAYLOAD_FIELDS = (
    "id",
    "citekey",
    "page",
    "end_page",
    "tier",
    "span_words",
    "matched_words",
    "start",
    "line",
    "char_start",
    "char_end",
    "draft_text",
    "fragment",
    "context",
    "cites_source",
    "quoted",
    # Tier 3's alignment strength, `None` on the two deterministic tiers
    # (#134). Appended rather than slotted next to `span_words`, so a
    # consumer reading these positionally -- `bench/`'s `KEPT_FIELDS`
    # lists are written by hand against this order -- sees the same
    # prefix it saw before the tier existed.
    "score",
)


def published(finding: dict) -> dict:
    """One of `scan_findings`' working dicts as the payload publishes it:
    `_PAYLOAD_FIELDS` in order, plus the derived `severity`.

    One function rather than the same comprehension in `scan_payload` and
    `recheck_findings`, so "what a published finding looks like" has a
    single definition -- `recheck` compares its own freshly-scanned
    findings against a baseline written by `scan`, and the two disagreeing
    about the shape is the one way that comparison could go quietly
    wrong.
    """
    return {
        **{field: finding[field] for field in _PAYLOAD_FIELDS},
        "severity": _bucket(finding),
    }
