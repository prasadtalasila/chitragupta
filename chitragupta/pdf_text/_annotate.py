"""Attributing everything a parser backend prints to the citekey it is
currently parsing (#154). Only `annotated_output` is used from outside.
"""

import contextlib
import contextvars
import sys
import threading
from collections.abc import Iterator
from typing import Any

# A context variable, not a module global (#960): with pdftotext and
# `[parser].workers > 1` the pool is threaded, so several documents are in
# flight in one process. The main thread, which prints sync's own contract
# lines, never sets it.
_ANNOTATED_CITEKEY: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "annotated_citekey", default=None
)


# Installed by the first document to open and removed by the last, not
# swapped per document: under threads, swapping left sync's stdout wearing
# another document's wrapper for the rest of the run.
class _Installed:
    """Which documents are open, and the streams the first one found.
    `open_citekeys` is a tuple replaced whole under `lock`, so
    `sole_citekey` can read it from any thread without one."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.open_citekeys: tuple[str, ...] = ()
        self.found_out: Any = None
        self.found_err: Any = None

    def sole_citekey(self) -> str | None:
        """The one open document's citekey, for a thread with none of its own.

        A thread a backend starts itself (docling runs its stages, OCR
        included, in one) cannot see the starting document's context. With
        several open, naming any would be the guess #154 removed; the main
        thread never gets one.
        """
        open_citekeys = self.open_citekeys
        if len(open_citekeys) != 1 or threading.current_thread() is threading.main_thread():
            return None
        return open_citekeys[0]


_INSTALLED = _Installed()


class _AnnotatedStream:
    """A text stream that puts the citekey being parsed *now* at the
    start of every line, and writes through untouched between documents.

    Read at write time, not fixed at construction: libraries capture
    `sys.stderr` once, lazily inside the first parse, so a fixed prefix
    would label every later document with the first one's citekey.

    Line-oriented: prefixes only when a new line starts, so a line built
    from several writes is not striped; `\\r` counts as ending a line, so
    a redrawn progress bar is prefixed again. Everything else (isatty
    included) is delegated, so docling's behaviour does not change.
    """

    def __init__(self, stream) -> None:
        self._stream = stream
        self._at_line_start = True

    def write(self, text: str) -> int:
        if not text:
            return 0
        citekey = _ANNOTATED_CITEKEY.get() or _INSTALLED.sole_citekey()
        # Returns the count the *caller* wrote; the prefix is not its text.
        if citekey is None:
            self._stream.write(text)
            self._at_line_start = text.endswith(("\n", "\r"))
            return len(text)
        prefix = f"[{citekey}] "
        pieces = []
        for line in text.splitlines(keepends=True):
            if self._at_line_start:
                pieces.append(prefix)
            pieces.append(line)
            self._at_line_start = line.endswith(("\n", "\r"))
        self._stream.write("".join(pieces))
        return len(text)

    def __getattr__(self, name) -> Any:
        return getattr(self._stream, name)


def _wrapped(stream) -> Any:
    """`stream`, annotated -- or `stream` itself if it already is, so the
    citekey is never printed twice on one line."""
    return stream if isinstance(stream, _AnnotatedStream) else _AnnotatedStream(stream)


@contextlib.contextmanager
def annotated_output(citekey: str) -> Iterator[None]:
    """Attribute everything a parser backend says to `citekey` (#154).

    RapidOCR's empty-page complaints (a bare `print` and a `logging`
    warning) name no document, and with several in flight sit under
    whichever citekey sync announced last. The stream is where both
    channels meet; also wrapping logging records was tried and printed the
    citekey twice per logged line.

    Handlers that resolved `sys.stderr` before the first parse are not
    reached, which keeps `logs/pipeline.log` (grepped per docs/CLI.md)
    unrewritten. Scoped to the backend call so sync's own stdout contract
    never sees a prefix; restores what it found, not `sys.__stdout__`, so
    it composes with pytest's capture.
    """
    token = _ANNOTATED_CITEKEY.set(citekey)
    _open_document(citekey)
    try:
        yield
    finally:
        # In `finally`, or one unreadable PDF would leave the rest of the
        # run wearing its citekey.
        _close_document(citekey)
        _ANNOTATED_CITEKEY.reset(token)


def _open_document(citekey: str) -> None:
    """Count `citekey` open, wrapping the streams if it is the first."""
    with _INSTALLED.lock:
        if not _INSTALLED.open_citekeys:
            _INSTALLED.found_out, _INSTALLED.found_err = sys.stdout, sys.stderr
            sys.stdout, sys.stderr = _wrapped(sys.stdout), _wrapped(sys.stderr)
        _INSTALLED.open_citekeys += (citekey,)


def _close_document(citekey: str) -> None:
    """Count `citekey` finished, restoring the streams if it was the last."""
    with _INSTALLED.lock:
        remaining = list(_INSTALLED.open_citekeys)
        remaining.remove(citekey)
        _INSTALLED.open_citekeys = tuple(remaining)
        if not remaining:
            sys.stdout, sys.stderr = _INSTALLED.found_out, _INSTALLED.found_err
            _INSTALLED.found_out = _INSTALLED.found_err = None
