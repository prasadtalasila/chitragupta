"""`scan`'s orchestrator: union every detection tier, dedupe, bucket by
severity, and the published finding shape both `scan` and `recheck` read.
"""

from pathlib import Path

from chitragupta import citation_gate, overlap_index, style_exceptions
from chitragupta.review.verbatim_check._allowlist import _load_allowlist_phrases
from chitragupta.review.verbatim_check._citekeys import _known_citekeys
from chitragupta.review.verbatim_check._corpus import norm
from chitragupta.review.verbatim_check._embed import _embed_tier_findings
from chitragupta.review.verbatim_check._exact import _exact_tier_findings
from chitragupta.review.verbatim_check._masking import _tokenize_draft
from chitragupta.review.verbatim_check._names import names_heavy
from chitragupta.review.verbatim_check._shared import _newline_offsets
from chitragupta.review.verbatim_check._skipgram import _skipgram_tier_findings


def scan_findings(
    draft: str | Path, min_run: int | None = None, gap: int = 1, limit: int | None = None
) -> tuple[list[dict], int, int, list[dict]]:
    """Run `draft` through every detection tier (exact, skip-gram,
    embedding), sharing one tokenization, allowlist and newline map.
    Returns `(findings, min_run, suppressed, not_run)`: findings unioned,
    deduped and longest-first, each naming its `"tier"`; `suppressed` is
    what the allowlist dropped; `not_run` is one `{"tier", "reason",
    "partial"}` per coverage gap (#499).

    `not_run` exists because an empty tier 3 may mean "checked, nothing",
    "never ran" or "ran on part", unlike always-available tiers 1 and 2.
    Never raises for "nothing found" (a review aid); raises `ValueError`
    for a request it cannot honour (`min_run` below the n-gram size, a
    malformed allowlist), which the CLI makes exit 2. A finding is dropped
    only when the allowlist leaves less than `min_run` of it; a long lift
    merely containing an allowlisted phrase is kept.
    """
    if min_run is None:
        min_run = overlap_index.DEFAULT_N

    text = Path(draft).read_text(encoding="utf-8")
    words, paragraph_citekeys = _tokenize_draft(
        text, latex=citation_gate.is_latex(draft), citekeys=_known_citekeys()
    )
    word_strs = [w.text for w in words]
    newlines = _newline_offsets(text)
    # Declared project terms (#1187) are allowlist phrases: a run they
    # account for cannot be repaired by rewording, so it is not reported.
    terms = (tuple(norm(term)) for term in style_exceptions.terms())
    allowlist = _load_allowlist_phrases() + [t for t in terms if t]

    exact_findings, exact_suppressed = _exact_tier_findings(
        words, word_strs, paragraph_citekeys, newlines, text, min_run, gap, allowlist
    )
    skipgram_findings, skipgram_suppressed = _skipgram_tier_findings(
        words, word_strs, paragraph_citekeys, newlines, text, min_run, gap, allowlist
    )
    # Drop a skip-gram finding only when an exact finding for the same
    # citekey fully CONTAINS it (pure verbatim reuse re-found). Mere overlap
    # must not suppress it: a verbatim island inside a longer paraphrase is
    # the paraphrase this tier exists to surface.
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

    # Tier 3 already filters against these spans before its cap (#499).
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

    # Longest first, no silent truncation unless --limit asks.
    for f in findings:
        f["names"] = names_heavy(f.get("draft_text") or "")
    findings.sort(key=lambda f: (-f["span_words"], f["citekey"], f["start"]))
    if limit is not None:
        findings = findings[:limit]
    return findings, min_run, suppressed, not_run


# "Long" for bucketing: project-wide reading guidance, not a flag.
LONG_RUN_WORDS = 15

# Most-damning first; quoted-and-cited is likeliest a legitimate quotation.
BUCKET_ORDER = ("long", "short", "quoted")


def _bucket(finding: dict) -> str:
    """Which severity bucket the written report groups `finding` under.

    `quoted` only when also cited: a quoted-but-uncited run is the one
    most worth reading first (`_flags`). Length uses `matched_words`, not
    `span_words`, which for skip-grams can stretch across many stopwords
    on little evidence.
    """
    if finding["quoted"] and finding["cites_source"]:
        return "quoted"
    return "long" if finding["matched_words"] >= LONG_RUN_WORDS else "short"


def _bucket_title(bucket: str) -> str:
    """`"words of evidence"`, not `"matched words"`: on tier 3 the field is
    the aligned width, not shared wording, which `_words_note` denies."""
    if bucket == "long":
        return f"Long runs (>= {LONG_RUN_WORDS} words of evidence)"
    if bucket == "short":
        return "Short runs"
    return "Quoted runs"


# The published finding fields, in order. Spelled out so an internal key
# never silently joins the contract #128's buckets and #129's loop consume.
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
    # 1-based, beside `line`: both are human-readable locators.
    "paragraph",
    "end_paragraph",
    "char_start",
    "char_end",
    "draft_text",
    "fragment",
    "context",
    "cites_source",
    "quoted",
    # Tier 3's strength, `None` on deterministic tiers (#134). Appended:
    # `bench/`'s hand-written `KEPT_FIELDS` read positionally.
    "score",
    # Tier 3's source passage; `None` where `fragment` is both sides.
    "source_text",
    # A short run mostly of copied proper names (#1187): the agenda
    # surfaces it to a person instead of marking it unattended.
    "names",
)


def published(finding: dict) -> dict:
    """One of `scan_findings`' working dicts as the payload publishes it:
    `_PAYLOAD_FIELDS` in order, plus `severity`. One definition, since
    `recheck` compares fresh findings against a `scan` baseline.
    """
    return {
        **{field: finding[field] for field in _PAYLOAD_FIELDS},
        "severity": _bucket(finding),
    }
