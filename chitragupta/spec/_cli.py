"""`python -m chitragupta.draft spec`'s four commands and their argparse tree.

Split from `chitragupta/spec/__init__.py` for the reason `chitragupta/dossier/_cli.py`
was split from its own package: parsing an outline and printing one are
different jobs, and together they crossed the 250-code-line limit
docs/CODE-STANDARDS.md sets. Everything here reads the parse; nothing
here parses.

Deliberately named `_cli.py`, not `__main__.py`, exactly as
`chitragupta/dossier/_cli.py` is: `python -m chitragupta.draft spec` is this layer's one
front door, and a package `__main__.py` would quietly open a second --
see docs/ARCHITECTURE.md's one-entry-point-per-layer invariant.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from chitragupta.spec import (
    _KINDS,
    SpecError,
    digest,
    parse,
    recorded_digest,
    signoff_path,
    spec_path,
)

_BOOK_HELP = "The book's directory under content/drafts/ (it need not exist yet)"

# `{title}` is substituted by `str.replace`, not `str.format`: this
# template is full of `{#id}` heading attributes, and `format` would read
# every one of them as a field and raise.
_TEMPLATE = """# {title}

<!-- The outline this book is generated from. Planned top-down; generated
     bottom-up, one section at a time. Every part, chapter and section
     needs an explicit `{#id}` -- ids are what units, cross-references and
     registries resolve against, so they must survive a reworded heading.

     Approve it with `python -m chitragupta.draft spec sign <book>` once it says
     what you want written. Nothing generates prose from an unsigned
     outline. -->

- reader: who this book is for, and what they already know
- scope: what it covers, and what it deliberately leaves out

## Part I {#part-i}

### Chapter 1 {#ch-1}

#### First section {#sec-1}

What this section must establish, and what it leaves to another.
"""


def _read(book: Path) -> tuple[str, dict]:
    """A book's spec text and its parse, refusing a book that has none."""
    path = spec_path(book)
    if not path.is_file():
        raise SpecError(
            f"No spec at {path}. Write one with `python -m chitragupta.draft spec init {book}`."
        )
    text = path.read_text(encoding="utf-8")
    return text, parse(text)


def _report_problems(parsed: dict, book: Path) -> int:
    """Print every parse problem and refuse. Always returns 1, so a
    caller reads as `return _report_problems(...)`."""
    for problem in parsed["problems"]:
        print(f"[spec] {problem}", file=sys.stderr)
    print(f"{len(parsed['problems'])} problem(s) in {spec_path(book)}.", file=sys.stderr)
    return 1


def _cmd_init(args) -> int:
    path = spec_path(args.book)
    if path.exists():
        print(
            f"[error] {path} already exists. Edit it rather than starting again "
            "-- an outline someone signed off is the record of that decision.",
            file=sys.stderr,
        )
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    title = args.title or Path(args.book).name
    path.write_text(_TEMPLATE.replace("{title}", title), encoding="utf-8")
    print(
        f"Wrote {path}. Edit it, then approve it with "
        f"`python -m chitragupta.draft spec sign {args.book}`."
    )
    return 0


def _show_tree(parsed: dict) -> None:
    print(parsed["title"])
    for unit in parsed["units"]:
        print(f"{'  ' * (len(unit['ancestors']) + 1)}[{unit['id']}] {unit['title']}")


def _show_unit(book: Path, text: str, parsed: dict, unit_id: str) -> int:
    """One unit's slice: what a genre skill is handed to generate from."""
    unit = next((entry for entry in parsed["units"] if entry["id"] == unit_id), None)
    if unit is None:
        print(
            f"[error] no unit `{unit_id}` in {spec_path(book)}. It holds: "
            + ", ".join(entry["id"] for entry in parsed["units"]),
            file=sys.stderr,
        )
        return 1
    signed = "yes" if recorded_digest(book) == digest(text) else "no"
    print(f"# {unit['title']}")
    print(f"- id: {unit['id']}")
    print(f"- kind: {unit['kind']}")
    print(f"- in: {' > '.join(unit['ancestor_titles']) or parsed['title']}")
    print(f"- signed off: {signed}")
    print()
    print(unit["brief"])
    return 0


def _cmd_show(args) -> int:
    text, parsed = _read(args.book)
    if parsed["problems"]:
        return _report_problems(parsed, args.book)
    if args.unit:
        return _show_unit(args.book, text, parsed, args.unit)
    _show_tree(parsed)
    return 0


def _signoff_text(text: str, parsed: dict, by: str) -> str:
    """What `sign` writes.

    No timestamp, the same rule the review layer's reports follow: two
    sign-offs of an unchanged outline produce byte-identical files, which
    is what makes "did this change?" a diff. *When* it was approved is
    not a question any check here asks; *what* was approved is.
    """
    lines = [
        "# Sign-off",
        "",
        "<!-- Written by `python -m chitragupta.draft spec sign`. The digest covers",
        "     spec.md alone, so this file can record it without invalidating it. -->",
        "",
        f"- spec digest: `{digest(text)}`",
        f"- units: {len(parsed['units'])}",
    ]
    if by:
        lines.append(f"- signed by: {by}")
    return "\n".join(lines) + "\n"


def _cmd_sign(args) -> int:
    text, parsed = _read(args.book)
    if parsed["problems"]:
        return _report_problems(parsed, args.book)
    path = signoff_path(args.book)
    path.write_text(_signoff_text(text, parsed, args.by), encoding="utf-8")
    print(f"Signed off {len(parsed['units'])} unit(s) at digest {digest(text)}.")
    print(f"Wrote {path}.")
    return 0


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _cmd_status(args) -> int:
    text, parsed = _read(args.book)
    if parsed["problems"]:
        return _report_problems(parsed, args.book)
    counts = Counter(unit["kind"] for unit in parsed["units"])
    print(f"{spec_path(args.book)}: {parsed['title']}")
    print("  " + ", ".join(_plural(counts[kind], kind) for kind in _KINDS.values()))
    recorded = recorded_digest(args.book)
    if recorded is None:
        print("  not signed off: nobody has approved this outline yet.")
        return 1
    if recorded != digest(text):
        print(f"  changed since sign-off: approved at {recorded}, now {digest(text)}.")
        return 1
    print(f"  signed off at digest {recorded}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft spec",
        description="The outline a book is generated from, and the human "
        "sign-off on it. Stdlib only; writes only under content/specs/.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Write an outline skeleton for a book")
    p_init.add_argument("book", help=_BOOK_HELP)
    p_init.add_argument("--title", help="The book's title (default: the directory's name)")
    p_init.set_defaults(func=_cmd_init)

    p_show = sub.add_parser("show", help="The outline as a tree, or one unit's slice")
    p_show.add_argument("book", help=_BOOK_HELP)
    p_show.add_argument("--unit", help="Print this unit's slice instead of the whole tree")
    p_show.set_defaults(func=_cmd_show)

    p_sign = sub.add_parser("sign", help="Record that a human approved this outline")
    p_sign.add_argument("book", help=_BOOK_HELP)
    p_sign.add_argument("--by", default="", help="Who approved it")
    p_sign.set_defaults(func=_cmd_sign)

    p_status = sub.add_parser("status", help="What the outline holds, and whether it is signed off")
    p_status.add_argument("book", help=_BOOK_HELP)
    p_status.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except SpecError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
