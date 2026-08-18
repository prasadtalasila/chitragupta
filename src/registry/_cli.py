"""`python -m src.draft registry`'s three commands, and the Markdown the
registries are written as.

Split from `src/registry/__init__.py` the way `src/spec/_cli.py` and
`src/unit/_cli.py` are, and named `_cli.py` for the same reason: this
package has no `__main__.py`, because `python -m src.draft registry` is
the one front door.
"""

import argparse
import sys

from src import spec
from src.unit import UnitError
from src.registry import (build, excerpt, findings, registry_dir)

_BOOK_HELP = "The book's directory under content/drafts/"

# The review layer's rule, applied to an artefact that will be found on
# disk months later with nobody around to explain it. Same words, same
# job: a file cannot rely on a reader having read the documentation.
_BANNER = ("<!-- Derived from the accepted units by a deterministic pass. "
           "Evidence for a judgement, not a verdict: nothing here blocks "
           "anything. See docs/BOOKS.md. -->")

_FILES = {
    "terms.md": ("term", "kind", "defined in", "definition"),
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
        return [(row["term"], row["kind"], row["unit"], row["definition"])
                for row in built["terms"]]
    if name == "claims.md":
        return [(row["claim"], row["unit"], " ".join(row["citekeys"]))
                for row in built["claims"]]
    return [(row["from"], row["target"], "yes" if row["resolves"] else "no")
            for row in built["xrefs"]]


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
        path.write_text(f"# {name.removesuffix('.md')}\n\n{_BANNER}\n\n"
                        f"{_coverage(built)}\n\n{_table(headers, _rows(name, built))}",
                        encoding="utf-8")
        written.append(path)
    return written


def _cmd_build(args) -> int:
    built = build(args.book)
    for path in _write(args.book, built):
        print(f"Wrote {path}.")
    print(f"  {_coverage(built)}")
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
    decides. docs/BOOKS.md carries the argument.
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
        print(f"- **{row['term']}** ({row['kind']}, in {row['unit']}) -- {row['definition']}")
    if not slice_["terms"]:
        print("- nothing yet.")
    print("\n## Ids this unit may point at\n")
    print("\n".join(f"- {anchor}" for anchor in slice_["anchors"]))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.draft registry",
        description="Terminology, claims and cross-references over a book's "
                    "accepted units. A review aid: it never blocks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="Rebuild the three registries from accepted units")
    p_build.add_argument("book", help=_BOOK_HELP)
    p_build.set_defaults(func=_cmd_build)

    p_check = sub.add_parser("check", help="What the registries disagree on (always exits 0)")
    p_check.add_argument("book", help=_BOOK_HELP)
    p_check.set_defaults(func=_cmd_check)

    p_excerpt = sub.add_parser(
        "excerpt", help="What one unit's generation should be told about the rest")
    p_excerpt.add_argument("book", help=_BOOK_HELP)
    p_excerpt.add_argument("unit", help="The section's `{#id}` from the outline")
    p_excerpt.set_defaults(func=_cmd_excerpt)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (UnitError, spec.SpecError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
