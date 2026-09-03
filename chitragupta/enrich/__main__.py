"""Orchestrates the full enrichment layer:

    Docling -> sentence-transformers/Chroma -> BERTopic -> declared
    keywords -> seed topics

The enrichment layer's single entry point, one level deep like every
other layer's: `python -m chitragupta.enrich`, as the corpus layer has
`python -m chitragupta.corpus sync`. The stage modules beside this one have no
`__main__` block, so `python -m chitragupta.enrich.docling_parse` imports a
module and exits 0 without doing anything -- `--stages` is the only way
to run them, and docs/ARCHITECTURE.md states the invariant.

One entry point for both the host and the Docker target
(docker/Dockerfile) -- the two don't need separate implementations. Each stage probes its own
prerequisites (docling importable, the upstream artefact written) and
reports a real per-stage status instead of assuming the target implies
availability. On a host without the enrich extra, some stages report
skipped, and one that parsed only part of the corpus reports partial --
both are correct, honest results, not a bug in this script. No stage
here shells out to a binary; the render path that once did was moved out
of this layer, as the paragraph below says.

Needs the venv populated by `poetry install --with enrich` (see
pyproject.toml, and .venv-full/ on the host this was developed on). The
corpus and drafting layers (python -m chitragupta.corpus sync, python -m chitragupta.draft gate) do
not depend on any of this and are unaffected either way.

Every stage here writes a **corpus** artefact, which is why this layer
takes the same write lock as `python -m chitragupta.corpus sync`. A per-draft
stage would not, and there deliberately isn't one: a `provenance`
(review-layer report) or `render` (drafting-layer publish) stage would be
a three-line wrapper around `python -m chitragupta.review provenance <draft>` or
`python -m chitragupta.draft render <draft> --format pdf`, both of which need no
venv at all and neither of which should be made to wait on a running
sync.

That is also what keeps the layer diagram acyclic: the enrichment layer
reads corpus artefacts and writes corpus artefacts, and does not import
the drafting or review layers.

Usage:
    python -m chitragupta.enrich --target host
    python -m chitragupta.enrich --stages embed,bertopic
    python -m chitragupta.enrich --for-draft content/drafts/chapter.md
"""

import argparse
import json
import logging

from chitragupta.enrich import corpus
from chitragupta.enrich._scope import SCOPE_REFUSED, resolve_scope, scope_corpus

# Re-exported, not used here: tests/test_enrich_script.py reaches these
# as enrich_script.CORPUS_STAGES/.EXIT_BAD_SCOPE/.draft_citekeys, the
# same shape chitragupta/ledger.py uses for upsert_reference.
# pylint: disable=unused-import
from chitragupta.enrich._scope import (  # noqa: F401
    CORPUS_STAGES,
    EXIT_BAD_SCOPE,
    draft_citekeys,
)

# pylint: enable=unused-import

# Re-exported, not used here: STAGE_FUNCS is what main() dispatches
# through, and the individual wrappers are named so that
# tests/test_enrich_script.py can reach them where it always has. The
# disable names pylint's own code -- a flake8 noqa means nothing to it,
# which is how two of these reached CI.
# pylint: disable=unused-import
from chitragupta.enrich.stages import (  # noqa: F401
    STAGE_FUNCS,
    stage_bertopic,
    stage_converge,
    stage_docling,
    stage_embed,
    stage_extract_keywords,
    stage_seed_topics,
    stage_topic_graph,
)

# pylint: enable=unused-import
from chitragupta import config, logging_setup, runlock
from chitragupta.progname import prog_for

# A fixed name, not __name__: this file is the layer's entry point, so
# Python sets __name__ to "__main__", which sits outside the logger tree
# logging_setup.configure() pins -- exactly the trap chitragupta/sync.py
# documents at its own getLogger call. Without the fixed name every line
# here would reach the log file and be silently dropped from the console.
logger = logging.getLogger("chitragupta.enrich")

STAGE_ORDER = [
    "docling",
    "embed",
    "bertopic",
    "extract-keywords",
    "seed-topics",
    "converge",
    "topic-graph",
]


