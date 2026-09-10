"""The Markdown report `scan --write` files: standing preamble prose plus
the findings, grouped into severity buckets.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

from pathlib import Path

from chitragupta import config, review
from chitragupta.review.verbatim_check._scan import (
    BUCKET_ORDER,
    _bucket,
    _bucket_title,
)
from chitragupta.review.verbatim_check._scan_diff import annotate
from chitragupta.review.verbatim_check._scan_notes import (
    _flags,
    _page_range,
    _tier_note,
    _words_note,
)
from chitragupta.review.verbatim_check._scan_preamble import _how_to_read


def render_scan_markdown(
    draft: str | Path,
    findings: list[dict],
    min_run: int,
    limit: int | None,
    command: str,
    suppressed: int = 0,
    not_run: list[dict] | None = None,
) -> str:
    """The same findings as a Markdown report, for `--write`.

    Kept beside `format_scan` rather than replacing it: stdout is read in
    a terminal mid-review and wants no syntax, while a file kept for
    months is read next to the same draft's provenance and coverage
    reports and should look like them.

    `command` is built once, by `scan_command`, and handed to both this
    function and `scan_payload` -- so the Markdown header and the JSON
    envelope cannot disagree about what produced them.
    """
    allowlist_path = config.VERBATIM_ALLOWLIST_PATH
    if not allowlist_path.exists():
        allowlist_line = f"- Allowlist: none configured (`{allowlist_path}` not found)"
    else:
        allowlist_line = f"- Allowlist: `{allowlist_path}` ({suppressed} finding(s) suppressed)"

    lines = review.header(Path(draft), "verbatim", command)
    lines = lines[:-1] + [allowlist_line, ""]
    lines += _how_to_read(not_run or []) + ["## Findings", ""]

    if not findings:
        lines += [
            f"No verbatim run of {min_run} words or more was found anywhere in the draft.",
            "",
        ]
        return "\n".join(lines)

    lines += [f"{len(findings)} run(s), grouped most-damning-first.", ""]
    if limit is not None:
        lines += [
            f"This report was capped at `--limit {limit}` finding(s), taken from",
            "the longest-first list *before* grouping into the buckets below --",
            "a bucket may look emptier here than an uncapped scan would show, or",
            "be absent entirely, because its findings were cut before grouping.",
            "",
        ]

    return "\n".join(lines + _bucketed_lines(findings))


def _bucketed_lines(findings: list[dict]) -> list[str]:
    """The findings themselves, grouped into `BUCKET_ORDER`'s severity
    sections.

    Extracted out of `render_scan_markdown` for the reason
    `_exact_findings_from_groups` was extracted out of its own caller:
    this double loop's nesting was counting against a function that is
    otherwise a straight-line assembly of a document, and that function
    was over CODE-STANDARDS.md's C1 limit before this tier added to it.
    """
    buckets = {key: [] for key in BUCKET_ORDER}
    for f in findings:
        buckets[_bucket(f)].append(f)

    lines = []
    for key in BUCKET_ORDER:
        bucket_findings = buckets[key]
        if not bucket_findings:
            continue
        lines += [f"### {_bucket_title(key)}", ""]
        for f in bucket_findings:
            flags = _flags(f)
            flag_text = f" -- **{', '.join(flags)}**" if flags else ""
            lines += [
                f"#### {_words_note(f)} -- `{f['citekey']}` "
                f"{_page_range(f)} ({_tier_note(f)}){flag_text}",
                "",
            ]
            lines += _passage_lines(f)
            lines += [
                f"In context: {f['context']}...",
                "",
            ]
    return lines


def _one_line(text: str) -> str:
    """`text` with every run of whitespace collapsed to one space.

    A blockquote is emitted as `f"> {text}"`, one line, so a newline
    inside `text` ends the quote and renders the remainder as an ordinary
    paragraph beside it. Source passages routinely contain them: most of
    this corpus's `content/parsed/*.txt` is hard-wrapped somewhere around
    110-156 characters, depending on the parser backend that wrote it, so
    any span of more than a few words is likely to cross a line break.

    Collapsed here, at the point of rendering, and deliberately not in
    `overlap_source_text.source_span` or in the payload: `source_text` is
    the source's real text, and a consumer matching it back against the
    parsed file needs the whitespace it actually has. Only the blockquote
    needs it flat.
    """
    return " ".join(text.split())


def _passage_lines(finding: dict) -> list[str]:
    """The finding's text: one blockquote where the two sides are the
    same words, two marked-up ones where they are not.

    A bare blockquote under a report headed "verbatim" reads as a
    quotation of the source, and on the exact tier it *is* one. On the
    skip-gram and embedding tiers it is the draft's own words,
    normalized -- so the same rendering made a substitution or a
    restatement look like an uncaught lift and invited exactly the wrong
    question ("why did the exact tier miss this?").

    Printing both sides answers that; marking them up is what makes the
    answer readable. Finding a swapped word by collating two paragraphs
    is work a reader will do carefully twice and then stop doing, and it
    is the whole content of a tier-2 or tier-3 finding -- so the words
    that differ are marked and the overlap is left bare, rather than the
    reverse. See `_scan_diff.annotate`.
    """
    if finding["source_text"] is None:
        return [f"> {finding['fragment']}", ""]
    draft, source = annotate(finding["fragment"], _one_line(finding["source_text"]))
    return [
        "Draft:",
        "",
        f"> {draft}",
        "",
        "Source:",
        "",
        f"> {source}",
        "",
    ]
