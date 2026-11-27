"""Building the docling worker pool itself: the mp context, the sys.path
guard, and the ProcessPoolExecutor.
"""

import multiprocessing
import os
import sys
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor

from chitragupta.pdf_text._gpu import usable_devices
from chitragupta.pdf_text._startup import preload_modules, start_method
from chitragupta.pdf_text._worker import init_worker

# Stdlib names seen shadowed by a dependency's sys.path entry; only
# `typing`, via OpenCV, so far.
_SHADOWED_STDLIB_NAMES = ("typing",)


def drop_stdlib_shadowing_path_entries() -> list[str]:
    """Remove sys.path entries that would shadow a standard-library
    module, and return what was removed.

    OpenCV (via docling) appends its package directory, which holds a
    `typing/` package, to sys.path. In a **spawned worker** it can land
    ahead of the stdlib, so `import typing` reaches `cv2.dnn` and needs
    `libGL.so.1`: on a slim container every worker dies with an error
    naming OpenCV. The entry survives even a failed `import cv2`. Only a
    directory *inside* site-packages is dropped, never site-packages
    itself.
    """
    removed = []
    # `.copy()`, not redundant: the loop removes from sys.path.
    for entry in sys.path.copy():
        if not entry:
            continue
        parent = os.path.basename(os.path.dirname(entry.rstrip(os.sep)))
        # Must be *inside* an installation directory, or a project dir
        # with its own `typing/` package would be dropped.
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

    Sets forkserver's preload list here so the two cannot drift; it must
    be set before the first Process starts the server, which reads it once.
    """
    drop_stdlib_shadowing_path_entries()
    method, complaint = start_method()
    ctx = multiprocessing.get_context(method)
    if method == "forkserver":
        ctx.set_forkserver_preload(preload_modules())
    return ctx, complaint


def docling_process_pool(workers: int, warn: Callable[[str], None]) -> ProcessPoolExecutor:
    """The one docling ProcessPoolExecutor builder, shared by
    chitragupta/sync.py and chitragupta/enrich/docling_parse.py so they
    cannot drift on what `init_worker` is handed (#290).

    `usable_devices(docling=True)` unconditionally, not re-derived from
    `config.PARSER`: enrich always runs Docling (#502). `warn` is a
    callback because the two callers report differently. Devices are
    queried at build time, since another process can fill a card a
    second later.
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
