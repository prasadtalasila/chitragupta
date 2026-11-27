"""What the raising aid's own filed report adds to an agenda item: the
overlapping passage, and where in the source and the draft it sits.

Split from `_render.py` along a real seam: this joins against the verbatim
aid's `.json` via `agenda.sources`, so the Markdown and JSON read one
locator and cannot disagree. Nothing here imports an aid module, so an
agenda builds from reports on disk alone.
"""

from chitragupta.passage_diff import annotate, one_line


def _passage_lines(agenda, item) -> list[str]:
    """The overlapping text behind a `verbatim-run` item, indented under
    it: the draft's words, and the source's where the two differ.

    Joined from the aid's filed JSON, not `item.detail`, which stays thin
    by decision (`agenda-reviser/SKILL.md`). Indented four spaces: flush
    left under a bullet, a blockquote is lazy continuation and does not
    render (see `_findings_lines`).
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
        # Exact tier: one passage, nothing to mark.
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
    """Where the run is: the source's page and the draft's line and
    paragraph. `line` serves an editor; `paragraph` survives ordinary
    revision. Ranges collapse when both ends agree (`p.7`, not `p.7-7`).
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
    """The verbatim aid's own filed finding for `verbatim_id`, or None when
    there is no id, no readable report, or (bare mode reads older reports)
    no such id. The item still prints, without its passage.
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
