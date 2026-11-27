"""The generation unit: one section's contract, and the record of its
acceptance.

The unit is fixed at the **section**, not the chapter (#137), so each
unit fits a context budget and is independently regenerable.
`input_digest` covers the inputs *only* (spec slice and sources), so it
answers "does this unit need regenerating?". `accept` records digests
of inputs and prose so `status` can tell unwritten, unaccepted and
changed-since apart. `accept` runs the one citation gate rather than
adding a second; nothing here blocks a write (docs/WRITE-A-BOOK.md).
"""

import json
from pathlib import Path

from chitragupta import config, spec
from chitragupta.spec._align import chapters, section_described

# Records live beside the outline they are accepted against.
UNITS_DIRNAME = "units"


class UnitError(Exception):
    """A book with no readable outline, or a unit that outline does not hold."""


def _parsed_spec(book: Path) -> tuple[str, dict]:
    """A book's outline text and its parse, refusing anything unusable.

    Refused wholesale: a contract built from a half-parsed spec would
    hash inputs nobody approved.
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


# A unit id must stay one path component (#820): `..` ids once wrote
# records outside content/. Two roots are checked: `units/` catches `..`,
# the spec directory catches a `units/` symlinked out of the tree.
def _inside(path: Path, *roots: Path) -> Path:
    """`path`, once it is certain it lands under every one of `roots`."""
    if all(config.resolves_inside(path, root) for root in roots):
        return path
    raise UnitError(
        f"{path} resolves to {path.resolve()}, outside {roots[0]}: a unit id is one "
        "path component, not a path, and no directory above it may be a symlink out."
    )


def draft_path(book: Path, unit_id: str) -> Path:
    """Where unit `unit_id`'s prose lives: `.md`, or `.tex` if that exists.

    Checked in `dossier.find_draft`'s order; the `.md` name is returned
    when neither exists, so a caller can say where the prose should go.
    """
    for suffix in (".md", ".tex"):
        candidate = _inside(Path(book) / f"{unit_id}{suffix}", Path(book))
        if candidate.is_file():
            return candidate
    return _inside(Path(book) / f"{unit_id}.md", Path(book))


def record_path(book: Path, unit_id: str) -> Path:
    units = spec.spec_dir(book) / UNITS_DIRNAME
    return _inside(units / f"{unit_id}.json", units, spec.spec_dir(book))


def acceptance_units(book: Path) -> list[dict]:
    """What `accept` records, in outline order.

    Not `sections()`: the outline declares **structure**, acceptance
    records an **artifact** (a file the gate runs on and that is hashed).
    Since #472 a chapter described at section level is the unit; one
    described only at chapter level keeps its single section as the
    unit; a chapter with no sections is its own unit (#1137). Alignment
    only has content while the outline is finer than the file.
    Unrelated to `chitragupta/review/_units.py`'s evidence-scale sense.
    """
    _, parsed = _parsed_spec(book)
    found: list[dict] = []
    for chapter, declared in chapters(parsed):
        # A generated page (#1137) is written by nobody, so it is no unit.
        if chapter["id"] in spec.GENERATED:
            continue
        found.extend(
            [chapter] if section_described(chapter, declared) or not declared else declared
        )
    return found


def contract(book: Path, unit_id: str, sources: list[str]) -> dict:
    text, _ = _parsed_spec(book)
    units = acceptance_units(book)
    found = next((entry for entry in units if entry["id"] == unit_id), None)
    if found is None:
        raise UnitError(
            f"`{unit_id}` is not a unit of {spec.spec_path(book)}. It is accepted in: "
            + ", ".join(entry["id"] for entry in units)
        )
    return {
        "unit": unit_id,
        "kind": found["kind"],
        "title": found["title"],
        "ancestors": found["ancestors"],
        "ancestor_titles": found["ancestor_titles"],
        "brief": found["brief"],
        # Sorted and de-duplicated so the digest answers for the *set*.
        "sources": sorted(set(sources)),
        # Registry excerpts deliberately stay out: a registry grows with
        # every acceptance, so hashing it would mark every later unit
        # stale. The empty labelled slot remains (docs/WRITE-A-BOOK.md).
        "registries": [],
        # POSIX spelling: the hash must match on the Windows CI leg.
        "draft": draft_path(book, unit_id).as_posix(),
        "signed_off": _signed_off(book, text, found),
    }


def _signed_off(book: Path, text: str, found: dict) -> bool:
    """Whether the outline this unit is generated from is approved.

    Asked of the unit's **chapter**, not the book, so revising one
    chapter's brief does not block every other chapter (#465). Falls
    back to the whole-book digest when `signoff.md` has no chapter lines,
    so older books keep working without re-approval.
    """
    approved = spec.signed_off_chapters(book, text)
    if approved is None:
        return spec.recorded_digest(book) == spec.digest(text)
    return chapter_of(found) in approved


def chapter_of(found: dict) -> str:
    """The chapter whose approval covers this unit.

    A chapter's last ancestor is its **part**, which is never in the
    approved set, so "last ancestor" would fail open in one place and
    closed in another. Works on a contract too (hence its `kind`).
    """
    if found["kind"] != "chapter":
        return found["ancestors"][-1]
    # An outline entry keys its id `id`; a contract keys it `unit`.
    return found.get("id") or found["unit"]


def input_digest(built: dict) -> str:
    """A fingerprint of everything the unit is generated *from*.

    Excludes `draft` and `signed_off`: neither is an input to the prose,
    so either would make a unit look stale for no reason. Parts are
    labelled so a citekey and a registry line cannot collide.
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

    No timestamp: accepting an unchanged unit twice is byte-identical.
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

    A half-written or hand-edited record is not evidence of acceptance.
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

    Rebuilt with the recorded sources, so "stale: inputs changed" means
    the *outline* moved; changing sources is a re-accept, not drift.
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
    """Every entry in a book's outline, parts and chapters included.

    For which ids exist at all, what a cross-reference resolves
    against (#138).
    """
    _, parsed = _parsed_spec(book)
    return parsed["units"]


# Kept with no production caller (#515): `acceptance_units` and `outline`
# are defined by contrast with it, and a #472 regression test pins it.
def sections(book: Path) -> list[dict]:
    """Every `####` section the outline declares, in outline order.

    The **structural** units: what a human approved and `spec align`
    checks against.
    """
    return [entry for entry in outline(book) if entry["kind"] == "section"]


# Re-exported as `spec/` and `dossier/` do; placed last because `_cli`
# imports the names above from this module.
# pylint: disable=wrong-import-position
from chitragupta.unit._cli import main
