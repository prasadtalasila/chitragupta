"""One log file for everything that holds the pipeline write lock.

`logs/pipeline.log`, shared by `python -m chitragupta.corpus sync` and
`python -m chitragupta.enrich`. One file rather than one per entrypoint, for a
reason that is structural rather than a matter of taste:
`RotatingFileHandler` is not safe for two processes to hold open on the
same file at once (a rotation from one can land mid-write from the
other), so a shared rotating file is only sound if the writers are
already mutually exclusive. They are -- both take
`runlock.pipeline_lock()` -- so **the log file's scope is deliberately
the same set as the lock's scope**. Anything that does not hold the
lock does not write here; see `configure()` on why that boundary is
load-bearing rather than incidental.

That is also the answer to "why isn't `chitragupta.retrieval` logged?" -- it,
`chitragupta.citation_gate`, `chitragupta.references`, `chitragupta.dossier` and the rest of the
drafting-layer CLIs are read-only, are invoked ad hoc by the genre
skills, and deliberately do *not* take the lock, so several can run at
once. Giving them a rotating handler would put concurrent processes on
one file, and giving each its own file would not help (two
`chitragupta.retrieval` calls still collide on `retrieval.log`). Their stdout is
a documented contract those skills parse, so it stays stdout. Logging
them would mean adding a channel alongside it, under a scheme that does
not depend on the lock -- not reusing this one.

The alternative, `sync.log`/`enrich.log`/..., would split what is one
causal story: `chitragupta/enrich/docling_parse.py` reuses the corpus layer's
parse, so "sync parsed X" and "docling reused X's parse" belong on
adjacent lines. The file formatter already carries `%(name)s`, so
`grep 'src\\.sync'` recovers the split view at any time -- no filter
recovers the merged one. Rotation also stays one on-disk budget --
5 MB of active file plus 5 backups of the same, so ~30 MB at the
ceiling -- instead of that much again for every component.
"""

import logging
import logging.handlers
import os
import sys

from chitragupta import config


# The root of this project's own logger tree. One tree, because every
# entrypoint lives inside the `chitragupta` package -- the enrichment layer's is
# chitragupta/enrich/__main__.py, and logs as `chitragupta.enrich`. Kept as a tuple: see
# _from_our_trees below for why a second root stays cheap to add.
_TREES = ("chitragupta",)

# Silence the stdlib's `logging.lastResort` fallback for these trees.
#
# Without this, a WARNING+ record logged before configure() has run --
# or in a process that never calls it -- finds no handler anywhere up
# the chain, so `Logger.callHandlers` falls back to `lastResort`, a
# stderr handler fixed at WARNING. `say()` would then print its message
# to stdout *and* have the logging machinery repeat it on stderr, which
# is both a duplicate and a direct contradiction of say()'s documented
# "no-op beyond the bare print when configure() has not run". The same
# applies to `chitragupta/sync.py`'s own logger.warning calls when `run()` is
# driven in-process, which this project explicitly supports.
#
# A NullHandler is the idiom the stdlib's own logging documentation
# prescribes for exactly this. It emits nothing and creates nothing --
# no file, no directory -- so it does not weaken the entrypoint-only
# invariant configure() carries; it only makes `callHandlers` stop
# looking. Records still propagate to whatever real handlers are
# attached later, so configure() and pytest's caplog both work
# unchanged.
for _tree in _TREES:
    logging.getLogger(_tree).addHandler(logging.NullHandler())


# Marks the handlers configure() attached, so a later call can take
# exactly those back off again. An attribute on the handler rather than
# a module-level list: it survives this module being re-imported, it
# cannot drift out of sync with what is actually on the root logger, and
# it can never match a handler some other library attached -- which a
# "remove every RotatingFileHandler" sweep would.
_OURS = "_chitragupta_pipeline_log_handler"


