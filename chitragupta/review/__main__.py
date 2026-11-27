"""The review layer's single entry point: `python -m chitragupta.review <aid>`.

Eleven read-only aids over a finished draft; none is a gate, takes the
write lock, or blocks a draft. Subcommands are the keys of `review.AIDS`,
which are also the report suffixes (`survey.provenance.md`), so command and
file share one vocabulary.

One entry point, one level deep: the aid modules have no `__main__`, so
`python -m chitragupta.review.verbatim_check` would import and exit 0
doing nothing. docs/ARCHITECTURE.md states the invariant. Each aid owns its
flags (`build_parser`) and work (`run`); this file never restates a flag.

Exit codes are the aids' own: `0` on any successful run, findings or not;
`1` for a draft the layer will not read (missing, or outside `content/`);
`2` for a malformed invocation.
"""

import argparse
import sys

from chitragupta import ledger
from chitragupta.progname import prog_for
from chitragupta.review._registry import AIDS
from chitragupta.help_format import ClickParser


# What `--help` prints, deliberately not the module docstring (#152); see
# chitragupta/corpus.py's DESCRIPTION.
DESCRIPTION = "The review layer: eleven read-only aids over a finished draft. No gate."


def build_parser() -> argparse.ArgumentParser:
    parser = ClickParser(
        prog=prog_for("review"),
        description=DESCRIPTION,
    )
    sub = parser.add_subparsers(dest="aid")
    for name, (module, help_text) in AIDS.items():
        module.build_parser(sub.add_parser(name, help=help_text))
    return parser


def main(argv=None) -> int:
    """No aid prints the usage and exits 0: a request for help, not an
    error, as each aid treats a missing mode."""
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.aid is None:
        parser.print_help()
        return 0
    # Aids read the ledger read-only (#843); none, or one needing a sync,
    # stops here with the same refusal `python -m chitragupta.draft` gives.
    try:
        return AIDS[args.aid][0].run(args)
    except ledger.NoLedger as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
