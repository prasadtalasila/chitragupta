"""`scan`'s stdout entry point, and the plain-text/JSON forms it prints or
writes.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

import json
import shlex
import sys
from pathlib import Path

from chitragupta import config, review
from chitragupta.review.verbatim_check._scan import (
    _flags,
    _matched_note,
    _not_run_lines,
    _page_range,
    _tier_note,
    published,
    scan_findings,
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
            lines.append(
                f"  [{f['span_words']} words{_matched_note(f)}, pdf {_page_range(f)}] "
                f"{f['citekey']} ({_tier_note(f)}){flag_text}"
            )
            lines.append(f"      {f['fragment']}")
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
    """The invocation recorded in both the Markdown report's header and
    the JSON payload's envelope, so a reader holding either file can
    regenerate it.

    Every flag that changes *what is reported* is recorded, including the
    two that decide where it went: a report capped by `--limit` reads
    very differently from an uncapped one, and a recorded command without
    `--write` reproduces the findings on stdout but not the file. Only
    `--formats` is left out -- it selects renders *of* the Markdown
    report and changes nothing in it or in the payload. The allowlist is
    left out too, on both the command and the payload: it's per-host
    config, not a flag, so it can't join a re-runnable invocation -- its
    path and effect are recorded separately (see `render_scan_markdown`'s
    header bullet and `scan_payload`'s `suppressed` field).
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
    three flags that set the reporting floor, how many findings the
    allowlist suppressed, and one object per finding.

    An additional serialisation of the list `scan_findings` already
    returned, never a second computation -- so the printed form and this
    one cannot disagree about what was found. `severity` is likewise
    derived, not stored: `_bucket` is a pure function of fields already in
    `_PAYLOAD_FIELDS`, so a consumer that wants the written report's
    long/short/quoted grouping gets it here instead of reimplementing the
    threshold.

    `start` is a **word** offset into the draft's normalised word stream
    (`_tokenize_draft`: masked, citation markers blanked, lowercased,
    punctuation dropped), not a character offset and not a line number.
    Neither it nor `fragment`/`context` -- which are that same stream,
    space-joined -- can be located or matched in the draft file as
    written. Those three locate a run for a *reader*.

    `line`, `char_start`, `char_end` and `draft_text` locate it for an
    *editor* (#129): they index the draft as written, so
    `draft[char_start:char_end] == draft_text` exactly -- which is what
    makes `draft_text` usable as an `Edit` `old_string`.

    The span runs from the first matched word's first character to the
    last matched word's last character, so it holds every original
    character *between* them: casing, interior punctuation, line breaks,
    and any citation marker sitting mid-run. It stops at the last word,
    which is the boundary worth being exact about -- a trailing period or
    closing quote sits just past `char_end` and is **not** included, so a
    rewrite substituted for `draft_text` leaves that punctuation where
    the sentence already had it. Leading punctuation is outside the span
    for the same reason.

    Nothing here decides *whether* to edit; the review layer still only
    ever reports.

    `id` names the finding across runs -- see `finding_id`, and `recheck`,
    which is the reason it exists.

    `cites_source` and `quoted` are the two bits the printed form shows
    as `UNCITED SOURCE` and `quoted`. Booleans rather than those labels:
    the point of this payload is that a caller stops matching display
    text, and a flag list would only move the parsing one layer down.
    """
    payload = review.envelope(Path(draft), "verbatim", command)
    payload.update(
        {
            "min_run": min_run,
            "gap": gap,
            "limit": limit,
            "suppressed": suppressed,
            # One entry per detection tier that could not run at all, each
            # naming the tier and why -- empty when every tier ran. A
            # consumer reading `findings` alone cannot tell a checked draft
            # from an unchecked one, and this is the field that answers it
            # (see `scan_findings`). Additive: `load_baseline` requires
            # `_BASELINE_FIELDS` and ignores everything else, so a payload
            # written before this key existed still reads.
            "tiers_not_run": not_run or [],
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

    Printing text stays the default -- the usual use is a question asked
    and answered in one sitting, by a person. `as_json` prints the
    payload instead, for a caller that would otherwise have to parse that
    text back into data.

    `write` additionally puts the Markdown report in `content/review/`,
    mirroring the draft's path, beside the same draft's provenance and
    coverage reports -- and the payload beside it as the report's `.json`
    sibling, whether or not `as_json` was asked for. Unconditionally,
    because the file is written for whatever reads it later
    (docs/AUTO-IMPROVEMENT.md's `agenda`), not for whoever ran this
    command: a payload that appeared only when someone happened to also
    pass `--json` would be missing exactly when a later consumer needed
    it.

    Under `as_json` the written-files summary goes to stderr, so stdout
    is only ever the payload and `scan --json --write > findings.json` is
    a valid JSON file -- the discipline `dossier brief` already follows.
    """
    findings, min_run, suppressed, not_run = scan_findings(draft, min_run, gap, limit)

    # The default path prints text and stops. Returning here rather than
    # falling through keeps the payload's cost off it entirely -- a
    # projection per finding, and the `pyproject.toml` read
    # `review.version()` does for the envelope -- none of which the
    # printed form uses.
    if not (as_json or write):
        print(format_scan(findings, min_run, suppressed, not_run))
        return

    command = scan_command(draft, min_run, gap, limit, write, as_json)
    payload = scan_payload(draft, findings, min_run, gap, limit, suppressed, command, not_run)

    # Same `indent=2`, same key order, no trailing difference: what this
    # prints is byte-for-byte what `write_json` files, so a caller may
    # redirect stdout or read the sibling and get the same bytes.
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
