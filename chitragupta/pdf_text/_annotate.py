"""Attributing everything a parser backend prints to the citekey it is
currently parsing.

Split out of chitragupta/pdf_text.py (#361). Self-contained: nothing else
in this package calls into `_AnnotatedStream` or `_wrapped` directly,
only `annotated_output`, which `__init__.extract_text` uses.
"""

import contextlib
import contextvars
import sys
import threading
from collections.abc import Iterator
from typing import Any

# The citekey the *current thread* is parsing, or None between documents.
# A context variable rather than a module global (#960): with pdftotext
# and `[parser].workers > 1` the pool is a ThreadPoolExecutor, so one
# process has several documents in flight at once, and a global named
# whichever entered last. Each pool thread runs in its own context, and
# the main thread, which prints sync's own contract lines, never sets it.
_ANNOTATED_CITEKEY: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "annotated_citekey", default=None
)


# The wrappers are installed by the first document to open and removed by
# the last to close, not swapped per document. Swapping per document is
# what broke under threads: in the order A enters, B enters, A exits,
# B exits, B restored what it had found on entry, which was A's wrapper,
# and sync's stdout kept it for the rest of the run.
class _Installed:
    """Which documents are open, and the streams the first one found.
    Written only under `lock`; `open_citekeys` is a tuple, replaced
    whole, so `sole_citekey` can read it from any thread without one."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.open_citekeys: tuple[str, ...] = ()
        self.found_out: Any = None
        self.found_err: Any = None

    def sole_citekey(self) -> str | None:
        """The one open document's citekey, for a thread with none of its own.

        A new thread starts with an empty context, so a thread a backend
        starts itself -- docling runs every pipeline stage, OCR included,
        in one, and RapidOCR's unattributed complaints are what #154 is
        for -- cannot see the citekey of the document that started it.
        With one document open there is only one it can belong to. With
        several, naming any would be the guess #154 removed, and the main
        thread is never given one: it prints sync's own contract lines.
        """
        open_citekeys = self.open_citekeys
        if len(open_citekeys) != 1 or threading.current_thread() is threading.main_thread():
            return None
        return open_citekeys[0]


_INSTALLED = _Installed()


class _AnnotatedStream:
    """A text stream that puts the citekey being parsed *now* at the
    start of every line, and writes through untouched between documents.

    Read at write time rather than fixed at construction, and that is the
    whole design. A library that logs or draws a progress bar resolves
    `sys.stderr` once -- when its handler or its `tqdm` is built -- and
    keeps that object for the rest of the process. Since backends are
    imported lazily *inside* the first document's parse, what they
    capture is this wrapper; a wrapper holding a fixed prefix would then
    label every remaining document in the run with the first one's
    citekey. Looking the citekey up per write turns that capture from a
    bug into the mechanism: whoever holds the wrapper stays correct.

    Line-oriented rather than write-oriented. A backend building one line
    out of several writes (`print(..., end="")`) must not have the
    citekey striped through the middle of it, so the wrapper remembers
    whether the last thing it wrote ended a line and prefixes only when
    the next one starts one. `\\r` counts as ending a line: a progress
    bar redrawing in place is starting the line again, and wants the
    prefix again.

    Everything else is delegated. Docling asks its stream whether it is a
    terminal before deciding how to report progress, so a wrapper that
    answered for it would change the backend's behaviour rather than only
    its formatting.
    """

    def __init__(self, stream) -> None:
        self._stream = stream
        self._at_line_start = True

    def write(self, text: str) -> int:
        if not text:
            return 0
        citekey = _ANNOTATED_CITEKEY.get() or _INSTALLED.sole_citekey()
        # The return value throughout is the count the *caller* wrote,
        # not the count that reached the underlying stream. A caller
        # checking it is asking "did all my text go?", and the prefix is
        # not its text.
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
    """`stream`, annotated -- or `stream` itself if it already is.

    Wrapping twice would print the citekey twice on one line, and a line
    naming the same document twice is noise of exactly the kind this
    exists to remove."""
    return stream if isinstance(stream, _AnnotatedStream) else _AnnotatedStream(stream)


@contextlib.contextmanager
def annotated_output(citekey: str) -> Iterator[None]:
    """Attribute everything a parser backend says to `citekey` (#154).

    With `[parser].ocr` on, RapidOCR reports a page it could not read
    twice -- a bare `print` ("RapidOCR returned empty result!") and a
    `logging` warning ("The text detection result is empty") -- and
    neither names a document. Interleaved with `sync`'s own progress
    lines the obvious inference is available and wrong: `sync` opens
    `[n/N] <citekey>` *before* the slow call, and above one worker there
    are several documents in flight at once, so a complaint sits under
    whichever citekey happened to be announced last.

    One mechanism covers both channels rather than two covering one
    each. The stream is the place they meet: a bare `print` writes to it,
    and so does the `StreamHandler` a logging library installs. Doing it
    twice -- a `logging` record factory *and* the stream -- was tried
    first and prints the citekey twice on every logged line, because the
    handler's own output passes through the stream as well.

    The one thing this cannot reach is a handler that resolved
    `sys.stderr` before the first document was ever parsed. That is not a
    gap so much as the reason `logs/pipeline.log` is safe: `sync`
    configures its handlers up front, so this project's own log format --
    which docs/CLI.md tells a scheduler to grep -- is never rewritten.

    Scoped as narrowly as the citekey is actually known: entered around
    the backend call inside `extract_text` and left immediately after, so
    `sync`'s own stdout -- a documented, diffable contract -- never sees
    a prefix. Restores what it found rather than `sys.__stdout__`, so it
    composes with pytest's capture and with a caller redirecting output.
    "What it found" is what the first of the open documents found, since
    the streams are shared by every thread and wrapped only once.
    """
    token = _ANNOTATED_CITEKEY.set(citekey)
    _open_document(citekey)
    try:
        yield
    finally:
        # Restored on the failing path too: without the `finally`, one
        # unreadable PDF would leave the rest of the run wearing its
        # citekey.
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
