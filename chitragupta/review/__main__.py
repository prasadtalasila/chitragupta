"""The review layer's single entry point: `python -m chitragupta.review <aid>`.

Ten aids, read over a finished draft -- by a person, or by a skill that
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

    python -m chitragupta.review union <book>/book.tex
        does the assembled book still carry every citekey its accepted
        units stand on? Set arithmetic against the acceptance records.

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
`.agenda.md`, `.support.md`, `book.union.md`) -- so the command a reader
types and the file they get back share one vocabulary.

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

from chitragupta import ledger
from chitragupta.progname import prog_for
from chitragupta.review._registry import AIDS


# What `--help` prints, deliberately *not* this module's docstring (#152)
# -- see chitragupta/corpus.py's DESCRIPTION for the reasoning, which is the same
# at every entry point in this project.
DESCRIPTION = "The review layer: ten read-only aids over a finished draft. No gate."


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
    # The aids read the ledger read-only (#843); with none to read, or one
    # needing a sync, the run stops here with the instruction -- the same
    # refusal `python -m chitragupta.draft` gives.
    try:
        return AIDS[args.aid][0].run(args)
    except ledger.NoLedger as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
