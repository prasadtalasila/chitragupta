"""One log file for everything that holds the pipeline write lock.

`logs/pipeline.log`, shared by `corpus sync` and `enrich`.
`RotatingFileHandler` is not safe for two processes on one file, so the
file is sound only because its writers already take
`runlock.pipeline_lock()`: **the log file's scope is the lock's scope.**
The read-only drafting CLIs (`retrieval`, `citation_gate`, ...) skip the
lock to run concurrently, so they must not write here; their stdout is
the contract the skills parse.

One file rather than one per entrypoint keeps one causal story ("sync
parsed X", "docling reused X's parse") on adjacent lines; `%(name)s`
recovers the split view with grep, and rotation stays one ~30 MB budget.
"""

import logging
import logging.handlers
import os
import sys

from chitragupta import config


# Every entrypoint lives in the `chitragupta` package. A tuple, so a
# second root costs one entry.
_TREES = ("chitragupta",)

# Without a handler, a WARNING+ record logged before configure() falls
# back to `logging.lastResort` and repeats on stderr what `say()` already
# printed. The NullHandler creates no file, and records still propagate
# to handlers attached later (configure(), pytest's caplog).
for _tree in _TREES:
    logging.getLogger(_tree).addHandler(logging.NullHandler())


# An attribute on the handler, not a module-level list: it survives a
# re-import and never matches a handler another library attached.
_OURS = "_chitragupta_pipeline_log_handler"


def _detach_ours() -> None:
    """Remove and close the handlers a previous configure() attached.

    Closed, not just detached: an open handle blocks replacing the file
    on Windows, which CI runs on.
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if getattr(handler, _OURS, False):
            root.removeHandler(handler)
            handler.close()


def _already_attached(path) -> bool:
    """True if this process already has a rotating handler on `path`.

    Checks the real condition rather than a "configured yet?" flag: a
    flag would also swallow a legitimate reconfiguration to a different
    LOGS_DIR. A repeat with the same target must be a no-op, or every
    line is duplicated in file and console.
    """
    # os.path.abspath, not Path.resolve(): it must match what FileHandler
    # stored, and resolve() differs behind a symlink.
    resolved = os.path.abspath(path)
    return any(
        isinstance(handler, logging.handlers.RotatingFileHandler)
        and getattr(handler, "baseFilename", None) == resolved
        for handler in logging.getLogger().handlers
    )


class _OneLineFormatter(logging.Formatter):
    """The file's one-record-one-line shape, enforced at the handler.

    A logged untrusted string (a bib title, a parser error) containing
    `\\n2026-... ERROR ...` otherwise forges a second record in the log
    users paste into bug reports (#640). No caller logs `exc_info`, so
    no legitimate multi-line record is lost.
    """

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        return " ".join(line.split("\n")) if "\n" in line else line


def _not_file_only(record: logging.LogRecord) -> bool:
    """False for a record logged with extra={"file_only": True}: stdout
    already carried it."""
    return not getattr(record, "file_only", False)


def _this_project_only(record: logging.LogRecord) -> bool:
    """False for a record from outside `_TREES`.

    Keeps third-party chatter (docling, torch) off the console; their
    WARNING+ still reaches the file.
    """
    return any(record.name == root or record.name.startswith(root + ".") for root in _TREES)


def say(
    logger: logging.Logger,
    message: str,
    *,
    level: int = logging.INFO,
    log_as: str | None = None,
) -> None:
    """Print one line to stdout and mirror it into logs/pipeline.log.

    For output that is a report or a CLI contract: a plain `logger.info`
    would move it to stderr and break callers that parse stdout.
    `file_only` stops the console handler printing it twice. A plain
    print when `configure()` has not run.

    Flushed because stdout is block-buffered under redirection, and the
    tail of an interrupted run is the part worth keeping.

    Whole lines only: an incremental `print(..., end="")` line would
    become several records. Pass `log_as` when the file wants a
    different rendering (one-line JSON) from the terminal (indented).

    **The record is always one line.** Surrounding newlines are
    stripped; an inner newline collapses with its whitespace, because a
    multi-line record breaks grep and tail.
    """
    print(message, flush=True)
    record = (log_as if log_as is not None else message).strip("\n")
    if "\n" in record:
        record = " ".join(record.split())
    logger.log(level, record, extra={"file_only": True})


def configure() -> None:
    """Attach a rotating file handler (logs/pipeline.log) and a stderr handler.

    **CLI-entrypoint-only, and only from inside the pipeline lock**, so
    that at most one process has a handler on the file and `run()` stays
    callable in-process without side effects. 5 MB x 5 is fixed; see
    config.LOGGING_LEVEL for why only the level is a setting.

    The level goes on file_handler, not on the loggers: a logger's
    level gates record creation before any handler, so it would also
    hide the INFO [n/N] progress line on the console. The trees are
    pinned at DEBUG so each handler decides for itself.

    A repeat with the same LOGS_DIR is a no-op; a changed LOGS_DIR
    replaces the old handlers rather than adding to them.
    """
    target = config.LOGS_DIR / "pipeline.log"
    if _already_attached(target):
        return
    _detach_ours()

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        target,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(_OneLineFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
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
