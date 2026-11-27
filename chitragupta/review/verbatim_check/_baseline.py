"""Reading a `scan` payload back off disk as a `recheck` baseline, refused
rather than degraded wherever it cannot serve as a comparison basis.
"""

import json
from pathlib import Path

from chitragupta import review

# What `recheck` reads off a baseline's findings, which it prints for
# resolved findings it never rescanned. Named rather than implied by `id`:
# `end_page` (#131) and `tier` (#500's `objective()`) would otherwise
# crash rather than refuse. Tests check it against `_PAYLOAD_FIELDS`.
_BASELINE_FIELDS = (
    "id",
    "citekey",
    "page",
    "end_page",
    "span_words",
    "severity",
    "line",
    "tier",
)


def _baseline_gaps(payload: dict) -> list[str]:
    """Everything `recheck` needs from `payload` and cannot find, named
    for the refusal message -- empty when nothing is missing."""
    gaps = []
    for key in ("min_run", "gap"):
        if key not in payload:
            gaps.append(key)
        elif not isinstance(payload[key], int) or isinstance(payload[key], bool):
            # Passed to `scan_findings` uncoerced, so `"8"` would raise
            # TypeError instead of a clean exit 2; bool is an int subclass
            # but True is not a word count.
            gaps.append(f"{key} (not an int)")

    findings = payload["findings"]
    if not isinstance(findings, list) or any(not isinstance(f, dict) for f in findings):
        gaps.append("findings (not a list of findings)")
    else:
        gaps += sorted({field for f in findings for field in _BASELINE_FIELDS if field not in f})
    return gaps


def load_baseline(path: str | Path) -> dict:
    """A `scan` payload read back off disk, refused if it cannot serve as
    a comparison basis.

    Each refusal prevents a confident wrong answer: not a verbatim payload
    (aids share `envelope()`, so a coverage report would make everything
    new); written under `--limit` (absent may mean cut); missing
    `_BASELINE_FIELDS` (an older scan at the canonical path, the likeliest
    bad baseline; an empty findings list is fine); another release series
    (#131 changed what one finding is, and so its `id`); unreadable or
    not JSON. Shape and series checks overlap but neither covers the other.
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read the baseline {path}: {exc}") from None
    except json.JSONDecodeError:
        raise ValueError(
            f"{path} is not a verbatim scan payload -- it is not valid JSON. "
            "Write one with `verbatim scan <draft> --write`."
        ) from None

    if (
        not isinstance(payload, dict)
        or payload.get("aid") != "verbatim"
        or "findings" not in payload
    ):
        raise ValueError(
            f"{path} is not a verbatim scan payload. Write one with "
            "`verbatim scan <draft> --write`, which files it as the "
            "report's .json sibling."
        )
    if payload.get("limit") is not None:
        raise ValueError(
            f"{path} was written with --limit {payload['limit']}, so it lists "
            "only the longest findings and cannot say what was absent. "
            "Re-scan without --limit to take a baseline."
        )
    missing = _baseline_gaps(payload)
    if missing:
        raise ValueError(
            f"{path} is missing {', '.join(missing)}, so it predates this "
            "command: it is a verbatim scan payload, but an older one than "
            "`recheck` can read. Re-scan the draft with `verbatim scan "
            "<draft> --write` to replace it, then compare against that."
        )
    recorded, running = payload.get("version"), review.version()
    if _series(recorded) and _series(recorded) != _series(running):
        raise ValueError(
            f"{path} was written by chitragupta {recorded}, and this is "
            f"{running}. What counts as one finding changes between release "
            "series -- a scan that learns to merge two runs into one gives "
            "wording nobody touched a different `id` -- so a comparison "
            "across one would report repairs that never happened. Re-scan "
            "the draft with `verbatim scan <draft> --write` to take a "
            "baseline this version wrote."
        )
    return payload


def _series(version: object) -> str | None:
    """A version's `major.minor`, or `None` where there is nothing to
    compare.

    The series is the granularity because a patch release cannot change
    what the pipeline does (DEVELOPER-AGENTS.md) while minors have
    repeatedly changed the finding shape. `None` for a missing or
    non-string version (the shape check covers a bad baseline) and for
    `review.version()`'s `"unknown"`, which is no reason for a refusal.
    """
    if not isinstance(version, str) or version == "unknown":
        return None
    return ".".join(version.split(".")[:2])
