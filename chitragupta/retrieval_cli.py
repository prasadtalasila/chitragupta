"""`evidence`, and `python -m chitragupta.draft retrieve`.

Split from `chitragupta/retrieval.py` (#441), where this was its own
"Zooming in on one document" section plus its own CLI banner. Grouped
together here for the same reason they were grouped there: `search`
answers "which documents, and roughly why"; `evidence` answers "what in
*this* paper actually bears on my query?" for a document already worth
the attention, and is a lookup rather than a mandatory stage --
docs/REJECTION.md has the full reckoning for why an earlier, mandatory
`triage` pass was rejected in favour of this shape. `search` itself, and
the window chooser `_windows` it shares with `evidence` through
`_snippet`, stay in `chitragupta/retrieval.py`: both are needed there
independent of anything below, so this module imports them rather than
the other way around. `retrieval.py` re-exports `main` from here (at the
bottom of that file, after `search`/`_windows`/`_full_text` are already
defined) so `chitragupta/draft.py`'s `retrieval.main(argv)` dispatch keeps
working unchanged.

Its own entrypoint rather than the `python -c "from chitragupta import
retrieval; [print(r.citekey, r.snippet) for r in ...]"` one-liner the
skills used to carry. Three reasons, all about the caller's context
rather than convenience: the one-liner's output shape was whatever the
author of each skill happened to write, `--log` needs somewhere to
hang, and a `--chars` flag with a documented default is a much more
obvious knob than an argument buried in a shell-quoted Python
expression.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Any

from chitragupta import config, ledger, retrieval_iterative
from chitragupta.retrieval import SearchResult, _full_text, _query_terms, _windows, search

EVIDENCE_CHARS = 600
EVIDENCE_WINDOWS = 2


def evidence(
    citekey: str, query: str, chars: int = EVIDENCE_CHARS, windows: int = EVIDENCE_WINDOWS
) -> list[str]:
    """The passages of one document that bear on `query`.

    A lookup for one document you already care about, not a stage
    anything is obliged to run: use it when a `search` snippet is not
    enough to judge a source you are minded to cite. Returns more text
    per document than a snippet, chosen for the query. Returns `[]` for a
    citekey with no parsed text: a source the corpus layer could not read
    is a real answer, not an error.

    Deliberately reads `parsed_path` rather than going through
    `chitragupta/passages.py`: this ranks the same text BM25 ranked, so what
    comes back is what the score was about. `passages.py` owns the
    quotable-paragraph/page ladder that `citation_provenance` needs to
    *attribute* a claim -- a different question, asked after drafting.
    """
    # The citekey is checked before the query, so that naming a key the
    # ledger doesn't have is reported as the caller error it is even when
    # the query happens to tokenize to nothing.
    with ledger.connection() as con:
        # row_factory set and cleared around the read, matching
        # ledger.all_items: connect() leaves rows as tuples, and
        # _full_text addresses its columns by name.
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT title, parsed_path FROM items WHERE citekey = ?", (citekey,)
        ).fetchone()
        con.row_factory = None
    if row is None:
        raise KeyError(f"{citekey} is not in the ledger")
    terms = set(_query_terms(query))
    if not terms:
        return []
    return _windows(_full_text(row), terms, width=chars, count=windows)


# ---------------------------------------------------------------------
# CLI: `python -m chitragupta.draft retrieve`
# ---------------------------------------------------------------------


def _print_results(results: list[SearchResult]) -> int:
    """One block per result. Returns the payload size in characters."""
    chars = 0
    for result in results:
        chars += len(result.snippet)
        print(f"\n{result.citekey}  (score {result.score:.1f})")
        print(f"  {result.title}")
        print(f"  {result.snippet}")
    return chars


def _build_parser() -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft retrieve",
        description="BM25 retrieval over the synced corpus. Read-only, takes no "
        "lock, and runs with the bare system python3.",
        epilog="`search` ranks the corpus and hands back a snippet to judge each "
        "candidate on. `evidence` zooms in on one document you already care "
        "about. Neither is a stage: nothing has to call evidence.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="Rank the corpus and return a snippet per candidate")
    p_search.add_argument("query")
    p_search.add_argument("--k", type=int, default=5, help="Results to return (default 5)")
    p_search.add_argument("--chars", type=int, default=500, help="Snippet size (default 500)")
    p_search.add_argument(
        "--collection",
        metavar="NAME",
        help="Only items in this Zotero collection, or one beneath it. Needs a "
        "Better BibTeX export with JabRef fields on (docs/ZOTERO.md); with "
        "any other export nothing is in any collection and this matches "
        "nothing",
    )
    p_search.add_argument(
        "--y-prev",
        metavar="TEXT",
        help="A hand-edited section's own prose (FEATURE-ROADMAP.md's E4: "
        "ITER-RETGEN with a human in the generation slot). Appended to the "
        "query for a second retrieval round, merged with the first and "
        f"capped back to --k. Bounded to {retrieval_iterative.Y_PREV_MAX_CHARS} "
        "characters explicitly; omit for an ordinary single-round search",
    )

    p_evidence = sub.add_parser(
        "evidence", help="The passages of one document that bear on the query"
    )
    p_evidence.add_argument("query")
    p_evidence.add_argument("--citekey", required=True)
    p_evidence.add_argument(
        "--chars", type=int, default=EVIDENCE_CHARS, help=f"Window size (default {EVIDENCE_CHARS})"
    )
    p_evidence.add_argument(
        "--windows",
        type=int,
        default=EVIDENCE_WINDOWS,
        help=f"Passages to return (default {EVIDENCE_WINDOWS})",
    )

    for each in (p_search, p_evidence):
        each.add_argument(
            "--log",
            metavar="DRAFT",
            help="Record this call in DRAFT's dossier (content/dossiers/...), so the "
            "cost of retrieval for this draft is measured rather than estimated",
        )
        each.add_argument(
            "--origin",
            choices=("declared", "extended", "reground"),
            help="With --log: this query came verbatim from outline.md "
            "(declared), was added because a declared section came up "
            "thin (extended), or is a --y-prev re-grounding round after a "
            "hand edit (reground). Omit for a call outline.md had no say in",
        )
    return parser


def _run_evidence(args) -> "tuple[int, int] | None":
    """The evidence subcommand: prints the passages and returns
    (results, chars), or None for a citekey it had to refuse (already
    reported to stderr)."""
    try:
        passages = evidence(args.citekey, args.query, args.chars, args.windows)
    except KeyError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return None
    if not passages:
        print(
            f"{args.citekey}: no passage matches that query "
            "(or the corpus layer has no parsed text for it)."
        )
    for passage in passages:
        print(f"\n  {passage}")
    return len(passages), sum(len(p) for p in passages)


def _run_search(args) -> tuple[int, int]:
    """The search subcommand: prints the ranking and returns
    (results, chars)."""
    if args.y_prev:
        found, truncated = retrieval_iterative.search_iterative(
            args.query, args.y_prev, k=args.k, snippet_chars=args.chars, collection=args.collection
        )
        if truncated:
            print(
                f"  [note] --y-prev was cut to {retrieval_iterative.Y_PREV_MAX_CHARS} "
                "characters before it was appended to the query."
            )
    else:
        found = search(args.query, k=args.k, snippet_chars=args.chars, collection=args.collection)
    if not found:
        print("No results.")
    chars = _print_results(found)
    if found:
        print(
            "\n  Judge each snippet yourself -- a high score means the query's "
            "words are in the document, not that it supports your claim. Run "
            "`evidence --citekey <key>` where a snippet is not enough to decide."
        )
    return len(found), chars


def _log_call(args, results: int, chars: int) -> None:
    """--log's dossier bookkeeping, reported but never fatal."""
    from chitragupta import dossier

    try:
        # The logged `k` is "how much was asked for", which is `--k`
        # for the ranking modes and `--windows` for `evidence` --
        # `evidence` has no `--k`, and logging a bare 1 there put a
        # number in the column that meant nothing.
        asked_for = args.windows if args.command == "evidence" else args.k
        # `--collection` is a `search`-only flag (`evidence` zooms into a
        # citekey already chosen, not a ranking to narrow), so `evidence`'s
        # args namespace never gets the attribute at all.
        path = dossier.log_retrieval(
            Path(args.log),
            args.command,
            args.query,
            asked_for,
            results,
            chars,
            collection=getattr(args, "collection", None),
            origin=args.origin,
        )
    except (dossier.DossierError, OSError) as exc:
        # A measurement is worth less than the retrieval it measures:
        # report and carry on rather than failing the search. OSError
        # is caught alongside DossierError because the failure this
        # has to survive is not only "that path isn't a draft" -- a
        # read-only content/, a full disk or a permissions problem
        # would otherwise let a bookkeeping write throw away results
        # the caller has already paid to compute.
        print(f"  [not logged] {exc}", file=sys.stderr)
    else:
        print(f"  Logged to {path}")


def main(argv: "list[str] | None" = None) -> int:
    args = _build_parser().parse_args(argv)

    if not config.LEDGER_PATH.exists():
        print(f"No ledger at {config.LEDGER_PATH}.", file=sys.stderr)
        print(
            "Run `python -m chitragupta.corpus sync` to build it from your bib file.",
            file=sys.stderr,
        )
        return 1

    if args.command == "evidence":
        outcome = _run_evidence(args)
        if outcome is None:
            return 1
        results, chars = outcome
    else:
        results, chars = _run_search(args)

    print(f"\n  {results} result(s), {chars:,} characters returned.")
    if args.log:
        _log_call(args, results, chars)
    return 0
