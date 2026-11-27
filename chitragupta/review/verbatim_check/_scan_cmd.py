"""`scan`'s stdout entry point, and the plain-text/JSON forms it prints or
writes.
"""

import json
import shlex
import sys
from pathlib import Path

from chitragupta import config, overlap_chroma, review
from chitragupta.review.verbatim_check._scan import published, scan_findings
from chitragupta.review.verbatim_check._scan_notes import (
    _draft_position,
    _flags,
    _not_run_lines,
    _page_range,
    _tier_note,
    _words_note,
)
from chitragupta.review.verbatim_check._scan_render import render_scan_markdown


def format_scan(
    findings: list[dict],
    min_run: int,
    suppressed: int = 0,
    not_run: list[dict] | None = None,
) -> str:
    """The plain-text form, for stdout."""
    if not findings:
        base = f"no verbatim run of >= {min_run} words found anywhere in the draft"
    else:
        lines = []
        for f in findings:
            flags = _flags(f)
            flag_text = f" [{', '.join(flags)}]" if flags else ""
            position = _draft_position(f)
            where = f", draft {position}" if position else ""
            lines.append(
                f"  [{_words_note(f)}, pdf {_page_range(f)}{where}] "
                f"{f['citekey']} ({_tier_note(f)}){flag_text}"
            )
            # "draft:" only where a source side is printed beside it.
            if f["source_text"] is None:
                lines.append(f"      {f['fragment']}")
            else:
                lines.append(f"      draft:  {f['fragment']}")
                lines.append(f"      source: {f['source_text']}")
            lines.append(f"      in: {f['context']}...")
        base = "\n".join(lines)
    if suppressed:
        base += (
            f"\n\n{suppressed} finding(s) suppressed by the allowlist "
            f"({config.VERBATIM_ALLOWLIST_PATH.name})."
        )
    for line in _not_run_lines(not_run or []):
        base += f"\n\n{line}"
    return base


def scan_command(
    draft: str | Path, min_run: int, gap: int, limit: int | None, write: bool, as_json: bool
) -> str:
    """The invocation recorded in the Markdown header and JSON envelope.

    Every flag that changes what is reported, `--limit` and `--write`
    included. `--formats` only selects renders, and the allowlist is
    per-host config, recorded separately (`suppressed`, the header).
    """
    command = [
        "python",
        "-m",
        "chitragupta.review",
        "verbatim",
        "scan",
        str(draft),
        "--min-run",
        str(min_run),
        "--gap",
        str(gap),
    ]
    if limit is not None:
        command += ["--limit", str(limit)]
    if write:
        command += ["--write"]
    if as_json:
        command += ["--json"]
    return shlex.join(command)


def scan_payload(
    draft: str | Path,
    findings: list[dict],
    min_run: int,
    gap: int,
    limit: int | None,
    suppressed: int,
    command: str,
    not_run: list[dict] | None = None,
) -> dict:
    """The same findings as data: `review.envelope`'s provenance, the
    floor flags, the allowlist's suppressed count, one object per finding.

    A serialisation of `scan_findings`' list, never a second computation;
    `severity` is derived by `_bucket`. `start`, `fragment` and `context`
    index the normalised word stream and locate a run for a *reader*;
    `line`, `char_start`, `char_end` and `draft_text` index the draft as
    written for an *editor* (#129): `draft[char_start:char_end] ==
    draft_text`, first word's first character to last word's last, so
    trailing punctuation stays outside a substituted rewrite. `id` serves
    `recheck`. `cites_source`/`quoted` are booleans so callers stop
    matching display text.
    """
    payload = review.envelope(Path(draft), "verbatim", command)
    payload.update(
        {
            "min_run": min_run,
            "gap": gap,
            "limit": limit,
            "suppressed": suppressed,
            # Tiers that did not (fully) run, so a checked draft is
            # distinguishable from an unchecked one. Additive: baselines
            # ignore keys outside `_BASELINE_FIELDS`.
            "tiers_not_run": not_run or [],
            # Tier 3's collection name now, recorded even when it did not
            # run, so `recheck` can warn of a model rebuild (#500).
            "corpus_key": overlap_chroma.corpus_key(),
            "findings": [published(f) for f in findings],
        }
    )
    return payload


def cmd_scan(
    draft: str | Path,
    min_run: int | None = None,
    gap: int = 1,
    limit: int | None = None,
    write: bool = False,
    formats: tuple[str, ...] | list[str] = ("md", "tex", "pdf"),
    as_json: bool = False,
) -> None:
    """`scan`'s stdout entry point: run the scan and print it.

    `write` files the Markdown report and, unconditionally, the payload as
    its `.json` sibling, because later readers (`agenda`) need it whether
    or not `--json` was passed. Under `as_json` the written-files summary
    goes to stderr, so stdout stays valid JSON.
    """
    findings, min_run, suppressed, not_run = scan_findings(draft, min_run, gap, limit)

    # The default path skips the payload's cost (projections and the
    # `review.version()` read).
    if not (as_json or write):
        print(format_scan(findings, min_run, suppressed, not_run))
        return

    command = scan_command(draft, min_run, gap, limit, write, as_json)
    payload = scan_payload(draft, findings, min_run, gap, limit, suppressed, command, not_run)

    # Byte-for-byte what `write_json` files.
    print(
        json.dumps(payload, indent=2)
        if as_json
        else format_scan(findings, min_run, suppressed, not_run)
    )

    if write:
        body = render_scan_markdown(draft, findings, min_run, limit, command, suppressed, not_run)
        written = review.write(Path(draft), "verbatim", body, list(formats))
        written["json"] = review.write_json(Path(draft), "verbatim", payload)
        review.print_written(written, stream=sys.stderr if as_json else sys.stdout)
