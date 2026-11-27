"""Does the authored chapter still match the outline a human approved?

The join between the book track's *structure* and the genre skills'
*content* (#472): a chapter is one authored document and the spec's
`####` sections are headings inside it
(plans/472-book-spec-drives-chapter-outlines.md).

**Scoped to chapters the spec describes at section level**: a
retrofitted book declares one section per chapter over dozens of
authored headings, and reporting each (~225 findings on the measured
book) would get the check turned off. Refuses nothing about content;
whether a misalignment withholds acceptance is `unit accept`'s question.
"""

import difflib
import json
import re
from pathlib import Path

from chitragupta import config
from chitragupta.dossier._sections import sections as _draft_sections
from chitragupta.spec import GENERATED, SpecError, spec_path
from chitragupta.spec._read import read_spec, report_problems

# A leading `3.1` is numbering, not structure: genre skills number
# headings and the outline does not.
_NUMBERING = re.compile(r"^\d+(?:\.\d+)*\.?\s+")

# Below this, two headings are different sections. Unmeasured and loose
# on purpose: a false rename is the cheaper error.
_RENAME_RATIO = 0.6

# Spec sections map to level 2 (level 1 is the chapter title, level 3 is
# below the spec, #472). `_TEX_LEVELS` puts `\section` at 2 as well.
SECTION_LEVEL = 2


def normalise(title: str) -> str:
    return " ".join(_NUMBERING.sub("", title).split()).casefold().rstrip(".")


def chapter_draft(book: Path, chapter_id: str) -> Path:
    """Where a chapter's prose lives -- `<book>/<chapter-id>.md`.

    `unit.draft_path`'s suffix order; the `.md` name when neither exists.
    Every candidate is confined to the book here (#875), not trusted to
    one id source's guard, which also catches a chapter file symlinked
    out of the book. Raises `SpecError` naming the path.
    """
    for suffix in (".md", ".tex"):
        candidate = _inside_book(Path(book) / f"{chapter_id}{suffix}", book)
        if candidate.is_file():
            return candidate
    return _inside_book(Path(book) / f"{chapter_id}.md", book)


def _inside_book(path: Path, book: Path) -> Path:
    """`path`, once it is certain it lands under `book`.

    Unresolvable paths (NUL byte, rejected name, symlink loop) are
    refused too, rather than raising a traceback that names nothing.
    """
    try:
        if config.resolves_inside(path, book):
            return path
    except (OSError, ValueError):
        pass
    raise SpecError(
        f"{path} does not resolve inside {book}: a chapter id is one path "
        "component, not a path, and a chapter file may not be a symlink out of "
        "its book or a symlink loop."
    )


def chapters(parsed: dict) -> list[tuple[dict, list[dict]]]:
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

    Two or more sections do; exactly one carrying the chapter's own title
    is the retrofitted shape and says nothing.
    """
    if len(declared) >= 2:
        return True
    return len(declared) == 1 and normalise(declared[0]["title"]) != normalise(chapter["title"])


def _pair_renames(missing: list[str], extra: list[str]) -> list[tuple[str, str]]:
    """Reworded headings, removed from `missing` and `extra` in place:
    one "renamed" finding, not a deletion plus an addition."""
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
    # A generated page (#1137) has no draft, so there is nothing to align.
    reports = [
        align_chapter(book, chapter, declared)
        for chapter, declared in chapters(parsed)
        if chapter["id"] not in GENERATED
    ]
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
    parser = sub.add_parser("align", help="Whether each authored chapter still matches the outline")
    parser.add_argument("book", help=book_help)
    parser.add_argument("--json", action="store_true", help="Machine-readable, for a skill to read")
    parser.set_defaults(func=_cmd_align)
