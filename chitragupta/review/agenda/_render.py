"""Markdown and JSON rendering for one `Agenda`, both read off the same
computed item list, so the two forms cannot disagree.
"""

from chitragupta import review
from chitragupta.review.agenda._items import CLASSES
from chitragupta.review.agenda._sources import AID_NAMES
from chitragupta.review.agenda._passages import (
    _passage_lines,
    _verbatim_finding,
)
from chitragupta.review.agenda._stale import stale_dicts, stale_lines

# Each aid agenda reads, labelled as `review.AIDS` labels it. Derived from
# `AID_NAMES` (#850), so `_source_notes` can never hit a missing key.
_SOURCE_LABELS = {aid: review.AIDS[aid] for aid in AID_NAMES}

# Read for the header, but neither yields items (see `_items_findings.py`).
_NO_CLASS_AIDS = ("synthesis", "figure")

# Quotation's two nothing-checked universes (#838), so a header over zero
# `misquoted` items says whether any quote was looked at. Pinned against
# `quotation.UNIVERSES` by TestRenderMarkdown.
_QUOTATION_UNIVERSE_NOTES = {"no-dossier": "no dossier", "no-quotes": "no quote the draft cites"}


def _aid_note(aid: str, label: str, source) -> str:
    # An aid that raised during the refresh (#893) did run: not "not run",
    # and with no earlier findings to call stale.
    if not source.available and source.refresh_error:
        note = f"- {label}: **not refreshed** -- raised: {source.refresh_error}"
        if source.reason:
            note += f" (and the earlier report is unreadable: {source.reason})"
        return note
    if not source.available:
        if source.reason:
            return f"- {label}: not run -- {source.reason}"
        return f"- {label}: not run"
    state = "read, no item class defined" if aid in _NO_CLASS_AIDS else "read"
    if universe := _QUOTATION_UNIVERSE_NOTES.get((source.data or {}).get("universe")):
        state += f", nothing checked -- {universe}"
    if source.stale:
        state += ", **stale** (older than the draft)"
    if source.refreshed is False:
        raised = f"raised: {source.refresh_error}; " if source.refresh_error else ""
        state += f", **not refreshed** ({raised}an earlier run's findings; not counted)"
    return f"- {label}: {state}"


def _source_notes(agenda) -> list[str]:
    notes = [
        _aid_note(aid, label, agenda.sources.aids[aid]) for aid, label in _SOURCE_LABELS.items()
    ]

    style = agenda.sources.style
    # #1187: a broken exceptions file reads as not run, not as absent Vale.
    state = "**partial** -- vale not on PATH" if style.partial else "read"
    state = f"not run -- {style.reason}" if style.reason else state
    notes.append(f"- Prose (style_check): {state}")

    drift = agenda.sources.drift
    if not drift.available:
        notes.append("- Dossier drift: not available -- no dossier for this draft")
    elif not drift.corpus_available:
        notes.append("- Dossier drift: read, but the corpus ledger is unavailable")
    else:
        notes.append("- Dossier drift: read")

    # Named even when absent: a source missing from the header reads as one
    # that found nothing.
    recorded = agenda.sources.recorded
    notes.append(
        "- Recorded-but-uncited citekeys: read"
        if recorded.available
        else "- Recorded-but-uncited citekeys: not available -- no dossier for this draft"
    )
    notes.append(_accepted_note(agenda.sources.accepted))
    return notes


def _accepted_note(accepted) -> str:
    """The acceptance record's line in the header. An unreadable record is
    named, saying the worklist below is the full one, so a reader can ask
    why an accepted item is back.
    """
    if accepted.reason:
        return (
            f"- Accepted items: **unreadable** -- {accepted.reason}. "
            "Nothing is suppressed, so every accepted item is listed below again"
        )
    if not accepted.available:
        return "- Accepted items: none recorded for this draft"
    return f"- Accepted items: read, {len(accepted.records)} recorded"


def _accepted_lines(agenda) -> list[str]:
    """The audit trail: every accepted item, and whether this run's
    worklist is shorter for it. Rows matching nothing (the span changed)
    are shown, or an acceptance would look permanent.
    """
    records = agenda.sources.accepted.records
    if not records:
        return []
    suppressed = {item.id for item in agenda.suppressed}
    lines = [
        "## Accepted",
        "",
        "Considered and accepted by a person, and therefore kept off the",
        "worklist below while each finding's identity is unchanged. An edit to",
        "an accepted span raises a new id, which no record matches, so the item",
        "returns by itself -- there is no reopen command because none is needed.",
        "",
    ]
    for record in records:
        state = "suppressed" if record["id"] in suppressed else "not raised by this run"
        lines.append(
            f"- `{record['id']}` [{record.get('class')}, {state}]: {record.get('summary')}"
        )
    lines.append("")
    return lines


def _summary_lines(agenda) -> list[str]:
    counts: dict[str, int] = {}
    for item in agenda.items:
        counts[item.cls] = counts.get(item.cls, 0) + 1
    lines = ["## Summary", ""]
    for cls in CLASSES:
        if counts.get(cls):
            lines.append(f"- {counts[cls]} {cls}")
    lines.append("")
    return lines


