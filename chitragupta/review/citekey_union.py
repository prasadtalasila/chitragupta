"""The citekey union invariant: the citekeys out must be the citekeys in.

A deterministic check on the one place this pipeline *combines* evidence
without writing prose. `book-assembler` composes accepted units into
`content/drafts/<book>/book.tex`; every unit has already recorded, in
`content/specs/<book>/units/<unit-id>.json`, the citekeys its prose
stands on. So the invariant is set arithmetic against something on disk:
the union of the inputs' citekeys must equal the union in the output.
No model, no judgement, no threshold.

docs/RAG.md catalogues why a combining step drops a source silently --
four of LlamaIndex's five synthesis modes can lose one with no error and
no log. What makes a *located* answer possible here is that the expected
set was recorded before the assembly existed, so "the book dropped
`smith_2024`, which `ch-model` stands on" is a subtraction rather than a
reconstruction.

**A book is composed by reference, and reading it any other way gives a
wholly false report.** `book.tex` is structure only -- it `\\input`s its
units and citeproc resolved each unit's citations inside that unit -- so
the assembly's own text contains no citekey, and subtracting against it
would report every source in the book as lost. `_citekey_union_includes`
owns that resolution and its docstring owns the argument; what follows
from it is the shape of both directions here:

- **Dropped**: an accepted unit the assembly never includes. Including a
  unit includes all of its prose, so omitting one is how a source
  actually goes missing at this step -- and every citekey only that unit
  stood on goes with it. Located to the unit.
- **Appeared**: a citekey in something the assembly includes that is
  *not* a unit -- a title page, an appendix, a preamble file. It entered
  outside any acceptance record, which the gate cannot see because the
  citekey is perfectly real.

Appeared is **withheld** while any unit is unchecked: that citekey may
be one of theirs, and this reports that it cannot tell rather than a
finding it has not earned.

**A unit whose record no longer describes its prose is not compared
against.** `unit.state` distinguishes `unwritten`/`drafted`/`stale:`
from `accepted`, and a stale record's citekeys describe text that no
longer exists -- comparing against them reports a drop that is not one.
Those units are named in the report instead, never silently skipped,
and so is any include that resolved to no file on disk.

One of the ten commands in the **review layer**: read over a finished
assembly, by a person or by a driver, never a gate, never holding the
write lock. chitragupta/review/__init__.py owns where a written report
goes (`content/review/<book>/book.union.md`) and what its header says.

Stdlib-only, reusing `chitragupta.citation_gate.extract_citekeys` -- the
same extractor `unit accept` recorded the input side with, which is what
makes the two sets comparable at all.

Usage:
    python -m chitragupta.review union content/drafts/<book>/book.tex
    python -m chitragupta.review union content/drafts/<book>/book.tex --write
"""

import argparse
import hashlib
import json
import shlex
import sys
from pathlib import Path

from chitragupta import citation_gate, config, review, unit
from chitragupta.review import _citekey_union_includes, _citekey_union_render
from chitragupta.review._citekey_union_result import UnionResult, UnitInput


def _recorded_citekeys(book: Path, unit_id: str) -> list[str]:
    """The citekeys `unit accept` recorded for `unit_id`.

    No error handling, and that is the contract rather than an omission:
    this is only ever called for a unit `unit.state` has just reported
    `accepted`, which it does not say unless the record parsed and both
    of its digests matched.
    """
    record = json.loads(unit.record_path(book, unit_id).read_text(encoding="utf-8"))
    return list(record["citekeys"])


def _citekeys(text: str) -> set[str]:
    """Every citekey in `text`, by the extractor the gate and `unit accept`
    both use -- so the two sides of the subtraction are the same set."""
    return {key for _, key in citation_gate.extract_citekeys(text)}


def compute(assembled: Path) -> UnionResult:
    """The invariant over `assembled` and the book directory holding it.

    Raises `unit.UnitError` for a path in no book, or in one whose
    outline does not parse -- there is no expected set to compare against
    in either case, and inventing one is the failure this aid exists to
    catch.
    """
    assembled = Path(assembled)
    book = assembled.parent
    units = unit.acceptance_units(book)
    text = assembled.read_text(encoding="utf-8")
    included, others, unread = _citekey_union_includes.split(
        book, text, {entry["id"] for entry in units}
    )

    result = UnionResult(
        assembled=assembled,
        # The assembly's *own* citekeys: its skeleton plus every file it
        # pulls in that no unit owns. Never a unit's -- reading those here
        # would answer the question with its own input.
        own=_citekeys(text).union(*(_citekeys(body) for _, body in others)),
        outside_units=[name for name, _ in others],
        unresolved=unread,
    )
    for entry in units:
        unit_id = entry["id"]
        state = unit.state(book, unit_id)
        # A unit that is both unincluded and unbelievable is reported as
        # unchecked, not as dropped: without a usable record there are no
        # citekeys to say were lost. The report names both facts.
        if state == "accepted":
            result.checked.append(
                UnitInput(unit_id, state, unit_id in included, _recorded_citekeys(book, unit_id))
            )
        else:
            result.unchecked.append(UnitInput(unit_id, state, unit_id in included))
    return result


