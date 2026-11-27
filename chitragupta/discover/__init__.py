"""`python -m chitragupta.corpus discover`: read the topic artefacts.

The reader half of topic discovery (docs/TOPIC-DISCOVERY.md): one verb,
many views (a topic, a paper's topics, groups, clusters, paths,
comparisons, hop rings, and an extractive overview behind `--out`).
It computes no topic and no edge: `chitragupta enrich` did that, and
`_data`'s refusals name the stage to run when an artefact is missing.
"""

import argparse
import sys

from chitragupta import retrieval, retrieval_added
from chitragupta.retrieval_added import SPELLING
from chitragupta.discover import (
    _data,
    _export,
    _origin,
    _overview,
    _render,
    _resolve,
    _walk,
)
from chitragupta.discover._views import emit as _emit, hops_view, own_view
from chitragupta.progname import prog_for
from chitragupta.help_format import ClickParser

DESCRIPTION = (
    "Discover topics in the synced corpus: resolve a phrase to a topic, "
    "list its papers and linked topics, show one paper's topics -- or "
    "explore the stored graph analytics: the merge-tree cut (--groups), "
    "family disagreement (--clusters), typed paths (--path), absence "
    "verdicts (--why), set comparison (--compare) and hop rings (--hops)."
)


def build_parser() -> argparse.ArgumentParser:
    parser = ClickParser(prog=f"{prog_for('corpus')} discover", description=DESCRIPTION)
    parser.add_argument(
        "phrase",
        nargs="*",
        help="a topic to look up -- a known label, a near-miss, or any free phrase",
    )
    parser.add_argument(
        "--paper",
        metavar="CITEKEY",
        help="show this paper's topics instead of resolving a phrase",
    )
    parser.add_argument(
        "--why",
        nargs=2,
        metavar=("TOPIC", "TOPIC"),
        help=(
            "why is there no overlap edge between these two topics? "
            "shared papers, the hypergeometric tail, and the gate's verdict"
        ),
    )
    parser.add_argument(
        "--groups",
        type=int,
        metavar="N",
        help=(
            "cut the stored merge tree into as close to N groups as it "
            "allows -- the app's resolution slider, as a view"
        ),
    )
    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="TOPIC",
        help=(
            "compare two or more topics: pairwise shared papers, the "
            "papers held by all, the bridges held by several, and the "
            "edges among them"
        ),
    )
    parser.add_argument(
        "--hops",
        metavar="N",
        help=(
            "with a phrase: the topic's neighbourhood as rings by hop "
            "distance (a count, or 'all' for everything reachable); "
            "add --family to measure over one family"
        ),
    )
    parser.add_argument(
        "--clusters",
        action="store_true",
        help=(
            "the stored MCL partitions of both edge families and where "
            "they disagree -- the app's disagreement grid, as a view"
        ),
    )
    parser.add_argument(
        "--inflation",
        type=float,
        default=2.0,
        help="which stored inflation --clusters reads (default: 2.0)",
    )
    parser.add_argument(
        "--path",
        nargs=2,
        metavar=("TOPIC", "TOPIC"),
        help=(
            "the strongest chain between two topics over one family "
            "(--family required), each hop with its evidence"
        ),
    )
    parser.add_argument(
        "--family",
        choices=("overlap", "semantic"),
        help=("which edge family --path walks and --hops measures over -- never one fused weight"),
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="also write the topic view as a Markdown overview file",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="results to show when falling back to paper search (default: 5)",
    )
    parser.add_argument(
        "--html",
        metavar="FILE",
        help="write the whole topic graph as one self-contained HTML page and exit",
    )
    parser.add_argument(
        "--origins",
        metavar="LIST",
        help=(
            "show only topics of these origins, comma-separated: "
            f"{', '.join(_origin.CLASSES)} (a corroborated topic -- named by hand "
            "and extracted from the corpus -- is shown by seed and by keyword too)"
        ),
    )
    parser.add_argument(
        "--app",
        metavar="DIR",
        help=(
            "write the topic graph as an interactive app directory "
            "(open its index.html from file://) and exit"
        ),
    )
    return parser


