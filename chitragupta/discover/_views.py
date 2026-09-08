"""The self-contained `discover` views: --why, --groups, --compare.

Each is its own view -- a pair or set question that cannot fall back to
paper search the way a single phrase does -- with its own refusals,
moved here from `__init__` when the third of them arrived (#715) and
the module ratchet said the dispatcher was full. `__init__` still owns
the parser and the dispatch; this module owns what each view does.
"""

import json as json_module
import sys

from chitragupta.discover import _absence, _clusters, _compare, _groups, _hops, _paths, _resolve


def emit(args, data: dict, prose: str) -> None:
    print(json_module.dumps(data, indent=2) if args.json else prose)


def _resolve_names(args, phrases, graph, topic_set, terms) -> "tuple[list, list] | None":
    """Every phrase through the same ladder every view uses; None (after
    a stderr refusal) when any name resolves nowhere."""
    labels, vias = [], []
    for phrase in phrases:
        resolution = _resolve.resolve(phrase, graph, topic_set, terms)
        if resolution.note and not args.json:
            print(f"note: {resolution.note}")
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
        # Exit 2, argparse's own code for a usage error, which is what
        # combining views is.
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
    the distance nearest the target. A count is not a phrase, so
    nothing here resolves or falls back."""
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
        # The same honest degradation the app shows by hiding the
        # slider: no stored hierarchy, no tree to cut.
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
    """The ego view's rings as text (#716). Unlike the views above this
    one rides on a resolved phrase -- it replaces the flat topic view
    the way the app's rings replace the flat canvas."""
    if args.hops == "all":
        bound = None
    elif args.hops.isdigit() and int(args.hops) >= 1:
        bound = int(args.hops)
    else:
        print("--hops takes a positive hop count, or 'all'.", file=sys.stderr)
        return 2
    # `--family` reached only --path before this, and was accepted and
    # ignored everywhere else: the rings were always walked over the
    # union, so "two hops out" meant "two hops over whichever family got
    # there first" and nothing said so. None still means both.
    families = [args.family] if args.family else None
    data = _hops.build_hops(graph, resolution.label, bound, families)
    data["resolved_via"] = resolution.via
    emit(args, data, _hops.render_hops(data))
    return 0


def clusters_view(args, graph, topic_set) -> int:
    """The disagreement grid as a view (#712), read from the stored
    partitions -- this side clusters nothing, so an artefact without
    them is refused with the stage to re-run, not silently recomputed."""
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
    stored next-hop matrices. The family flag is required, mirroring the
    app's two buttons: a single fused distance over both families is a
    number nobody can interpret, and the design refuses it."""
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
