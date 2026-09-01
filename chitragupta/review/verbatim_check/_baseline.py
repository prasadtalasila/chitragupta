"""Reading a `scan` payload back off disk as a `recheck` baseline, refused
rather than degraded wherever it cannot serve as a comparison basis.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

import json
from pathlib import Path

from chitragupta import review

# What `recheck` reads off a *baseline's* findings. It prints them in
# `resolved` -- the findings that are gone, so it never rescanned them and
# has only the file to go on. Named rather than stood in for by `id`,
# because the two failures differ: a payload can carry an `id` and still
# be missing something the output line needs. `end_page` is the live case
# -- a payload written between `id` landing and #131's page range claims
# the same release series, passes the version check below, and then
# crashes `_page_range`. `tier` is the same shape of case for
# `recheck_findings`' `objective()`, which excludes the embedding tier
# from the count (#500) and would `KeyError` without it rather than
# refuse cleanly. Checked against `_PAYLOAD_FIELDS` in the tests, so a
# field required here but never written cannot slip in.
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
    for the refusal message -- empty when there is nothing missing.

    Its own function rather than a block inside `load_baseline`: that one
    is a sequence of five independent refusals, and this is the only one
    that has to look inside every finding, so inlining it made the
    longest and least readable step of the five also the hardest to see
    the shape of.
    """
    gaps = []
    for key in ("min_run", "gap"):
        if key not in payload:
            gaps.append(key)
        elif not isinstance(payload[key], int) or isinstance(payload[key], bool):
            # `recheck_findings` hands these straight to `scan_findings`
            # uncoerced; a hand-edited `"min_run": "8"` would otherwise
            # reach `_merge_runs`' `int <= str` comparison and raise
            # TypeError, not the clean ValueError/exit-2 refusal every
            # other malformed baseline gets. `bool` is a subclass of
            # `int`, but `min_run`/`gap` are word counts -- True/False
            # would silently become 1/0 instead of naming the problem.
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

    Refuses rather than degrades in five cases, all of which would
    otherwise produce a confident and wrong answer:

    - not this aid's payload. The review layer's aids share `envelope()`,
      so a coverage report is also JSON with a `findings` key, and
      comparing against one would report every verbatim finding as new.
    - a payload written under `--limit`. Truncation happens after
      sorting, so a finding absent from a capped baseline may simply have
      been cut -- "new" then means "new or merely unreported", which is
      not something a caller can act on.
    - a payload missing any of `_BASELINE_FIELDS`, which is what an older
      `scan` wrote. One of those sits at the canonical report path for
      every draft an earlier version scanned, which is exactly where a
      caller is told to look, so this is the likeliest bad baseline of
      the five and the one that most deserves a remedy rather than a
      `KeyError`. An empty findings list is not this case: a draft
      repaired to clean is a legitimate baseline, and has no finding to
      be missing anything.
    - a payload from a different release series (`_series`, below). What
      counts as one finding can change between series -- #131 made a run
      that used to report as two merge into one, which changes that
      finding's `id` (`finding_id`'s `page` argument) even though nothing
      in the draft or the source moved -- so a cross-series comparison
      could report a repair that never happened.
    - unreadable or not JSON at all.

    The last two overlap but neither covers the other: a payload can be
    the right shape and mean something different (same series check), or
    claim this series and still be missing a field (the shape check --
    which is what a build taken between `id` landing and #131's
    `end_page` produces).
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

    The release series is the right granularity because
    DEVELOPER-AGENTS.md defines it that way: a patch release is
    "nothing that changes what the pipeline does", so a finding-shape
    change cannot land in one, while a minor release is exactly where new
    functionality -- `severity` in 5.4.0, the allowlist in 5.5.0, `id`
    here -- has repeatedly arrived. Checking the full string instead
    would force a needless re-scan after every patch; checking nothing
    would let a real contract change through silently.

    `None` for a missing version, a non-string one (a hand-edited or
    corrupted baseline JSON can put anything under that key, and a
    malformed `version` is not this function's refusal to make -- the
    shape check above already covers a baseline that isn't trustworthy),
    and for `review.version()`'s `"unknown"` fallback, which means
    pyproject could not be read: turning one unreadable file into a
    second, unrelated refusal helps nobody.
    """
    if not isinstance(version, str) or version == "unknown":
        return None
    return ".".join(version.split(".")[:2])
