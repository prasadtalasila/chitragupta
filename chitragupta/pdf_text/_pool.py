"""Building the docling worker pool itself: the mp context, the sys.path
guard, and the ProcessPoolExecutor.

Split out of chitragupta/pdf_text.py (#361). The one seam that reaches
across every other piece of this package -- `docling_process_pool` needs
a start method (`_startup`), the GPUs worth using (`_gpu`), and the
per-worker initialiser (`_worker`) -- because building the pool is where
all three questions have to be answered at once.
"""

import multiprocessing
import os
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor

from chitragupta.pdf_text._gpu import usable_devices
from chitragupta.pdf_text._startup import preload_modules, start_method
from chitragupta.pdf_text._worker import init_worker

# Standard-library top-level names we have actually seen shadowed by a
# path entry a dependency added to sys.path. Only `typing` so far, and
# only via OpenCV -- but the list is the mechanism, not the diagnosis.
_SHADOWED_STDLIB_NAMES = ("typing",)


def drop_stdlib_shadowing_path_entries() -> list[str]:
    """Remove sys.path entries that would shadow a standard-library
    module, and return what was removed.

    OpenCV -- pulled in transitively by docling -- appends its own package
    directory to sys.path when imported, and that directory contains a
    `typing/` package. On this process it usually loses the race against
    the standard library, so nothing is visibly wrong. In a **spawned
    worker** it does not: spawn rebuilds sys.path from the parent's, the
    cv2 entry can land ahead of the stdlib, and `import typing` then
    resolves to `cv2.typing`, which imports `cv2.dnn`, which needs
    `libGL.so.1`.

    On a host without that library -- any slim container -- the import
    fails and every worker dies before it runs a line of this project's
    code. The parse then reports every document as failed for a reason
    that names OpenCV and mentions neither PDFs nor docling.

    Worse, the failure survives its cause: `import cv2` leaves the path
    entry behind even when the import itself raises, so a host where
    OpenCV is merely *broken* poisons workers exactly like one where it
    works.

    Called before a pool is built, so children inherit a clean path.
    Deliberately conservative: an entry is only dropped if it is a
    directory *inside* site-packages that contains one of the shadowing
    names, so a site-packages directory itself is never removed even if
    something has installed a top-level `typing` backport into it.
    """
    removed = []
    # A copy, spelled `.copy()` so it cannot be misread (or "cleaned up")
    # as a redundant cast: the loop body removes entries from sys.path,
    # and mutating the list being iterated skips the element after each
    # removal.
    for entry in sys.path.copy():
        if not entry:
            continue
        parent = os.path.basename(os.path.dirname(entry.rstrip(os.sep)))
        # The entry must be a package directory *inside* an installation
        # directory. Checking only that the entry itself isn't named
        # site-packages would still drop, say, a project directory that
        # happens to contain a `typing/` package of its own.
        if parent not in {"site-packages", "dist-packages"}:
            continue
        for name in _SHADOWED_STDLIB_NAMES:
            if os.path.isfile(os.path.join(entry, name, "__init__.py")):
                sys.path.remove(entry)
                removed.append(entry)
                break
    return removed


def process_pool_context() -> tuple[multiprocessing.context.BaseContext, str | None]:
    """The mp context to build the docling pool on, plus any complaint
    about how it was chosen.

    Sets forkserver's preload list as a side effect, because that is the
    entire reason for preferring forkserver and the two must not drift
    apart. It has to be set before the first Process is created: the
    server is started lazily by that call and imports its preload list
    once, so a list set afterwards would be read by nothing.
    """
    drop_stdlib_shadowing_path_entries()
    method, complaint = start_method()
    ctx = multiprocessing.get_context(method)
    if method == "forkserver":
        ctx.set_forkserver_preload(preload_modules())
    return ctx, complaint


def docling_process_pool(workers: int, warn: Callable[[str], None]) -> ProcessPoolExecutor:
    """The one docling ProcessPoolExecutor builder, shared by chitragupta/sync.py
    and chitragupta/enrich/docling_parse.py so the two cannot silently drift on
    what `init_worker` is handed -- see #290. Both already import this
    package, so this costs no new dependency edge.

    Always builds a *Docling* pool -- the name says so, and both callers
    only ever call it to run Docling workers -- so `usable_devices` is
    asked with `docling=True` unconditionally. It is *not* re-derived from
    `config.PARSER` here: that setting is `chitragupta/sync.py`'s own choice of
    backend, but `chitragupta/enrich/` always runs Docling regardless of it,
    and re-deriving "is this a Docling pool" from `config.PARSER` made every
    GPU on a `pdftotext`-configured host invisible to enrich's pool -- see
    #502.

    `warn` is a `str -> None` callback rather than a fixed logger, because
    the two callers report a complaint differently: chitragupta/sync.py logs it
    plainly, chitragupta/enrich/docling_parse.py mirrors it to stdout via
    logging_setup.say. Passing the callback keeps that choice with the
    caller instead of forcing one convention on both.

    usable_devices() is queried here, at pool-build time, rather than
    earlier and passed in -- the free-card answer is only true for as
    long as it takes to start the workers, since another process can
    fill a card a second later. One GPU per worker, round-robin; see
    init_worker's docstring for why a poisoned or full card must be
    skipped rather than merely counted.
    """
    ctx, complaint = process_pool_context()
    if complaint:
        warn(complaint)
    devices, gpu_complaint = usable_devices(docling=True)
    if gpu_complaint:
        warn(gpu_complaint)
    return ProcessPoolExecutor(
        max_workers=workers,
        mp_context=ctx,
        initializer=init_worker,
        initargs=(ctx.Value("i", 0), ctx.Lock(), devices),
    )