def refuse_a_unit(assembled: Path) -> str | None:
    """Why `assembled` is one of the book's own units, if it is.

    Pointed at `ch-model.md`, this aid would report every *other*
    unit's citekeys as dropped -- a confident and wholly wrong report,
    and the one misuse the path shape makes easy. Checked by id rather
    than by name, so it holds for both suffixes a genre skill emits.
    """
    book = Path(assembled).parent
    if Path(assembled).stem in {entry["id"] for entry in unit.acceptance_units(book)}:
        return (
            f"{assembled} is unit `{Path(assembled).stem}` of {book}, not an assembly of "
            "its units. This aid compares a composed book against the units it was "
            "composed from; pointed at one unit it would report every other unit's "
            "citekeys as lost. Name the assembled document instead."
        )
    return None


def _command(assembled: Path, as_json: bool, write: bool) -> str:
    """The invocation recorded in the Markdown header and JSON envelope."""
    parts = ["python", "-m", "chitragupta.review", "union", str(assembled)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def finding_id(citekey: str, status: str) -> str:
    """A finding's name, stable across runs and position-free -- the same
    convention `citation_coverage.finding_id` and
    `verbatim_check.finding_id` use."""
    return hashlib.sha256(f"{citekey}\x00{status}".encode()).hexdigest()[:12]


def _findings(result: UnionResult) -> list[dict]:
    """One object per citekey the report itemises, dropped first: it is
    the direction that is always answerable, and the one a reader acts
    on."""
    findings = [
        {
            "id": finding_id(key, "dropped"),
            "citekey": key,
            "status": "dropped",
            "units": units,
        }
        for key, units in result.dropped.items()
    ]
    findings += [
        {"id": finding_id(key, "appeared"), "citekey": key, "status": "appeared", "units": []}
        for key in sorted(result.appeared or ())
    ]
    return findings


def union_payload(result: UnionResult, command: str) -> dict:
    """The same findings the report prints, as data -- an additional
    serialisation, never a second computation.

    `appeared_determinable` is carried explicitly rather than left for a
    consumer to infer from a null: "no citekey appeared from nowhere" and
    "this run could not tell" are different answers, and a caller acting
    on the payload has to be able to distinguish them.
    """
    payload = review.envelope(result.assembled, "union", command)
    payload.update(
        {
            "units_checked": [
                {"unit": entry.unit, "included": entry.included} for entry in result.checked
            ],
            "units_unchecked": [
                {"unit": entry.unit, "state": entry.state, "included": entry.included}
                for entry in result.unchecked
            ],
            "units_omitted": [entry.unit for entry in result.omitted],
            # What the assembly pulled in besides its units, and what it
            # named but could not be found. Both reported rather than
            # dropped: a run that quietly skipped an include would be
            # claiming coverage of prose it never opened.
            "includes_outside_units": result.outside_units,
            "includes_unresolved": result.unresolved,
            "citekeys_outside_units": len(result.own),
            "appeared_determinable": result.appeared is not None,
            "findings": _findings(result),
        }
    )
    return payload


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, declared once here so chitragupta/review/__main__.py
    never restates them."""
    if parser is None:
        parser = argparse.ArgumentParser(
            description="Report whether an assembled book carries every citekey its units do.",
        )
    parser.add_argument("draft", help="Path to the assembled document (e.g. book.tex)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the findings as JSON instead of as text. "
        "--write files it beside the report either way.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Also write the report to content/review/, mirroring the "
        "draft's path. Off by default: printing is the usual use.",
    )
    parser.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown "
        "report (default: md,tex,pdf). The .md is always "
        "written -- it is the report; tex/pdf are renders "
        "of it, and need pandoc/pdflatex on PATH.",
    )
    return parser


def main(argv: list[str]) -> int:
    return run(build_parser().parse_args(argv))


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments, split from main() so
    chitragupta/review/__main__.py can hand over args parsed with this
    module's own build_parser().

    Exit 1 covers both refusals for the reason the layer already gives it
    that meaning: an input this aid will not read, said once on stderr,
    rather than a traceback or a report built on a guess.
    """
    try:
        assembled = review.require_reviewable(Path(args.draft), "assembled document")
        refusal = refuse_a_unit(assembled)
        if refusal:
            print(refusal, file=sys.stderr)
            return 1
        result = compute(assembled)
    except (FileNotFoundError, config.OutsideContentDir, unit.UnitError) as exc:
        print(exc, file=sys.stderr)
        return 1

    if not (args.json or args.write):
        print(_citekey_union_render.format_report(result))
        return 0

    command = _command(assembled, args.json, args.write)
    payload = union_payload(result, command)
    print(
        json.dumps(payload, indent=2) if args.json else _citekey_union_render.format_report(result)
    )

    if args.write:
        formats = [f.strip() for f in args.formats.split(",") if f.strip()]
        body = _citekey_union_render.render_markdown(result, command)
        written = review.write(assembled, "union", body, formats)
        written["json"] = review.write_json(assembled, "union", payload)
        review.print_written(written, stream=sys.stderr if args.json else sys.stdout)
    return 0
