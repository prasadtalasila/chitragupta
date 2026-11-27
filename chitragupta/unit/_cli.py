"""`python -m chitragupta.draft unit`'s three commands and their argparse tree.

No `__main__.py`: `python -m chitragupta.draft unit` is the one front
door (docs/ARCHITECTURE.md's one-entry-point-per-layer invariant).
"""

import json
import sys
from pathlib import Path

from chitragupta import citation_gate, ledger, spec
from chitragupta.ledger_citable import citable_citekeys, unparsed_citekeys
from chitragupta.dossier import dossier_dir
from chitragupta.dossier._draft_fingerprint import recorded_draft_digest
from chitragupta.spec._align import align
from chitragupta.unit import (
    UNITS_DIRNAME,
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
from chitragupta.help_format import ClickParser
from chitragupta.progname import prog_for

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


def _refusal_before_the_ledger(args, built: dict, draft: Path) -> "str | None":
    """Why `built` may not be accepted at all, or None if it may.

    Answerable without the ledger, so an unsigned book refuses with that
    reason even where no ledger has been built.
    """
    if not built["signed_off"]:
        return (
            f"{args.book}'s outline is not signed off, so there is nothing to "
            f"accept a unit against. `python -m chitragupta.draft spec sign {args.book}`."
        )
    drifted = _misalignment(args.book, chapter_of(built))
    if drifted:
        return (
            f"{args.unit}'s chapter no longer matches the outline it was approved "
            f"against ({drifted}). `python -m chitragupta.draft spec align {args.book}` "
            "lists what moved."
        )
    if not draft.is_file():
        return f"no draft at {draft}. Generate the unit from its contract before accepting it."
    return None


def _unknown_sources(built: dict, known: "set[str]", unparsed: "dict[str, str]") -> "str | None":
    """Why `--source` may not be recorded, or None if it may.

    An unchecked `--source` put citekeys no real parse produced into the
    permanent record (#506/m-69), which CLAUDE.md's one rule forbids.
    """
    unknown = [source for source in built["sources"] if source not in known]
    if not unknown:
        return None
    # A .bib entry whose PDF never parsed is refused too, and said so
    # (#1118), so nobody re-exports a bib that already holds it.
    reasons = [f"{s} has no parsed PDF (status {unparsed[s]})" for s in unknown if s in unparsed]
    absent = [source for source in unknown if source not in unparsed]
    if absent:
        reasons.append(f"{', '.join(absent)} is not in the ledger")
    return (
        "; ".join(reasons) + ", so it cannot be recorded as a source this unit is grounded in. "
        "`python -m chitragupta.corpus sync` picks up a newly exported .bib."
    )


def _cmd_accept(args) -> int:
    built = contract(args.book, args.unit, args.source)
    draft = Path(built["draft"])
    refusal = _refusal_before_the_ledger(args, built, draft)
    if refusal:
        return _refuse(refusal)

    with ledger.reading() as con:
        known, unparsed = citable_citekeys(con), unparsed_citekeys(con)
    refusal = _unknown_sources(built, known, unparsed)
    if refusal:
        return _refuse(refusal)

    # Read once and gate *that* string: re-reading after gating let a
    # concurrent write get a record for ungated prose (#506/m-69).
    text = draft.read_text(encoding="utf-8")
    result = citation_gate.check_text(draft, text, known, unparsed)
    citation_gate.report(str(draft), result)
    if not result.ok:
        return _refuse(
            f"the citation gate refuses {draft}, so it cannot be "
            "accepted. Fix the citekeys it named."
        )
    # The gate's LaTeX-aware blanking, or a citation between LaTeX
    # quotes would drop from the record.
    citekeys = sorted({key for _, key in citation_gate.extract_citekeys_for(draft, text)})
    path = record_path(args.book, args.unit)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record_text(built, text, citekeys), encoding="utf-8")
    print(f"Accepted {args.unit} at input digest {input_digest(built)}.")
    print(f"Wrote {path}.")
    return 0


def _misalignment(book, chapter: str) -> str:
    """How this unit's chapter disagrees with the outline, or "".

    Only chapters described at section level are held to it. An unwritten
    chapter is not a refusal, or the first unit could never be accepted.
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

    `output_digest` (changed since accepted) and the dossier fingerprint
    (changed since stamped) can disagree; reported, never enforced.
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


def _orphaned(book: Path, found: list[dict]) -> list[str]:
    """Acceptance records whose unit the outline no longer holds.

    Listed, never deleted (#1137): the record is evidence a person
    approved the prose.
    """
    units = spec.spec_dir(book) / UNITS_DIRNAME
    held = {entry["id"] for entry in found}
    return sorted(path.stem for path in units.glob("*.json") if path.stem not in held)


def _cmd_status(args) -> int:
    found = acceptance_units(args.book)
    orphaned = _orphaned(args.book, found)
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
        report = {"units": rows, "accepted": accepted, "orphaned": orphaned}
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if accepted == len(found) else 1
    for row in rows:
        print(f"  {row['id']:<24} {row['state']:<38} dossier: {row['fingerprint']}")
    print(f"\n  {accepted} of {len(found)} unit(s) accepted and current.")
    if orphaned:
        print(
            f"  accepted, but no longer in the outline: {', '.join(orphaned)} "
            "(records and prose are left on disk)"
        )
    return 0 if accepted == len(found) else 1


def main(argv: list[str] | None = None) -> int:
    parser = ClickParser(
        prog=f"{prog_for('draft')} unit",
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