def _topic_view(args, resolution, graph, topic_set, terms) -> int:
    label = resolution.label
    data = _render.build_topic(label, graph, topic_set, terms)
    data["resolved_via"] = resolution.via
    # Only a plural hybrid resolution gets a PageRank-ranked
    # neighbourhood; a singular one already has its linked-topics lists.
    if resolution.via == "hybrid" and len(resolution.ranked) > 1:
        data["neighbourhood"] = [
            {"label": node, "score": score}
            for node, score in _walk.personalised_pagerank(graph, resolution.ranked)
        ]
    _emit(args, data, _render.render_topic(data))
    if args.out:
        quoted = _overview.snippets(_data.members_of(topic_set)[label], graph, label)
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(_overview.build_markdown(data, quoted))
        except OSError as failure:
            # The view already printed; exit 1 naming the path beats a
            # traceback. Always stderr (unlike review's print_written):
            # under --json, stdout already holds the payload, and prose
            # there would be a parse error about a file write.
            print(f"Could not write the overview to {args.out}: {failure}", file=sys.stderr)
            return 1
    return 0


def _search_view(args, phrase: str, note, topic_set) -> int:
    results = retrieval.search(phrase, k=args.k)
    # Stderr, as `retrieve` does: a hit on a word the caller never typed
    # must say so (#1232). Corrections only, no acronym expansion note.
    added = retrieval.query_terms(phrase)[1]
    retrieval_added.announce([entry for entry in added if entry.source == SPELLING])
    if not results:
        labels = ", ".join(t["label"] for t in topic_set["topics"])
        # Stderr in both modes: a --json caller gets an empty document and
        # a nonzero exit, never English in the payload.
        print(f"No topic matched {phrase!r} and paper search returned nothing.", file=sys.stderr)
        print(f"Known topics: {labels}", file=sys.stderr)
        return 1
    data = _render.build_search(phrase, results, topic_set)
    if note:
        data["note"] = note
    _emit(args, data, _render.render_search(data))
    return 0


def main(argv=None) -> int:
    """Parse, dispatch, and translate every MissingArtefact (absent graph
    or ledger, a member a later sync removed) into a refusal on stderr
    and exit 1, wherever in a view it surfaces."""
    args = build_parser().parse_args(argv)
    try:
        origins = _origin.parse(args.origins)
    except ValueError as bad:
        # Stderr, before any view runs, so --json stdout stays empty.
        print(bad, file=sys.stderr)
        return 1
    if args.path and origins != set(_origin.CLASSES):
        # Exit 2, argparse's usage code. --path walks stored next-hop
        # matrices indexed over the *whole* graph; a subset cannot be
        # answered without recomputing, and the reader recomputes nothing.
        print(
            "--path walks the stored next-hop matrices, which are indexed over the "
            "whole graph -- it does not compose with --origins.",
            file=sys.stderr,
        )
        return 2
    try:
        return _run(args, origins)
    except _data.MissingArtefact as missing:
        # Cannot consult args: stderr in every mode, so stdout carries a
        # payload or nothing.
        print(missing, file=sys.stderr)
        return 1


def _paper_view(args, topic_set) -> int:
    data = _render.build_paper(args.paper, topic_set)
    if data is None:
        # With --origins, "in no topic" is usually the filter's doing, so
        # don't send the reader off to re-run enrich.
        why = (
            f"none of its topics are of the origins you asked for ({args.origins})"
            if args.origins
            else "is the citekey right, and has the enrich pipeline run since it was synced?"
        )
        print(f"{args.paper} is in no topic -- {why}", file=sys.stderr)
        return 1
    _emit(args, data, _render.render_paper(data))
    return 0


def _run(args, origins: set) -> int:
    if args.app:
        return _export.app_view(args, origins)

    if args.html:
        return _export.html_view(args, origins)

    # Filters the artefacts, not one view, so every view agrees and a
    # filtered-out topic resolves like an unknown phrase.
    graph, topic_set = _origin.keep(_data.load_graph(), _data.load_topic_set(), origins)
    terms = _data.top_terms(topic_set)

    own = own_view(args, graph, topic_set, terms)
    if own is not None:
        return own

    if args.paper:
        return _paper_view(args, topic_set)

    phrase = " ".join(args.phrase).strip()
    if not phrase:
        data = _render.build_list(graph, topic_set, terms)
        _emit(args, data, _render.render_list(data))
        return 0

    resolution = _resolve.resolve(phrase, graph, topic_set, terms)
    if resolution.note and not args.json:
        print(f"note: {resolution.note}")
    if resolution.label is None:
        return _search_view(args, phrase, resolution.note, topic_set)
    if args.hops:
        return hops_view(args, resolution, graph)
    return _topic_view(args, resolution, graph, topic_set, terms)
