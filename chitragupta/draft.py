"""The drafting layer's single entry point: `python -m chitragupta.draft <verb>`.

`gate` is the hard gate every genre skill loops on; the other verbs
(dossier, retrieve, references, evidence, render, style, spec, unit,
registry, tldr, figures, diff) are listed in `VERBS`, with help text in
chitragupta/command_help.py.

One entry point, one level deep, like `corpus` and `review`: no module
beside this one has a `__main__` block, so `python -m chitragupta.dossier`
does nothing (docs/ARCHITECTURE.md states the invariant). This parses
only the verb and forwards the rest verbatim to the module's own
`main(argv)`, so flags cannot drift between two parsers. `retrieve`, not
`retrieval`, keeps verbs imperative or noun-like.

Exit codes are each module's own (0 success, 1 refusal, 2 bad usage,
`gate`'s 3 for an unreadable ledger); the one refusal said here is
`ledger.NoLedger`, exit 1.
"""

import argparse
import sys

from chitragupta import (
    citation_gate,
    dossier,
    draft_diff,
    draft_figures,
    evidence_appendix,
    ledger,
    references,
    registry,
    render_output,
    retrieval,
    spec,
    style_check,
    tldr,
    unit,
)
from chitragupta.command_help import verbs
from chitragupta.help_format import dispatcher_parser
from chitragupta.progname import prog_for

# Help strings live in command_help.py, readable without importing a layer.
VERBS = {
    verb: (module, verbs("draft")[verb])
    for verb, module in {
        "gate": citation_gate,
        "dossier": dossier,
        "retrieve": retrieval,
        "references": references,
        "evidence": evidence_appendix,
        "render": render_output,
        "style": style_check,
        "spec": spec,
        "unit": unit,
        "registry": registry,
        "tldr": tldr,
        "figures": draft_figures,
        "diff": draft_diff,
    }.items()
}


# Not the module docstring (#152); see corpus.py's DESCRIPTION.
DESCRIPTION = "The drafting layer: work on one draft -- gate it, cite it, render it."


def build_parser() -> argparse.ArgumentParser:
    rows = [(verb, text) for verb, (_, text) in VERBS.items()]
    return dispatcher_parser(prog_for("draft"), DESCRIPTION, rows, "verb")


def main(argv=None) -> int:
    """No verb prints the usage and exits 0, as `review` does for a
    missing aid."""
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.verb is None:
        parser.print_help()
        return 0
    # Every verb reads through `ledger.read_connection` (#843), which
    # refuses rather than creates; said as an `[error]` line, not a traceback.
    try:
        return VERBS[args.verb][0].main(args.rest)
    except ledger.NoLedger as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
