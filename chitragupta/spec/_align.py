"""Does the authored chapter still match the outline a human approved?

The book track owns a book's *structure*; the dossier track and the genre
skills own its *content* (#472). This module is the join: it compares the
sections a signed `spec.md` declares for a chapter against the headings
that chapter's author actually wrote.

**A chapter is one authored document**, and the spec's `####` sections are
the headings inside it -- which is what makes this check mean anything.
Under one file per section every file *is* a section by construction, so
nothing could ever drift. See plans/472-book-spec-drives-chapter-outlines.md.

**Scoped to chapters the spec describes at section level**, and that
scoping is the whole design. A book retrofitted from prose written before
this track declares one section per chapter, carrying the chapter's own
title, while its author wrote about forty headings underneath -- measured
on `digital-twins-for-software-engineers`, 4 declared sections against 161
authored headings across the first four chapters. Reporting each of those
as an undeclared section would put ~225 findings on a book that is not
wrong, only described at chapter granularity, and a check like that is the
first thing anyone turns off. So a chapter is compared only when its spec
says something a draft could contradict.

Reads and refuses nothing. Whether a misalignment withholds acceptance is
`unit accept`'s question, not this module's.
"""

import difflib
import json
import re
from pathlib import Path

from chitragupta.dossier._sections import sections as _draft_sections
from chitragupta.spec import spec_path
from chitragupta.spec._read import read_spec, report_problems

# `3.`, `3.1`, `3.1.2 ` at the start of a heading. A genre skill numbers
# what it writes and the outline does not, so `3.1 The model half` and
# `The model half` are the same section -- a numbering scheme is not a
# structural change and must not read as one.
_NUMBERING = re.compile(r"^\d+(?:\.\d+)*\.?\s+")

# Below this, two headings are different sections rather than one
# reworded. Unmeasured, and deliberately loose: a false rename merges two
# findings a human then separates, while a false pair of findings hides
# that an edit was a rewording. The cheaper error is the rename.
_RENAME_RATIO = 0.6

# The heading level a spec section maps to. A chapter document's level 1
# is its own title and level 3 is detail below what the spec describes --
# `spec.md` stops at the sections of a chapter (#472). `_TEX_LEVELS` puts
# `\section` at 2 as well, so `.tex` chapters need no separate path.
SECTION_LEVEL = 2


def normalise(title: str) -> str:
    """A heading reduced to what makes it the same section or not."""
    return " ".join(_NUMBERING.sub("", title).split()).casefold().rstrip(".")


def chapter_draft(book: Path, chapter_id: str) -> Path:
    """Where a chapter's prose lives -- `<book>/<chapter-id>.md`.

    The two suffixes the genre skills emit, checked in the order
    `unit.draft_path` already checks them, and the `.md` name returned
    when neither exists so a caller can say what is missing. No search and
    no fallback to a section's own filename: a retrofitted chapter is
    never section-described, so nothing here ever has to guess at the
    legacy naming.
    """
    for suffix in (".md", ".tex"):
        candidate = Path(book) / f"{chapter_id}{suffix}"
        if candidate.is_file():
            return candidate
    return Path(book) / f"{chapter_id}.md"


def chapters(parsed: dict) -> list[tuple[dict, list[dict]]]:
    """Each chapter in a parsed spec, with the sections declared under it."""
    found: list[tuple[dict, list[dict]]] = []
    for unit in parsed["units"]:
        if unit["kind"] == "chapter":
            found.append((unit, []))
        elif unit["kind"] == "section" and found:
            found[-1][1].append(unit)
    return found


def section_described(chapter: dict, declared: list[dict]) -> bool:
    """Whether the spec says anything about this chapter a draft could
    contradict.

    Two or more sections is a description. Exactly one *carrying the
    chapter's own title* is the retrofitted shape -- it names no structure
    beyond "this chapter exists", so there is nothing for a heading to
    disagree with.
    """
    if len(declared) >= 2:
        return True
    return len(declared) == 1 and normalise(declared[0]["title"]) != normalise(chapter["title"])


