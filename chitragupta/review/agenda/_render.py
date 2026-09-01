"""Markdown and JSON rendering for one `Agenda` -- both read off the same
computed item list `_render.py` never itself computes, so the printed
and published forms cannot disagree about what was found (the same
discipline every other review aid's `*_payload` function documents).
"""

from chitragupta import review
from chitragupta.review.agenda._items import CLASSES

_SOURCE_LABELS = {
    "provenance": "Citation provenance",
    "verbatim": "Verbatim scan",
    "coverage": "Citation coverage",
    "synthesis": "Multi-source synthesis",
    "figure": "TikZ layout check",
    "uncited": "Uncited prose",
    "quotation": "Quotation integrity",
    "support": "Claim support",
}

# Read for header completeness, but neither carries an item class --
# see `_items.py`'s module docstring for why the two reasons differ.
_NO_CLASS_AIDS = ("synthesis", "figure")


def _aid_note(aid: str, label: str, source) -> str:
    if not source.available:
        if source.reason:
            return f"- {label}: not run -- {source.reason}"
        return f"- {label}: not run"
    state = "read, no item class defined" if aid in _NO_CLASS_AIDS else "read"
    if source.stale:
        state += ", **stale** (older than the draft)"
    return f"- {label}: {state}"


def _source_notes(agenda) -> list[str]:
    notes = [
        _aid_note(aid, label, agenda.sources.aids[aid]) for aid, label in _SOURCE_LABELS.items()
    ]

    style = agenda.sources.style
    notes.append(
        "- Prose (style_check): **partial** -- vale not on PATH"
        if style.partial
        else "- Prose (style_check): read"
    )

    drift = agenda.sources.drift
    if not drift.available:
        notes.append("- Dossier drift: not available -- no dossier for this draft")
    elif not drift.corpus_available:
        notes.append("- Dossier drift: read, but the corpus ledger is unavailable")
    else:
        notes.append("- Dossier drift: read")
    return notes


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
    lines = ["## Findings", ""]
    current = None
    for item in agenda.items:
        if item.cls != current:
            lines += [f"### {item.cls}", ""]
            current = item.cls
        marker = "unattended" if item.unattended else "surfaced"
        section = f" ({item.section})" if item.section else ""
        lines.append(f"- `{item.id}` [{marker}]{section}: {item.summary}")
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

    if not agenda.items:
        lines += ["No items -- nothing for this worklist to report.", ""]
        return "\n".join(lines)

    lines += _summary_lines(agenda)
    lines += _findings_lines(agenda)
    return "\n".join(lines)


def _item_dict(item) -> dict:
    return {
        "id": item.id,
        "class": item.cls,
        "section": item.section,
        "citekey": item.citekey,
        "line": item.line,
        "unattended": item.unattended,
        "summary": item.summary,
        "detail": item.detail,
    }


def _sources_dict(agenda) -> dict:
    return {
        "aids": {
            aid: {"available": source.available, "stale": source.stale}
            for aid, source in agenda.sources.aids.items()
        },
        "style": {
            "available": agenda.sources.style.available,
            "partial": agenda.sources.style.partial,
        },
        "drift": {
            "available": agenda.sources.drift.available,
            "corpus_available": agenda.sources.drift.corpus_available,
        },
    }


def agenda_payload(agenda, command: str) -> dict:
    """The same items `render_markdown` prints, as data -- an additional
    serialisation, never a second computation.

    `pass_bound` and `objective_class_count` are carried because neither
    is reachable any other way: `PASS_BOUND` lives only as a module
    constant and the count only as a property, and a `SKILL.md` can
    import neither. Without them a skill re-running this loop would
    write `3` into its own prose, which is the literal
    `plans/f-auto-improvement-adoption.md`'s Decision 2 forbids -- it is
    how a backstop against a miscounting bug later gets mistaken for a
    budget.
    """
    # Imported here rather than at module scope, and not moved to a leaf
    # module to avoid it: `PASS_BOUND` belongs beside the property it
    # bounds (see the package `__init__.py`'s own comment), and that
    # package imports this module, so a top-level import would be a
    # cycle. The parameter shadows the package name, hence the alias.
    from chitragupta.review import agenda as agenda_module

    payload = review.envelope(agenda.draft, "agenda", command)
    payload.update(
        {
            "sources": _sources_dict(agenda),
            "pass_bound": agenda_module.PASS_BOUND,
            "objective_class_count": agenda.objective_class_count,
            "items": [_item_dict(item) for item in agenda.items],
        }
    )
    return payload
