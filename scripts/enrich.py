#!/usr/bin/env python3
"""Orchestrates the full enrichment layer:

    Docling -> sentence-transformers/Chroma -> BERTopic
    -> citation provenance -> Pandoc/LaTeX

One script for both the host and the Docker target (docker/Dockerfile) --
the two don't need separate implementations. Each stage probes its own
prerequisites (pandoc/pdflatex on PATH) and reports a real per-stage
status instead of assuming the target implies availability. On a plain
host that's missing TeX Live, some stages report
skipped/missing-binary -- that is a correct, honest result, not a
bug in this script.

Needs the venv populated by `poetry install --with enrich` (see
pyproject.toml, and .venv-full/ on the host this was developed on). The
corpus and drafting layers (python -m src.sync, src/citation_gate.py) do
not depend on any of this and are unaffected either way.

Usage:
    python scripts/enrich.py --target host
    python scripts/enrich.py --stages embed,bertopic
    python scripts/enrich.py --stages render --input draft.md
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.enrich import corpus, docling_parse, embed_index, topic_model
from src import citation_provenance, config, logging_setup, render_output, runlock

# A fixed name, not __name__: this file is run as a script
# (`python scripts/enrich.py`), so Python sets __name__ to "__main__",
# which sits outside the logger trees logging_setup.configure() pins --
# exactly the trap src/sync.py documents at its own getLogger call. The
# "scripts" root is the second tree that function's _this_project_only
# filter accepts; without it every line here would reach the log file
# and be silently dropped from the console.
logger = logging.getLogger("scripts.enrich")

STAGE_ORDER = ["docling", "embed", "bertopic", "provenance", "render"]


def stage_docling(docs, args):
    status = docling_parse.parse_corpus(docs)
    errors = {k: v for k, v in status.items() if v.startswith("error")}
    return {"status": "ok" if not errors else "partial", "detail": status}


def stage_embed(docs, args):
    return {"status": "ok", "detail": embed_index.build_index(docs)}


def stage_bertopic(docs, args):
    result = topic_model.run_topic_model(docs)
    return {"status": "ok", "detail": {"n_docs": result["n_docs"], "assignments": result["assignments"]}}


def stage_provenance(docs, args):
    if not args.input:
        return {"status": "skipped", "detail": "no --input given"}
    written = citation_provenance.write_report(Path(args.input), ["md", "tex", "pdf"])
    missing = [f for f in ("tex", "pdf") if f not in written]
    return {
        "status": "ok" if not missing else "partial",
        "detail": {fmt: str(path) for fmt, path in written.items()},
    }


def stage_render(docs, args):
    if not args.input:
        return {"status": "skipped", "detail": "no --input given"}
    try:
        return {"status": "ok", "detail": str(render_output.render(args.input, args.output_format, args.documentclass))}
    except render_output.MissingBinary as exc:
        return {"status": "missing-binary", "detail": str(exc)}


STAGE_FUNCS = {
    "docling": stage_docling,
    "embed": stage_embed,
    "bertopic": stage_bertopic,
    "provenance": stage_provenance,
    "render": stage_render,
}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", choices=["host", "docker"], default="host",
                         help="Informational only -- stages self-probe regardless of this flag.")
    parser.add_argument("--stages", default=",".join(STAGE_ORDER),
                         help=f"Comma-separated subset of: {','.join(STAGE_ORDER)}")
    parser.add_argument("--input", help="Input file for the render stage")
    parser.add_argument("--output-format", default="pdf", help="Output format for the render stage")
    parser.add_argument("--documentclass", default="article", help="LaTeX documentclass for the render stage (default: article)")
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
    entrypoint-only in the same way src/sync.py does. The flag exists
    at all because this script takes its lock *inside* main() rather
    than at the entrypoint, and configure() must happen inside the lock
    (see its docstring) -- so it cannot simply sit beside the
    SystemExit below. Tests call main() directly and must not attach
    handlers or create a logs/ directory as a side effect.
    """
    args = parse_args()
    # Strip and drop blanks: "--stages 'embed, bertopic'" and a trailing
    # comma are both natural to type, and without this the first makes a
    # real stage look unknown (" bertopic" matches nothing) while the
    # second puts an empty name in the warning below.
    selected = {name.strip() for name in args.stages.split(",") if name.strip()}

    # An unrecognized stage name would otherwise be a silent no-op: the
    # loop below iterates STAGE_ORDER and skips anything not selected, so
    # nothing ever reports that the name went unused. Say so instead --
    # notably for a stage name this pipeline used to have and no longer does.
    unknown = sorted(selected - set(STAGE_ORDER))
    if unknown:
        # A bare print, not _say: this runs before the lock, so no log
        # file is open yet and none may be opened here (see main()'s
        # docstring). Argument validation belongs to the caller's
        # terminal anyway -- the run it describes has not started.
        print(f"WARNING: unknown stage(s) {', '.join(unknown)} -- known stages: {', '.join(STAGE_ORDER)}")

    # Same lock as `python -m src.sync`: this stage writes content/ too,
    # and sync's parsed-text writes are not atomic, so an enrichment run
    # overlapping a sync can read a half-written .txt. One lock rather
    # than two, because the unsafe overlap is any-writer-vs-any-writer,
    # not just sync-vs-sync.
    try:
        with runlock.pipeline_lock():
            # Inside the lock for the same reason src/sync.py configures
            # inside its own: RotatingFileHandler is not safe for two
            # processes on one file, and this script shares
            # logs/pipeline.log with sync. The lock is what makes the
            # shared file sound -- see src/logging_setup.py's docstring.
            if configure_logging:
                logging_setup.configure()
            return _run_stages(args, selected)
    except runlock.AlreadyRunning as exc:
        # Deliberately still a bare print, not _say: this is the losing
        # side of the race above and must not touch logs/pipeline.log,
        # which the winner may already be writing to. Same reasoning as
        # the matching branch in src/sync.py.
        print(f"  {exc}")
        return runlock.EXIT_ALREADY_RUNNING


def _run_stages(args, selected) -> int:
    docs = corpus.build_corpus()
    _say(f"Target: {args.target}")
    _say(f"Corpus: {len(docs)} doc(s) from {config.BIB_FILE_PATH}")

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
        detail = result["detail"]
        # Two renderings of the same detail on purpose. The terminal gets
        # the indented JSON it has always had; the log gets it on one
        # line, because a record spanning several lines turns one event
        # into several with only the first timestamped, and every stage
        # but `render` returns a dict here -- so this is the common case,
        # not an edge one.
        #
        # A failed stage is logged at WARNING so an unattended reader
        # grepping logs/pipeline.log at the default level still sees it
        # -- the stage swallowed the exception to keep the run going,
        # so this line is the only trace it leaves.
        is_text = isinstance(detail, str)
        _say(
            f"[{result['status']}] " + (detail if is_text else json.dumps(detail, indent=2, default=str)),
            level=logging.WARNING if result["status"] == "error" else logging.INFO,
            log_as=None if is_text else f"[{result['status']}] " + json.dumps(detail, default=str),
        )

    _say("\n=== Summary ===")
    for name in STAGE_ORDER:
        if name in results:
            _say(f"  {name:10s} {results[name]['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(configure_logging=True))
