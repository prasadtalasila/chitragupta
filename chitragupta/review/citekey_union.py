"""The citekey union invariant: the citekeys out must be the citekeys in.

Each accepted unit recorded its citekeys under `content/specs/<book>/units/`,
so the union of the inputs' citekeys must equal the union in the assembled
`book.tex`: set arithmetic, no model, no threshold (docs/RAG.md on silent drops).

`book.tex` only `\\input`s its units, so its own text has no citekeys;
`_citekey_union_includes` resolves the includes. **Dropped** is an accepted
unit the assembly never includes; **appeared** is a citekey in an included
non-unit file, withheld while any unit is unchecked. A unit whose record is
not `accepted` (stale records describe text that no longer exists) is named,
never compared against. A review aid, never a gate, no write lock.

Usage:
    python -m chitragupta.review union content/rendered/<book>/book.tex
    python -m chitragupta.review union content/rendered/<book>/book.tex --write
"""

import argparse
import json
import shlex
import sys
from pathlib import Path

from chitragupta import citation_gate, config, review, spec, unit
from chitragupta.review import _emit
from chitragupta.review import _book_paths, _citekey_union_includes, _citekey_union_render
from chitragupta.review._citekey_union_result import UnionResult, UnitInput
from chitragupta.help_format import ClickParser


def _recorded_citekeys(book: Path, unit_id: str) -> list[str]:
    """The citekeys `unit accept` recorded for `unit_id`.

    No error handling: only called once `unit.state` said `accepted`,
    which means the record parsed and its digests matched.
    """
    record = json.loads(unit.record_path(book, unit_id).read_text(encoding="utf-8"))
    return list(record["citekeys"])


def _citekeys(text: str, name: str | Path) -> set[str]:
    """Every citekey in `text`, by `unit accept`'s extractor, so both sides
    of the subtraction are the same set."""
    return {key for _, key in citation_gate.extract_citekeys_for(name, text)}


def compute(assembled: Path) -> UnionResult:
    """The invariant over `assembled` and the book it was composed from.

    Raises `unit.UnitError` or `spec.SpecError` for a path in no book or with
    an unparsable outline: inventing an expected set is the failure this
    catches. `_book_paths` maps the assembly to the records' directory.
    """
    assembled = Path(assembled)
    book = _book_paths.drafts_dir_for(assembled)
    units = unit.acceptance_units(book)
    text = assembled.read_text(encoding="utf-8")
    included, others, unread = _citekey_union_includes.split(
        assembled.parent, text, {entry["id"] for entry in units}
    )

    result = UnionResult(
        assembled=assembled,
        # Never a unit's citekeys: that would answer with its own input.
        own=_citekeys(text, assembled).union(*(_citekeys(body, name) for name, body in others)),
        outside_units=[name for name, _ in others],
        unresolved=unread,
    )
    for entry in units:
        unit_id = entry["id"]
        state = unit.state(book, unit_id)
        # Without a usable record there are no citekeys to call lost, so a
        # non-accepted unit is unchecked, never dropped.
        if state == "accepted":
            result.checked.append(
                UnitInput(unit_id, state, unit_id in included, _recorded_citekeys(book, unit_id))
            )
        else:
            result.unchecked.append(UnitInput(unit_id, state, unit_id in included))
    return result


def refuse_a_unit(assembled: Path) -> str | None:
    """Why `assembled` is one of the book's own units, if it is.

    Pointed at a unit, this aid would call every other unit's citekeys
    dropped. Checked by id, so it holds for both suffixes.
    """
    book = _book_paths.drafts_dir_for(Path(assembled))
    if Path(assembled).stem in {entry["id"] for entry in unit.acceptance_units(book)}:
        return (
            f"{assembled} is unit `{Path(assembled).stem}` of {book}, not an assembly of "
            "its units. This aid compares a composed book against the units it was "
            "composed from; pointed at one unit it would report every other unit's "
            "citekeys as lost. Name the assembled document instead."
        )
    return None


def _command(assembled: Path, as_json: bool, write: bool) -> str:
    parts = ["python", "-m", "chitragupta.review", "union", str(assembled)]
    if as_json:
        parts += ["--json"]
    if write:
        parts += ["--write"]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    """This aid's flags, declared once for chitragupta/review/__main__.py."""
    if parser is None:
        parser = ClickParser(
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
    _emit.add_formats(parser)
    return parser


def main(argv: list[str]) -> int:
    return run(build_parser().parse_args(argv))


def _read(draft: str) -> tuple[Path, UnionResult] | None:
    """The assembly and its result, or None once a refusal is on stderr.

    `spec.SpecError` is a sibling of `unit.UnitError`, not a subclass, so
    both are caught (a path in no book was a traceback).
    """
    try:
        assembled = review.require_reviewable(Path(draft), "assembled document")
        refusal = refuse_a_unit(assembled)
        if refusal:
            print(refusal, file=sys.stderr)
            return None
        return assembled, compute(assembled)
    except (FileNotFoundError, config.OutsideContentDir, spec.SpecError, unit.UnitError) as exc:
        print(exc, file=sys.stderr)
        return None


def run(args: argparse.Namespace) -> int:
    """Dispatch already-parsed arguments (for __main__). Exit 1 is a
    refusal (see `_read`)."""
    read = _read(args.draft)
    if read is None:
        return 1
    assembled, result = read

    return _emit.emit(
        assembled,
        "union",
        args,
        text=lambda: _citekey_union_render.format_report(result),
        command=lambda: _command(assembled, args.json, args.write),
        payload=lambda command: _citekey_union_render.union_payload(result, command),
        markdown=lambda command: _citekey_union_render.render_markdown(result, command),
    )
