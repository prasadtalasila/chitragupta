"""`python -m chitragupta.draft unit`'s three commands and their argparse tree.

Split from `chitragupta/unit/__init__.py` the way `chitragupta/spec/_cli.py` and
`chitragupta/dossier/_cli.py` are split from theirs, and named `_cli.py` for the
same reason: this package has no `__main__.py`, because
`python -m chitragupta.draft unit` is the one front door
(docs/ARCHITECTURE.md's one-entry-point-per-layer invariant).
"""

import argparse
import json
import sys
from pathlib import Path

from chitragupta import citation_gate, spec
from chitragupta.dossier import dossier_dir
from chitragupta.dossier._draft_fingerprint import recorded_draft_digest
from chitragupta.spec._align import align
from chitragupta.unit import (
    UnitError,
    chapter_of,
    contract,
    draft_path,
    input_digest,
    acceptance_units,
    record_path,
    record_text,
    state,
)

_BOOK_HELP = "The book's directory under content/drafts/"

_SOURCE_HELP = (
    "A citekey this unit is grounded in -- repeatable. Part of the "
    "input digest, so re-running with a different set is a different "
    "unit to generate"
)


def _print_contract(built: dict) -> None:
    print(f"# {built['title']}")
    print(f"- unit: {built['unit']}")
    print(f"- in: {' > '.join(built['ancestor_titles'])}")
    print(f"- draft: {built['draft']}")
    print(f"- sources: {', '.join(built['sources']) or 'none'}")
    print(f"- input digest: {input_digest(built)}")
    print(f"- outline: {'signed off' if built['signed_off'] else 'not signed off'}")
    print()
    print(built["brief"])


def _cmd_contract(args) -> int:
    built = contract(args.book, args.unit, args.source)
    if args.json:
        print(json.dumps({**built, "input_digest": input_digest(built)}, indent=2, sort_keys=True))
        return 0
    _print_contract(built)
    return 0


def _refuse(message: str) -> int:
    print(f"[error] {message}", file=sys.stderr)
    return 1


def _cmd_accept(args) -> int:
    built = contract(args.book, args.unit, args.source)
    if not built["signed_off"]:
        return _refuse(
            f"{args.book}'s outline is not signed off, so there is nothing to "
            f"accept a unit against. `python -m chitragupta.draft spec sign {args.book}`."
        )
    drifted = _misalignment(args.book, chapter_of(built))
    if drifted:
        return _refuse(
            f"{args.unit}'s chapter no longer matches the outline it was approved "
            f"against ({drifted}). `python -m chitragupta.draft spec align {args.book}` "
            "lists what moved."
        )
    draft = Path(built["draft"])
    if not draft.is_file():
        return _refuse(
            f"no draft at {draft}. Generate the unit from its contract before accepting it."
        )
    # The project's one gate, invoked rather than re-implemented: a unit
    # nobody may cite from is not a unit a book may assemble from. It
    # prints its own PASS/FAIL, so nothing is restated here.
    if citation_gate.run([str(draft)]) != 0:
        return _refuse(
            f"the citation gate refuses {draft}, so it cannot be "
            "accepted. Fix the citekeys it named."
        )
    text = draft.read_text(encoding="utf-8")
    # Same LaTeX-aware blanking the gate itself just applied to this
    # draft -- recording with the Markdown rules would drop a citation
    # sitting between two LaTeX-quoted phrases from the permanent record.
    citekeys = sorted(
        {
            key
            for _, key in citation_gate.extract_citekeys(text, latex=draft.suffix.lower() == ".tex")
        }
    )
    path = record_path(args.book, args.unit)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record_text(built, text, citekeys), encoding="utf-8")
    print(f"Accepted {args.unit} at input digest {input_digest(built)}.")
    print(f"Wrote {path}.")
    return 0


