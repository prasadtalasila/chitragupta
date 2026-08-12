"""The corpus layer's single entry point: `python -m src.corpus <verb>`.

Two commands over one subject -- the ledger and the parsed text beside it:

    python -m src.corpus sync [--reparse] [--remove-stale]
        bib file -> ledger -> PDF text. Deterministic, idempotent,
        incremental; safe to run unattended or on a schedule.

    python -m src.corpus ledger [--list|--status S|--citekey K]
        read-only view of what that run recorded.

**One entry point, one level deep**, like `python -m src.draft <verb>`
for the drafting layer and `python -m src.review <aid>` for review.
Neither `sync.py` nor `ledger.py` carries a `__main__` block any more, so
`python -m src.sync` imports the module and exits 0 without doing
anything -- the same trap `src/enrich/`'s, `src/review/`'s and the
drafting layer's modules carry, and the reason this file exists rather
than two scattered commands. docs/ARCHITECTURE.md states the invariant.

That trap is a sharper one here than anywhere else it has been accepted,
and it was accepted knowingly: `python -m src.sync` is the one command
string in this project that plausibly exists *outside* this repository,
in a crontab or a systemd unit no in-repo edit reaches. Such a schedule
now succeeds while doing nothing, until its owner changes the command.
docs/CLI.md's "Upgrading from 5.1.0" section is where that is paid for.

Two things are specific to this layer.

**The verbs are imported lazily, one at a time.** `src/draft.py` imports
all five of its modules at the top of the file, which is free because all
five are stdlib-only. Here they are not: `sync` needs bibtexparser, while
reading the ledger needs sqlite3 and nothing else, which is why
docs/LADDERS.md puts `ledger` on the bare-`python`, no-venv rung and
`sync` nowhere near it. A top-level `from src import sync` would quietly
take that rung away -- and quietly is the word, since it would still work
on every host that has the venv, including CI. So `VERBS` holds module
*names*, and `main` imports the one it was actually given.

**The two verbs differ on the write lock, and must keep differing.**
`sync` holds `runlock.pipeline_lock()` for its whole run; `ledger` takes
no lock at all, so it keeps working *during* a sync -- the property the
separate lock file was built to preserve, and the one
docs/ARCHITECTURE.md leans on when explaining why the review layer takes
no lock either. A shared front door is a shared *command surface*, not a
shared lock: this file takes nothing, and each verb keeps its own
behaviour.

What this file does not settle: `src/ledger.py` is a library all four
layers import, not corpus-layer code only `sync` touches. Dispatching it
here says where its *command* belongs, not who owns the module -- #143
and docs/ARCHITECTURE.md have the argument. And this is not
`src/enrich/corpus.py`, which is the enrichment layer's ledger-backed
document source: same word, different module path, different job.

Each verb already parses its own arguments, so this file does not parse
flags at all -- restating them here would give a flag a second place to
drift out of sync with what the command does. It parses exactly one
thing, the verb, and forwards everything after it verbatim.

Exit codes are each command's own, unchanged by the dispatch: for `sync`,
`0` clean, `1` at least one parse failed, `2` another writer holds the
lock; for `ledger`, `0` on any successful read and `1` for a citekey the
ledger doesn't hold.
"""

import argparse
import importlib
import sys

VERBS = {
    "sync": ("src.sync", "bib file -> ledger -> PDF text: the deterministic corpus run"),
    "ledger": ("src.ledger", "read-only view of what that run recorded -- takes no lock"),
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m src.corpus",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "verb", choices=sorted(VERBS), nargs="?",
        help=" / ".join(f"{name} -- {help_text}" for name, (_, help_text) in VERBS.items()),
    )
    # Everything after the verb belongs to that command's own parser, not
    # this one -- REMAINDER rather than a second set of flags means a verb
    # can take `-h`/`--help` of its own and this parser never sees it.
    parser.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def main(argv=None):
    """No verb at all prints the usage and exits 0 -- the same "tell me
    how to use this" request as `--help`, not an error. The same rule
    `src/draft.py` and `src/review/__main__.py` already apply.

    The import happens here rather than at module scope so that asking
    for `ledger` never pays for `sync`'s dependencies -- see this
    module's docstring."""
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.verb is None:
        parser.print_help()
        return 0
    return importlib.import_module(VERBS[args.verb][0]).main(args.rest)


if __name__ == "__main__":
    raise SystemExit(main())