def _findings_lines(agenda) -> list[str]:
    """One `### <class>` heading per class, then a bullet per item.

    The blank line before each later heading is load-bearing: directly
    under a `- ...` bullet, `###` is lazy continuation, so every heading
    but the first vanished into the item above it.
    """
    lines = ["## Findings", ""]
    current = None
    for item in agenda.items:
        if item.cls != current:
            if current is not None:
                lines.append("")
            lines += [f"### {item.cls}", ""]
            current = item.cls
        marker = "unattended" if item.unattended else "surfaced"
        section = f" ({item.section})" if item.section else ""
        lines.append(f"- `{item.id}` [{marker}]{section}: {item.summary}")
        lines += _passage_lines(agenda, item)
    lines.append("")
    return lines


def render_markdown(agenda, command: str) -> str:
    lines = review.header(agenda.draft, "agenda", command)
    lines += [
        "## How to read this",
        "",
        "This is a **review aid, not a gate**: every item below is evidence",
        "for a human judgement, ranked by class and then severity, never a",
        "verdict. `unattended` items are ones a future `agenda-reviser` may",
        "act on without asking first; every other item is surfaced for a",
        "person to decide.",
        "",
        "## Sources",
        "",
    ]
    lines += _source_notes(agenda)
    lines.append("")
    # Refusals sit above the worklist: a run whose every item was refused
    # must still say so.
    lines += stale_lines(agenda.stale)
    # Then acceptances, in `build_agenda`'s partition order.
    lines += _accepted_lines(agenda)

    if not agenda.items:
        lines += ["No items -- nothing for this worklist to report.", ""]
        return "\n".join(lines)

    lines += _summary_lines(agenda)
    lines += _findings_lines(agenda)
    return "\n".join(lines)


def _item_dict(agenda, item) -> dict:
    """One item as the payload publishes it.

    `page`/`end_page`/`paragraph`/`end_paragraph` are joined from the
    raising aid's filed JSON, as `_passage_lines` does, and `None` where a
    class has no locator, so every item has one key set. Joined rather
    than carried on `Item`, whose `detail` is thin by decision.
    """
    finding = (
        _verbatim_finding(agenda, item.detail.get("verbatim_id"))
        if item.cls == "verbatim-run"
        else None
    ) or {}
    return {
        "id": item.id,
        "class": item.cls,
        "section": item.section,
        "citekey": item.citekey,
        "line": item.line,
        # Appended after `line`, so the previous shape is an unchanged prefix.
        "page": finding.get("page"),
        "end_page": finding.get("end_page"),
        "paragraph": finding.get("paragraph"),
        "end_paragraph": finding.get("end_paragraph"),
        "unattended": item.unattended,
        "summary": item.summary,
        "detail": item.detail,
    }


def _sources_dict(agenda) -> dict:
    return {
        "aids": {aid: source.flags() for aid, source in agenda.sources.aids.items()},
        "style": {
            "available": agenda.sources.style.available,
            "partial": agenda.sources.style.partial,
        },
        "drift": {
            "available": agenda.sources.drift.available,
            "corpus_available": agenda.sources.drift.corpus_available,
        },
        "accepted": {
            "available": agenda.sources.accepted.available,
            "count": len(agenda.sources.accepted.records),
        },
    }


def _accepted_dicts(agenda) -> list[dict]:
    """The acceptance record as the payload publishes it. `suppressed` is
    computed per run, never stored: a stored copy would be the mutable
    per-item state #767 rejected.
    """
    suppressed = {item.id for item in agenda.suppressed}
    return [
        {**record, "suppressed": record["id"] in suppressed}
        for record in agenda.sources.accepted.records
    ]


def agenda_payload(agenda, command: str) -> dict:
    """The same items `render_markdown` prints, as data.

    Carries `pass_bound` and `objective_class_count` because a `SKILL.md`
    can import neither; otherwise a skill would write `3` into its prose,
    the literal Decision 2 of `plans/f-auto-improvement-adoption.md`
    forbids.
    """
    # Imported here: the package defines `PASS_BOUND` beside the property it
    # bounds and imports this module, so a top-level import is a cycle.
    # The parameter shadows the package name, hence the alias.
    from chitragupta.review import agenda as agenda_module

    payload = review.envelope(agenda.draft, "agenda", command)
    payload.update(
        {
            "sources": _sources_dict(agenda),
            "pass_bound": agenda_module.PASS_BOUND,
            "objective_class_count": agenda.objective_class_count,
            "items": [_item_dict(agenda, item) for item in agenda.items],
            # `stale_spans`: `stale` already means an aid report older than
            # the draft (`sources.aids.<aid>.stale`).
            "stale_spans": stale_dicts(agenda.stale),
            # `accepted` names the stored records. Both keys follow `items`,
            # so an earlier shape is an unchanged prefix.
            "accepted": _accepted_dicts(agenda),
        }
    )
    return payload
