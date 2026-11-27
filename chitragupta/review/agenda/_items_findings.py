"""Item extractors reading the other aids' `.json` and `style_check`'s
findings.

`synthesis` and `figure` are read but produce no items, for distinct
reasons: `synthesis` has no row in docs/AUTO-IMPROVEMENT.md's item-class
table (a doc-scope decision), and `figure_layout`'s findings carry no `id`
or severity to hang an identity or ranking on.
"""

from chitragupta.dossier._sections import Section
from chitragupta.review._quotation_render import which
from chitragupta.review.agenda._identity import item_id, section_anchor
from chitragupta.review.agenda._items import Item
from chitragupta.review.agenda._sources import AidSource, StyleSource


def verbatim_run_items(source: AidSource, sections: list[Section]) -> list[Item]:
    """`severity == \"short\"` is unattended (`agenda-reviser` handles
    it); `\"long\"` is surfaced (#129); `\"quoted\"` is excluded."""
    if not source.available:
        return []
    items = []
    for finding in source.data.get("findings", []):
        severity = finding.get("severity")
        if severity not in ("long", "short"):
            continue
        line = finding.get("line")
        section = section_anchor(sections, line)
        span = finding.get("fragment") or finding.get("draft_text") or finding.get("id", "")
        citekey = finding.get("citekey")
        # `span_words`, plus `matched_words` when they differ, as the aid's
        # own report ("15 words, 6 matched"): matched words alone described a
        # gapped match as shorter than `--min-run`. `_matched_note` is not
        # imported: this module reads filed JSON only, tolerating partial
        # payloads, so an agenda builds without the aid importable.
        words = finding.get("span_words", "?")
        matched = finding.get("matched_words", "?")
        tier = finding.get("tier")
        items.append(
            Item(
                id=item_id("verbatim", "verbatim-run", section, citekey, span),
                cls="verbatim-run",
                section=section,
                citekey=citekey,
                line=line,
                # `short` and a deterministic tier: `_bucket` ignores `tier`,
                # so a short embedding alignment once authorised
                # `agenda-reviser` to edit a passage on a similarity score.
                # `verbatim_check/_recheck.py` treats that tier as advisory
                # only (#500), and advisory cannot also be safe unasked.
                # `names` (#1187): a run mostly of proper names is a
                # person's judgement; `.get` keeps older baselines unchanged.
                unattended=(
                    severity == "short" and tier != "embedding" and not finding.get("names", False)
                ),
                summary=_run_summary(tier, words, matched, citekey),
                detail={"severity": severity, "verbatim_id": finding.get("id")},
                # `draft_text`, not the hashed `fragment`: only the former
                # is `draft[char_start:char_end]` (R12).
                span=finding.get("draft_text") or None,
            )
        )
    return items


def _run_summary(tier: str | None, words, matched, citekey: str | None) -> str:
    """One line naming what the tier actually found: only the exact tier
    is a "verbatim run", and calling a restatement one overclaims. A
    report predating `tier` falls back to the neutral "run".
    """
    kind = {
        "exact": "verbatim run",
        "skip-gram": "skip-gram match",
        "embedding": "embedding-tier alignment",
    }.get(tier, "run")
    return (
        f"{words}-word {kind}"
        + (f" citing `{citekey}`" if citekey else "")
        + (f", {matched} matched" if matched != words else "")
    )


def prose_items(source: StyleSource, sections: list[Section]) -> list[Item]:
    """One item per `style_check` finding, as-is: it already keeps to
    WRITING-STANDARDS.md Section 9's decidable rules. A `line` of 0
    (acronym-drift) is treated as None.

    Unattended (issue 421): the repair is a draft edit (R1's write-set)
    and fixes rather than disguises the finding, there being no evidential
    claim to misrepresent; R3 was tested (a caption and a reference zeroed
    `TableNoCaption` and `FigureUnreferenced`). Except a finding marked
    `repair="review"` (issue 836), whose right repair may be to leave it;
    the rule decides that, this only reads it."""
    if not source.available or source.data is None:
        return []
    items = []
    for finding in source.data.get("findings", []):
        line = finding.get("line") or None
        section = section_anchor(sections, line)
        span = f"{finding.get('rule', '')}\x00{finding.get('match', '')}"
        items.append(
            Item(
                id=item_id("style_check", "prose", section, None, span),
                cls="prose",
                section=section,
                citekey=None,
                line=line,
                unattended=finding.get("repair", "edit") == "edit",
                summary=f"{finding.get('rule')}: {finding.get('match')!r} "
                f"({finding.get('count', 1)}x)",
                detail={
                    "message": finding.get("message"),
                    "severity": finding.get("severity"),
                    "count": finding.get("count"),
                },
                # Vale's `Match` alone: the id hashes `rule\x00match`, not
                # draft text (R12); never refused in practice (#839).
                span=finding.get("match") or None,
            )
        )
    return items


