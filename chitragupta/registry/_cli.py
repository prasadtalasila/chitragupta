"""`python -m chitragupta.draft registry`'s three commands, and the Markdown the
registries are written as.

Split from `chitragupta/registry/__init__.py` the way `chitragupta/spec/_cli.py` and
`chitragupta/unit/_cli.py` are, and named `_cli.py` for the same reason: this
package has no `__main__.py`, because `python -m chitragupta.draft registry` is
the one front door.
"""

import argparse
import subprocess
import sys

from pathlib import Path

from chitragupta import spec
from chitragupta.unit import UnitError
from chitragupta.registry import _pages, _symbols, _terms, build, excerpt, findings, registry_dir
from chitragupta.render_output._errors import ConversionError, MissingBinary
from chitragupta.render_output._pandoc import markdown_to_latex

_BOOK_HELP = "The book's directory under content/drafts/"

# The review layer's rule, applied to an artefact that will be found on
# disk months later with nobody around to explain it. Same words, same
# job: a file cannot rely on a reader having read the documentation.
_BANNER = (
    "<!-- Derived from the accepted units by a deterministic pass. "
    "Evidence for a judgement, not a verdict: nothing here blocks "
    "anything. See docs/WRITE-A-BOOK.md. -->"
)

_FILES = {
    "terms.md": ("term", "defined in", "definition"),
    "symbols.md": ("symbol", "meaning", "defined in"),
    "claims.md": ("claim", "unit", "citekeys"),
    "xrefs.md": ("from", "target", "resolves"),
}


def _cell(value) -> str:
    """A table cell, with any `|` escaped the way the dossier's own row
    parser expects to find it (`_ROW_SPLIT` splits on an unescaped one)."""
    return str(value).replace("|", r"\|")


def _table(headers, rows) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _rows(name: str, built: dict) -> list[tuple]:
    if name == "terms.md":
        return [(row["term"], row["unit"], row["definition"]) for row in built["terms"]]
    if name == "symbols.md":
        return [(row["symbol"], meaning_cell(row), row["unit"]) for row in built["symbols"]]
    if name == "claims.md":
        return [(row["claim"], row["unit"], " ".join(row["citekeys"])) for row in built["claims"]]
    return [
        (row["from"], row["target"], "yes" if row["resolves"] else "no") for row in built["xrefs"]
    ]


def meaning_cell(row: dict) -> str:
    """A `## Symbols` row's meaning as its `math.md` writes it."""
    if row["kind"] == "link":
        return f"**{row['text']}**" + (f", {row['note']}" if row["note"] else "")
    if row["kind"] == "see":
        return f"see {row['text']}"
    return row["text"]


def _coverage(built: dict) -> str:
    covered = f"{len(built['accepted'])} of {len(built['accepted']) + len(built['skipped'])}"
    line = f"{covered} unit(s) accepted and read."
    if built["skipped"]:
        line += " Not read, because not accepted: " + ", ".join(built["skipped"]) + "."
    return line


def _write(book, built: dict) -> list:
    written = []
    directory = registry_dir(book)
    directory.mkdir(parents=True, exist_ok=True)
    for name, headers in _FILES.items():
        path = directory / name
        # No timestamp, the same rule the review layer's reports and the
        # sign-off record follow: rebuilding over unchanged units is
        # byte-identical, so a diff of content/specs/ is a diff of the book.
        path.write_text(
            f"# {name.removesuffix('.md')}\n\n{_BANNER}\n\n"
            f"{_coverage(built)}\n\n{_table(headers, _rows(name, built))}",
            encoding="utf-8",
        )
        written.append(path)
    return written


def _cmd_build(args) -> int:
    built = build(args.book)
    for path in _write(args.book, built):
        print(f"Wrote {path}.")
    print(f"  {_coverage(built)}")
    if args.glossary or args.notation:
        return _write_pages(built, args)
    return 0


