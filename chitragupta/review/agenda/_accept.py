"""The considered-and-accepted record: what keeps a surfaced judgement
item off the next worklist, and the rule for which classes may have one.

The agenda still recomputes from the aids every run; a durable queue with
item state was rejected (#767). What persists is a set of identities a
person decided about, and suppression filters a freshly computed list.
Reopening needs no mechanism: `_identity.item_id` hashes the matched span,
so a reworded claim gets a new id and returns to the worklist.

`claim-support`, `uncited-claim` and `unsupported-claim` may be accepted.
`misquoted` deliberately may not (#775):

1. It is surfaced because its defect is in `evidence.md`, out of
   `agenda-reviser`'s reach, not because a person has a call to make.
2. An `absent` finding is either an unverifiable correct quote or a
   fabricated one, the failure SOUL.md exists to prevent; 38 residual
   absents remain, 5 real (`_quotation_match.py`), and R3 bars tuning a
   discriminator.
3. Its identity is keyed on the quote, not the draft, so it can become
   newly true with the quote unchanged (a re-parse, a replaced PDF); an
   acceptance would then hide a real fabrication.

`TestAcceptableClasses` derives the refused set from `_items.CLASSES`, so
a new class must decide. The record lives beside `<stem>.agenda.json` in
`content/review/`, so `dossier export`/`restore` does not carry it; losing
one costs a re-judgement, never a wrong answer.
"""

import json
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta import review

# Not derived from `Item.unattended`, which says whether a tool may act,
# not whether a person has a judgement to record.
ACCEPTABLE = (
    "claim-support",
    "uncited-claim",
    "unsupported-claim",
)

# `<stem>.accepted.json`: `review.report_path` rightly refuses names
# outside `review.AIDS`, and this is no aid's report.
SUFFIX = "accepted"


class NotAcceptable(ValueError):
    """An id that cannot be accepted: unknown, of a class that may not be
    accepted, or held in a record file this run could not read."""


@dataclass
class AcceptedSource:
    """The acceptance record as the agenda sees it: optional, degrading to
    absent like `_sources.py`'s inputs. Safe, since an unreadable record
    suppresses nothing; the cost is a re-judgement, never a hidden finding.
    """

    available: bool = False
    records: list[dict] = field(default_factory=list)
    reason: str | None = None


def accepted_path(draft: Path) -> Path:
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
    # An id-less hand-edited row names no item; drop it, keep the rest.
    kept = [row for row in records if isinstance(row, dict) and isinstance(row.get("id"), str)]
    return AcceptedSource(available=True, records=kept)


def accepted_ids(source: AcceptedSource) -> set[str]:
    return {record["id"] for record in source.records}


def partition(items: list, source: AcceptedSource) -> tuple[list, list]:
    """`(kept, suppressed)` for one run's items against the record, in the
    caller's order: a filter must not renumber what it did not remove.
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
    """One accepted item, as the file keeps it. Only the id decides
    suppression; class, section, citekey and summary keep the decision
    auditable without the agenda that raised it.
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
    Raises `NotAcceptable` before writing, so a mistyped id leaves the
    record untouched.
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
    """`--accept`'s side of the command: record each id, report, and return
    the usage-error code if any was refused. Takes the built `Agenda`, so
    this module stays a leaf.
    """
    # Resolved against `items + suppressed`, so a re-accepted id says
    # "already accepted"; stale-refused items are excluded (no refusable
    # class is acceptable). Messages go to stderr under `--json`.
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
    """The record, with every report's envelope and no date, so identical
    histories produce byte-identical files."""
    payload = review.envelope(draft, "agenda", command)
    payload[SUFFIX] = records
    path = accepted_path(draft)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
