"""The drafting layer's single entry point: `python -m src.draft <verb>`.

Eight commands, run by hand or by a genre skill over one draft:

    python -m src.draft gate <file> [<file> ...]
        verify every citekey in a draft against the ledger -- this
        layer's only exit, the hard gate every genre skill loops on.

    python -m src.draft dossier <command> ...
        the working state behind a draft: create it, inspect it,
        back it up, restore it.

    python -m src.draft retrieve search|evidence ...
        BM25 retrieval over the synced corpus.

    python -m src.draft references <file.md> [--heading TEXT]
        an IEEE reference list built from exactly the citekeys a
        Markdown draft cites.

    python -m src.draft render <file> --format tex|pdf|...
        the drafting layer's publish step: Pandoc/LaTeX rendering to
        tex/pdf/docx.

    python -m src.draft style <file>
        a draft's prose against docs/WRITING-STANDARDS.md -- a review
        aid, never a gate.

    python -m src.draft spec init|show|sign|status <book>
        the outline a book is generated from, and the human sign-off on
        it -- the book-scale track's first artefact (docs/BOOKS.md).

    python -m src.draft unit contract|accept|status <book> [<unit-id>]
        one section's generation contract -- what it is generated from,
        hashed -- and the record of its acceptance (docs/BOOKS.md).

**One entry point, one level deep**, like `python -m src.corpus sync` for the
corpus layer and `python -m src.review <aid>` for the review layer. None
of the modules beside this one carries a `__main__` block any more,
so `python -m src.dossier` (or any of the others) imports the module
and exits 0 without doing anything -- the same trap `src/enrich/`'s and
`src/review/`'s submodules carry, and the reason this file exists rather
than a scattering of separate commands. docs/ARCHITECTURE.md states the invariant.

Unlike the review layer, the verb names are not the keys of some
other dict that also owns a file-naming contract -- there was no existing
vocabulary here to inherit (the modules share little beyond
`src/config.py`), so `VERBS` is where the vocabulary is decided, once.

Most verbs are their module's own name. `retrieve` is not:
it was chosen over `retrieval` because every other verb here is already
an imperative (`gate`, `render`) or a noun standing in for one
(`dossier`, `references`), and a layer whose commands read as a mix of
the two would be harder to guess at than one that picks a form and
keeps it.

Each module already parses its own arguments -- `dossier` and `retrieval`
built their own `argparse.ArgumentParser` with their own subcommands
before this file existed, `render_output` and `references` had their own
flat parser, and `citation_gate` was deliberately never argparse at all
(it takes no options). Restating any of that here, in a shared
`build_parser`, would mean a second place for a flag to drift out of
sync with what the module actually does -- so this file does not parse
flags at all. It parses exactly one thing, the verb, and forwards
everything after it verbatim to that module's own `main(argv)`.

Exit codes are each module's own, unchanged by the dispatch: whatever `0`
(success), `1` (refusal -- outside `content/`, missing, unresolved
citekey) and `2` (malformed invocation) already meant for that command
before it had a shared front door.
"""

import argparse
import sys

from src import (citation_gate, dossier, references, render_output, retrieval, spec,
                 style_check, unit)

VERBS = {
    "gate": (citation_gate, "verify every citekey in a draft against the ledger"),
    "dossier": (dossier, "the working state behind a draft: create it, "
                         "inspect it, back it up, restore it"),
    "retrieve": (retrieval, "BM25 retrieval over the synced corpus"),
    "references": (references, "an IEEE reference list built from a draft's own cited citekeys"),
    "render": (render_output, "render a Pandoc-markdown or LaTeX draft to tex/pdf/docx"),
    "style": (style_check, "check a draft's prose against docs/WRITING-STANDARDS.md "
                           "-- a review aid, never a gate"),
    "spec": (spec, "the outline a book is generated from, and the human sign-off on it"),
    "unit": (unit, "one section's generation contract, and the record of its acceptance"),
}


# What `--help` prints, deliberately *not* this module's docstring (#152)
# -- see src/corpus.py's DESCRIPTION for the reasoning, which is the same
# at every entry point in this project.
DESCRIPTION = "The drafting layer: work on one draft -- gate it, cite it, render it."


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m src.draft",
        description=DESCRIPTION,
    )
    parser.add_argument(
        "verb", choices=sorted(VERBS), nargs="?",
        help=" / ".join(f"{name} -- {help_text}" for name, (_, help_text) in VERBS.items()),
    )
    # Everything after the verb belongs to that module's own parser, not
    # this one -- REMAINDER rather than a second set of flags means a verb
    # can take `-h`/`--help` of its own and this parser never sees it.
    parser.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    """No verb at all prints the usage and exits 0 -- the same "tell me
    how to use this" request as `--help`, not an error. The same rule
    `src/review/__main__.py` already applies to a missing aid."""
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.verb is None:
        parser.print_help()
        return 0
    return VERBS[args.verb][0].main(args.rest)


if __name__ == "__main__":
    raise SystemExit(main())
