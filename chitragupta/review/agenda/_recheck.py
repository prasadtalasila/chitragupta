"""`agenda --baseline`: this agenda against a recorded one, over freshly
re-run aids. The deterministic half of the R4 cycle
(docs/AUTO-IMPROVEMENT.md), and the one mode of this aid that invokes
another -- the re-running itself is `_refresh.py`'s.

The comparison is `resolved`/`persisting`/`new` matched by each item's
stable `id`, plus an objective count before and after, so "is this item
gone?" and "did the total rise?" are field lookups rather than a model
reading two JSON documents side by side. An aid whose refresh failed
(`_refresh.refresh_aids`, #837) is named in `not_refreshed`, and its
items sit out the comparison and both counts: they are an earlier run's
findings, not evidence about the draft as it now stands.

Mirrors `chitragupta/review/verbatim_check/_recheck.py`'s payload shape
key for key, because the skill reading this one already reads that one.
What differs is what an item *is*: agenda's are `_render._item_dict`
dicts, not raw scan findings, and "objective" here is `unattended`
(`Agenda.objective_class_count`), not verbatim's "severity is not quoted".
Nothing here imports from `chitragupta.review.agenda` -- `run()` hands
its own `build_agenda()` result to `compare` as plain data.
"""

import json
import shlex
from pathlib import Path

from chitragupta import review
from chitragupta.review.agenda._sources import AID_NAMES, unverified_classes


def load_baseline(path: str | Path) -> dict:
    """A previously written `agenda` payload, read back as a comparison
    basis and refused if it cannot serve as one.

    Deliberately much lighter than `verbatim_check/_baseline.py`'s five
    refusals, which guard hazards specific to a scan -- a
    `--limit`-truncated finding list, and an `id` whose meaning moved
    between release series -- neither of which exists here. Two failures
    remain worth naming, both of which would produce a confident wrong
    answer rather than an error: a file that is not readable JSON, and
    JSON that is some other aid's payload. The layer's aids share
    `envelope()`, so another aid's `.json` is a dict with a `command` too,
    and comparing against one reports every agenda item as new.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read the baseline {path}: {exc}") from None
    except json.JSONDecodeError:
        raise ValueError(
            f"{path} is not an agenda payload -- it is not valid JSON. "
            "Write one with `review agenda <draft>`, which files it as "
            "the report's .json sibling."
        ) from None

    if not isinstance(payload, dict) or payload.get("aid") != "agenda" or "items" not in payload:
        raise ValueError(
            f"{path} is not an agenda payload. Write one with `review "
            "agenda <draft>`, which files it as the report's .json "
            "sibling."
        )
    return payload


def not_refreshed(payload: dict) -> list[str]:
    """The aids an agenda payload marks `refreshed: false`, in
    `AID_NAMES` order.

    Read off `sources.aids`, which `_render._sources_dict` fills from
    `AidSource.refreshed`. A payload carrying no refresh state -- one
    filed by a bare `agenda` run, an older release, or written by hand
    -- names none: absence of the key is not evidence that an aid failed.
    """
    aids = (payload.get("sources") or {}).get("aids") or {}
    return [aid for aid in AID_NAMES if (aids.get(aid) or {}).get("refreshed") is False]


def refresh_errors(payload: dict) -> dict[str, str]:
    """`{aid: one-line reason}` for each aid whose refresh raised (#893),
    in `AID_NAMES` order -- `not_refreshed`'s companion, read off the
    same `sources.aids` entries, and empty for a payload filed before
    the field existed."""
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

    Both sides are `_render._item_dict`-shaped, and matching is on `id`
    alone. That id is content-addressed (`_identity.item_id`) and carries
    no line number, so an edit above an item does not report it as
    resolved-and-new. `objective_*` counts `unattended` items, which is
    `Agenda.objective_class_count`'s definition to the letter -- keeping
    the two in step is the point, not tidiness: a caller reads
    `objective_after` against the payload's `pass_bound` without
    re-deriving what "objective" means, and a second definition here is
    how the two would come to disagree.
    """
    # `accepted_ids` exists so an accepted item is not reported resolved,
    # which is exactly the silent wrong answer this module was written to
    # prevent: such an item is absent from `new_items` by suppression,
    # not by repair, so plain set difference would call it fixed. The
    # caller passes only the ids this run actually suppressed
    # (`_render._accepted_dicts`), so an accepted item that has genuinely
    # gone -- the span was edited, the finding did not recur -- still
    # lands in `resolved`, which is what it is. Neither objective count
    # moves either way: the acceptable classes are all surfaced.
    # `unverified` names aids not refreshed on *either* side, and their
    # items leave both lists before anything is matched or counted
    # (#837). One side alone is not enough: a failed aid dropped from the
    # new list only would show every one of its baseline items resolved
    # and the delta falling -- progress nobody made. Such items are in no
    # group; `not_refreshed` in the payload is what says why.
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
    """How many of `items` are `unattended` -- the one definition of
    "objective" that `compare`'s two counts and the payload's
    `objective_new` all share."""
    return sum(1 for item in items if item["unattended"])


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    """The invocation recorded in the comparison payload's envelope, so a
    reader holding it can regenerate it.

    Always carries `--json`, and takes no flag saying whether to, for
    `verbatim._recheck.recheck_command`'s reason: only the JSON form has
    an envelope, so the recorded command reproduces *this file*. It is
    **not** what the filed `<stem>.agenda.json` records -- that one keeps
    `_command`'s bare form, being itself the next run's baseline, so it
    must name a command regenerating an agenda, not a comparison
    against itself.
    """
    parts = ["python", "-m", "chitragupta.review", "agenda", str(draft)]
    return shlex.join([*parts, "--baseline", str(baseline), "--json"])


def recheck_payload(
    draft: str | Path,
    baseline_path: str | Path,
    groups: tuple[list[dict], list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
    refresh_failed: list[str],
    refresh_errors: "dict[str, str] | None" = None,
) -> dict:
    """The comparison as data -- `verbatim recheck`'s payload shape, key
    for key, plus the `accepted` group, the `not_refreshed` list and the
    `refresh_errors` map that shape has no counterpart for. Carries the
    baseline's path too: a verdict whose basis is not recorded beside it
    is one nobody can check later. The envelope's command is
    `recheck_command`'s, always."""
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
            # The unattended items in `new` (#839). The delta is a total,
            # and a total holds level when an edit resolves one finding
            # and introduces another, so a swap reads as no change from
            # it alone. Counted here so a driver reads it rather than
            # re-deriving it from `new` -- the rule it serves is that
            # this must be 0 for a repair to be kept.
            "objective_new": _unattended(appeared),
            "resolved": resolved,
            "persisting": persisting,
            "new": appeared,
            # Last, so the three groups a reader of the previous shape
            # already looks up keep their place.
            "accepted": accepted,
            # This run's failed refreshes (#837), whose items are in no
            # group above and neither count: a driver must stop or
            # surface them, never read a quiet list as progress.
            "not_refreshed": refresh_failed,
            # The reason for each of those that raised (#893). A map
            # beside the list rather than objects inside it: a driver
            # branches on which names are in `not_refreshed`, and an
            # object there would quietly stop matching.
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
    """The plain-text form, for stdout. Lists each item by `id`, `class`
    and `summary` -- an agenda item's own fields, where `verbatim
    recheck`'s counterpart prints a citekey, a page range and a line.
    """
    # `accepted` prints last and always, empty or not, for the same
    # reason the other three do: a group that appears only when it is
    # non-empty teaches a reader it does not exist.
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
