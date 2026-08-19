"""Orchestrates the full enrichment layer:

    Docling -> sentence-transformers/Chroma -> BERTopic

The enrichment layer's single entry point, one level deep like every
other layer's: `python -m src.enrich`, as the corpus layer has
`python -m src.corpus sync`. The stage modules beside this one have no
`__main__` block, so `python -m src.enrich.docling_parse` imports a
module and exits 0 without doing anything -- `--stages` is the only way
to run them, and docs/ARCHITECTURE.md states the invariant.

One entry point for both the host and the Docker target
(docker/Dockerfile) -- the two don't need separate implementations. Each stage probes its own
prerequisites (pandoc/pdflatex on PATH) and reports a real per-stage
status instead of assuming the target implies availability. On a plain
host that's missing TeX Live, some stages report
skipped/missing-binary -- that is a correct, honest result, not a
bug in this script.

Needs the venv populated by `poetry install --with enrich` (see
pyproject.toml, and .venv-full/ on the host this was developed on). The
corpus and drafting layers (python -m src.corpus sync, python -m src.draft gate) do
not depend on any of this and are unaffected either way.

Every stage here writes a **corpus** artefact, which is why this layer
takes the same write lock as `python -m src.corpus sync`. A per-draft
stage would not, and there deliberately isn't one: a `provenance`
(review-layer report) or `render` (drafting-layer publish) stage would be
a three-line wrapper around `python -m src.review provenance <draft>` or
`python -m src.draft render <draft> --format pdf`, both of which need no
venv at all and neither of which should be made to wait on a running
sync.

That is also what keeps the layer diagram acyclic: the enrichment layer
reads corpus artefacts and writes corpus artefacts, and does not import
the drafting or review layers.

Usage:
    python -m src.enrich --target host
    python -m src.enrich --stages embed,bertopic
    python -m src.enrich --for-draft content/drafts/chapter.md
"""

import argparse
import json
import logging
from pathlib import Path

from src.enrich import corpus, docling_parse, embed_index, topic_model
# citation_gate is read, not called into: draft_citekeys() below uses its
# citekey reader so a scoped run covers exactly the papers the gate will
# check against. That is this layer reading a draft, not invoking the
# drafting layer -- see the module docstring on why nothing else from
# src/ outside the corpus path is imported here.
from src import citation_gate, config, logging_setup, runlock

# A fixed name, not __name__: this file is the layer's entry point, so
# Python sets __name__ to "__main__", which sits outside the logger tree
# logging_setup.configure() pins -- exactly the trap src/sync.py
# documents at its own getLogger call. Without the fixed name every line
# here would reach the log file and be silently dropped from the console.
logger = logging.getLogger("src.enrich")

STAGE_ORDER = ["docling", "embed", "bertopic"]

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

# The stages that read the corpus at all -- every stage there is, since
# 4.0.0 removed the two per-draft passthroughs. Kept as its own name
# rather than folded into STAGE_ORDER because it answers a different
# question: an empty scope is only a reason to stop if some stage was
# going to use it, and SCOPE_REFUSED says which stages refuse to have a
# scope narrowed rather than which read one.
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
    return {"status": "ok",
            "detail": {"n_docs": result["n_docs"],
                       "assignments": result["assignments"]}}


STAGE_FUNCS = {
    "docling": stage_docling,
    "embed": stage_embed,
    "bertopic": stage_bertopic,
}


# What `--help` prints, deliberately *not* this module's docstring (#152)
# -- see src/corpus.py's DESCRIPTION for the reasoning, which is the same
# at every entry point in this project.
DESCRIPTION = ("The enrichment layer: Docling -> embeddings/Chroma -> BERTopic. "
               "Each stage probes its own prerequisites and reports honestly.")