# What `--help` prints, deliberately *not* this module's docstring (#152)
# -- see chitragupta/corpus.py's DESCRIPTION for the reasoning, which is the same
# at every entry point in this project.
DESCRIPTION = (
    "The enrichment layer: Docling -> embeddings/Chroma -> BERTopic -> "
    "keywords -> seeded topics -> converged topic set -> topic graph. "
    "Each stage probes its own prerequisites and reports honestly."
)


def parse_args() -> argparse.Namespace:
    # prog, because argparse would otherwise derive "__main__.py" from
    # sys.argv[0] and print a usage line nobody can type.
    parser = argparse.ArgumentParser(prog=prog_for("enrich"), description=DESCRIPTION)
    parser.add_argument(
        "--target",
        choices=["host", "docker"],
        default="host",
        help="Informational only -- stages self-probe regardless of this flag.",
    )
    # default=None, not the joined list, so main() can tell "the user
    # asked for every stage" apart from "the user asked for nothing in
    # particular" -- --for-draft narrows the second and is refused
    # against the first. argparse shows no "(default: ...)" of its own
    # here, so the help text below is the only place that default is
    # stated and it has to state both halves.
    parser.add_argument(
        "--stages",
        default=None,
        help=f"Comma-separated subset of: {','.join(STAGE_ORDER)} "
        "(default: all seven, or docling alone with --for-draft)",
    )
    parser.add_argument(
        "--for-draft",
        metavar="PATH",
        help="Scope the docling stage to the papers this draft cites, instead of "
        "the whole corpus. Refused "
        "together with an explicit --stages naming "
        f"{' or '.join(SCOPE_REFUSED)}.",
    )
    return parser.parse_args()


def _say(message: str, *, level: int = logging.INFO, log_as: str | None = None) -> None:
    """This script's stdout is its human-facing report -- the stage
    table and the summary -- so every line goes to stdout and is
    mirrored into the log file rather than moved to it. `log_as` gives
    the log a different rendering of the same thing where the terminal
    wants one shape and a grep wants another. See logging_setup.say()."""
    logging_setup.say(logger, message, level=level, log_as=log_as)


def main(configure_logging: bool = False) -> int:
    """Run the selected stages under the pipeline lock.

    `configure_logging` is off by default and set only by the
    `__main__` block below, which keeps logging_setup.configure()
    entrypoint-only in the same way chitragupta/sync.py does. The flag exists
    at all because this script takes its lock *inside* main() rather
    than at the entrypoint, and configure() must happen inside the lock
    (see its docstring) -- so it cannot simply sit beside the
    SystemExit below. Tests call main() directly and must not attach
    handlers or create a logs/ directory as a side effect.
    """
    args = parse_args()
    # Every print in this function and its two helpers is deliberately a
    # bare print rather than _say: no log file is open yet and none may
    # be opened here (see this docstring). Argument validation belongs to
    # the caller's terminal anyway -- the run it describes has not
    # started.
    selected = _selected_stages(args)

    scope = None
    if args.for_draft:
        scope, error = resolve_scope(args, selected)
        if error is not None:
            return error
    # Same lock as `python -m chitragupta.corpus sync`: every stage here writes a corpus
    # artefact, and
    # sync's parsed-text writes are not atomic, so an enrichment run
    # overlapping a sync can read a half-written .txt. One lock rather
    # than two, because the unsafe overlap is any-writer-vs-any-writer,
    # not just sync-vs-sync.
    try:
        with runlock.pipeline_lock():
            # Inside the lock for the same reason chitragupta/sync.py configures
            # inside its own: RotatingFileHandler is not safe for two
            # processes on one file, and this script shares
            # logs/pipeline.log with sync. The lock is what makes the
            # shared file sound -- see chitragupta/logging_setup.py's docstring.
            if configure_logging:
                logging_setup.configure()
            return _run_stages(args, selected, scope)
    except runlock.AlreadyRunning as exc:
        # Deliberately still a bare print, not _say: this is the losing
        # side of the race above and must not touch logs/pipeline.log,
        # which the winner may already be writing to. Same reasoning as
        # the matching branch in chitragupta/sync.py.
        print(f"  {exc}")
        return runlock.EXIT_ALREADY_RUNNING


