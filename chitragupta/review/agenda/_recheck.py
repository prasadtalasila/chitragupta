"""`agenda --baseline`: this agenda against a recorded one, over freshly
re-run aids. The deterministic half of the R4 cycle
(docs/AUTO-IMPROVEMENT.md), and the one mode of this aid that invokes
another.

Refreshing first is the whole point, and what a skill re-deriving this
loop in prose gets wrong **silently**: a naive re-run of `agenda` alone
reads the aids' pre-edit `.json` and reports a finding resolved that is
not. So this module re-runs the eight, then compares --
`resolved`/`persisting`/`new` matched by each item's stable `id`, plus an
objective count before and after, so "is this item gone?" and "did the
total rise?" are field lookups rather than a model reading two JSON
documents side by side. `support` is one of the eight for the same
reason as the other seven -- skipping it would leave `claim-support`
stale, the exact bug this module exists to prevent -- at the cost of
its own ~21--60 s model-load floor (docs/REVIEW.md) every call.

Mirrors `chitragupta/review/verbatim_check/_recheck.py`'s payload shape
key for key, because the skill reading this one already reads that one.
What differs is what an item *is*: agenda's are `_render._item_dict`
dicts, not raw scan findings, and "objective" here is `unattended`
(`Agenda.objective_class_count`), not verbatim's "severity is not quoted".

**Why the eight aid modules are imported directly here.**
`chitragupta/review/__main__.py` already owns a name->module mapping, and
reusing it is impossible: it imports `chitragupta.review.agenda`, which
imports this module, so reaching back into either is a cycle. The mapping
is restated below instead, keyed by `_sources.AID_NAMES`' own eight
strings and checked against them in the tests -- a small, deliberate
duplication in exchange for an import graph that stays a tree. Nothing
here imports from `chitragupta.review.agenda` either -- `run()` hands its
own `build_agenda()` result to `compare` as plain data.

Module scope rather than inside `refresh_aids`: measured here, importing
all eight beside `chitragupta.review.agenda` costs 13 ms against a bare
`review agenda <draft>` run of ~500 ms -- too little to buy indirection.
"""

import contextlib
import io
import json
import shlex
from pathlib import Path

from chitragupta import dossier, review
from chitragupta.dossier._retrieval import recorded_queries
from chitragupta.review import (
    citation_coverage,
    citation_provenance,
    claim_support,
    figure_layout,
    quotation,
    synthesis,
    uncited_prose,
    verbatim_check,
)
from chitragupta.review.agenda._sources import AID_NAMES

_AID_MODULES = {
    "provenance": citation_provenance,
    "verbatim": verbatim_check,
    "coverage": citation_coverage,
    "synthesis": synthesis,
    "figure": figure_layout,
    "uncited": uncited_prose,
    "quotation": quotation,
    "support": claim_support,
}


def _coverage_queries(draft: Path) -> list[str]:
    """The queries `coverage` is re-run with -- the draft's own
    `retrieval.md` rows, revision markers excluded.

    That source is `f-auto-improvement-adoption.md`'s Q5 answer, and
    already solved: `recorded_queries` deduplicates, preserves first-seen
    order, and skips `mark_revision`'s boundary rows, whose third cell
    holds a `--label` and not a query. Empty for a draft outside
    `content/drafts/`, one with no dossier directory yet, and one
    recording no non-revision row -- the degrade-rather-than-raise
    posture `_sources._read_drift` keeps. The caller then skips
    `coverage` entirely; fabricating a query to avoid that would invent
    the very thing this pipeline exists to refuse.
    """
    try:
        directory = dossier.dossier_dir(draft)
    except dossier.DossierError:
        return []
    if not directory.is_dir():
        return []
    return recorded_queries(directory)


