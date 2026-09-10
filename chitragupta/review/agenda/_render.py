"""Markdown and JSON rendering for one `Agenda` -- both read off the same
computed item list `_render.py` never itself computes, so the printed
and published forms cannot disagree about what was found (the same
discipline every other review aid's `*_payload` function documents).
"""

from chitragupta import review
from chitragupta.passage_diff import annotate, one_line
from chitragupta.review.agenda._items import CLASSES

# `{aid: review.AIDS[aid] for aid in _sources.AID_NAMES}`, restated
# rather than derived -- and the restatement is load-bearing to get
# right, because `_source_notes` below indexes `agenda.sources.aids` by
# every key here. A key `AID_NAMES` does not have is a `KeyError`
# mid-report, not a missing line. `TestAidNames` asserts the two against
# each other for that reason (#573).
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

    # Named even when absent, like every source above: the header's job
    # is to say what this run could and could not see, and a source
    # silently missing from it reads as one that found nothing.
    recorded = agenda.sources.recorded
    notes.append(
        "- Recorded-but-uncited citekeys: read"
        if recorded.available
        else "- Recorded-but-uncited citekeys: not available -- no dossier for this draft"
    )
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
    """One `### <class>` heading per class, then a bullet per item.

    The blank line before each heading after the first is load-bearing,
    not cosmetic. A `###` line placed directly under a `- ...` bullet is
    lazy continuation in Markdown, not a heading: it is parsed as more
    text of that bullet, so every class heading but the first vanished
    into the last item of the class above it. Rendered to PDF the second
    section had no heading at all, and its items read as a continuation
    of the previous class -- which, on a worklist whose whole structure
    is "grouped by class", is the one thing it must not do.
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


def _passage_lines(agenda, item) -> list[str]:
    """The overlapping text behind a `verbatim-run` item, indented under
    it: the draft's words, and the source's where the two differ.

    A worklist that says "9-word skip-gram match citing `x_2024`" and
    stops has told a reader the shape of the finding and none of its
    content -- so the first thing anyone does is open the aid's report to
    see what the words actually were. Carrying the passage here answers
    that in place.

    **Joined from the aid's filed JSON, not from `item.detail`.** That
    field stays exactly `{"severity", "verbatim_id"}`: it is thin by a
    documented decision (`agenda-reviser/SKILL.md`), and the contract it
    exists to enforce is "look the id up in the raising aid's own JSON".
    This does precisely that, through `agenda.sources`, which is the same
    filed report every consumer is pointed at -- so the decision is
    honoured rather than reversed, and nothing is recomputed here.

    Indented four spaces, not emitted flush left. A blockquote or a
    heading placed directly under a `- ...` bullet is lazy continuation
    in Markdown, not a quote or a heading -- the same failure that lost
    every class heading but the first (see `_findings_lines`). Indenting
    to the bullet's own continuation column is what makes these render as
    part of the item rather than beside it.
    """
    if item.cls != "verbatim-run":
        return []
    finding = _verbatim_finding(agenda, item.detail.get("verbatim_id"))
    if finding is None:
        return []
    draft, source = finding.get("fragment", ""), finding.get("source_text")
    if not draft:
        return []
    locator = _locator_line(finding)
    if source is None:
        # The exact tier: the two sides are the same words, so there is
        # one passage and nothing to mark.
        return ["", locator, "", f"    > {one_line(draft)}", ""]
    marked_draft, marked_source = annotate(one_line(draft), one_line(source))
    return [
        "",
        locator,
        "",
        f"    > **draft** -- {marked_draft}",
        "",
        f"    > **source** -- {marked_source}",
        "",
    ]


def _locator_line(finding: dict) -> str:
    """Where the run is, on both sides: the source's page and the draft's
    line and paragraph.

    The verbatim aid's own report has carried `p.N` since it was written,
    and the agenda never did -- an item said which paper and how many
    words and left the reader to open the aid's report for the only two
    numbers that say *where to look*. The draft-side pair is why it is
    not just the page: `line` locates the run for an editor and moves the
    moment anything above it is edited, while `paragraph` is coarse
    enough to survive ordinary revision, so a report read a week later
    still points somewhere real.

    Ranges collapse when both ends agree -- `p.7` not `p.7-7` -- and
    `end_paragraph` is omitted rather than repeated for the single-
    paragraph run, which is nearly all of them.
    """
    page, end_page = finding.get("page"), finding.get("end_page")
    para, end_para = finding.get("paragraph"), finding.get("end_paragraph")
    parts = []
    if page is not None:
        parts.append(f"source p.{page}" if page == end_page else f"source p.{page}-{end_page}")
    if finding.get("line") is not None:
        parts.append(f"draft line {finding['line']}")
    if para is not None:
        parts.append(f"paragraph {para}" if para == end_para else f"paragraphs {para}-{end_para}")
    return f"    *{', '.join(parts)}*" if parts else ""


def _verbatim_finding(agenda, verbatim_id: str | None) -> dict | None:
    """The verbatim aid's own filed finding for `verbatim_id`.

    `None` for every way this can come up empty -- no id, the aid's
    report absent or unreadable, or an id that is in the agenda but not
    in the report. The last one is not hypothetical: the agenda in its
    bare form *reads* reports rather than running them, so a `.json`
    older than the item list can genuinely lack an id. The item still
    prints; only its passage is omitted.
    """
    if not verbatim_id:
        return None
    source = agenda.sources.aids.get("verbatim")
    if source is None or not source.available:
        return None
    for finding in source.data.get("findings", []):
        if finding.get("id") == verbatim_id:
            return finding
    return None


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
