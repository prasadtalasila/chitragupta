"""The review layer's single entry point: `python -m chitragupta.review <aid>`.

Nine aids, read over a finished draft -- by a person, or by a skill that
runs one on your behalf. None of them is a gate, none takes the write
lock, and none of them can block a draft:

    python -m chitragupta.review provenance <draft>
        what in each cited source supports the claim citing it.

    python -m chitragupta.review coverage <draft> --query "..."
        retrieval surfaced these sources -- did the draft cite them?

    python -m chitragupta.review verbatim overlap|scan|locate ...
        how much wording the draft shares with a cited source, with any
        parsed source, and which page a phrase is on.

    python -m chitragupta.review synthesis <draft>
        how many sources each unit of the draft rests on, at the unit
        its genre binds at.

    python -m chitragupta.review figure <draft>
        what a TikZ figure's own geometry says -- overlapping nodes,
        overlong labels, protruding content, and the edge list to confirm.

    python -m chitragupta.review uncited <draft>
        which sentences carry no citation at all. The only aid that
        reads no corpus.

    python -m chitragupta.review quotation <draft>
        is each quoted span in the dossier actually in the source it is
        attributed to? The only aid whose answer is binary.

    python -m chitragupta.review agenda <draft>
        merge the other eight aids' reports, the drafting layer's prose
        check, and the dossier's drift report into one ranked,
        deduplicated worklist. Reads what the others wrote; runs none
        of them.

    python -m chitragupta.review support <draft>
        does the cited source actually entail the claim citing it,
        scored by a real NLI entailment model.

**One entry point, one level deep**, like `python -m chitragupta.corpus sync` for the
corpus layer. The aid modules beside this one have no `__main__` block,
so `python -m chitragupta.review.verbatim_check` imports a module and exits 0
without doing anything -- the same trap `chitragupta/enrich/`'s submodules carry,
and the reason this file exists rather than three scattered commands.
docs/ARCHITECTURE.md states the invariant.

The subcommand names are not invented here. They are the keys of
`review.AIDS`, which are also the suffixes a written report is filed
under (`survey.provenance.md`, `.verbatim.md`, `.coverage.md`,
`.synthesis.md`, `.figure.md`, `.uncited.md`, `.quotation.md`,
`.agenda.md`, `.support.md`) -- so the command a reader types and the
file they get back share one vocabulary.

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

from chitragupta import review
from chitragupta.review import (
    agenda,
    citation_coverage,
    citation_provenance,
    claim_support,
    figure_layout,
    quotation,
    synthesis,
    uncited_prose,
    verbatim_check,
)
from chitragupta.progname import prog_for

# Keyed by review.AIDS, so a new aid cannot appear here without also
# appearing in the dict that owns the report suffixes.
AIDS = {
    "provenance": (citation_provenance, "what in the source supports this claim?"),
    "verbatim": (verbatim_check, "verbatim overlap with one source, or with the whole corpus"),
    "coverage": (citation_coverage, "retrieval surfaced it -- did the draft cite it?"),
    "synthesis": (synthesis, "how many sources does each unit of the draft rest on?"),
    "figure": (figure_layout, "what a TikZ figure's own geometry says about it"),
    "uncited": (uncited_prose, "which sentences of the draft carry no citation?"),
    "quotation": (quotation, "is each quoted span really in the source it cites?"),
    "agenda": (agenda, "one ranked, deduplicated worklist across every other aid"),
    "support": (claim_support, "does the cited source entail this claim?"),
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


# What `--help` prints, deliberately *not* this module's docstring (#152)
# -- see chitragupta/corpus.py's DESCRIPTION for the reasoning, which is the same
# at every entry point in this project.
DESCRIPTION = "The review layer: nine read-only aids over a finished draft. No gate."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog_for("review"),
        description=DESCRIPTION,
    )
    sub = parser.add_subparsers(dest="aid")
    for name, (module, help_text) in AIDS.items():
        module.build_parser(sub.add_parser(name, help=help_text))
    return parser


def main(argv=None) -> int:
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
