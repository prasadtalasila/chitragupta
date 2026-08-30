"""The generation unit: one section's contract, and the record of its
acceptance.

`python -m chitragupta.draft unit contract|accept|status` over a book whose
outline `chitragupta/spec/` already holds. The unit of generation is fixed at the
**section**, not the chapter (#137): small enough that the spec slice,
the grounding sources and the genre instructions fit in a context budget
with room to spare, which is what makes a unit independently
regenerable -- and independent regeneration is what makes "regenerate one
section fifty times while 200 pages sit untouched" cheap.

**The contract is explicit and hashed.** Inputs -- the spec slice and the
sources retrieved for this unit -- go in; a draft and its citations come
out. The registry excerpts a unit is also generated with
(`python -m chitragupta.draft registry excerpt`) deliberately stay out of the
digest; the comment on `registries` below says why. `input_digest`
covers the inputs *only*: a digest that moved when the prose moved could
never answer the question it exists for, which is "does this unit need
regenerating?". That is the same incremental discipline `chitragupta/ledger.py`
and the enrichment caches already follow, one level up.

**Acceptance is recorded, not asserted.** `accept` writes
`content/specs/<book>/units/<unit-id>.json` -- the input digest it was
generated against, the sources, what it cites, and a digest of the prose
itself. `status` re-derives all three, so it can tell "never written"
from "written but nobody accepted it" from "accepted, and one of them has
changed since".

**`accept` invokes the one gate rather than adding a second.** A unit is
acceptable only if `python -m chitragupta.draft gate` already passes on it; this
module runs `citation_gate.run` and refuses to write a record when it
does not. Nothing here judges a draft on its own authority, and nothing
here blocks a write -- see docs/BOOKS.md.
"""

import json
from pathlib import Path

from chitragupta import spec

# Where a book's acceptance records live, beside the outline they are
# accepted against rather than in a fifth top-level directory under
# content/: everything about one book stays in one place.
UNITS_DIRNAME = "units"


class UnitError(Exception):
    """A book with no readable outline, or a unit that outline does not hold."""


def _parsed_spec(book: Path) -> tuple[str, dict]:
    """A book's outline text and its parse, refusing anything unusable.

    An outline with problems is refused wholesale rather than worked
    around: a contract built from a half-parsed spec would hash inputs
    nobody approved.
    """
    path = spec.spec_path(book)
    if not path.is_file():
        raise UnitError(
            f"No spec at {path}. Write one with `python -m chitragupta.draft spec init {book}`."
        )
    text = path.read_text(encoding="utf-8")
    parsed = spec.parse(text)
    if parsed["problems"]:
        raise UnitError(
            f"{path} does not parse: {len(parsed['problems'])} problem(s). "
            f"`python -m chitragupta.draft spec show {book}` lists them."
        )
    return text, parsed


def draft_path(book: Path, unit_id: str) -> Path:
    """Where unit `unit_id`'s prose lives.

    `<unit-id>.md` under the book's own directory, unless a `.tex` is
    there instead -- the two suffixes the genre skills emit, checked in
    the order `dossier.find_draft` already checks them. The `.md` name is
    returned when neither exists, so a caller can say where the prose it
    is missing should go.
    """
    for suffix in (".md", ".tex"):
        candidate = Path(book) / f"{unit_id}{suffix}"
        if candidate.is_file():
            return candidate
    return Path(book) / f"{unit_id}.md"


def record_path(book: Path, unit_id: str) -> Path:
    """Where `accept` records that this unit was accepted."""
    return spec.spec_dir(book) / UNITS_DIRNAME / f"{unit_id}.json"


def contract(book: Path, unit_id: str, sources: list[str]) -> dict:
    """The inputs one unit is generated from, and what it must produce."""
    text, parsed = _parsed_spec(book)
    found = next((entry for entry in parsed["units"] if entry["id"] == unit_id), None)
    if found is None:
        raise UnitError(
            f"no unit `{unit_id}` in {spec.spec_path(book)}. It holds: "
            + ", ".join(entry["id"] for entry in parsed["units"])
        )
    if found["kind"] != "section":
        raise UnitError(
            f"`{unit_id}` is a {found['kind']}, not a section. The section is the "
            f"generation unit; a {found['kind']} names no prose of its own."
        )
    return {
        "unit": unit_id,
        "title": found["title"],
        "ancestors": found["ancestors"],
        "ancestor_titles": found["ancestor_titles"],
        "brief": found["brief"],
        # Sorted and de-duplicated here rather than at every call site, so
        # the digest below answers for the *set* of sources a unit was
        # grounded in and not for the order somebody happened to list them.
        "sources": sorted(set(sources)),
        # Registry excerpts are supplied at generation time by
        # `python -m chitragupta.draft registry excerpt`, and deliberately do not
        # arrive here: a registry grows with every acceptance, so hashing
        # it into this digest would mark every later unit stale each time
        # an earlier one was accepted -- destroying the cheap-regeneration
        # property this contract exists for. It stays in the digest's
        # shape (empty, labelled) so a caller that does want to pin an
        # excerpt has somewhere to put it. docs/BOOKS.md has the argument.
        "registries": [],
        # POSIX spelling, not the host's: this string is hashed into a
        # record that has to read the same on the Windows CI leg as on
        # Linux.
        "draft": draft_path(book, unit_id).as_posix(),
        "signed_off": _signed_off(book, text, found["ancestors"]),
    }


