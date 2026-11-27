"""The short per-finding notes both report forms print: flags, the word
count, the tier-and-score parenthesis, the page range, and the coverage
gaps a scan could not close.

Shared by both renderers so the two forms cannot disagree. `_bucket` and
friends stay in `_scan.py`: severity is part of the payload contract.
"""


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


def _words_note(finding: dict) -> str:
    """The word count at the head of a finding, in units true for its tier.

    Tier 3's `matched_words` is the aligned sentences' width, not shared
    wording, so it says `aligned`, or a bare "31 words" would read as a
    wording overlap like tiers 1 and 2.
    """
    if finding["tier"] != "embedding":
        return f"{finding['span_words']} words{_matched_note(finding)}"
    if finding["matched_words"] == finding["span_words"]:
        return f"{finding['span_words']} words aligned"
    return (
        f"{finding['span_words']} words aligned, {finding['matched_words']} in matched sentence(s)"
    )


def _tier_note(finding: dict) -> str:
    """`tier=exact`, or `tier=embedding, score=0.41`. The score sits in the
    tier's parenthesis: shifted-cosine units, comparable to nothing else.
    """
    if finding["score"] is None:
        return f"tier={finding['tier']}"
    return f"tier={finding['tier']}, score={finding['score']}"


def _page_range(finding: dict) -> str:
    """`p.N`, or `p.N-M` for postings starting on several pages (#131).
    A remainder shorter than the n-gram size can reach a page without
    moving `end_page`."""
    page, end_page = finding["page"], finding["end_page"]
    return f"p.{page}" if page == end_page else f"p.{page}-{end_page}"


def _draft_position(finding: dict) -> str:
    """Where in the *draft* the run sits: `line 35, paragraph 9`.

    `line` is what an editor jumps to; `paragraph` survives revision.
    Degrades key by key, since `recheck` reads older baselines. Not shared
    with `review/agenda/_render.py`, which imports no aid module
    (`_items_findings.py`); tests keep the two in step.
    """
    parts = []
    if finding.get("line") is not None:
        parts.append(f"line {finding['line']}")
    para, end_para = finding.get("paragraph"), finding.get("end_paragraph")
    if para is not None:
        parts.append(f"paragraph {para}" if para == end_para else f"paragraphs {para}-{end_para}")
    return ", ".join(parts)


def _not_run_lines(not_run: list[dict]) -> list[str]:
    """One line per coverage gap, shared by both forms. "did not run" only
    for `partial: False`, so neither contradicts `_scan_render.py` (#499).
    """
    return [
        f"tier {entry['tier']} did not run: {entry['reason']}"
        if not entry.get("partial")
        else f"tier {entry['tier']} ran, but not against everything: {entry['reason']}"
        for entry in not_run
    ]
