"""`recheck`: this scan against a recorded one -- the deterministic half
of #129's remediation loop, so "is this finding gone, and did the repair
break anything else" is never a model's judgement.
"""

import json
import shlex
from pathlib import Path

from chitragupta import overlap_chroma, review
from chitragupta.review.verbatim_check._baseline import load_baseline
from chitragupta.review.verbatim_check._scan import published, scan_findings
from chitragupta.review.verbatim_check._scan_notes import _draft_position, _page_range


def _tier_drift_warnings(baseline: dict, not_run: list[dict]) -> list[str]:
    """Advisory lines naming tier-availability or corpus-key drift since
    the baseline, which `objective()` cannot see.

    Warns rather than refuses: tiers 1 and 2 are unaffected and
    `objective()` excludes tier 3 (#500). A baseline predating either
    field is "unknown", not "everything ran", as `_series` treats a
    missing version.
    """
    warnings = []
    baseline_not_run_raw = baseline.get("tiers_not_run")
    if baseline_not_run_raw is not None:
        baseline_not_run = {entry["tier"] for entry in baseline_not_run_raw}
        current_not_run = {entry["tier"] for entry in not_run}
        if baseline_not_run != current_not_run:
            warnings.append(
                "tier availability changed since the baseline: not run then "
                f"{sorted(baseline_not_run) or ['none']}, not run now "
                f"{sorted(current_not_run) or ['none']} -- embedding findings in "
                "resolved/new may reflect that rather than an edit"
            )
    baseline_corpus_key = baseline.get("corpus_key")
    current_corpus_key = overlap_chroma.corpus_key()
    if baseline_corpus_key is not None and baseline_corpus_key != current_corpus_key:
        warnings.append(
            f"corpus key changed since the baseline ({baseline_corpus_key} -> "
            f"{current_corpus_key}) -- the embedding model or corpus was rebuilt, so "
            "embedding findings are not comparable to the baseline's"
        )
    return warnings


def recheck_findings(
    draft: str | Path, baseline: dict
) -> tuple[list[dict], list[dict], list[dict], int, int, list[str]]:
    """`(resolved, persisting, new, objective_before, objective_after,
    warnings)` for `draft` against `baseline`, rescanned at the
    baseline's own floor.

    The floor is the baseline's, never a flag, or a strict scan could be
    compared to a lax one and read as progress. Matched by position-free
    `finding_id`; two findings sharing an id understate progress, the
    safe direction for an acceptance test.
    """
    findings, _, _, not_run = scan_findings(draft, baseline["min_run"], baseline["gap"], None)
    payload_now = [published(f) for f in findings]
    before = baseline["findings"]

    now_ids = {f["id"] for f in payload_now}
    before_ids = {f["id"] for f in before}
    resolved = [f for f in before if f["id"] not in now_ids]
    persisting = [f for f in payload_now if f["id"] in before_ids]
    new = [f for f in payload_now if f["id"] not in before_ids]

    # Defect buckets, deterministic tiers only: a quoted-and-cited run is a
    # correct quotation (one of the repairs), and embedding findings move
    # with tier availability, not edits, which would stall the counter (#500).
    def objective(items: list[dict]) -> int:
        return sum(1 for f in items if f["severity"] != "quoted" and f["tier"] != "embedding")

    warnings = _tier_drift_warnings(baseline, not_run)
    return resolved, persisting, new, objective(before), objective(payload_now), warnings


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    """The invocation recorded in the payload's envelope. Always `--json`:
    only the JSON form carries an envelope to reproduce.
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
    warnings: list[str] | None = None,
) -> dict:
    """The comparison as data, the form the remediation loop reads, with
    the baseline's path, version and floor so the verdict's basis is
    recorded."""
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
            "warnings": warnings or [],
        }
    )
    return payload


def format_recheck(
    baseline_path: str | Path,
    baseline: dict,
    groups: tuple[list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
    warnings: list[str] | None = None,
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
                f"{f['citekey']} {_page_range(f)}"
                + (f" -- draft {_draft_position(f)}" if _draft_position(f) else "")
            )
        lines.append("")
    lines.append(f"objective findings (long + short): {before} -> {after} ({after - before:+d})")
    for warning in warnings or []:
        lines.append(f"\nwarning: {warning}")
    return "\n".join(lines)


def cmd_recheck(draft: str | Path, baseline: str | Path, as_json: bool = False) -> None:
    """`recheck`'s stdout entry point. No `--write`: a comparison against
    one baseline is stale at the next edit, so filing it only piles up
    near-identical reports.
    """
    loaded = load_baseline(baseline)
    resolved, persisting, new, before, after, warnings = recheck_findings(draft, loaded)
    groups, counts = (resolved, persisting, new), (before, after)

    if not as_json:
        print(format_recheck(baseline, loaded, groups, counts, warnings))
        return

    command = recheck_command(draft, baseline)
    payload = recheck_payload(draft, baseline, loaded, groups, counts, command, warnings)
    print(json.dumps(payload, indent=2))