def _signed_off(book: Path, text: str, ancestors: list[str]) -> bool:
    """Whether the outline this unit is generated from is approved.

    Asked of the unit's own **chapter**, not of the book. A whole-book
    answer meant that revising one chapter's brief flipped this False for
    every unit in every chapter, so `unit accept` refused across a
    fifteen-chapter book while one chapter sat half-revised (#465). A
    chapter nobody edited has not moved, and its units stay acceptable.

    Falls back to the whole-book digest when `signoff.md` carries no
    chapter lines -- every book signed before they existed. That is the
    old behaviour exactly, which is the point: those books keep working
    and nothing re-approves them on their author's behalf.
    """
    approved = spec.signed_off_chapters(book, text)
    if approved is None:
        return spec.recorded_digest(book) == spec.digest(text)
    # A section's immediate parent is a chapter -- `_unit_problem` refuses
    # any outline where it is not -- so the last ancestor is the chapter.
    return bool(ancestors) and ancestors[-1] in approved


def input_digest(built: dict) -> str:
    """A fingerprint of everything the unit is generated *from*.

    Deliberately not the whole contract. `draft` is where the output
    goes, and `signed_off` is a human's approval of the outline -- neither
    is an input to the prose, and folding either in would make a unit look
    stale for a reason that changes nothing about what should be written.

    Each part is labelled rather than concatenated bare, so a source
    citekey and a registry line cannot collide into the same text.
    """
    parts = [
        f"unit: {built['unit']}",
        f"in: {' > '.join(built['ancestors'])}",
        f"title: {built['title']}",
        "brief:",
        built["brief"],
        "sources:",
        *built["sources"],
        "registries:",
        *built["registries"],
    ]
    return spec.digest("\n".join(parts))


def record_text(built: dict, draft_text: str, citekeys: list[str]) -> str:
    """What `accept` writes.

    No timestamp, the same rule `spec sign` and the review layer's reports
    follow: accepting an unchanged unit twice produces byte-identical
    files, so a diff of `content/specs/` is a diff of what was accepted.
    """
    payload = {
        "unit": built["unit"],
        "input_digest": input_digest(built),
        "sources": built["sources"],
        "draft": built["draft"],
        "output_digest": spec.digest(draft_text),
        "citekeys": citekeys,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _record(book: Path, unit_id: str) -> dict | None:
    """The acceptance record for a unit, or None if there is no readable one.

    Unreadable and absent are the same answer on purpose: a half-written
    or hand-edited record is not evidence that anybody accepted anything.
    """
    path = record_path(book, unit_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def state(book: Path, unit_id: str) -> str:
    """Where one unit stands: what `status` prints and a harness branches on.

    The recorded sources are re-used to rebuild the contract, so
    "stale: inputs changed" means the *outline* moved. Changing which
    sources a unit is grounded in is done by accepting it again with the
    new ones, which is a decision rather than a drift.
    """
    path = draft_path(book, unit_id)
    if not path.is_file():
        return "unwritten"
    record = _record(book, unit_id)
    if record is None:
        return "drafted"
    if record.get("input_digest") != input_digest(
        contract(book, unit_id, record.get("sources", []))
    ):
        return "stale: inputs changed"
    if record.get("output_digest") != spec.digest(path.read_text(encoding="utf-8")):
        return "stale: draft changed since accepted"
    return "accepted"


def outline(book: Path) -> list[dict]:
    """Every entry in a book's outline -- parts and chapters included.

    `sections` is the generation unit and is what most callers want. This
    is for the one question that is about the whole outline rather than
    about what is generated: which ids exist at all, which is what a
    cross-reference to a chapter resolves against (#138).
    """
    _, parsed = _parsed_spec(book)
    return parsed["units"]


def sections(book: Path) -> list[dict]:
    """Every generation unit in a book's outline, in outline order."""
    return [entry for entry in outline(book) if entry["kind"] == "section"]


# Re-exported so `from chitragupta import unit` reaches the entry point
# `chitragupta/draft.py` dispatches to, exactly as `chitragupta/spec/` and `chitragupta/dossier/`
# do. Position is load-bearing for the same reason: `_cli` imports the
# names above from this module.
# pylint: disable=wrong-import-position
from chitragupta.unit._cli import main