def _misalignment(book, chapter: str) -> str:
    """How this unit's chapter disagrees with the outline, or "".

    Acceptance records that a human approved *this prose against that
    outline*, so a chapter whose headings have drifted makes the record
    say something untrue. Only chapters the outline describes at section
    level are held to it; `align` reports the rest as having nothing to
    align, and they carry no findings.

    A chapter nobody has written yet is deliberately not a refusal. A book
    is drafted unit by unit, and `align`'s "not written yet" would
    otherwise make the very first unit impossible to accept.
    """
    parsed = spec.parse(spec.spec_path(book).read_text(encoding="utf-8"))
    for report in align(book, parsed)["chapters"]:
        if report["id"] != chapter or not report.get("written"):
            continue
        counts = {
            "not authored": len(report["not_authored"]),
            "not declared": len(report["not_declared"]),
            "renamed": len(report["renamed"]),
        }
        named = [f"{n} {what}" for what, n in counts.items() if n]
        if report["out_of_order"]:
            named.append("out of order")
        return ", ".join(named)
    return ""


def _fingerprint(book, unit_id: str) -> str:
    """What the *dossier* says about this unit's prose.

    Two records of the same text exist -- this layer's `output_digest`,
    written by `accept`, and the dossier's draft fingerprint, written by
    `dossier stamp`. They answer different questions ("changed since a
    human accepted it" against "changed since the sidecars were
    reconciled") and are refreshed by different commands, so they can
    disagree. Neither report mentioned the other, which left "stale:
    draft changed since accepted" as the whole story on a book where
    nothing had been stamped at all.

    Reported, never enforced: this layer does not judge a dossier.
    """
    draft = draft_path(book, unit_id)
    target = dossier_dir(draft)
    if not target.is_dir():
        return "no dossier"
    recorded = recorded_draft_digest(target)
    if recorded is None:
        return "not stamped"
    if not draft.is_file():
        return "stamped, no draft"
    return "agrees" if recorded == spec.digest(draft.read_text(encoding="utf-8")) else "disagrees"


def _cmd_status(args) -> int:
    found = acceptance_units(args.book)
    rows = [
        {
            "id": entry["id"],
            "state": state(args.book, entry["id"]),
            "fingerprint": _fingerprint(args.book, entry["id"]),
        }
        for entry in found
    ]
    accepted = sum(1 for row in rows if row["state"] == "accepted")
    if args.json:
        print(json.dumps({"units": rows, "accepted": accepted}, indent=2, sort_keys=True))
        return 0 if accepted == len(found) else 1
    for row in rows:
        print(f"  {row['id']:<24} {row['state']:<38} dossier: {row['fingerprint']}")
    print(f"\n  {accepted} of {len(found)} unit(s) accepted and current.")
    return 0 if accepted == len(found) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft unit",
        description="One section's generation contract, and the record of its "
        "acceptance. Writes only under content/specs/.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_contract = sub.add_parser(
        "contract", help="The inputs one unit is generated from, and their digest"
    )
    p_contract.add_argument("book", help=_BOOK_HELP)
    p_contract.add_argument("unit", help="The section's `{#id}` from the outline")
    p_contract.add_argument("--source", action="append", default=[], help=_SOURCE_HELP)
    p_contract.add_argument(
        "--json", action="store_true", help="Machine-readable, for a genre skill to read"
    )
    p_contract.set_defaults(func=_cmd_contract)

    p_accept = sub.add_parser(
        "accept", help="Record a generated unit as accepted, once the gate passes"
    )
    p_accept.add_argument("book", help=_BOOK_HELP)
    p_accept.add_argument("unit", help="The section's `{#id}` from the outline")
    p_accept.add_argument("--source", action="append", default=[], help=_SOURCE_HELP)
    p_accept.set_defaults(func=_cmd_accept)

    p_status = sub.add_parser("status", help="Where every unit in the book stands")
    p_status.add_argument("book", help=_BOOK_HELP)
    p_status.add_argument(
        "--json", action="store_true", help="Machine-readable, for a skill to read"
    )
    p_status.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (UnitError, spec.SpecError) as exc:
        return _refuse(str(exc))
