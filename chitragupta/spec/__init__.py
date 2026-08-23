"""The outline a book is generated from, and the human sign-off on it.

`python -m chitragupta.draft spec init|show|sign|status` over a book directory
under `content/drafts/`. The artefact is one Markdown file --
`content/specs/<the book's path under content/drafts/>/spec.md` -- plus
a `signoff.md` beside it recording that a human approved it.

**Planned top-down, generated bottom-up** (#136). The outline names
every part, chapter and section *before* any prose exists; a genre skill
then generates one unit at a time from the slice `show --unit` prints,
instead of inventing structure per invocation. That is what makes a
document larger than a context window tractable: the structure lives on
disk rather than in a model's memory of an earlier call.

**Why the sign-off is a separate file.** `sign` records a digest of
`spec.md`, so "is this still the outline that was approved?" is
arithmetic rather than a memory. Writing that digest *into* `spec.md`
would change the file it just measured, and no later read could ever
match -- so it goes in a sibling, and the digest covers `spec.md` alone.

**Why an id is required rather than derived from the heading.** A
generated id would change when someone rewords a heading, and every unit
already written against the old one would silently become an orphan. So
`{#some-id}` is mandatory on every part, chapter and section, and a
heading without one is a parse problem rather than something this module
guesses at. The same ids are what the cross-reference graph (#138) will
resolve against.

**`status`'s exit code is not a gate.** It answers "has a human approved
this outline yet?" -- a record of a person's decision, not a machine's
judgement of a draft's content. No draft is blocked by it; the one gate
in this project stays `python -m chitragupta.draft gate`. docs/BOOKS.md carries
that reconciliation in full.

Stdlib only, like `citation_gate` and `render_output`, so a genre skill
can read a slice under bare `python` with no venv.

This module is the parse and the paths; `_cli.py` beside it is the four
commands. That split is the one `chitragupta/dossier/` already makes, and for
the same reason: together they crossed the 250-code-line limit.
"""

import hashlib
import re
from pathlib import Path

from chitragupta import config

# Fence tracking is not re-derived here. `_prose_lines` says in its own
# docstring that it is "shared so no caller re-derives it", and a brief
# in a book about software will contain a fenced block sooner or later --
# where a `# comment` line read as a heading would refuse the whole
# outline for a unit that does not exist. Reaching for a private name
# across the two packages is the lesser evil against a second copy of
# the same three-state loop.
from chitragupta.dossier._sections import _prose_lines

SPEC_MD = "spec.md"


SIGNOFF_MD = "signoff.md"

# Heading depth -> what a heading at that depth is. Four levels and no
# more: `#` is the book, and the section (level 4) is the generation
# unit (#137), so a level below it would be a unit nothing generates.
_KINDS = {2: "part", 3: "chapter", 4: "section"}

