"""The considered-and-accepted record: what keeps a surfaced judgement
item off the next worklist, and the rule for which classes may have one.

The agenda still recomputes from the aids on every run -- nothing here is
a durable queue with mutable item state, which #767 weighed and rejected:
the recompute-from-aids property is worth more than the convenience. What
persists is a set of *identities* a person has already decided about, and
suppression is a filter applied to a freshly computed list, never a
stored verdict about an item.

**Reopening needs no mechanism.** `_identity.item_id` hashes the matched
span, so a reworded claim raises a different id, which no record matches,
and the item is back on the worklist -- see `partition` and its test. The
acceptance says "I have read *this* text and I accept it", which is
exactly what a span-keyed identity can carry and a citekey- or
section-keyed one could not (the alternative #767 rejects as too coarse).

**Three classes may be accepted, and one surfaced class deliberately may
not.** `claim-support`, `uncited-claim` and `unsupported-claim` are
surfaced because a person genuinely has a call to make. `misquoted` is
not, and is excluded here rather than merely unimplemented:

1. It is surfaced for a *write-set* reason, not a judgement one --
   docs/AUTO-IMPROVEMENT.md's own entry says the defect is in
   `evidence.md` while `agenda-reviser` edits drafts, so there is no
   unattended repair. That is a statement about what a tool can reach,
   not about a person having a decision to record.
2. The class conflates two very different findings.
   `chitragupta/review/_quotation_match.py` measured 70 raw findings
   reducing to 33 after three normalisations, and 40 to 38 after the
   fourth issue #775 added, and calls the residue
   "residual absents": an `absent` finding is either a correct quote the
   matcher cannot verify or a genuinely fabricated quotation, which is
   the one failure SOUL.md exists to prevent. The aid does not
   distinguish them, and the obvious discriminator is closed off --
   `_quotation_match.py` states that R3 bars a continuous
   `near_miss_score` from being optimised against.
3. Its identity is keyed on the wrong side of the comparison.
   `_items_findings.misquoted_items` sets `section=None`, `line=None` and
   spans the quote text from `evidence.md`, so a `misquoted` finding can
   become newly true with the quote byte-identical -- a re-parse under
   different `PARSER_*` settings, a replaced PDF, a `corpus sync`. The
   identity would not change, so the acceptance would hold and a real
   fabrication would stay suppressed. Every acceptable class above is
   keyed on the draft text it is about.

Issue #775 asked whether `misquoted` should ever be acceptable and
answered **no**, after narrowing the class with a fourth normalisation
first. Finding 2 above is reduced but not removed -- 38 residual absents
remain on the measured corpus, 5 of them the real defect the aid exists
for -- and finding 3 is untouched, so accepting one would still need an
identity carrying the parsed source's fingerprint, which #767 declined
to build. docs/AUTO-IMPROVEMENT.md records the decision; this module
refuses it today, and
`TestAcceptableClasses` derives the refused set from `_items.CLASSES` so
a ninth class has to decide rather than inherit an answer.

**Filed under `content/review/`, beside the report it suppresses from.**
That is the review layer, which is where #767 places this feature, and
it keeps the record next to the `<stem>.agenda.json` whose ids it names.
One consequence is worth knowing: `draft dossier export`/`restore`
bundles drafts and dossiers, not `content/review/`, so unlike
`rejected.md` an acceptance record does not survive that round-trip. The
cost of losing one is a re-judgement, not a wrong answer -- every item
simply comes back surfaced.
"""

import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import review

# The surfaced classes a person may record a decision about. Not derived
# from `Item.unattended`: that field says whether a *tool* may act
# without asking, which is a different question from whether a *person*
# has a judgement to record -- `verbatim-run`'s long bucket is surfaced
# and is still a defect.
ACCEPTABLE = (
    "claim-support",
    "uncited-claim",
    "unsupported-claim",
)

# `<stem>.accepted.json`, not `<stem>.<aid>.json`: `review.report_path`
# refuses any name outside `review.AIDS`, and rightly -- this is not an
# aid's report, and adding a tenth key to that registry to file it would
# claim a report nothing writes.
SUFFIX = "accepted"


class NotAcceptable(ValueError):
    """An id that cannot be accepted: unknown, of a class that may not be
    accepted, or held in a record file this run could not read."""


@dataclass
class AcceptedSource:
    """The acceptance record as the agenda sees it -- an optional input
    that degrades to absent rather than raising, exactly like the eight
    aids' `.json` in `_sources.py`.

    Degrading is safe in the one direction that matters: a record that
    cannot be read suppresses nothing, so every accepted item returns to
    the worklist. The failure mode is a re-judgement, never a hidden
    finding.
    """

    available: bool = False
    records: list[dict] = field(default_factory=list)
    reason: str | None = None


def accepted_path(draft: Path) -> Path:
    """`content/review/<topic>/<stem>.accepted.json` for `draft`."""
    return review.report_dir(draft) / f"{Path(draft).stem}.{SUFFIX}.json"


