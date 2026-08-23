"""`recheck`: this scan against a recorded one. The half of #129's
remediation loop that has to be deterministic -- "is this finding gone,
and did repairing it break anything else" is the acceptance test a
constrained rewrite is held to, and a model deciding that by reading two
reports is exactly the judgement that should not be a judgement.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

import json
import shlex
from pathlib import Path

from chitragupta import review
from chitragupta.review.verbatim_check._baseline import load_baseline
from chitragupta.review.verbatim_check._scan import _page_range, published, scan_findings


def recheck_findings(
    draft: str | Path, baseline: dict
) -> tuple[list[dict], list[dict], list[dict], int, int]:
    """`(resolved, persisting, new, objective_before, objective_after)`
    for `draft` against `baseline`, rescanned at the baseline's own floor.

    The floor comes from the baseline rather than from a flag because two
    scans are only comparable at the same one, and the baseline's already
    happened -- a caller who could pass `--min-run` here could quietly
    compare a strict run against a lax one and read the difference as
    progress.

    Findings are matched by `finding_id`, which is position-free, so an
    edit above a finding does not report it as resolved-and-new. Where a
    baseline holds two findings sharing an id (see `finding_id`), a
    single repair leaves the id present and both still count as
    persisting -- understating progress, which is the direction an
    acceptance test should err in.
    """
    findings, _, _, _ = scan_findings(draft, baseline["min_run"], baseline["gap"], None)
    payload_now = [published(f) for f in findings]
    before = baseline["findings"]

    now_ids = {f["id"] for f in payload_now}
    before_ids = {f["id"] for f in before}
    resolved = [f for f in before if f["id"] not in now_ids]
    persisting = [f for f in payload_now if f["id"] in before_ids]
    new = [f for f in payload_now if f["id"] not in before_ids]

    # "Objective" is the two defect buckets. A run that is both quoted and
    # cited is a correctly attributed quotation, so counting it here would
    # make converting a lift into a quotation -- one of the two repairs
    # this loop is for -- look like no improvement at all.
    def objective(items: list[dict]) -> int:
        return sum(1 for f in items if f["severity"] != "quoted")

    return resolved, persisting, new, objective(before), objective(payload_now)


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    """The invocation recorded in the payload's envelope, so a reader
    holding the payload can regenerate it.

    Always includes `--json`, and takes no flag saying whether to: only
    the JSON form carries an envelope, so the recorded command is the one
    that reproduces *this file*. `scan_command` takes the flag because it
    is shared with the Markdown report, which the text form of a
    comparison has no counterpart to.
    """
    return shlex.join(
        [
            "python",
            "-m",
            "chitragupta.review",
            "verbatim",
            "recheck",
            str(draft),
            "--baseline",
            str(baseline),
            "--json",
        ]
    )


def recheck_payload(
    draft: str | Path,
    baseline_path: str | Path,
    baseline: dict,
    groups: tuple[list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
    command: str,
) -> dict:
    """The comparison as data -- the form the remediation loop reads.

    Carries the baseline's path, version and floor as well as the three
    groups: a verdict whose basis is not recorded beside it is one nobody
    can check later, which is the same reason `scan_payload` carries
    `min_run`. See `_version_note` for what the version is doing here.
    """
    resolved, persisting, new = groups
    before, after = counts
    payload = review.envelope(Path(draft), "verbatim", command)
    payload.update(
        {
            "baseline": str(baseline_path),
            "baseline_version": baseline.get("version"),
            "min_run": baseline["min_run"],
            "gap": baseline["gap"],
            "objective_before": before,
            "objective_after": after,
            "objective_delta": after - before,
            "resolved": resolved,
            "persisting": persisting,
            "new": new,
        }
    )
    return payload


def format_recheck(
    baseline_path: str | Path,
    baseline: dict,
    groups: tuple[list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
) -> str:
    """The plain-text form, for stdout."""
    resolved, persisting, new = groups
    before, after = counts
    lines = [
        f"baseline: {baseline_path}",
        f"floor:    --min-run {baseline['min_run']} --gap {baseline['gap']} (from the baseline)",
        "",
    ]
    for label, items in (("resolved", resolved), ("persisting", persisting), ("new", new)):
        lines.append(f"  {label} ({len(items)}):")
        if not items:
            lines.append("      -")
        for f in items:
            lines.append(
                f"      {f['id']}  [{f['span_words']} words, {f['severity']}] "
                f"{f['citekey']} {_page_range(f)} line {f['line']}"
            )
        lines.append("")
    lines.append(f"objective findings (long + short): {before} -> {after} ({after - before:+d})")
    return "\n".join(lines)


def cmd_recheck(draft: str | Path, baseline: str | Path, as_json: bool = False) -> None:
    """`recheck`'s stdout entry point.

    Prints and stops -- no `--write`. A scan report is kept beside the
    draft because it is read again months later; this is a comparison
    against one particular baseline, consumed by whoever asked for it and
    stale the next time the draft is touched. Filing it would leave a
    directory of near-identical reports whose only difference is which
    edit had happened yet.
    """
    loaded = load_baseline(baseline)
    resolved, persisting, new, before, after = recheck_findings(draft, loaded)
    groups, counts = (resolved, persisting, new), (before, after)

    if not as_json:
        print(format_recheck(baseline, loaded, groups, counts))
        return

    command = recheck_command(draft, baseline)
    print(json.dumps(recheck_payload(draft, baseline, loaded, groups, counts, command), indent=2))