def _write_pages(built: dict, args) -> int:
    """The Glossary and List of Symbols, or a refusal that writes neither.

    A *build* refusing, not a check blocking: `registry check` reports
    the same `[glossary]` bullets and `[notation]` rows and exits 0. A
    page built over them would silently leave terms out or print a
    symbol as code, so this stops and says which, as `render` stops on an
    unmapped `<!-- math -->` marker (SOUL.md, "Atomic, or not at all").
    """
    problems = _terms.problem_findings(built) + _symbols.blocking(built)
    if problems:
        for kind, message in problems:
            print(f"  [{kind}] {message}", file=sys.stderr)
        print(
            f"\n  {len(problems)} glossary bullet(s) or symbol row(s) cannot be printed; "
            "no page written.",
            file=sys.stderr,
        )
        return 1
    try:
        pages = _pages.render(built, markdown_to_latex)
    except MissingBinary as exc:
        print(f"[missing-binary] {exc}", file=sys.stderr)
        return 1
    except (ConversionError, OSError, subprocess.CalledProcessError) as exc:
        print(f"[conversion] pandoc could not convert the glossary: {exc}", file=sys.stderr)
        return 1
    for target, text, what in zip((args.glossary, args.notation), pages, ("glossary", "symbol")):
        if target is None:
            continue
        if text is None:
            print(f"  No {what} entries in the accepted units; {target} not written.")
            continue
        _pages.write(Path(target), text)
        print(f"Wrote {target}.")
    return 0


def _cmd_check(args) -> int:
    """Reports and exits 0, whatever it finds.

    Not an oversight and not a flag away from blocking: this is a
    machine's reading of prose -- which term was defined where, which
    sentences match, which reference resolves -- and
    docs/ARCHITECTURE.md's "Layer 4" is explicit that such a check
    "reports and never blocks, whichever layer it lives in". What #138
    calls blocking is guaranteed *invocation*: the assembly step (#139)
    must run this and surface it, and the human sign-off is what
    decides. docs/WRITE-A-BOOK.md carries the argument.
    """
    built = build(args.book)
    print("Consistency check -- evidence for a judgement, not a verdict.")
    print(f"  {_coverage(built)}")
    found = findings(built)
    if not found:
        print("  no findings.")
        return 0
    for kind, message in found:
        print(f"  [{kind}] {message}")
    print(f"\n  {len(found)} finding(s). Nothing here blocks anything.")
    return 0


def _cmd_excerpt(args) -> int:
    """What a unit's generation should be told the rest of the book settled."""
    slice_ = excerpt(args.book, args.unit)
    print(f"# What the rest of {args.book} already settled")
    print("\n## Terminology already defined elsewhere\n")
    for row in slice_["terms"]:
        print(f"- **{row['term']}** (in {row['unit']}) -- {row['definition']}")
    if not slice_["terms"]:
        print("- nothing yet.")
    print("\n## Symbols already settled elsewhere\n")
    for row in slice_["symbols"]:
        print(f"- `{row['symbol']}` (in {row['unit']}) -- {meaning_cell(row)}")
    if not slice_["symbols"]:
        print("- nothing yet.")
    print("\n## Ids this unit may point at\n")
    print("\n".join(f"- {anchor}" for anchor in slice_["anchors"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft registry",
        description="Terminology, claims and cross-references over a book's "
        "accepted units. A review aid: `check` never blocks; `build --glossary` "
        "refuses to write a page it would have to leave terms out of.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Rebuild the three registries from accepted units")
    p_build.add_argument("book", help=_BOOK_HELP)
    p_build.add_argument(
        "--glossary", metavar="PATH", help="Also write the book's Glossary as LaTeX to PATH"
    )
    p_build.add_argument(
        "--notation", metavar="PATH", help="Also write the book's List of Symbols as LaTeX to PATH"
    )
    p_build.set_defaults(func=_cmd_build)

    p_check = sub.add_parser("check", help="What the registries disagree on (always exits 0)")
    p_check.add_argument("book", help=_BOOK_HELP)
    p_check.set_defaults(func=_cmd_check)

    p_excerpt = sub.add_parser(
        "excerpt", help="What one unit's generation should be told about the rest"
    )
    p_excerpt.add_argument("book", help=_BOOK_HELP)
    p_excerpt.add_argument("unit", help="The section's `{#id}` from the outline")
    p_excerpt.set_defaults(func=_cmd_excerpt)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (UnitError, spec.SpecError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
