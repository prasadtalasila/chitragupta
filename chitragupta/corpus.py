"""The corpus layer's single entry point: `python -m chitragupta.corpus <verb>`.

Four commands over one subject -- the ledger, the parsed text beside it,
and the topics found in them:

    python -m chitragupta.corpus sync [--reparse] [--remove-stale]
        bib file -> ledger -> PDF text. Deterministic, idempotent,
        incremental; safe to run unattended or on a schedule.

    python -m chitragupta.corpus ledger [--list|--status S|--citekey K]
        read-only view of what that run recorded.

    python -m chitragupta.corpus topics
        read-only view of which papers each seed topic matched.

    python -m chitragupta.corpus discover [PHRASE]
        resolve a phrase to a topic and walk its papers and neighbours.

**One entry point, one level deep**, like `draft` and `review`
(docs/ARCHITECTURE.md states the invariant). `ledger_cli.py` has no
`__main__` block, so running it directly does nothing; `sync.py` instead
refuses out loud (#153, `sync.refuse_direct_invocation`), because its old
spelling plausibly runs unattended from a crontab.

**The verbs are imported lazily.** `sync` needs bibtexparser, while
`ledger` must stay on the bare-`python` rung (docs/LADDERS.md); a
top-level import would quietly take that away on every host without a
venv, while still passing CI. So `VERBS` holds module names.

**The write lock differs by verb, and must.** `sync` holds
`runlock.pipeline_lock()`; `ledger` takes none, so it works during a
sync. This file takes nothing.

`chitragupta/ledger.py` is a library all layers import; dispatching its
command here does not make it corpus-only (#143). Not to be confused
with `chitragupta/enrich/corpus.py`. Flags are each verb's own and
forwarded verbatim. Exit codes are each command's own: `sync` 0 clean,
1 a parse failed, 2 lock held; `ledger` 0, or 1 for an unknown citekey.
"""

import argparse
import importlib
import sys

from chitragupta.command_help import verbs
from chitragupta.help_format import dispatcher_parser
from chitragupta.progname import prog_for

# Help strings live in command_help.py, readable without importing a layer.
VERBS = {
    verb: (module, verbs("corpus")[verb])
    for verb, module in {
        "sync": "chitragupta.sync",
        "ledger": "chitragupta.ledger_cli",
        "topics": "chitragupta.seed_topics",
        "discover": "chitragupta.discover",
    }.items()
}

# What `--help` prints, deliberately *not* the module docstring (#152):
# that is design commentary and would bury the usage. Every entry point
# draws the line the same way.
DESCRIPTION = "The corpus layer: bring the ledger up to date, or read what it recorded."


def build_parser() -> argparse.ArgumentParser:
    rows = [(verb, text) for verb, (_, text) in VERBS.items()]
    return dispatcher_parser(prog_for("corpus"), DESCRIPTION, rows, "verb")


def main(argv=None) -> int:
    """No verb prints the usage and exits 0, as `draft` and `review` do.
    The import happens here so `ledger` never pays for `sync`'s
    dependencies."""
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.verb is None:
        parser.print_help()
        return 0
    return importlib.import_module(VERBS[args.verb][0]).main(args.rest)


if __name__ == "__main__":
    raise SystemExit(main())