def _selected_stages(args) -> set[str]:
    """The stage names this run will attempt, warned but not filtered.

    Strip and drop blanks: "--stages 'embed, bertopic'" and a trailing
    comma are both natural to type, and without this the first makes a
    real stage look unknown (" bertopic" matches nothing) while the
    second puts an empty name in the warning below.
    """
    if args.stages is not None:
        stages = args.stages
    elif args.for_draft:
        # Just docling: the other two are refused with a scope
        # (SCOPE_REFUSED above), and quotable passages for the cited
        # papers are what --for-draft is for.
        stages = "docling"
    else:
        stages = ",".join(STAGE_ORDER)
    selected = {name.strip() for name in stages.split(",") if name.strip()}

    # An unrecognized stage name would otherwise be a silent no-op: the
    # loop in _run_stages iterates STAGE_ORDER and skips anything not
    # selected, so nothing ever reports that the name went unused. Say so
    # instead -- notably for a stage name this pipeline used to have and
    # no longer does.
    unknown = sorted(selected - set(STAGE_ORDER))
    if unknown:
        print(
            f"WARNING: unknown stage(s) {', '.join(unknown)} -- "
            f"known stages: {', '.join(STAGE_ORDER)}"
        )
    return selected


def _run_stages(args, selected, scope: set[str] | None = None) -> int:
    docs = corpus.build_corpus()
    _say(f"Target: {args.target}")
    if scope is None:
        _say(f"Corpus: {len(docs)} doc(s) from {config.BIB_FILE_PATH}")
    else:
        docs, error = scope_corpus(docs, scope, args, selected, _say)
        if error is not None:
            return error

    results = {}
    for name in STAGE_ORDER:
        if name not in selected:
            continue
        _say(f"\n=== {name} ===")
        try:
            result = STAGE_FUNCS[name](docs, args)
        except Exception as exc:  # noqa: BLE001 -- a stage failing must not abort the run
            result = {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}
        results[name] = result
        _report_stage_result(result)

    return _summarise(results)


def _summarise(results: dict) -> int:
    """Print the run's summary and return its exit code.

    Nonzero if any stage errored (#509/m-39). A stage failing does not
    abort the run -- the `except` in `_run_stages` is deliberate, since a
    later stage may still be worth attempting -- but returning 0
    afterwards made "everything worked" and "everything errored"
    indistinguishable to the only consumer that cannot read the summary:
    cron, which is how this is actually run.
    """
    _say("\n=== Summary ===")
    for name in STAGE_ORDER:
        if name in results:
            _say(f"  {name:10s} {results[name]['status']}")
    errored = [name for name, result in results.items() if result.get("status") == "error"]
    if not errored:
        return 0
    _say(f"\n{len(errored)} stage(s) errored: {', '.join(errored)}")
    return 1


def _report_stage_result(result) -> None:
    """One stage's outcome, to the terminal and the log.

    Two renderings of the same detail on purpose. The terminal gets
    the indented JSON it has always had; the log gets it on one
    line, because a record spanning several lines turns one event
    into several with only the first timestamped, and every stage
    but `render` returns a dict here -- so this is the common case,
    not an edge one.

    A failed stage is logged at WARNING so an unattended reader
    grepping logs/pipeline.log at the default level still sees it
    -- the stage swallowed the exception to keep the run going,
    so this line is the only trace it leaves.
    """
    detail = result["detail"]
    is_text = isinstance(detail, str)
    _say(
        f"[{result['status']}] "
        + (detail if is_text else json.dumps(detail, indent=2, default=str)),
        level=logging.WARNING if result["status"] == "error" else logging.INFO,
        log_as=None if is_text else f"[{result['status']}] " + json.dumps(detail, default=str),
    )


if __name__ == "__main__":
    raise SystemExit(main(configure_logging=True))
