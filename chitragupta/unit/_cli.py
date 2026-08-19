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
from chitragupta.unit import (UnitError, contract, input_digest, record_path, record_text,
                      sections, state)

_BOOK_HELP = "The book's directory under content/drafts/"

_SOURCE_HELP = ("A citekey this unit is grounded in -- repeatable. Part of the "
                "input digest, so re-running with a different set is a different "
                "unit to generate")


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
        print(json.dumps({**built, "input_digest": input_digest(built)},
                         indent=2, sort_keys=True))
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
            f"accept a unit against. `python -m chitragupta.draft spec sign {args.book}`.")
    draft = Path(built["draft"])
    if not draft.is_file():
        return _refuse(f"no draft at {draft}. Generate the unit from its contract "
                       "before accepting it.")
    # The project's one gate, invoked rather than re-implemented: a unit
    # nobody may cite from is not a unit a book may assemble from. It
    # prints its own PASS/FAIL, so nothing is restated here.
    if citation_gate.run([str(draft)]) != 0:
        return _refuse(f"the citation gate refuses {draft}, so it cannot be "
                       "accepted. Fix the citekeys it named.")
    text = draft.read_text(encoding="utf-8")
    citekeys = sorted({key for _, key in citation_gate.extract_citekeys(text)})
    path = record_path(args.book, args.unit)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record_text(built, text, citekeys), encoding="utf-8")
    print(f"Accepted {args.unit} at input digest {input_digest(built)}.")
    print(f"Wrote {path}.")
    return 0


def _cmd_status(args) -> int:
    found = sections(args.book)
    accepted = 0
    for section in found:
        current = state(args.book, section["id"])
        if current == "accepted":
            accepted += 1
        print(f"  {section['id']:<24} {current}")
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
        "contract", help="The inputs one unit is generated from, and their digest")
    p_contract.add_argument("book", help=_BOOK_HELP)
    p_contract.add_argument("unit", help="The section's `{#id}` from the outline")
    p_contract.add_argument("--source", action="append", default=[], help=_SOURCE_HELP)
    p_contract.add_argument("--json", action="store_true",
                            help="Machine-readable, for a genre skill to read")
    p_contract.set_defaults(func=_cmd_contract)

    p_accept = sub.add_parser(
        "accept", help="Record a generated unit as accepted, once the gate passes")
    p_accept.add_argument("book", help=_BOOK_HELP)
    p_accept.add_argument("unit", help="The section's `{#id}` from the outline")
    p_accept.add_argument("--source", action="append", default=[], help=_SOURCE_HELP)
    p_accept.set_defaults(func=_cmd_accept)

    p_status = sub.add_parser("status", help="Where every unit in the book stands")
    p_status.add_argument("book", help=_BOOK_HELP)
    p_status.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (UnitError, spec.SpecError) as exc:
        return _refuse(str(exc))
