"""The Markdown report `scan --write` files: standing preamble prose plus
the findings, grouped into severity buckets.
"""

from pathlib import Path

from chitragupta import config, review
from chitragupta.dossier import draft_relpath
from chitragupta.passage_diff import annotate, one_line
from chitragupta.review.verbatim_check._scan import (
    BUCKET_ORDER,
    _bucket,
    _bucket_title,
)
from chitragupta.review.verbatim_check._scan_notes import (
    _draft_position,
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
    """The same findings as a Markdown report, for `--write`, beside
    `format_scan` (a terminal wants no syntax; a kept file should look
    like its sibling reports). `command` comes from `scan_command`, shared
    with `scan_payload` so header and envelope agree.
    """
    allowlist_path = config.VERBATIM_ALLOWLIST_PATH
    # Shown relative to the project, as the draft is: an absolute path put
    # the author's home directory into every committed report (#1167).
    shown = draft_relpath(allowlist_path)
    if not allowlist_path.exists():
        allowlist_line = f"- Allowlist: none configured (`{shown}` not found)"
    else:
        allowlist_line = f"- Allowlist: `{shown}` ({suppressed} finding(s) suppressed)"

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
    """The findings, grouped into `BUCKET_ORDER`'s severity sections
    (split out for C1)."""
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
            # Locates the run in the draft; the heading has the source page.
            position = _draft_position(f)
            if position:
                lines += [f"At draft {position}.", ""]
            lines += _passage_lines(f)
            lines += [
                f"In context: {f['context']}...",
                "",
            ]
    return lines


def _passage_lines(finding: dict) -> list[str]:
    """The finding's text: one blockquote where the two sides are the
    same words, two marked-up ones where they are not.

    On tiers 2 and 3 a lone blockquote of the draft's normalised words
    looked like an uncaught lift. Both sides are shown, differing words
    marked and the overlap bare, since collating by eye is work readers
    stop doing (`passage_diff.annotate`).
    """
    if finding["source_text"] is None:
        return [f"> {finding['fragment']}", ""]
    draft, source = annotate(finding["fragment"], one_line(finding["source_text"]))
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
