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
    python scripts/enrich.py --for-draft content/drafts/chapter.md
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.enrich import corpus, docling_parse, embed_index, topic_model
from src import citation_gate, citation_provenance, config, logging_setup, render_output, runlock

# A fixed name, not __name__: this file is run as a script
# (`python scripts/enrich.py`), so Python sets __name__ to "__main__",
# which sits outside the logger trees logging_setup.configure() pins --
# exactly the trap src/sync.py documents at its own getLogger call. The
# "scripts" root is the second tree that function's _this_project_only
# filter accepts; without it every line here would reach the log file
# and be silently dropped from the console.
logger = logging.getLogger("scripts.enrich")

STAGE_ORDER = ["docling", "embed", "bertopic", "provenance", "render"]

# The stages --for-draft refuses to run, rather than running over a
# subset. Both write one whole-corpus artefact whose partial form is
# indistinguishable from its complete one: `embed` upserts into a Chroma
# collection that records no completeness marker, and four skills branch
# on nothing more than "does content/chroma/ exist" before searching it,
# so a collection holding a draft's eleven papers would answer as if it
# held the corpus; `bertopic` overwrites content/topics.json outright, so
# a scoped run replaces a corpus-wide topic model with an eleven-document
# one. Allowing either would mean inventing that marker, which is a
# larger change than this filter and belongs to its own issue.
#
# This is a tier and not a ladder, in docs/LADDERS.md's vocabulary: the
# run stops and names what it cannot give you, rather than quietly
# substituting the whole corpus (an hour of work nobody asked for) or a
# fraction of it (an index that lies about its coverage).
SCOPE_REFUSED = ("embed", "bertopic")

# The stages that read the corpus at all. `provenance` and `render` are
# handed the document list and never look at it -- both work entirely off
# args.input, and are per-draft already -- so once the two above are
# refused, --for-draft's filter changes the behaviour of exactly one
# stage. Named here because an empty scope is only a reason to stop if
# some stage was going to use it.
#
# Overlapping SCOPE_REFUSED is not redundancy: this tuple says which
# stages read the corpus at all, which stays true whether or not a scope
# is in play, while that one says which refuse to have it narrowed.
CORPUS_STAGES = ("docling", "embed", "bertopic")

# 3, not 2: argparse already exits 2 for a usage error it detects
# itself, and runlock.EXIT_ALREADY_RUNNING is 2 as well. A wrapper needs
# to tell "you asked for something incoherent" apart from "someone else
# holds the lock, try later", because only the second is worth retrying.
EXIT_BAD_SCOPE = 3


