"""What the raising aid's own filed report adds to an agenda item: the
overlapping passage, and where in the source and the draft it sits.

Split out of `_render.py` when that module crossed CODE-STANDARDS.md's C2
line limit. The seam is a real one rather than a convenience: everything
here *joins* -- it reads the verbatim aid's `.json` through
`agenda.sources` and formats what it finds -- while `_render.py` assembles
a document out of the item list and never looks past it. Both the
Markdown and the JSON payload read their locator from this one join, so
the two forms cannot disagree about where a finding is.

Nothing here imports an aid module. `review/agenda/` is built to read the
aids' filed JSON and nothing else, so an agenda can be assembled from
reports on disk without the tool that wrote them being importable
(`_items_findings.py` says so directly); `chitragupta.passage_diff` is in
the shared layer for exactly that reason.
"""

from chitragupta.passage_diff import annotate, one_line


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
