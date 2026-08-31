"""Hand a chapter's declared structure to whoever will draft it.

The book spec owns a book's *structure*; the dossier and the genre skills
own its *content* (#472). `spec seed` is the handover: for each chapter
the outline describes at section level, it writes that chapter's section
names into the chapter dossier's `outline.md` as bare `##` headings, and
stops. Every `brief:`, `claim:` and `queries:` line under them is left
for the person who drafts the chapter -- inventing one here would be the
book track writing content, which is the thing this split exists to
prevent.

**The write is delegated, not re-implemented.** `content/dossiers/` is
the dossier package's tree, so `dossier.init` creates the dossier and the
`outline.md` template, and only the heading lines are appended here. That
keeps the module that owns a directory the one that creates files in it,
and it inherits `init`'s own guarantee: it "must not be able to destroy
the thing it exists to protect".

**Nothing is ever rewritten.** A heading already in `outline.md` is left
exactly as it stands, whatever a human has written beneath it; only names
the file does not yet carry are appended. Re-running is therefore a no-op,
which is what makes it safe to re-run after the spec grows.

**Refuses an unsigned outline.** Seeding from a structure nobody approved
would put unsettled section names in front of an author as though they
were decided -- which is exactly what `spec sign` exists to stop.
"""

import sys
from pathlib import Path

from chitragupta.dossier import OUTLINE_MD, dossier_dir
from chitragupta.dossier._create import init as _init_dossier
from chitragupta.dossier._outline import parse as _parse_outline
from chitragupta.spec import digest, recorded_digest
from chitragupta.spec._align import chapter_draft, chapters, normalise, section_described
from chitragupta.spec._read import read_spec, report_problems


def _existing_headings(path: Path) -> set[str]:
    """What `outline.md` already names, normalised for comparison.

    Reuses the outline parser rather than re-deriving headings, so "does
    this file already have this section?" is answered the same way
    `dossier outline` answers it -- including its fence handling, which a
    fresh regex here would get wrong on a chapter about software.
    """
    if not path.is_file():
        return set()
    # `Outline.sections` is keyed by heading. A heading with no `brief:`
    # or `claim:` yet is still one of its keys -- it is additionally
    # reported as a problem, which is exactly right for a seeded outline
    # nobody has filled in, and is not this module's business.
    return set(map(normalise, _parse_outline(path.read_text(encoding="utf-8")).sections))


def _missing(declared: list[dict], path: Path) -> list[str]:
    """The declared section titles `outline.md` does not carry yet."""
    have = _existing_headings(path)
    return [entry["title"] for entry in declared if normalise(entry["title"]) not in have]


def _append(path: Path, titles: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    # A blank line before each heading, so appending to a template that
    # ends in its own comment block still produces valid Markdown rather
    # than a heading glued to the line above it.
    body = "".join(f"\n## {title}\n" for title in titles)
    path.write_text(text + body, encoding="utf-8")


def seed_chapter(book: Path, chapter: dict, declared: list[dict], genre: str, write: bool) -> dict:
    """One chapter's handover: what is missing, and what was done."""
    draft = chapter_draft(book, chapter["id"])
    path = dossier_dir(draft) / OUTLINE_MD
    missing = _missing(declared, path)
    report = {
        "id": chapter["id"],
        "title": chapter["title"],
        "added": missing,
        "created": not path.is_file(),
    }
    if write and missing:
        _init_dossier(draft, genre, outline=True)
        _append(path, missing)
    return report


def seed(book: Path, parsed: dict, genre: str, write: bool = True) -> list[dict]:
    """Seed every chapter the outline describes at section level.

    A chapter described only at chapter granularity names no structure
    worth handing over -- the retrofitted shape -- so it is skipped for
    the same reason `spec align` does not check it.
    """
    return [
        seed_chapter(book, chapter, declared, genre, write)
        for chapter, declared in chapters(parsed)
        if section_described(chapter, declared)
    ]


def _cmd_seed(args) -> int:
    text, parsed = read_spec(args.book)
    if parsed["problems"]:
        return report_problems(parsed, args.book)
    if recorded_digest(args.book) != digest(text):
        print(
            f"[error] {args.book}'s outline is not signed off, so there is nothing to "
            f"seed from. `python -m chitragupta.draft spec sign {args.book}`.",
            file=sys.stderr,
        )
        return 1
    for report in seed(args.book, parsed, args.genre, write=not args.dry_run):
        print(f"  {report['id']:<24} {report['title']}")
        if not report["added"]:
            print("    unchanged: every declared section is already named.")
            continue
        verb = "would add" if args.dry_run else "added"
        for title in report["added"]:
            print(f"    {verb}: {title}")
    return 0


def add_parser(sub, book_help: str) -> None:
    """Register `seed`, beside the handover it performs."""
    parser = sub.add_parser(
        "seed", help="Write each chapter's declared sections into its dossier outline"
    )
    parser.add_argument("book", help=book_help)
    parser.add_argument("--genre", required=True, help="The genre for any dossier this creates")
    parser.add_argument(
        "--dry-run", action="store_true", help="Say what it would write, and write nothing"
    )
    parser.set_defaults(func=_cmd_seed)