def unsupported_claim_items(source: AidSource, sections: list[Section]) -> list[Item]:
    """Every provenance finding except `band == \"supported\"`."""
    if not source.available:
        return []
    items = []
    for finding in source.data.get("findings", []):
        if finding.get("band") == "supported":
            continue
        line = finding.get("line")
        section = section_anchor(sections, line)
        claim = finding.get("claim", "")
        citekey = finding.get("citekey")
        items.append(
            Item(
                id=item_id("provenance", "unsupported-claim", section, citekey, claim),
                cls="unsupported-claim",
                section=section,
                citekey=citekey,
                line=line,
                unattended=False,
                summary=f"`[@{citekey}]` scores {finding.get('band')}: {claim[:80]}",
                detail={
                    "band": finding.get("band"),
                    "score": finding.get("score"),
                    "claim": claim,
                    "provenance_id": finding.get("id"),
                },
            )
        )
    return items


def claim_support_items(source: AidSource, sections: list[Section]) -> list[Item]:
    """One item per finding the entailer scored (`note` set means nothing
    to rank). Unfiltered by design: a cutoff would claim a precision this
    corpus lacks, so `_order.severity_rank` ranks instead. The summary
    says the score is no verdict, since an item is read without the
    standalone report's caveat."""
    if not source.available:
        return []
    items = []
    for finding in source.data.get("findings", []):
        if finding.get("note") is not None:
            continue
        line = finding.get("line")
        section = section_anchor(sections, line)
        claim = finding.get("claim", "")
        citekey = finding.get("citekey")
        score = finding.get("score")
        items.append(
            Item(
                id=item_id("support", "claim-support", section, citekey, claim),
                cls="claim-support",
                section=section,
                citekey=citekey,
                line=line,
                unattended=False,
                summary=f"`[@{citekey}]` entailment score {score:.0%} "
                f"(not a verdict): {claim[:80]}",
                detail={"score": score, "claim": claim, "support_id": finding.get("id")},
            )
        )
    return items


def uncited_claim_items(source: AidSource, sections: list[Section]) -> list[Item]:
    """Every uncited-prose finding becomes an item (already binary)."""
    if not source.available:
        return []
    items = []
    for finding in source.data.get("findings", []):
        line = finding.get("line")
        section = section_anchor(sections, line)
        sentence = finding.get("sentence", "")
        items.append(
            Item(
                id=item_id("uncited", "uncited-claim", section, None, sentence),
                cls="uncited-claim",
                section=section,
                citekey=None,
                line=line,
                unattended=False,
                summary=sentence[:80],
                detail={"block_cites": finding.get("block_cites"), "uncited_id": finding.get("id")},
            )
        )
    return items


def misquoted_items(source: AidSource) -> list[Item]:
    """One item per `absent` quotation (`unverifiable` is a parse limit,
    never a finding). No line: the quote lives in `evidence.md`, which
    `agenda-reviser` cannot edit, hence no unattended repair."""
    if not source.available:
        return []
    items = []
    for finding in source.data.get("findings", []):
        citekey = finding.get("citekey")
        quote = finding.get("quote", "")
        # `.get`: a report filed before #1174 has no `index`/`of`.
        position = which(finding.get("index", 1), finding.get("of", 1))
        items.append(
            Item(
                id=item_id("quotation", "misquoted", None, citekey, quote),
                cls="misquoted",
                section=None,
                citekey=citekey,
                line=None,
                unattended=False,
                summary=f"`[@{citekey}]`'s quoted span{position} was not found in its source: "
                f"{quote[:80]}",
                detail={
                    "near_miss_page": finding.get("near_miss_page"),
                    "near_miss_score": finding.get("near_miss_score"),
                    "quotation_id": finding.get("id"),
                },
            )
        )
    return items
