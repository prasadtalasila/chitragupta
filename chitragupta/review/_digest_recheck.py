"""`review digest --baseline`: this run against a recorded one (#991).

"Minimise unsupported text" is a number a person watches fall, never a
threshold. This is the arithmetic: items matched by their stable `id`
into `resolved`/`persisting`/`new`, the per-class counts before and
after, the unsupported and copied fractions before and after, and one
boolean, `fell`, true when no class rose, at least one fell, nothing
new appeared, and the unsupported fraction did not rise -- the
conditions the skill keeps a repair under. The fraction is checked as
well as the counts because deleting a flagged sentence and half the
copied text with it resolves an item and makes the digest worse.
Nothing is refreshed here: the aid recomputed everything before
comparing, so there is no stale report to guard against.

Mirrors `agenda/_recheck.py`'s payload keys where the two say the same
thing, because the skill reading this already reads that one.
"""

import json
import shlex
from pathlib import Path

from chitragupta import review
from chitragupta.review._digest_match import CLASSES


def load_baseline(path: str | Path) -> dict:
    """A previously filed `digest` payload, refused if it cannot serve.

    Two confident-wrong-answer failures are named: unreadable JSON, and
    another aid's payload (every aid's `.json` has a `command`, and the
    likeliest typo is the agenda's beside it).
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read the baseline {path}: {exc}") from None
    except json.JSONDecodeError:
        raise ValueError(
            f"{path} is not a digest payload -- it is not valid JSON. "
            "Write one with `review digest <draft>`, which files it as the report's .json sibling."
        ) from None
    if not isinstance(payload, dict) or payload.get("aid") != "digest" or "items" not in payload:
        raise ValueError(
            f"{path} is not a digest payload. Write one with `review digest <draft>`, "
            "which files it as the report's .json sibling."
        )
    return payload


def compare(payload: dict, baseline: dict) -> dict:
    new_items, old_items = payload["items"], baseline["items"]
    new_ids = {item["id"] for item in new_items}
    old_ids = {item["id"] for item in old_items}
    before = {cls: baseline["counts"].get(cls, 0) for cls in CLASSES}
    after = {cls: payload["counts"].get(cls, 0) for cls in CLASSES}
    appeared = [item for item in new_items if item["id"] not in old_ids]
    rose = any(after[cls] > before[cls] for cls in CLASSES)
    fell = any(after[cls] < before[cls] for cls in CLASSES)
    unsupported_before = baseline.get("unsupported_fraction", 0.0)
    unsupported_after = payload["unsupported_fraction"]
    return {
        "resolved": [item for item in old_items if item["id"] not in new_ids],
        "persisting": [item for item in new_items if item["id"] in old_ids],
        "new": appeared,
        "counts_before": before,
        "counts_after": after,
        "unsupported_before": unsupported_before,
        "unsupported_after": unsupported_after,
        "copied_before": baseline.get("copied_fraction", 0.0),
        "copied_after": payload["copied_fraction"],
        "fell": fell and not rose and not appeared and unsupported_after <= unsupported_before,
    }


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    parts = ["python", "-m", "chitragupta.review", "digest", str(draft)]
    return shlex.join([*parts, "--baseline", str(baseline), "--json"])


def recheck_payload(draft: Path, baseline: str | Path, comparison: dict) -> dict:
    data = review.envelope(draft, "digest", recheck_command(draft, baseline))
    data["baseline"] = str(baseline)
    data.update(comparison)
    return data


def format_recheck(baseline: str | Path, comparison: dict) -> str:
    lines = [f"baseline: {baseline}", ""]
    for group in ("resolved", "persisting", "new"):
        lines.append(f"{group}: {len(comparison[group])}")
        lines += [
            f"  - `{item['id']}` [{item['class']}] {item['summary']}" for item in comparison[group]
        ]
    lines.append("")
    for cls in CLASSES:
        lines.append(f"{cls}: {comparison['counts_before'][cls]} -> {comparison['counts_after'][cls]}")
    lines.append(
        f"unsupported fraction: {comparison['unsupported_before']} -> "
        f"{comparison['unsupported_after']}"
    )
    lines.append(f"copied fraction: {comparison['copied_before']} -> {comparison['copied_after']}")
    lines.append(f"fell: {'yes' if comparison['fell'] else 'no'}")
    return "\n".join(lines)
