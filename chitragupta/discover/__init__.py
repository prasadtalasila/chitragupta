"""`python -m chitragupta.corpus discover`: read the topic artefacts.

The reader half of topic discovery (docs/TOPIC-DISCOVERY.md): resolve a
phrase to a topic that exists, show its papers with ledger detail and
each paper's other topics, list the linked topics from both edge
families, and -- behind `--out` -- write an extractive Markdown
overview. Three invocations of one verb:

    chitragupta corpus discover                     # every topic
    chitragupta corpus discover "digital twin"      # one topic
    chitragupta corpus discover --paper smith2021   # one paper's topics

This module computes no topic and no edge; `chitragupta enrich` did
that once, and `_data`'s refusals name the stage to run when an
artefact is missing. The resolution ladder lives in `_resolve`, the
views in `_render`, the overview file in `_overview`.
"""

import argparse
import json as json_module
import sys

from chitragupta import retrieval
from chitragupta.discover import _app, _data, _overview, _page, _render, _resolve, _walk
from chitragupta.progname import prog_for

DESCRIPTION = (
    "Discover topics in the synced corpus: resolve a phrase to a topic, "
    "list its papers and linked topics, or show one paper's topics."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"{prog_for('corpus')} discover", description=DESCRIPTION)
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
        "--app",
        metavar="DIR",
        help=(
            "write the topic graph as an interactive app directory "
            "(open its index.html from file://) and exit"
        ),
    )
    return parser


def _emit(args, data: dict, prose: str) -> None:
    print(json_module.dumps(data, indent=2) if args.json else prose)


def _topic_view(args, resolution, graph, topic_set, terms) -> int:
    label = resolution.label
    data = _render.build_topic(label, graph, topic_set, terms)
    data["resolved_via"] = resolution.via
    # A plural hybrid resolution gets its neighbourhood ranked by
    # topology (personalised PageRank seeded from every candidate) --
    # a singular one does not, because the linked-topics lists above
    # already answer "what is next to this one".
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
            # The view above already printed; only the file write failed,
            # and "exit 1 naming the path" beats a traceback that buries
            # the topic view the user asked for.
            #
            # On stderr unconditionally, and that is the difference from
            # review's print_written, whose stream= is conditional on
            # --json: "wrote X" is legitimate human output when the run
            # is not emitting a payload, so it belongs on stdout there.
            # A failure line is never part of the payload in either mode,
            # and under --json _emit has already written the JSON document
            # to stdout by the time this runs -- so prose on that stream
            # hands the caller a parse error about a *file write*.
            print(f"Could not write the overview to {args.out}: {failure}", file=sys.stderr)
            return 1
    return 0


def _search_view(args, phrase: str, note, topic_set) -> int:
    results = retrieval.search(phrase, k=args.k)
    if not results:
        labels = ", ".join(t["label"] for t in topic_set["topics"])
        # Stderr in both modes, by the same rule the --out and --html
        # write failures below follow: a line the caller cannot parse is
        # never part of the payload. Nothing has reached stdout on this
        # path, so a --json caller reads an empty document and a nonzero
        # exit rather than two English sentences.
        print(f"No topic matched {phrase!r} and paper search returned nothing.", file=sys.stderr)
        print(f"Known topics: {labels}", file=sys.stderr)
        return 1
    data = _render.build_search(phrase, results, topic_set)
    if note:
        data["note"] = note
    _emit(args, data, _render.render_search(data))
    return 0


def main(argv=None) -> int:
    """Parse, dispatch, and translate every MissingArtefact -- absent
    graph, absent ledger, a topic member a later sync removed -- into a
    refusal on stderr and exit 1, wherever in a view it surfaces."""
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except _data.MissingArtefact as missing:
        # One clause for every invocation, --json included, which is why
        # it cannot consult args: the refusal goes to stderr in both
        # modes so that stdout carries a payload or nothing at all.
        print(missing, file=sys.stderr)
        return 1


def _paper_view(args, topic_set) -> int:
    data = _render.build_paper(args.paper, topic_set)
    if data is None:
        print(
            f"{args.paper} is in no topic -- is the citekey right, "
            "and has the enrich pipeline run since it was synced?",
            file=sys.stderr,
        )
        return 1
    _emit(args, data, _render.render_paper(data))
    return 0


def _app_view(args) -> int:
    try:
        written = _app.write_app(args.app)
    except OSError as failure:
        # Stderr in both modes, for the reason _run's --html clause
        # gives: a failure line is never part of the payload.
        print(f"Could not write the app to {args.app}: {failure}", file=sys.stderr)
        return 1
    # One more pure renderer of the artefacts --json reads, so it
    # honours the flag exactly as --html does.
    _emit(args, {"written": written}, f"written: {written}")
    return 0


def _run(args) -> int:
    if args.app:
        return _app_view(args)

    if args.html:
        try:
            written = _page.write_page(args.html)
        except OSError as failure:
            # Stderr in both modes, unlike the success line below: a
            # failure line is never part of the payload, which is the
            # rule _topic_view's --out write already follows. Under
            # --json nothing has reached stdout yet, so the caller reads
            # an empty document and a nonzero exit rather than a
            # sentence in the stream they opened expecting one.
            print(f"Could not write the page to {args.html}: {failure}", file=sys.stderr)
            return 1
        # The page is a pure renderer of the artefacts --json reads
        # (docs/TOPIC-DISCOVERY.md), so --html is one more view and
        # honours the flag like every other one rather than ignoring it.
        _emit(args, {"written": written}, f"written: {written}")
        return 0

    graph = _data.load_graph()
    topic_set = _data.load_topic_set()
    terms = _data.top_terms(topic_set)

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
    return _topic_view(args, resolution, graph, topic_set, terms)
