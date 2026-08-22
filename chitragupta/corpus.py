"""The corpus layer's single entry point: `python -m chitragupta.corpus <verb>`.

Two commands over one subject -- the ledger and the parsed text beside it:

    python -m chitragupta.corpus sync [--reparse] [--remove-stale]
        bib file -> ledger -> PDF text. Deterministic, idempotent,
        incremental; safe to run unattended or on a schedule.

    python -m chitragupta.corpus ledger [--list|--status S|--citekey K]
        read-only view of what that run recorded.

**One entry point, one level deep**, like `python -m chitragupta.draft <verb>`
for the drafting layer and `python -m chitragupta.review <aid>` for review.
Neither `sync.py` nor `ledger.py` carries a command of its own any more,
which is the reason this file exists rather than two scattered ones.
docs/ARCHITECTURE.md states the invariant.

`ledger.py` carries the usual price of that: no `__main__` block, so
running it directly imports the module and exits 0 having done nothing --
the same silent trap `chitragupta/enrich/`'s, `chitragupta/review/`'s and the drafting
layer's modules carry. `sync.py` does not, and that is the one place
this layer departs from the others. Its old spelling is the one command
string in this project that plausibly runs unattended, from a crontab or
a systemd unit rather than from a terminal with someone watching, so it
refuses out loud instead of exiting 0 (#153) -- see
`sync.refuse_direct_invocation`. That refusal is not a second entry
point: it parses nothing, offers no `--help`, and runs nothing.

Two things are specific to this layer.

**The verbs are imported lazily, one at a time.** `chitragupta/draft.py` imports
all five of its modules at the top of the file, which is free because all
five are stdlib-only. Here they are not: `sync` needs bibtexparser, while
reading the ledger needs sqlite3 and nothing else, which is why
docs/LADDERS.md puts `ledger` on the bare-`python`, no-venv rung and
`sync` nowhere near it. A top-level `from chitragupta import sync` would quietly
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

What this file does not settle: `chitragupta/ledger.py` is a library all four
layers import, not corpus-layer code only `sync` touches. Dispatching it
here says where its *command* belongs, not who owns the module -- #143
and docs/ARCHITECTURE.md have the argument. And this is not
`chitragupta/enrich/corpus.py`, which is the enrichment layer's ledger-backed
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

from chitragupta.progname import prog_for

VERBS = {
    "sync": ("chitragupta.sync", "bib file -> ledger -> PDF text: the deterministic corpus run"),
    "ledger": ("chitragupta.ledger", "read-only view of what that run recorded -- takes no lock"),
    "topics": ("chitragupta.seed_topics",
               "read-only view of which papers each seed topic matched -- takes no lock"),
}

# What `--help` prints, deliberately *not* this module's docstring (#152).
# The docstring is design commentary aimed at whoever opens the file: why
# the verbs import lazily, why the two differ on the write lock, what the
# invariant is. None of that answers "how do I run this", and printing it
# buries the two lines that do under forty that don't. Every entry point
# in this project draws the line the same way -- the file keeps its prose,
# `--help` gets one sentence.
DESCRIPTION = "The corpus layer: bring the ledger up to date, or read what it recorded."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog_for("corpus"),
        description=DESCRIPTION,
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


def main(argv=None) -> int:
    """No verb at all prints the usage and exits 0 -- the same "tell me
    how to use this" request as `--help`, not an error. The same rule
    `chitragupta/draft.py` and `chitragupta/review/__main__.py` already apply.

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