def _detach_ours() -> None:
    """Remove and close the handlers a previous configure() attached.

    Only reached when LOGS_DIR has moved, since the same-target case
    returns before this. Closing rather than merely detaching matters:
    the old RotatingFileHandler holds an open file descriptor, and on
    Windows a still-open handle blocks the file from being replaced or
    removed -- a real case here, since CI runs the suite on
    windows-latest.
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if getattr(handler, _OURS, False):
            root.removeHandler(handler)
            handler.close()


def _already_attached(path) -> bool:
    """True if this process already has a rotating handler on `path`.

    The actual condition, rather than a module-level "configured yet?"
    flag: the hazard being guarded against is two handlers open on one
    file, so asking whether that is the case cannot go stale the way a
    bookkeeping boolean can. It also keeps the guard honest about
    scope. A second call with a *different* LOGS_DIR is a real
    reconfiguration and is allowed through -- a flag would have
    swallowed it silently and sent those records to the first call's
    file, which is the confusing failure this project would rather not
    have. A second call with the same target is the no-op case that
    matters: two entrypoints share this module, and the enrichment
    layer runs several stages in one process, so an unguarded repeat would
    duplicate every subsequent line in both the file and the console --
    output that reads as corruption rather than as a config bug.
    """
    # os.path.abspath, not Path.resolve(): this has to match what
    # logging.FileHandler stored, and that is exactly what it uses. On a
    # host where the log directory sits behind a symlink, resolve()
    # would produce a different string and the guard would never fire.
    resolved = os.path.abspath(path)
    return any(
        isinstance(handler, logging.handlers.RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == resolved
        for handler in logging.getLogger().handlers
    )


def _not_file_only(record: logging.LogRecord) -> bool:
    """False for a record logged with extra={"file_only": True} -- the
    summary line, which is already printed to stdout and would otherwise
    print a second time via the console handler below."""
    return not getattr(record, "file_only", False)


def _this_project_only(record: logging.LogRecord) -> bool:
    """False for a record from outside this project's own logger trees --
    a third party already using stdlib logging (docling, torch; see the
    [n/N] progress comment in chitragupta/sync.py about their own chatter).
    Their WARNING+ still reaches logs/pipeline.log via file_handler
    below, "for free" -- this filter only keeps their chatter off the
    console, which is the one thing this project's own output was never
    supposed to include.

    One tree, because every entrypoint lives in the `chitragupta` package. That
    has not always been true: an entry point under `scripts/` logged as
    `scripts.<name>`, and matching only `chitragupta*` would have sent its every
    line to the file while silently dropping it from the console -- a
    half-failure much harder to notice than no logging at all. `_TREES`
    is therefore still a tuple and this still loops, so a second root
    outside `chitragupta` costs one entry rather than a rewrite.
    """
    return any(
        record.name == root or record.name.startswith(root + ".")
        for root in _TREES
    )


def say(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    log_as: str | None = None,
) -> None:
    """Report one line to stdout, and mirror it into logs/pipeline.log.

    Printed *and* logged, rather than logged alone, for callers whose
    stdout is a human-facing report or a documented CLI contract --
    `chitragupta/enrich/__main__.py`'s stage table, the enrichment stages' summary
    lines. The console handler writes to stderr, so a plain
    `logger.info` would move those lines to a different stream and
    break both the tests that assert on them and anything piping the
    output.

    `extra={"file_only": True}` is what makes the pairing safe: it is
    the flag `_not_file_only` above drops, so the console handler does
    not print a second copy of a line stdout already carried. Same
    mechanism `chitragupta/sync.py` uses for its own summary block.

    A no-op beyond the bare print when `configure()` has not run --
    there is simply no handler attached -- so a library caller in a
    test still behaves exactly as it did before logging existed.

    Flushed, because it replaces calls that already were: stdout is
    block-buffered when it isn't a terminal (a cron job's redirect, a
    Docker log), and the tail of an interrupted run is exactly the part
    worth keeping. See chitragupta/enrich/embed_index.py's build_index
    docstring, which measured this.

    Only for whole lines. A caller building one line from several
    writes (`print(..., end="")`) cannot use this: a log record is a
    line by construction, so the pieces would arrive in the file as
    separate records, and the "which document is it on right now"
    property of an incremental line would be lost from the terminal.
    Those callers stay bare prints.

    `log_as` is for when the terminal and the file genuinely want
    different renderings of the same thing. The motivating case is
    `chitragupta/enrich/__main__.py`'s stage detail: a human reading the terminal
    wants `json.dumps(..., indent=2)`, and a person grepping the log
    wants that same object on one line. Pass the compact form here and
    the pretty one as `message`; the alternative -- picking one -- makes
    either the terminal unreadable or the log unparseable.

    **The record is always exactly one line.** Leading and trailing
    newlines are stripped (callers use them to space sections apart on a
    terminal, `say(f"\\n=== {stage} ===")`, where in the file they
    produce a record whose first line is empty and whose text sits on
    the next). Any newline left *inside* the text collapses along with
    the whitespace around it. That collapse is a structural backstop,
    not the intended path: a multi-line record breaks the
    one-line-per-entry shape `grep`, `tail` and every log parser assume,
    turning one event into several with only the first timestamped. Use
    `log_as` to control what the single line says; the backstop only
    guarantees that it *is* single. Indentation survives when there is
    no internal newline to collapse -- the summary table is indented and
    stays that way.
    """
    print(message, flush=True)
    record = (log_as if log_as is not None else message).strip("\n")
    if "\n" in record:
        record = " ".join(record.split())
    logger.log(level, record, extra={"file_only": True})


def configure() -> None:
    """Attach a rotating file handler (logs/pipeline.log) and a stderr handler.

    **CLI-entrypoint-only, and only from inside the pipeline lock.**
    Deliberately not called from `run()` or any library function --
    same split as `runlock.pipeline_lock()` itself, and for two
    reasons. First, `run()` stays callable in-process (the tests do
    that) without a handler side effect or a `logs/` directory
    appearing as an import-time surprise. Second, and the harder
    constraint: `RotatingFileHandler` isn't safe for two processes to
    hold open on the same file at once, so two overlapping scheduled
    invocations must not both attach one. Calling this inside the lock
    makes the lock serialize handler creation as well as the actual
    work, so at most one process ever has a live handler on the file.
    A caller that does not hold the lock must not call this -- see this
    module's docstring on why the file's scope is the lock's scope.

    5 MB x 5 backups is fixed rather than configurable -- see
    config.LOGGING_LEVEL's own comment for why only the level is a
    setting here.

    config.LOGGING_LEVEL is applied to file_handler alone (via
    setLevel), not to any logger. Setting it on this project's logger
    trees instead -- an earlier version of this function did -- silently
    gated the console too: a logger only creates a record at all if the
    *logger's* effective level allows it, before any handler is even
    reached, so a level of WARNING would have suppressed the [n/N]
    progress line (INFO) everywhere, not just in the file, contradicting
    the "only affects the file" this project documents for this
    setting. The trees below are instead pinned permissive (DEBUG) so
    every record this project's own code logs always reaches both
    handlers; each handler then decides for itself what it keeps.

    Calling this twice in one process, with the same LOGS_DIR, is a
    no-op rather than a second pair of handlers -- see
    `_already_attached` for why the guard is that condition and not a
    flag. Calling it again after LOGS_DIR has changed *replaces* the
    previous pair rather than adding to it: without the detach below,
    "reconfigure" would mean every subsequent record landing in the old
    file as well as the new one, and every console line printing twice.
    """
    target = config.LOGS_DIR / "pipeline.log"
    if _already_attached(target):
        return
    _detach_ours()

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        target, maxBytes=5_000_000, backupCount=5, encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    ))
    file_handler.setLevel(config.LOGGING_LEVEL)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.addFilter(_not_file_only)
    console_handler.addFilter(_this_project_only)

    root = logging.getLogger()
    for handler in (file_handler, console_handler):
        setattr(handler, _OURS, True)
        root.addHandler(handler)
    for tree in _TREES:
        logging.getLogger(tree).setLevel(logging.DEBUG)
