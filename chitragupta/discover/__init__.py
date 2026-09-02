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

from chitragupta import retrieval
from chitragupta.discover import _data, _overview, _render, _resolve
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
    return parser


def _emit(args, data: dict, prose: str) -> None:
    print(json_module.dumps(data, indent=2) if args.json else prose)


def _topic_view(args, label: str, via: str, graph, topic_set, terms) -> int:
    data = _render.build_topic(label, graph, topic_set, terms)
    data["resolved_via"] = via
    _emit(args, data, _render.render_topic(data))
    if args.out:
        quoted = _overview.snippets(_data.members_of(topic_set)[label], graph, label)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(_overview.build_markdown(data, quoted))
    return 0


def _search_view(args, phrase: str, note, topic_set) -> int:
    results = retrieval.search(phrase, k=args.k)
    if not results:
        labels = ", ".join(t["label"] for t in topic_set["topics"])
        print(f"No topic matched {phrase!r} and paper search returned nothing.")
        print(f"Known topics: {labels}")
        return 1
    data = _render.build_search(phrase, results, topic_set)
    if note:
        data["note"] = note
    _emit(args, data, _render.render_search(data))
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        graph = _data.load_graph()
        topic_set = _data.load_topic_set()
    except _data.MissingArtefact as missing:
        print(missing)
        return 1
    terms = _data.top_terms(topic_set)

    if args.paper:
        data = _render.build_paper(args.paper, topic_set)
        if data is None:
            print(
                f"{args.paper} is in no topic -- is the citekey right, "
                "and has the enrich pipeline run since it was synced?"
            )
            return 1
        _emit(args, data, _render.render_paper(data))
        return 0

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
    return _topic_view(args, resolution.label, resolution.via, graph, topic_set, terms)