def parse_args():
    # prog, because argparse would otherwise derive "__main__.py" from
    # sys.argv[0] and print a usage line nobody can type.
    parser = argparse.ArgumentParser(prog="python -m src.enrich", description=DESCRIPTION)
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
                              "(default: all three, or docling alone with --for-draft)")
    parser.add_argument("--for-draft", metavar="PATH",
                         help="Scope the docling stage to the papers this draft cites, instead of "
                              "the whole corpus. Refused "
                              "together with an explicit --stages naming "
                              f"{' or '.join(SCOPE_REFUSED)}.")
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
    # Every print in this function and its two helpers is deliberately a
    # bare print rather than _say: no log file is open yet and none may
    # be opened here (see this docstring). Argument validation belongs to
    # the caller's terminal anyway -- the run it describes has not
    # started.
    selected = _selected_stages(args)

    scope = None
    if args.for_draft:
        scope, error = _resolve_scope(args, selected)
        if error is not None:
            return error
    # Same lock as `python -m src.corpus sync`: every stage here writes a corpus
    # artefact, and
    # sync's parsed-text writes are not atomic, so an enrichment run
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
        print(f"WARNING: unknown stage(s) {', '.join(unknown)} -- "
              f"known stages: {', '.join(STAGE_ORDER)}")
    return selected


def _resolve_scope(args, selected) -> "tuple[set[str] | None, int | None]":
    """--for-draft's citekey set, or the exit code refusing it.

    Returns (scope, None) on success and (None, EXIT_BAD_SCOPE) on any
    refusal, so main() has one place to bail. All of it runs before the
    lock: every answer here is a property of the file the user named,
    answerable without the ledger, so there is no reason to make a
    concurrent sync wait for it.
    """
    # Refused against the stages the user *typed*, not against the
    # default: a bare --for-draft selects docling alone in
    # _selected_stages and never reaches this branch, so the only way
    # here is having asked for a scoped embed or bertopic in so many
    # words.
    refused = sorted(selected & set(SCOPE_REFUSED))
    if refused:
        print(f"  --for-draft cannot scope {' or '.join(refused)}: "
              f"{'they each build' if len(refused) > 1 else 'it builds'} one whole-corpus "
              "artefact, and a partial one is indistinguishable from a complete one. Run "
              "them as separate commands:\n"
              f"      python -m src.enrich --for-draft {args.for_draft} --stages docling\n"
              f"      python -m src.enrich --stages {','.join(refused)}")
        return None, EXIT_BAD_SCOPE

    draft_path = Path(args.for_draft)
    try:
        scope = draft_citekeys(draft_path)
    except OSError as exc:
        print(f"  cannot read --for-draft {draft_path}: {exc}")
        return None, EXIT_BAD_SCOPE
    except UnicodeDecodeError as exc:
        # A separate branch because it is a separate failure:
        # UnicodeDecodeError is a ValueError, so the clause above
        # does not catch it, and the fix is different enough to be
        # worth naming. Not read with errors="replace" instead --
        # a replacement character lands in the middle of whatever
        # citekey the bad byte was part of, and the run would then
        # scope itself to a quietly wrong set of papers rather than
        # stopping.
        print(f"  cannot read --for-draft {draft_path} as UTF-8: {exc}\n"
              "      Every draft this pipeline writes is UTF-8, so this one came from "
              "somewhere else -- re-save it in that encoding.")
        return None, EXIT_BAD_SCOPE
    if not scope:
        print(f"  no citations found in {draft_path} -- nothing to scope the run to. "
              "Drop --for-draft to enrich the whole corpus.")
        return None, EXIT_BAD_SCOPE
    return scope, None


def _run_stages(args, selected, scope: set[str] | None = None) -> int:
    docs = corpus.build_corpus()
    _say(f"Target: {args.target}")
    if scope is None:
        _say(f"Corpus: {len(docs)} doc(s) from {config.BIB_FILE_PATH}")
    else:
        docs, error = _scope_corpus(docs, scope, args, selected)
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

    _say("\n=== Summary ===")
    for name in STAGE_ORDER:
        if name in results:
            _say(f"  {name:10s} {results[name]['status']}")
    return 0


def _scope_corpus(docs, scope, args, selected):
    """The corpus narrowed to --for-draft's citekeys, with the losses named.

    The filter sits here rather than inside build_corpus(): that
    function's whole contract is "every ledger item", the full SELECT is
    microseconds next to any stage, and keeping the unfiltered list in
    hand is what lets the count below say what was left out instead of
    only what was kept.

    Returns (docs, None), or (docs, EXIT_BAD_SCOPE) when a corpus stage
    was asked to run over nothing.
    """
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
             "`python -m src.corpus sync` first.", level=logging.WARNING)
        return docs, EXIT_BAD_SCOPE
    return docs, None


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
