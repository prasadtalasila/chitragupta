"""Item extractors reading the other aids' `.json` and `style_check`'s
findings -- split out of `_items.py` once the drift-based extractors,
this half and `all_items` together crossed the 250-code-line cap.

`synthesis` and `figure` are read (`_sources.py`) but produce no items
here, for two different reasons worth keeping distinct: `synthesis`
carries a stable `finding_id` (`chitragupta/review/synthesis.py:122`) but
has no row in `docs/AUTO-IMPROVEMENT.md`'s item-class table -- a doc-scope
decision, not a technical blocker. `figure_layout`'s findings
(`chitragupta/review/figure_layout/_report.py:131`) carry no `id` and no
severity vocabulary at all -- there is nothing to hang a stable identity
or a class ranking off, so no class could be defined for it without
inventing one from nothing.
"""

from chitragupta.dossier._sections import Section
from chitragupta.review.agenda._identity import item_id, section_anchor
from chitragupta.review.agenda._items import Item
from chitragupta.review.agenda._sources import AidSource, StyleSource


def verbatim_run_items(source: AidSource, sections: list[Section]) -> list[Item]:
    """`severity == \"short\"` is unattended (`overlap-reviser` handles
    it); `\"long\"` is surfaced (#129 reserves it for a human);
    `\"quoted\"` is not a defect and is excluded entirely."""
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
        items.append(
            Item(
                id=item_id("verbatim", "verbatim-run", section, citekey, span),
                cls="verbatim-run",
                section=section,
                citekey=citekey,
                line=line,
                unattended=(severity == "short"),
                summary=f"{finding.get('matched_words', '?')}-word verbatim run"
                + (f" citing `{citekey}`" if citekey else ""),
                detail={"severity": severity, "verbatim_id": finding.get("id")},
            )
        )
    return items


def prose_items(source: StyleSource, sections: list[Section]) -> list[Item]:
    """One item per `style_check` finding, consumed as-is: it already
    restricts itself to the decidable rules of
    docs/WRITING-STANDARDS.md's Section 9, so no further filtering for
    "mechanically re-checkable" is needed here. A `line` of 0
    (acronym-drift, which checks the draft's vocabulary as a whole) is
    not a position and is treated as None, same as any other item with
    nothing to anchor on.

    **Unattended, decided in issue 421** after shipping `False` here for
    one release while nothing consumed the flag. Two other classes are
    binary and deterministic yet still surfaced, so being re-checkable
    is not sufficient on its own -- but neither of those is surfaced for
    failing R3. `uncited-claim` is surfaced because the fix is evidence
    rather than wording, and `misquoted` because the defect is in
    `evidence.md` while a reviser edits drafts. `prose` fails neither
    test: the repair is an edit to the draft, which is R1's write-set
    exactly, and it fixes the finding rather than disguising it, because
    there is no underlying evidential claim for a rewording to
    misrepresent.

    R3 was tested rather than argued. A draft carrying an uncaptioned
    table and an unreferenced figure reported `chitragupta.TableNoCaption`
    and `chitragupta.FigureUnreferenced`; adding the caption and the
    inline reference took `draft style` to zero findings. That is the
    whole of what R3 asks, so the flag is set for the class rather than
    for a per-rule subset -- a filter whose every entry is `True` is what
    the paragraph above already rules out."""
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
                unattended=True,
                summary=f"{finding.get('rule')}: {finding.get('match')!r} "
                f"({finding.get('count', 1)}x)",
                detail={
                    "message": finding.get("message"),
                    "severity": finding.get("severity"),
                    "count": finding.get("count"),
                },
            )
        )
    return items


def unsupported_claim_items(source: AidSource, sections: list[Section]) -> list[Item]:
    """Every provenance finding except `band == \"supported\"`, which
    needs no action."""
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


def uncited_source_items(source: AidSource) -> list[Item]:
    """Only `status == \"uncited_candidates\"`. `\"cited_outside_candidates\"`
    is explicitly not a problem per `citation_coverage.py`'s own
    docstring and is excluded."""
    if not source.available:
        return []
    items = []
    for finding in source.data.get("findings", []):
        if finding.get("status") != "uncited_candidates":
            continue
        citekey = finding.get("citekey")
        items.append(
            Item(
                id=item_id("coverage", "uncited-source", None, citekey, citekey),
                cls="uncited-source",
                section=None,
                citekey=citekey,
                line=None,
                unattended=False,
                summary=f"`{citekey}` ({finding.get('title', '')}) was retrieved but never cited",
                detail={"coverage_id": finding.get("id")},
            )
        )
    return items


def uncited_claim_items(source: AidSource, sections: list[Section]) -> list[Item]:
    """Every uncited-prose finding becomes an item -- already binary, per
    the aid's own docstring."""
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
    """One item per quotation-integrity finding -- already filtered to
    `absent` quotes by `quotation.findings()` itself (`unverifiable` is a
    count, never a finding, since it names a parse limit rather than a
    fabrication). No line: a quote lives in `evidence.md`, not the
    draft's own numbered text, so there is nothing to anchor a section
    to -- the defect is in the dossier, and `agenda-reviser` edits
    drafts, which is why this class has no unattended repair."""
    if not source.available:
        return []
    items = []
    for finding in source.data.get("findings", []):
        citekey = finding.get("citekey")
        quote = finding.get("quote", "")
        items.append(
            Item(
                id=item_id("quotation", "misquoted", None, citekey, quote),
                cls="misquoted",
                section=None,
                citekey=citekey,
                line=None,
                unattended=False,
                summary=f"`[@{citekey}]`'s quoted span was not found in its source: {quote[:80]}",
                detail={
                    "near_miss_page": finding.get("near_miss_page"),
                    "near_miss_score": finding.get("near_miss_score"),
                    "quotation_id": finding.get("id"),
                },
            )
        )
    return items
