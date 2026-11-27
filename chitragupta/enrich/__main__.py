"""Orchestrates the full enrichment layer:

    Docling -> sentence-transformers/Chroma -> BERTopic -> declared
    keywords -> seed topics

The single entry point, one level deep: the stage modules have no
`__main__` block, so `--stages` is the only way to run them, an invariant
docs/ARCHITECTURE.md states. Each stage probes its own prerequisites and
reports skipped or partial honestly. Every stage writes a **corpus**
artefact, hence the same write lock as sync; per-draft stages (provenance,
render) deliberately don't exist here, need no venv, and shouldn't wait on
a sync. The layer never imports the drafting or review layers.

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

# Re-exported for tests/test_enrich_script.py.
# pylint: disable=unused-import
from chitragupta.enrich._scope import (  # noqa: F401
    CORPUS_STAGES,
    EXIT_BAD_SCOPE,
    draft_citekeys,
)

# pylint: enable=unused-import

# Re-exported: tests/test_enrich_script.py reaches the wrappers. pylint
# ignores a flake8 noqa, hence its own disable.
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
from chitragupta import config, ledger, logging_setup, runlock
from chitragupta.progname import prog_for
from chitragupta.help_format import ClickParser

# A fixed name, not __name__ ("__main__" here), which sits outside the
# logger tree logging_setup.configure() pins: lines would miss the console.
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


# What `--help` prints, deliberately *not* this module's docstring (#152);
# see chitragupta/corpus.py's DESCRIPTION.
DESCRIPTION = (
    "The enrichment layer: Docling -> embeddings/Chroma -> BERTopic -> "
    "keywords -> seeded topics -> converged topic set -> topic graph. "
    "Each stage probes its own prerequisites and reports honestly."
)


def parse_args() -> argparse.Namespace:
    # prog, or argparse prints an untypable "__main__.py" usage line.
    parser = ClickParser(prog=prog_for("enrich"), description=DESCRIPTION)
    parser.add_argument(
        "--target",
        choices=["host", "docker"],
        default="host",
        help="Informational only -- stages self-probe regardless of this flag.",
    )
    # default=None, so main() can tell "every stage" from "nothing in
    # particular" (--for-draft narrows the second, is refused against the
    # first); the help text below is the only place both are stated.
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
    """Print to stdout (the human-facing report) and mirror it to the log.
    `log_as` gives the log a different rendering. See logging_setup.say()."""
    logging_setup.say(logger, message, level=level, log_as=log_as)


def main(configure_logging: bool = False) -> int:
    """Run the selected stages under the pipeline lock.

    `configure_logging` is set only by the `__main__` block: configure()
    must happen inside the lock, which is taken here, and tests calling
    main() must not attach handlers or create logs/.
    """
    args = parse_args()
    # Bare prints, not _say: no log file may be opened yet.
    selected = _selected_stages(args)

    scope = None
    if args.for_draft:
        scope, error = resolve_scope(args, selected)
        if error is not None:
            return error
    # Same lock as sync: a sync re-parsing a document mid-run would hand
    # this run two versions of its .txt. The overlap is any-writer-vs-any.
    try:
        with runlock.pipeline_lock():
            # Inside the lock: RotatingFileHandler is unsafe for two
            # processes on logs/pipeline.log (see logging_setup.py).
            if configure_logging:
                logging_setup.configure()
            return _run_stages(args, selected, scope)
    except runlock.AlreadyRunning as exc:
        # A bare print: the losing side must not touch logs/pipeline.log.
        print(f"  {exc}")
        return runlock.EXIT_ALREADY_RUNNING
    except ledger.NoLedger as exc:
        # The ledger is read read-only (#843), so an unsynced checkout is
        # refused by name rather than enriched as an empty corpus.
        print(f"  {exc}")
        return 1


def _selected_stages(args) -> set[str]:
    """The stage names this run will attempt, warned but not filtered.

    Strips and drops blanks, so "'embed, bertopic'" and a trailing comma work.
    """
    if args.stages is not None:
        stages = args.stages
    elif args.for_draft:
        # Just docling: the other two are refused with a scope.
        stages = "docling"
    else:
        stages = ",".join(STAGE_ORDER)
    selected = {name.strip() for name in stages.split(",") if name.strip()}

    # An unrecognized name would be a silent no-op (e.g. a removed stage).
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

    Nonzero if any stage errored (#509/m-39): stages don't abort the run,
    but cron cannot read the summary.
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

    The log gets the JSON on one line, since a multi-line record has only
    its first line timestamped. A failed stage logs at WARNING: the stage
    swallowed the exception, so this is its only trace.
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