def _aid_argv(aid: str, draft: Path, queries: list[str]) -> list[str] | None:
    """One aid's refresh argv, or `None` for one that must be skipped.

    Everything runs at `--formats md`: only three of the eight render
    beside the Markdown at all, and dropping those saves ~2.5 s a cycle
    (Decision 6 of `plans/f3-agenda-reviser.md`, measured). Each aid's
    `.tex`/`.pdf` therefore goes stale against its `.md` during a pass --
    acceptable only because reports are regenerable and untimestamped.

    Three of the eight depart from the common shape, and each is an
    argparse `SystemExit(2)` rather than quiet misbehaviour if got wrong:
    `provenance` has **no `--write` flag** (it files unconditionally, the
    convention `agenda` itself follows); `verbatim` takes a subcommand,
    so `scan` has to be argv[0]; and `coverage`'s `--query` is
    `required=True`. `None` means skip, and that aid's existing `.json`,
    if any, is read as-is by the rebuild -- like any other aid whose
    report is simply absent.
    """
    if aid == "provenance":
        return [str(draft), "--formats", "md"]
    if aid == "verbatim":
        return ["scan", str(draft), "--write", "--formats", "md"]
    if aid == "coverage":
        if not queries:
            return None
        flags = [flag for query in queries for flag in ("--query", query)]
        return [str(draft), *flags, "--write", "--formats", "md"]
    return [str(draft), "--write", "--formats", "md"]


def refresh_aids(draft: Path) -> None:
    """Re-run the eight aids over `draft`, so the rebuild that follows
    reads this edit's findings and not the last one's.

    No return value: the side effect is the eight `.json`/`.md` landing
    on disk, which the caller's own `build_agenda()` then reads. Exit
    codes are deliberately ignored -- every aid here exits 0 whatever it
    finds, and one that could not read an input degrades to "absent",
    which the agenda names in its header rather than refuses on.

    **Each `main()` runs with stdout redirected into a throwaway buffer.**
    All eight print a written-files summary of their own, which under
    `agenda --baseline ... --json` would land on stdout ahead of the
    payload and corrupt a caller piping it through `json.loads`.
    Discarding it is right rather than convenient: it reports files this
    command asked for on the caller's behalf and never promised to show.
    """
    queries = _coverage_queries(draft)
    for aid in AID_NAMES:
        argv = _aid_argv(aid, draft, queries)
        if argv is None:
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            _AID_MODULES[aid].main(argv)


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


def compare(
    new_items: list[dict], baseline_items: list[dict]
) -> tuple[list[dict], list[dict], list[dict], int, int]:
    """`(resolved, persisting, new, objective_before, objective_after)`
    for one agenda against another.

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
    new_ids = {item["id"] for item in new_items}
    baseline_ids = {item["id"] for item in baseline_items}
    resolved = [item for item in baseline_items if item["id"] not in new_ids]
    persisting = [item for item in new_items if item["id"] in baseline_ids]
    appeared = [item for item in new_items if item["id"] not in baseline_ids]

    def objective(items: list[dict]) -> int:
        return sum(1 for item in items if item["unattended"])

    return resolved, persisting, appeared, objective(baseline_items), objective(new_items)


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
    groups: tuple[list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
    command: str,
) -> dict:
    """The comparison as data -- `verbatim recheck`'s payload shape, key
    for key. Carries the baseline's path as well as the three groups: a
    verdict whose basis is not recorded beside it is one nobody can
    check later.
    """
    resolved, persisting, appeared = groups
    before, after = counts
    payload = review.envelope(Path(draft), "agenda", command)
    payload.update(
        {
            "baseline": str(baseline_path),
            "objective_before": before,
            "objective_after": after,
            "objective_delta": after - before,
            "resolved": resolved,
            "persisting": persisting,
            "new": appeared,
        }
    )
    return payload


def format_recheck(
    baseline_path: str | Path,
    groups: tuple[list[dict], list[dict], list[dict]],
    counts: tuple[int, int],
) -> str:
    """The plain-text form, for stdout. Lists each item by `id`, `class`
    and `summary` -- an agenda item's own fields, where `verbatim
    recheck`'s counterpart prints a citekey, a page range and a line.
    """
    resolved, persisting, appeared = groups
    before, after = counts
    lines = [f"baseline: {baseline_path}", ""]
    for label, items in (
        ("resolved", resolved),
        ("persisting", persisting),
        ("new", appeared),
    ):
        lines.append(f"  {label} ({len(items)}):")
        if not items:
            lines.append("      -")
        for item in items:
            lines.append(f"      `{item['id']}` [{item['class']}]: {item['summary']}")
        lines.append("")
    lines.append(f"objective items (unattended): {before} -> {after} ({after - before:+d})")
    return "\n".join(lines)
