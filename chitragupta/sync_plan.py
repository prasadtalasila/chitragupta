"""The resolved sync plan, written down before any parsing starts, so an
interrupted run can be *offered* back its own plan instead of deriving
one from scratch (#764).

`docs/PERFORMANCE.md` measures a full serial run at 1h56m, and a machine
that sleeps an hour into one loses nothing it parsed -- content hashing
and `chitragupta/ledger.py`'s (size, mtime)-before-hash skip see to that
-- but it does lose the *decision*: which of 646 references still needed
work. This module is the missing half. It records that decision beside
the ledger and hands it back on request.

Split from `chitragupta/sync_decide.py` rather than added to it: that
module answers "what does the bibliography say", reading the ledger and
the bib file only. This one answers "what did the previous run decide",
reading an artefact -- a different question with a different source of
truth, and `sync.py` has 15 code lines of headroom against
docs/CODE-STANDARDS.md's C2 limit either way. The dependency is one-way:
this module calls `sync_decide._to_parse`, nothing calls back.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from chitragupta import config, sync_decide

# Bumped if the payload's shape ever changes. A plan whose schema this
# release does not know is treated as no plan at all: the work it
# describes is re-derived, which is exactly what happened before this
# module existed, so an unreadable plan can only ever cost the saving --
# never correctness.
_SCHEMA = 1

PLAN_FILENAME = "sync_plan.json"


def plan_path() -> Path:
    """Resolved on every call, never bound at import.

    `chitragupta/config.py` is read as a live module attribute by design
    (its own closing note says so) and the tests monkeypatch
    `config.CONTENT_DIR` onto a tmp tree. A module-level constant here
    would point at the real, gitignored corpus for the whole session.
    """
    return config.CONTENT_DIR / PLAN_FILENAME


def fingerprint(references) -> str:
    """What makes a recorded plan stale: the bibliography, and only it.

    Sorted (citekey, pdf path, resolution) over every reference, so an
    added, removed or re-filed entry rejects the plan -- the three shapes
    of "the bibliography changed" a resumed run must not paper over.

    Deliberately *not* the attachments' size/mtime. That would make this
    a fingerprint of the PDFs rather than of the bibliography, and a
    Zotero re-write or a restore from backup would then reject every
    valid plan -- disabling the feature in the one case (a long docling
    run over a big corpus) it exists for. A PDF that changes mid-run is
    outside the guarantee either way: an uninterrupted run would not
    re-stat it after its own decide phase either.
    """
    lines = sorted(f"{r.citekey}\t{r.pdf_path or ''}\t{r.pdf_resolution}" for r in references)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _read() -> "dict | None":
    """The recorded plan, or None when there is nothing usable to offer.

    Absent, unreadable, a schema this release does not know, and "recorded
    but nothing left in it" all collapse to the same answer, because the
    caller does the same thing with all four: derive the plan itself.
    """
    try:
        plan = json.loads(plan_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(plan, dict) or plan.get("schema") != _SCHEMA or not plan.get("remaining"):
        return None
    return plan


def _offer(plan, references, resume) -> "list[str] | None":
    """Which citekeys a resumed run should parse, or None to re-derive.

    **Offered, never forced.** `--resume` is the offer's acceptance, and
    the offer itself is a printed line. An interactive prompt would be
    the wrong shape: docs/CLI.md publishes `sync` as the one command in
    this project that plausibly runs from a crontab, where nothing is
    there to answer it and a blocked run holds the write lock until
    someone notices. Same posture as `dossier prune`'s `--apply` -- the
    confirmation is the feature -- and it means every existing caller,
    scheduled or not, behaves exactly as it did before this module.

    A rejected plan is never an error and never exits nonzero: the run
    simply derives its own, which is what it did before #764.
    """
    if plan is None:
        if resume:
            print("  --resume: no incomplete sync plan is recorded -- deriving one from scratch.")
        return None
    if plan["bib_fingerprint"] != fingerprint(references):
        print(
            f"  the sync plan recorded at {plan['recorded_at']} is stale: the bibliography "
            "has changed since it was written, so it was not resumed. Deriving a fresh plan."
        )
        return None
    if not resume:
        print(
            f"  an interrupted sync run left a plan recorded at {plan['recorded_at']}, with "
            f"{len(plan['remaining'])} document(s) still to parse. Re-run with --resume to "
            "continue it; this run derives a fresh plan instead."
        )
        return None
    print(
        f"  resuming the recorded sync plan from {plan['recorded_at']}: "
        f"{len(plan['remaining'])} document(s) still to parse."
    )
    return plan["remaining"]


def _restore(tally, decided) -> None:
    """Put the recorded run's decide-phase counts back on this run's
    tally, so a resumed run's summary reports the whole bibliography and
    not just the slice it re-decided."""
    tally.skipped += decided["skipped"]
    tally.no_pdf += decided["no_pdf"]
    tally.backend_unavailable += decided["backend_unavailable"]
    tally.no_pdf_reasons.update(decided["no_pdf_reasons"])


def _record(references, to_parse, tally) -> None:
    """Write this run's plan down, before a single document is parsed.

    A JSON file beside the ledger, never a table *in* it. docs/DESIGN.md
    counts six ledger commit points and turns down locking the ledger
    precisely because it "would force a run into one transaction,
    discarding the incremental commit points on a crash"; a seventh
    commit point would reopen that. A file write adds none, and lands
    after `sync_decide._to_parse`'s own `finally: con.commit()` -- so
    everything the plan presumes is already on disk is already on disk.

    Written via a temporary file and `replace()` so an interrupt during
    the write leaves either the old plan or the new one, never half of
    one -- the failure this whole feature is about.

    Nothing to parse means nothing to resume: the plan is discarded
    rather than recorded empty, so a caught-up corpus's routine no-op
    sync never offers a resume of nothing.
    """
    if not to_parse:
        discard()
        return
    payload = {
        "schema": _SCHEMA,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bib_fingerprint": fingerprint(references),
        "remaining": [ref.citekey for ref in to_parse],
        "decided": {
            "skipped": tally.skipped,
            "no_pdf": tally.no_pdf,
            "backend_unavailable": tally.backend_unavailable,
            "no_pdf_reasons": dict(tally.no_pdf_reasons),
        },
    }
    path = plan_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def discard() -> None:
    """Spend the plan, once every document in it has been attempted.

    On *attempted*, not on a clean exit code. A corpus with one
    permanently broken PDF exits nonzero on every run forever, and
    keeping the plan on that basis would offer the same doomed resume
    until someone fixed the PDF. What the plan records is what was still
    to be tried; a document that was tried and failed is recorded in the
    ledger, with its `failure_kind`, which is the mechanism that decides
    whether it is tried again -- deliberately the only one (#764 turns
    down a per-task retry counter for exactly that reason).
    """
    plan_path().unlink(missing_ok=True)


def resolve(con, references, reparse, parser_available, tally, resume=False) -> list:
    """The decide phase, with the recorded plan in front of it.

    Wraps `sync_decide._to_parse` rather than sitting beside it so
    `chitragupta/sync.py` changes by one call, not five -- it has 15 code
    lines of headroom against the C2 limit and is not a registered
    offender.

    A resumed run runs the *same* decide function over the plan's slice
    of the bibliography, rather than trusting the plan about what is
    already done. The ledger stays the single source of truth for that
    (a document parsed just before the interrupt is skipped here exactly
    as it would be in any later run), and the plan is only ever an answer
    to "which references were worth asking about".
    """
    plan = _read()
    remaining = _offer(plan, references, resume)
    # `deciding` is the slice to ask the ledger about; `references` stays
    # the whole bibliography, because that is what the fingerprint of the
    # plan we are about to record has to be over. Collapsing the two
    # would fingerprint the slice, and a run interrupted twice would then
    # reject its own second plan as stale.
    deciding = references
    if remaining is not None:
        _restore(tally, plan["decided"])
        by_citekey = {ref.citekey: ref for ref in references}
        deciding = [by_citekey[citekey] for citekey in remaining]
    to_parse = sync_decide._to_parse(con, deciding, reparse, parser_available, tally)
    _record(references, to_parse, tally)
    return to_parse
