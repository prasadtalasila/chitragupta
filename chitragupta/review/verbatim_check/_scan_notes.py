"""The short per-finding notes both report forms print: flags, the word
count, the tier-and-score parenthesis, the page range, and the coverage
gaps a scan could not close.

Split out of `_scan.py` when that module crossed CODE-STANDARDS.md's C2
line limit. The seam is the one `_scan_render.py` and `_scan_cmd.py`
already imply: `_scan.py` decides *what* a scan found (orchestrating the
tiers, bucketing by severity, projecting the published payload), and
these six functions decide *how one finding reads on a line*. Every one
of them is called by both renderers and by neither tier -- which is why
they live together, and why they live outside the orchestrator: the two
forms of the report must not be able to disagree about any of them, and
`_scan.py` never calls one.

`_bucket`/`_bucket_title`/`LONG_RUN_WORDS` deliberately stayed behind:
`published` derives `severity` from `_bucket`, so the severity
vocabulary is part of the payload contract rather than of the rendering.
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
    """The word count at the head of a finding, in units that are true
    for the tier that produced it.

    Tier 1 and tier 2 count words they actually matched against the
    source, so `"23 words"` (or `"40 words, 23 matched"`) says what it
    appears to say. Tier 3's `matched_words` is
    `overlap_segments.matched_words` -- the union of the *aligned
    sentences'* word ranges -- so for the common single-sentence
    alignment it simply equals `span_words`, `_matched_note` correctly
    suppresses itself, and the finding printed as a bare `"31 words"`
    beside two tiers whose identical-looking count means shared wording.
    It does not mean that here, and nothing else on the line said so.

    `aligned` is the whole fix: it is the one word that stops the number
    being read as a wording overlap, and it is why this is a separate
    function rather than a second branch inside `_matched_note` -- the
    two renderers must not be able to disagree about it.
    """
    if finding["tier"] != "embedding":
        return f"{finding['span_words']} words{_matched_note(finding)}"
    if finding["matched_words"] == finding["span_words"]:
        return f"{finding['span_words']} words aligned"
    return (
        f"{finding['span_words']} words aligned, {finding['matched_words']} in matched sentence(s)"
    )


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


def _not_run_lines(not_run: list[dict]) -> list[str]:
    """One line per coverage gap, naming the tier and why.

    Shared by the printed and written forms so the two cannot end up
    saying different things about the same scan -- the same reason
    `scan_command` is built once and handed to both. `"did not run"` is
    only said of an entry that is actually `partial: False` -- an entry
    that ran and still contributed real findings gets its own phrasing,
    so the two forms cannot contradict the prose `_scan_render.py`
    prints directly above them (#499).
    """
    return [
        f"tier {entry['tier']} did not run: {entry['reason']}"
        if not entry.get("partial")
        else f"tier {entry['tier']} ran, but not against everything: {entry['reason']}"
        for entry in not_run
    ]
