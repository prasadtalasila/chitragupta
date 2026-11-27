"""Hand a chapter's declared structure to whoever will draft it.

`spec seed` appends each section-described chapter's section names to
its dossier's `outline.md` as bare `##` headings, and stops: writing
`brief:`/`claim:` lines would be the book track writing content (#472).
The write is delegated to `dossier.init`, which owns the tree and must
never destroy what it protects. Existing headings are never rewritten,
so re-running is a no-op. An unsigned outline is refused: unsettled
names must not look decided.
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

    Reuses the outline parser, including its fence handling.
    """
    if not path.is_file():
        return set()
    # An unfilled heading is still a key (and reported as a problem by
    # the parser, which is right for a seeded outline).
    return set(map(normalise, _parse_outline(path.read_text(encoding="utf-8")).sections))


def _missing(declared: list[dict], path: Path) -> list[str]:
    have = _existing_headings(path)
    return [entry["title"] for entry in declared if normalise(entry["title"]) not in have]


def _append(path: Path, titles: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if text and not text.endswith("\n"):
        text += "\n"
    # A blank line first, or a heading glues onto a trailing comment.
    body = "".join(f"\n## {title}\n" for title in titles)
    path.write_text(text + body, encoding="utf-8")


def seed_chapter(chapter: dict, declared: list[dict], draft: Path, genre: str, write: bool) -> dict:
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

    Chapter-granularity chapters are skipped, as `spec align` skips them.
    """
    described = [
        (chapter, declared)
        for chapter, declared in chapters(parsed)
        if section_described(chapter, declared)
    ]
    # Confine every path *before* writing, so a refusal cannot leave
    # earlier chapters seeded with no report.
    drafts = [chapter_draft(book, chapter["id"]) for chapter, _ in described]
    return [
        seed_chapter(chapter, declared, draft, genre, write)
        for (chapter, declared), draft in zip(described, drafts)
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
    parser = sub.add_parser(
        "seed", help="Write each chapter's declared sections into its dossier outline"
    )
    parser.add_argument("book", help=book_help)
    parser.add_argument("--genre", required=True, help="The genre for any dossier this creates")
    parser.add_argument(
        "--dry-run", action="store_true", help="Say what it would write, and write nothing"
    )
    parser.set_defaults(func=_cmd_seed)
