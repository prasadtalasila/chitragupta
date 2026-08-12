"""The review layer's single entry point: `python -m src.review <aid>`.

Three aids, run by hand over a finished draft. None of them is a gate,
none takes the write lock, and nothing invokes them automatically:

    python -m src.review provenance <draft>
        what in each cited source supports the claim citing it.

    python -m src.review coverage <draft> --query "..."
        retrieval surfaced these sources -- did the draft cite them?

    python -m src.review verbatim overlap|scan|locate ...
        how much wording the draft shares with a cited source, with any
        parsed source, and which page a phrase is on.

**One entry point, one level deep**, like `python -m src.corpus sync` for the
corpus layer. The aid modules beside this one have no `__main__` block,
so `python -m src.review.verbatim_check` imports a module and exits 0
without doing anything -- the same trap `src/enrich/`'s submodules carry,
and the reason this file exists rather than three scattered commands.
docs/ARCHITECTURE.md states the invariant.

The subcommand names are not invented here. They are the keys of
`review.AIDS`, which are also the suffixes a written report is filed
under (`survey.provenance.md`, `.verbatim.md`, `.coverage.md`) -- so the
command a reader types and the file they get back share one vocabulary.

Each aid declares its own flags in its own `build_parser(parser)` and
does its work in its own `run(args)`. This file only wires them
together: it never restates a flag, so there is no second place for one
to drift out of sync.

Exit codes are the aids' own, unchanged by the dispatch: `0` on every
successful run, findings or not; `1` for a draft the layer will not read
(missing, or outside `content/`); `2` for a malformed invocation.
"""

import argparse
import sys

from src import review
from src.review import citation_coverage, citation_provenance, verbatim_check

# Keyed by review.AIDS, so a fourth aid cannot appear here without also
# appearing in the dict that owns the report suffixes.
AIDS = {
    "provenance": (citation_provenance, "what in the source supports this claim?"),
    "verbatim": (verbatim_check, "verbatim overlap with one source, or with the whole corpus"),
    "coverage": (citation_coverage, "retrieval surfaced it -- did the draft cite it?"),
}

# A raise rather than an assert: `python -O` strips assertions, and this
# is the one check standing between a mistyped subcommand and a report
# filed under a name the rest of the layer cannot find. An invariant
# worth stating is worth stating in every interpreter mode.
if set(AIDS) != set(review.AIDS):
    raise RuntimeError(
        "the entry point's subcommands and review.AIDS have drifted apart: "
        f"{sorted(set(AIDS) ^ set(review.AIDS))}. AIDS owns the report suffixes, "
        "so a subcommand missing from it would write a report nothing can find."
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m src.review",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="aid")
    for name, (module, help_text) in AIDS.items():
        module.build_parser(sub.add_parser(name, help=help_text))
    return parser


def main(argv=None):
    """No aid at all prints the usage and exits 0 -- the same "tell me how
    to use this" request as `--help`, not an error. The same rule each aid
    already applies to a missing mode."""
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.aid is None:
        parser.print_help()
        return 0
    return AIDS[args.aid][0].run(args)


if __name__ == "__main__":
    raise SystemExit(main())
