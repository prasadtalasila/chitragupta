"""`agenda --baseline`: this agenda against a recorded one, over freshly
re-run aids (`_refresh.py`); the deterministic half of the R4 cycle
(docs/AUTO-IMPROVEMENT.md).

Items match by stable `id` into `resolved`/`persisting`/`new`, with
objective counts before and after, so a driver reads fields rather than
diffing JSON. An aid whose refresh failed (#837) is named in
`not_refreshed` and its items sit out both: they are an earlier run's.
The payload mirrors `verbatim_check/_recheck.py` key for key; "objective"
here means `unattended`.
"""

from pathlib import Path

from chitragupta import review
from chitragupta.review import _emit
from chitragupta.review.agenda._sources import AID_NAMES, unverified_classes


def load_baseline(path: str | Path) -> dict:
    """A previously written `agenda` payload, refused if it cannot serve.
    Lighter than `verbatim_check/_baseline.py`, whose scan hazards do not
    arise; the two refusals (unreadable JSON, another aid's payload) live
    in `_emit.read_baseline`.
    """
    return _emit.read_baseline(path, "agenda", "an agenda payload")


def not_refreshed(payload: dict) -> list[str]:
    """The aids an agenda payload marks `refreshed: false`, in `AID_NAMES`
    order. A payload with no refresh state names none: absence is not
    evidence of failure.
    """
    aids = (payload.get("sources") or {}).get("aids") or {}
    return [aid for aid in AID_NAMES if (aids.get(aid) or {}).get("refreshed") is False]


def refresh_errors(payload: dict) -> dict[str, str]:
    """`{aid: one-line reason}` for each aid whose refresh raised (#893),
    in `AID_NAMES` order; empty for older payloads."""
    aids = (payload.get("sources") or {}).get("aids") or {}
    errors = {aid: (aids.get(aid) or {}).get("refresh_error") for aid in AID_NAMES}
    return {aid: error for aid, error in errors.items() if error}


def compare(
    new_items: list[dict],
    baseline_items: list[dict],
    accepted_ids: "set[str] | frozenset[str]" = frozenset(),
    unverified: "set[str] | frozenset[str]" = frozenset(),
) -> tuple[list[dict], list[dict], list[dict], list[dict], int, int]:
    """`(resolved, persisting, new, accepted, before, after)`, one agenda against another.

    Matching is on the content-addressed `id` alone, so an edit above an
    item does not read as resolved-and-new. `objective_*` counts
    `unattended` items, exactly `Agenda.objective_class_count`'s
    definition, so `pass_bound` is read without a second definition.
    """
    # `accepted_ids` (only this run's suppressions) keeps an accepted item
    # from reading as resolved by set difference; one genuinely gone still
    # lands in `resolved`. Aids unrefreshed on either side leave both lists
    # first (#837): dropping only the new side would show progress nobody
    # made.
    skipped = unverified_classes(unverified)
    new_items = [item for item in new_items if item["class"] not in skipped]
    baseline_items = [item for item in baseline_items if item["class"] not in skipped]
    new_ids = {item["id"] for item in new_items}
    baseline_ids = {item["id"] for item in baseline_items}
    resolved = [item for item in baseline_items if item["id"] not in new_ids | accepted_ids]
    accepted = [item for item in baseline_items if item["id"] in accepted_ids - new_ids]
    persisting = [item for item in new_items if item["id"] in baseline_ids]
    appeared = [item for item in new_items if item["id"] not in baseline_ids]

    before, after = _unattended(baseline_items), _unattended(new_items)
    return resolved, persisting, appeared, accepted, before, after


def _unattended(items: list[dict]) -> int:
    """How many of `items` are `unattended`: the one "objective" definition."""
    return sum(1 for item in items if item["unattended"])


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    """The invocation recorded in the comparison payload's envelope, always
    with `--json` (only JSON has an envelope). Not what the filed
    `<stem>.agenda.json` records, which must regenerate an agenda.
    """
    return _emit.recheck_command("agenda", draft, baseline)


def recheck_payload(
    draft: str | Path,
    baseline_path: str | Path,
    groups: tuple[list[dict], list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
    refresh_failed: list[str],
    refresh_errors: "dict[str, str] | None" = None,
) -> dict:
    """The comparison as data: `verbatim recheck`'s shape plus `accepted`,
    `not_refreshed` and `refresh_errors`, and the baseline's path, since a
    verdict needs its basis recorded."""
    resolved, persisting, appeared, accepted = groups
    before, after = counts
    command = recheck_command(draft, baseline_path)
    payload = review.envelope(Path(draft), "agenda", command)
    payload.update(
        {
            "baseline": str(baseline_path),
            "objective_before": before,
            "objective_after": after,
            "objective_delta": after - before,
            # Unattended items in `new` (#839): a total holds level when an
            # edit swaps one finding for another. Must be 0 to keep a repair.
            "objective_new": _unattended(appeared),
            "resolved": resolved,
            "persisting": persisting,
            "new": appeared,
            # Last, so earlier groups keep their place.
            "accepted": accepted,
            # Failed refreshes (#837): a driver must stop or surface them.
            "not_refreshed": refresh_failed,
            # Reasons for those (#893), as a map beside the list, so
            # membership checks on `not_refreshed` keep matching.
            "refresh_errors": refresh_errors or {},
        }
    )
    return payload


def format_recheck(
    baseline_path: str | Path,
    groups: tuple[list[dict], list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
    refresh_failed: "list[str] | tuple[str, ...]" = (),
    refresh_errors: "dict[str, str] | None" = None,
) -> str:
    """The plain-text form, for stdout, listing items by `id`, `class` and
    `summary`."""
    # Every group prints, empty or not: an absent group reads as nonexistent.
    before, after = counts
    lines = [f"baseline: {baseline_path}", ""]
    labels = ("resolved", "persisting", "new", "accepted")
    for label, items in zip(labels, groups, strict=True):
        lines.append(f"  {label} ({len(items)}):")
        if not items:
            lines.append("      -")
        for item in items:
            lines.append(f"      `{item['id']}` [{item['class']}]: {item['summary']}")
        lines.append("")
    appeared = groups[2]  # (resolved, persisting, new, accepted)
    lines.append(
        f"objective items (unattended): {before} -> {after} ({after - before:+d}), "
        f"{_unattended(appeared)} new"
    )
    if refresh_failed:
        errors = refresh_errors or {}
        names = [
            f"{aid} (raised: {errors[aid]})" if aid in errors else aid for aid in refresh_failed
        ]
        lines.append(
            f"not refreshed: {', '.join(names)} -- their items are "
            "an earlier run's, and are left out of every group and count above"
        )
    return "\n".join(lines)
