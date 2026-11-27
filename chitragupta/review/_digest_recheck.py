"""`review digest --baseline`: this run against a recorded one (#991).

"Minimise unsupported text" is a number a person watches fall, never a
threshold. Items match by stable `id` into `resolved`/`persisting`/`new`;
`fell` is true when no class rose, one fell, nothing new appeared and the
unsupported fraction did not rise. The fraction is checked too, because
deleting a flagged sentence with half the copied text resolves an item and
worsens the digest. Payload keys mirror `agenda/_recheck.py`'s.
"""

from pathlib import Path

from chitragupta import review
from chitragupta.review import _emit
from chitragupta.review._digest_match import CLASSES


def load_baseline(path: str | Path) -> dict:
    """A previously filed `digest` payload, refused if it cannot serve.
    Beyond `_emit.read_baseline`'s refusals, the three keys `compare` reads
    are checked, so a truncated file is a usage error, not a false
    regression.
    """
    payload = _emit.read_baseline(path, "digest", "a digest payload")
    for key in ("counts", "unsupported_fraction", "copied_fraction"):
        if key not in payload:
            raise ValueError(
                f"{path} is not a complete digest payload: it lacks {key!r}. "
                "Write one with `review digest <draft>`, which files it as the "
                "report's .json sibling."
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
    unsupported_before = baseline["unsupported_fraction"]
    unsupported_after = payload["unsupported_fraction"]
    return {
        "resolved": [item for item in old_items if item["id"] not in new_ids],
        "persisting": [item for item in new_items if item["id"] in old_ids],
        "new": appeared,
        "counts_before": before,
        "counts_after": after,
        "unsupported_before": unsupported_before,
        "unsupported_after": unsupported_after,
        "copied_before": baseline["copied_fraction"],
        "copied_after": payload["copied_fraction"],
        "fell": fell and not rose and not appeared and unsupported_after <= unsupported_before,
    }


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    return _emit.recheck_command("digest", draft, baseline)


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
        lines.append(
            f"{cls}: {comparison['counts_before'][cls]} -> {comparison['counts_after'][cls]}"
        )
    lines.append(
        f"unsupported fraction: {comparison['unsupported_before']} -> "
        f"{comparison['unsupported_after']}"
    )
    lines.append(f"copied fraction: {comparison['copied_before']} -> {comparison['copied_after']}")
    lines.append(f"fell: {'yes' if comparison['fell'] else 'no'}")
    return "\n".join(lines)