# `#### A section title {#sec-id}`. The id group is optional in the
# *regex* and required by `_unit_problem`, deliberately: a heading
# missing its id has to be reported by name, and a regex that refuses to
# match it could only report "some line, somewhere".
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*(?:\{#([^}\s]+)\})?\s*$")

# `- spec digest: `a1b2c3d4e5f6`` in signoff.md.
_DIGEST_LINE = re.compile(r"^-\s*spec digest:\s*`?([0-9a-f]{12})`?", re.MULTILINE)


class SpecError(Exception):
    """A book path outside `content/drafts/`, or a book with no spec yet."""


def spec_dir(book: Path) -> Path:
    """Where `book`'s spec lives.

    The same path-mirroring rule as `content/dossiers/` and
    `content/review/`, read one level up: a *book* is a directory of
    drafts rather than a single file, so its whole relative path is
    carried over rather than its parent's. `content/drafts/twins/`
    gets `content/specs/twins/`.

    Raises rather than guessing for a book outside `content/drafts/`,
    for the reason `dossier.dossier_dir` does: an artefact written
    somewhere unmirrored is found by nothing later.
    """
    try:
        relative = Path(book).resolve().relative_to(config.DRAFTS_DIR.resolve())
    except ValueError as exc:
        raise SpecError(
            f"{book} is not under {config.DRAFTS_DIR}. A spec mirrors its book's "
            "path, so the book has to live where the genre skills save a draft."
        ) from exc
    target = config.SPECS_DIR / relative
    # The argument cannot get out -- `resolve()` ran on both sides above.
    # What can is the target: a directory under content/specs/ that is
    # itself a symlink out of the tree, which is the case
    # `dossier.dossier_dir` and `render_output._output_dir` each check.
    if not config.resolves_inside(target, config.SPECS_DIR):
        raise SpecError(
            f"{target} resolves to {target.resolve()}, outside "
            f"{config.SPECS_DIR.resolve()}. Remove the symlink, or point "
            "[content].dir (config.toml) at the tree you are really working in."
        )
    return target


def spec_path(book: Path) -> Path:
    """`book`'s outline file."""
    return spec_dir(book) / SPEC_MD


def signoff_path(book: Path) -> Path:
    """Where `sign` records a human's approval of `book`'s outline."""
    return spec_dir(book) / SIGNOFF_MD


def digest(text: str) -> str:
    """A short fingerprint of a spec's text.

    Twelve hex characters, the same shape and for the same reason as
    `dossier.digest`: enough to answer "is this the same document?", short
    enough to sit on one line of a Markdown file. Not that function
    itself, which fingerprints a *set* of citekeys order-independently --
    here the order of the outline is exactly what must be covered.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _headings(text: str) -> list[dict]:
    """Every heading in `text`, each carrying the lines beneath it.

    Prose before the first heading is dropped: a spec's preamble is for
    the human reading the file, and no unit is generated from it.
    """
    found: list[dict] = []
    for _, line in _prose_lines(text.splitlines()):
        match = _HEADING.match(line)
        if match:
            found.append(
                {
                    "level": len(match.group(1)),
                    "title": match.group(2),
                    "id": match.group(3),
                    "brief": [],
                }
            )
        elif found:
            found[-1]["brief"].append(line)
    return found


def _unit_problem(head: dict, seen: set[str], stack: list[dict]) -> str | None:
    """Why `head` cannot be a unit, or None if it can."""
    if head["level"] > 4:
        return (
            f"`{head['title']}` is deeper than a section. A section is the "
            "generation unit; there is nothing below it to generate."
        )
    if not head["id"]:
        return (
            f"`{head['title']}` has no `{{#id}}`. Every part, chapter and "
            "section needs one, so a reworded heading does not orphan the "
            "units written against it."
        )
    if head["id"] in seen:
        return (
            f"`{head['id']}` is used more than once. An id has to name one "
            "unit for a cross-reference to resolve."
        )
    above = stack[-1]["level"] if stack else 1
    if head["level"] > above + 1:
        kind = _KINDS[head["level"]]
        return (
            f"`{head['title']}` is a {kind} directly under a "
            f"{_KINDS.get(above, 'book')}: a {kind} needs a "
            f"{_KINDS[head['level'] - 1]} above it."
        )
    return None


def _unit(head: dict, ancestors: list[dict]) -> dict:
    return {
        "id": head["id"],
        "kind": _KINDS[head["level"]],
        "title": head["title"],
        "brief": "\n".join(head["brief"]).strip(),
        "ancestors": [entry["id"] for entry in ancestors],
        "ancestor_titles": [entry["title"] for entry in ancestors],
    }


def _missing(title: str | None, units: list[dict]) -> list[str]:
    problems = []
    if title is None:
        problems.append("no book title: the spec's first heading should be `# <title>`.")
    if not units:
        problems.append(
            "no units: an outline with no part, chapter or section names nothing to generate."
        )
    return problems


def parse(text: str) -> dict:
    """`{"title", "units", "problems"}` for a spec's text.

    Every problem is collected rather than raised on the first one: a
    human editing an outline wants the whole list, not one round trip per
    missing id. A heading that is a problem contributes no unit, so the
    units that *are* returned are always well-formed.
    """
    title = None
    units: list[dict] = []
    problems: list[str] = []
    seen: set[str] = set()
    stack: list[dict] = []
    for head in _headings(text):
        if head["level"] == 1:
            if title is None:
                title = head["title"]
            else:
                problems.append(
                    f"more than one book title: `{head['title']}` is a "
                    "second `#` heading. A spec describes one book."
                )
            continue
        problem = _unit_problem(head, seen, stack)
        if problem:
            problems.append(problem)
            continue
        stack[:] = [entry for entry in stack if entry["level"] < head["level"]]
        units.append(_unit(head, stack))
        stack.append(head)
        seen.add(head["id"])
    return {"title": title, "units": units, "problems": problems + _missing(title, units)}


def recorded_digest(book: Path) -> str | None:
    """The digest `sign` recorded for `book`, or None if none was.

    None covers both "nobody signed off" and "a signoff.md exists but
    carries no digest" -- a hand-written one, say. Both mean the same
    thing to every caller: no approval this module can check.
    """
    path = signoff_path(book)
    if not path.is_file():
        return None
    match = _DIGEST_LINE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


# Re-exported so `from chitragupta import spec` reaches the entry point by the
# name `chitragupta/draft.py` dispatches to, exactly as `chitragupta/dossier/` does. The
# position matters for the same reason it does there: `_cli` imports the
# names above from this module, so importing it any earlier would fail on
# a name this file has not defined yet.
# pylint: disable=wrong-import-position
from chitragupta.spec._cli import main