def _pair_renames(missing: list[str], extra: list[str]) -> list[tuple[str, str]]:
    """Reworded headings, removed from `missing` and `extra` in place.

    One finding rather than two: "you renamed this" is what happened, and
    reporting a deletion plus an addition would leave the reader to work
    that out themselves.
    """
    renamed: list[tuple[str, str]] = []
    for declared in list(missing):
        close = difflib.get_close_matches(
            normalise(declared), [normalise(e) for e in extra], n=1, cutoff=_RENAME_RATIO
        )
        if not close:
            continue
        authored = next(e for e in extra if normalise(e) == close[0])
        renamed.append((declared, authored))
        missing.remove(declared)
        extra.remove(authored)
    return renamed


def _compare(declared: list[str], authored: list[str]) -> dict:
    """The four ways an authored chapter can disagree with its outline."""
    shared = {normalise(t) for t in declared} & {normalise(t) for t in authored}
    missing = [t for t in declared if normalise(t) not in shared]
    extra = [t for t in authored if normalise(t) not in shared]
    renamed = _pair_renames(missing, extra)
    in_order = [normalise(t) for t in authored if normalise(t) in shared] == [
        normalise(t) for t in declared if normalise(t) in shared
    ]
    return {
        "not_authored": missing,
        "not_declared": extra,
        "renamed": [list(pair) for pair in renamed],
        "out_of_order": not in_order,
    }


def _clean(chapter: dict, **extra) -> dict:
    return {"id": chapter["id"], "title": chapter["title"], **extra}


def align_chapter(book: Path, chapter: dict, declared: list[dict]) -> dict:
    """One chapter's alignment report."""
    if not section_described(chapter, declared):
        return _clean(chapter, section_described=False, findings=0)
    draft = chapter_draft(book, chapter["id"])
    if not draft.is_file():
        return _clean(
            chapter, section_described=True, written=False, draft=draft.as_posix(), findings=1
        )
    authored = [
        section.title
        for section in _draft_sections(draft.read_text(encoding="utf-8"))
        if section.level == SECTION_LEVEL
    ]
    report = _compare([entry["title"] for entry in declared], authored)
    count = len(report["not_authored"]) + len(report["not_declared"]) + len(report["renamed"])
    return _clean(
        chapter,
        section_described=True,
        written=True,
        draft=draft.as_posix(),
        findings=count + int(report["out_of_order"]),
        **report,
    )


def align(book: Path, parsed: dict) -> dict:
    """Every chapter's alignment, and whether anything disagreed."""
    reports = [align_chapter(book, chapter, declared) for chapter, declared in chapters(parsed)]
    return {"chapters": reports, "findings": sum(report["findings"] for report in reports)}


def _print_chapter(report: dict) -> None:
    print(f"  {report['id']:<24} {report['title']}")
    if not report["section_described"]:
        print("    described at chapter level; nothing to align.")
        return
    if not report.get("written"):
        print(f"    not written yet: {report['draft']}")
        return
    for title in report["not_authored"]:
        print(f"    not authored: {title}")
    for title in report["not_declared"]:
        print(f"    not declared: {title}")
    for declared, authored in report["renamed"]:
        print(f"    renamed: {declared} -> {authored}")
    if report["out_of_order"]:
        print("    out of order: the sections are all here, in a different sequence.")
    if not report["findings"]:
        print("    aligned.")


def _cmd_align(args) -> int:
    _, parsed = read_spec(args.book)
    if parsed["problems"]:
        return report_problems(parsed, args.book)
    report = align(args.book, parsed)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["findings"] else 0
    print(f"{spec_path(args.book)}: {parsed['title']}")
    for chapter in report["chapters"]:
        _print_chapter(chapter)
    return 1 if report["findings"] else 0


def add_parser(sub, book_help: str) -> None:
    """Register `align`. Kept beside the check it runs, the way
    `chitragupta/dossier/_outline.py` keeps its own command."""
    parser = sub.add_parser("align", help="Whether each authored chapter still matches the outline")
    parser.add_argument("book", help=book_help)
    parser.add_argument("--json", action="store_true", help="Machine-readable, for a skill to read")
    parser.set_defaults(func=_cmd_align)