def load(draft: Path) -> AcceptedSource:
    """The acceptance record for `draft`, or an absent one."""
    path = accepted_path(draft)
    if not path.is_file():
        return AcceptedSource()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return AcceptedSource(reason=f"{path}: {exc}")
    records = payload.get(SUFFIX) if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return AcceptedSource(reason=f"{path}: no '{SUFFIX}' list -- not an acceptance record")
    # A hand-edited row without an id names no item and can suppress
    # nothing; dropping it keeps the rest of the record usable rather
    # than failing the whole agenda over one bad line.
    kept = [row for row in records if isinstance(row, dict) and isinstance(row.get("id"), str)]
    return AcceptedSource(available=True, records=kept)


def accepted_ids(source: AcceptedSource) -> set[str]:
    return {record["id"] for record in source.records}


def partition(items: list, source: AcceptedSource) -> tuple[list, list]:
    """`(kept, suppressed)` for one run's items against the record.

    Order is the caller's, untouched: `_order.sort` has already run, and
    a filter must not renumber what it did not remove.
    """
    ids = accepted_ids(source)
    kept = [item for item in items if item.id not in ids]
    suppressed = [item for item in items if item.id in ids]
    return kept, suppressed


def accept_command(draft: Path, ids: list[str]) -> str:
    """The invocation recorded in the acceptance file's envelope, so the
    record says how it came to exist."""
    flags = [flag for item_id in ids for flag in ("--accept", item_id)]
    parts = ["python", "-m", "chitragupta.review", "agenda", str(draft), *flags]
    return shlex.join(parts)


def _record(item) -> dict:
    """One accepted item, as the file keeps it.

    Carries the class, section, citekey and summary beside the id, none
    of which the suppression reads: the id alone decides that. They are
    there so the record is auditable by a person who no longer has the
    agenda that raised it -- an opaque list of twelve-character hashes
    would record the decision without preserving what was decided.
    """
    return {
        "id": item.id,
        "class": item.cls,
        "section": item.section,
        "citekey": item.citekey,
        "summary": item.summary,
    }


def _resolve(item_id: str, by_id: dict) -> object:
    item = by_id.get(item_id)
    if item is None:
        raise NotAcceptable(
            f"No agenda item `{item_id}` for this draft. Ids come from the "
            "worklist this command files; run it without --accept first."
        )
    if item.cls not in ACCEPTABLE:
        raise NotAcceptable(
            f"`{item_id}` is a {item.cls} item, which cannot be accepted. "
            f"Only {', '.join(ACCEPTABLE)} are surfaced for a judgement a "
            "person records; every other class describes something to "
            "repair, not to decide about."
        )
    return item


def accept(draft: Path, items: list, ids: list[str], command: str) -> list[str]:
    """Record each of `ids` as accepted, returning one message per id.

    Raises `NotAcceptable` before writing anything, so a mistyped id in a
    repeated `--accept` leaves the record exactly as it was rather than
    half-applied.
    """
    source = load(draft)
    if source.reason:
        raise NotAcceptable(
            f"The acceptance record is unreadable ({source.reason}), so this "
            "run will not rewrite it. Repair or delete the file; every "
            "accepted item is on the worklist again until you do."
        )
    by_id = {item.id: item for item in items}
    known = accepted_ids(source)
    records, messages = list(source.records), []
    for item_id in ids:
        if item_id in known:
            messages.append(f"`{item_id}` was already accepted -- nothing to do.")
            continue
        item = _resolve(item_id, by_id)
        records.append(_record(item))
        known.add(item_id)
        messages.append(f"accepted `{item_id}` [{item.cls}]: {item.summary}")
    write(draft, records, command)
    return messages


def apply(draft: Path, agenda, args) -> int | None:
    """`--accept`'s whole side of the command: record each id, say what
    was recorded, and return the layer's usage-error code if any id was
    refused.

    Takes the built `Agenda` rather than building one, so this module
    stays a leaf its own package can import without a cycle.
    """
    # Resolved against `items + suppressed`, so an id accepted by an
    # earlier run reports "already accepted" rather than "no such item"
    # -- suppression is what would otherwise hide it from the very lookup
    # checking it. A stale-refused item is deliberately not in that
    # lookup: it is off this run's worklist on other grounds, and every
    # refusable class is unacceptable anyway (`build_agenda`). The
    # messages keep the written-files summary's stream discipline:
    # stderr under `--json`, so a caller piping stdout through
    # `json.loads` is unaffected.
    try:
        messages = accept(
            draft,
            agenda.items + agenda.suppressed,
            args.accept,
            accept_command(draft, args.accept),
        )
    except NotAcceptable as exc:
        print(exc, file=sys.stderr)
        return 2
    stream = sys.stderr if args.json else sys.stdout
    for message in messages:
        print(message, file=stream)
    return None


def write(draft: Path, records: list[dict], command: str) -> Path:
    """The record, with the same provenance envelope every report carries
    and the same no-date discipline: two identical acceptance histories
    produce byte-identical files."""
    payload = review.envelope(draft, "agenda", command)
    payload[SUFFIX] = records
    path = accepted_path(draft)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
