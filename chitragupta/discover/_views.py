"""The self-contained `discover` views: --why, --groups, --compare.

Pair or set questions that cannot fall back to paper search. `__init__`
owns the parser and dispatch; this module owns what each view does.
"""

import json as json_module
import sys

from chitragupta.discover import _absence, _clusters, _compare, _groups, _hops, _paths, _resolve


def emit(args, data: dict, prose: str) -> None:
    print(json_module.dumps(data, indent=2) if args.json else prose)


def _resolve_names(args, phrases, graph, topic_set, terms) -> "tuple[list, list] | None":
    """Every phrase through the same ladder every view uses; None (after
    a stderr refusal) when any name resolves nowhere."""
    labels, vias, noted = [], [], set()
    for phrase in phrases:
        resolution = _resolve.resolve(phrase, graph, topic_set, terms)
        # Each note part once (#1023): a failed model degrades every phrase
        # alike. By part, since `resolve` joins notes with "; ".
        parts = resolution.note.split("; ") if resolution.note else []
        fresh = [part for part in parts if part not in noted]
        noted.update(fresh)
        if fresh and not args.json:
            print(f"note: {'; '.join(fresh)}")
        if resolution.label is None:
            print(
                f"No topic matched {phrase!r} -- this view needs topics that exist.",
                file=sys.stderr,
            )
            return None
        labels.append(resolution.label)
        vias.append(resolution.via)
    return labels, vias


def own_view(args, graph, topic_set, terms) -> "int | None":
    """Dispatch to whichever self-contained view was asked for; None
    when none was, so `_run` can carry on to the phrase views."""
    if args.groups is not None:
        return groups_view(args, graph)
    if args.why:
        return why_view(args, graph, topic_set, terms)
    if args.compare:
        return compare_view(args, graph, topic_set, terms)
    if args.clusters:
        return clusters_view(args, graph, topic_set)
    if args.path:
        return path_view(args, graph, topic_set, terms)
    return None


def why_view(args, graph, topic_set, terms) -> int:
    """The absence verdict's terminal twin (#708)."""
    if args.phrase or args.paper or args.compare:
        # Exit 2, argparse's code for a usage error.
        print("--why is its own view: give it two topics and nothing else.", file=sys.stderr)
        return 2
    resolved = _resolve_names(args, args.why, graph, topic_set, terms)
    if resolved is None:
        return 1
    labels, vias = resolved
    if labels[0] == labels[1]:
        print(
            f"Both phrases resolve to the same topic ({labels[0]}) -- "
            "--why compares two different ones.",
            file=sys.stderr,
        )
        return 1
    data = _absence.explain(graph, topic_set, labels[0], labels[1])
    data["resolved_via"] = {"a": vias[0], "b": vias[1]}
    emit(args, data, _absence.render(data))
    return 0


def groups_view(args, graph) -> int:
    """The resolution slider as a view (#709): cut the stored tree at
    the distance nearest the target."""
    if args.phrase or args.paper or args.why or args.compare:
        print(
            "--groups is its own view: give it a target count and nothing else.",
            file=sys.stderr,
        )
        return 2
    if args.groups < 1:
        print("--groups needs a target of at least one group.", file=sys.stderr)
        return 2
    if not graph["hierarchy"]:
        # As the app hides the slider: no stored hierarchy, nothing to cut.
        print(
            "The artefact stores no merge hierarchy, so there is no tree to "
            "cut -- re-run `chitragupta enrich --stages topic-graph`.",
            file=sys.stderr,
        )
        return 1
    data = _groups.build_groups(graph, args.groups)
    emit(args, data, _groups.render_groups(data))
    return 0


def hops_view(args, resolution, graph) -> int:
    """The ego view's rings as text (#716), riding on a resolved phrase."""
    if args.hops == "all":
        bound = None
    elif args.hops.isdigit() and int(args.hops) >= 1:
        bound = int(args.hops)
    else:
        print("--hops takes a positive hop count, or 'all'.", file=sys.stderr)
        return 2
    # `--family` was once silently ignored here, walking the union.
    # None still means both.
    families = [args.family] if args.family else None
    data = _hops.build_hops(graph, resolution.label, bound, families)
    data["resolved_via"] = resolution.via
    emit(args, data, _hops.render_hops(data))
    return 0


def clusters_view(args, graph, topic_set) -> int:
    """The disagreement grid as a view (#712), read from the stored
    partitions; an artefact without them is refused, never recomputed."""
    if args.phrase or args.paper or args.why or args.groups is not None or args.compare:
        print(
            "--clusters is its own view: give it an --inflation at most and nothing else.",
            file=sys.stderr,
        )
        return 2
    data = _clusters.build_clusters(graph, topic_set, args.inflation)
    if data is None:
        print(
            f"The artefact stores no partition at inflation {args.inflation:g}. "
            "Stored steps run 1.2 to 4.0 by 0.1; an artefact from an older run "
            "stores none at all -- re-run `chitragupta enrich --stages topic-graph`.",
            file=sys.stderr,
        )
        return 1
    emit(args, data, _clusters.render_clusters(data))
    return 0


def path_view(args, graph, topic_set, terms) -> int:
    """One family's path between two topics (#714), walked from the
    stored next-hop matrices. The family flag is required: a fused
    distance over both families is uninterpretable."""
    if args.phrase or args.paper or args.why or args.groups is not None or args.compare:
        print(
            "--path is its own view: give it two topics, --family, and nothing else.",
            file=sys.stderr,
        )
        return 2
    if args.family is None:
        print(
            "--path needs --family overlap or --family semantic -- never one fused weight.",
            file=sys.stderr,
        )
        return 2
    resolved = _resolve_names(args, args.path, graph, topic_set, terms)
    if resolved is None:
        return 1
    labels, vias = resolved
    if labels[0] == labels[1]:
        print(
            f"Both phrases resolve to the same topic ({labels[0]}) -- "
            "--path walks between two different ones.",
            file=sys.stderr,
        )
        return 1
    result = _paths.walk_path(graph, args.family, labels[0], labels[1])
    if result is None:
        print(
            "The artefact stores no path matrices -- it predates them; "
            "re-run `chitragupta enrich --stages topic-graph`.",
            file=sys.stderr,
        )
        return 1
    result["resolved_via"] = {"a": vias[0], "b": vias[1]}
    emit(args, result, _paths.render_path(result))
    return 0


def compare_view(args, graph, topic_set, terms) -> int:
    """Set comparison across named topics (#715), capped honestly."""
    if args.phrase or args.paper or args.why or args.groups is not None:
        print(
            "--compare is its own view: give it topics and nothing else.",
            file=sys.stderr,
        )
        return 2
    if len(args.compare) > _compare.CAP:
        print(
            f"--compare reads best under {_compare.CAP + 1} topics; "
            f"{len(args.compare)} were given. Ask in smaller sets.",
            file=sys.stderr,
        )
        return 2
    resolved = _resolve_names(args, args.compare, graph, topic_set, terms)
    if resolved is None:
        return 1
    labels, vias = resolved
    distinct = list(dict.fromkeys(labels))
    if len(distinct) < 2:
        print(
            "The phrases resolve to fewer than two distinct topics -- "
            "--compare needs at least two.",
            file=sys.stderr,
        )
        return 1
    data = _compare.build_compare(distinct, graph, topic_set)
    data["resolved_via"] = dict(zip(labels, vias))
    emit(args, data, _compare.render_compare(data))
    return 0