def draft_citekeys(path: Path) -> set[str]:
    """Every citekey `path` cites, as the docling stage's scope.

    citation_gate.extract_citekeys() rather than a regex of this
    script's own, for two reasons: it is the same reader the hard gate
    uses, so a scoped run covers exactly the papers the gate will check
    the draft against, and it is whole-document rather than per-line, so
    a `\\citep{a,\\n b}` wrapped across lines contributes both keys
    (extract_citekeys_from_line would contribute neither).

    Returns a set: a draft cites the same paper many times, and the
    caller wants the papers, not the citations.
    """
    return {key for _, key in citation_gate.extract_citekeys(path.read_text(encoding="utf-8"))}


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
    # default=None, not the joined list, so main() can tell "the user
    # asked for every stage" apart from "the user asked for nothing in
    # particular" -- --for-draft narrows the second and is refused
    # against the first. argparse shows no "(default: ...)" of its own
    # here, so the help text below is the only place that default is
    # stated and it has to state both halves.
    parser.add_argument("--stages", default=None,
                         help=f"Comma-separated subset of: {','.join(STAGE_ORDER)} "
                              "(default: all five, or docling alone with --for-draft)")
    parser.add_argument("--for-draft", metavar="PATH",
                         help="Scope the docling stage to the papers this draft cites, instead of "
                              "the whole corpus, and use it as the --input default. Refused "
                              f"together with an explicit --stages naming {' or '.join(SCOPE_REFUSED)}.")
    parser.add_argument("--input", help="Input file for the provenance and render stages "
                                        "(defaults to --for-draft's draft when that is given)")
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
    # Every print between here and the lock is deliberately a bare print
    # rather than _say: no log file is open yet and none may be opened
    # here (see this docstring). Argument validation belongs to the
    # caller's terminal anyway -- the run it describes has not started.
    if args.stages is not None:
        stages = args.stages
    elif args.for_draft:
        # Just docling, not docling,provenance,render: the scope only
        # reaches docling (provenance and render read args.input and
        # never look at the corpus), and quotable passages for the cited
        # papers are what --for-draft is for. Adding the other two would
        # make a bare --for-draft write a rendered PDF nobody asked for.
        stages = "docling"
    else:
        stages = ",".join(STAGE_ORDER)
    # Strip and drop blanks: "--stages 'embed, bertopic'" and a trailing
    # comma are both natural to type, and without this the first makes a
    # real stage look unknown (" bertopic" matches nothing) while the
    # second puts an empty name in the warning below.
    selected = {name.strip() for name in stages.split(",") if name.strip()}

    # An unrecognized stage name would otherwise be a silent no-op: the
    # loop below iterates STAGE_ORDER and skips anything not selected, so
    # nothing ever reports that the name went unused. Say so instead --
    # notably for a stage name this pipeline used to have and no longer does.
    unknown = sorted(selected - set(STAGE_ORDER))
    if unknown:
        print(f"WARNING: unknown stage(s) {', '.join(unknown)} -- known stages: {', '.join(STAGE_ORDER)}")

    scope = None
    if args.for_draft:
        # Refused against the stages the user *typed*, not against the
        # default: a bare --for-draft selects docling alone above and
        # never reaches this, so the only way here is having asked for a
        # scoped embed or bertopic in so many words.
        refused = sorted(selected & set(SCOPE_REFUSED))
        if refused:
            print(f"  --for-draft cannot scope {' or '.join(refused)}: "
                  f"{'they each build' if len(refused) > 1 else 'it builds'} one whole-corpus "
                  "artefact, and a partial one is indistinguishable from a complete one. Run "
                  "them as separate commands:\n"
                  f"      python scripts/enrich.py --for-draft {args.for_draft} --stages docling\n"
                  f"      python scripts/enrich.py --stages {','.join(refused)}")
            return EXIT_BAD_SCOPE

        draft_path = Path(args.for_draft)
        try:
            scope = draft_citekeys(draft_path)
        except OSError as exc:
            print(f"  cannot read --for-draft {draft_path}: {exc}")
            return EXIT_BAD_SCOPE
        if not scope:
            # Before the lock rather than after: this is a property of
            # the file the user named, and answerable without the
            # ledger, so there is no reason to make a concurrent sync
            # wait for the answer.
            print(f"  no citations found in {draft_path} -- nothing to scope the run to. "
                  "Drop --for-draft to enrich the whole corpus.")
            return EXIT_BAD_SCOPE
        # The draft is the only input a scoped run could sensibly have,
        # so --for-draft supplies it -- but never overrides an --input
        # the user typed, which is the only way to enrich one draft's
        # papers while rendering another document.
        if args.input is None:
            args.input = str(draft_path)

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
            return _run_stages(args, selected, scope)
    except runlock.AlreadyRunning as exc:
        # Deliberately still a bare print, not _say: this is the losing
        # side of the race above and must not touch logs/pipeline.log,
        # which the winner may already be writing to. Same reasoning as
        # the matching branch in src/sync.py.
        print(f"  {exc}")
        return runlock.EXIT_ALREADY_RUNNING


def _run_stages(args, selected, scope: set[str] | None = None) -> int:
    docs = corpus.build_corpus()
    _say(f"Target: {args.target}")
    if scope is None:
        _say(f"Corpus: {len(docs)} doc(s) from {config.BIB_FILE_PATH}")
    else:
        # The filter sits here rather than inside build_corpus(): that
        # function's whole contract is "every ledger item", the full
        # SELECT is microseconds next to any stage, and keeping the
        # unfiltered list in hand is what lets the count below say what
        # was left out instead of only what was kept.
        total = len(docs)
        docs = [doc for doc in docs if doc.citekey in scope]
        _say(f"Corpus: {len(docs)} of {total} doc(s) from {config.BIB_FILE_PATH} "
             f"-- scoped to {args.for_draft}")

        # Named, not just counted. A citekey a draft cites and the
        # ledger has never heard of is normally the hard gate's business
        # and cannot reach a passing draft -- but a draft written before
        # a re-export, or against a corpus that has since moved, has
        # them, and silently enriching the remainder would report a
        # smaller number with nothing to explain it.
        unknown = sorted(scope - {doc.citekey for doc in docs})
        if unknown:
            _say(f"  {len(unknown)} cited citekey(s) are not in the ledger and cannot be "
                 f"enriched: {', '.join(unknown)}", level=logging.WARNING)
        if not docs and selected & set(CORPUS_STAGES):
            _say("  nothing to enrich -- re-export your bibliography and run "
                 "`python -m src.sync` first.", level=logging.WARNING)
            return EXIT_BAD_SCOPE

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
