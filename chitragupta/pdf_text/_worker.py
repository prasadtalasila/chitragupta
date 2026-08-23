"""Which GPU *this* worker process claimed, and what to do when it runs
out of room on it.

Split out of chitragupta/pdf_text.py (#361). `_WORKER_DEVICE` is set once
per worker at pool startup (`init_worker`) and read by `_converter.py`'s
cache key through `worker_device()` -- the accessor that already existed
for exactly this cross-module read, per its own docstring below -- rather
than by reaching into this module's global directly.
"""

import sys

# The CUDA device this worker process was assigned, or None to leave
# Docling's own AUTO resolution alone. Process-global because it is set
# once per worker, at pool startup, and read whenever that worker builds
# a converter.
_WORKER_DEVICE = None


def worker_device() -> str | None:
    """The CUDA device this worker claimed, or None if it claimed none.

    The public read of the process-global set by init_worker, so other
    modules (chitragupta/enrich/docling_parse.py) don't reach into this one's
    internals to build their own converters.
    """
    return _WORKER_DEVICE


def _reset_worker_device() -> None:
    """Test hook -- module state otherwise leaks between tests."""
    global _WORKER_DEVICE
    _WORKER_DEVICE = None
    # Deferred: _converter imports worker_device from this module, so a
    # top-level import here would be circular. Cheap after the first
    # call -- a sys.modules lookup, same as every other import.
    from chitragupta.pdf_text._converter import _reset_docling_converter

    _reset_docling_converter()


def init_worker(counter, lock, devices) -> None:
    """Pool initialiser: claim one GPU for this worker, round-robin.

    Docling's `AcceleratorDevice.AUTO` resolves to `cuda:0` in *every*
    process, so without this, N workers all pile onto one card. Measured
    on this project's corpus before it existed: at 12 workers GPU 0 ran
    pinned at 100% while GPUs 1-3 sat at 0%, and 12 workers were no
    faster than 4.

    `devices` is usable_devices()'s list rather than a device *count*,
    so a card with no memory free is never handed out -- the round-robin
    walks the cards that can actually take a worker, and an empty list
    leaves docling's own AUTO resolution alone.

    The index comes from a shared counter rather than the worker's PID or
    position, because a ProcessPoolExecutor neither numbers its workers
    nor guarantees it starts all of them -- it creates them lazily, as
    work arrives. A counter handed out under a lock is the only thing
    that gives each *live* worker a distinct index.
    """
    global _WORKER_DEVICE
    devices = list(devices)
    if not devices:
        _WORKER_DEVICE = None
        return
    with lock:
        index = counter.value
        counter.value += 1
    _WORKER_DEVICE = f"cuda:{devices[index % len(devices)]}"


def is_cuda_oom(exc: BaseException) -> bool:
    """Does this exception mean the GPU had no memory left?

    Matched on the message rather than the type because the two shapes it
    arrives in are different classes: `torch.OutOfMemoryError` for an
    allocation torch made itself ("CUDA out of memory. Tried to allocate
    20.00 MiB"), and a bare `RuntimeError` for one the driver refused
    underneath it ("CUDA error: out of memory"), which has no dedicated
    type to catch. The run this comes from had 240 of the second and 94
    of the first, so matching only the type with a name would have missed
    the larger half.
    """
    text = str(exc)
    return "CUDA out of memory" in text or "CUDA error: out of memory" in text


def _demote_to_cpu() -> None:
    """Give up on this worker's GPU and carry on without one.

    A worker that cannot get device memory fails a document in about 19s
    where a working one takes minutes, so the pool -- which hands the
    next document to whichever worker is free first -- feeds the broken
    one preferentially. In the run this comes from, four workers of 24
    were on a card another process had filled, and they claimed and
    failed 334 of 456 documents between them. Falling back to the CPU
    turns that worker from an attractor for the whole queue back into a
    worker that is merely slower.

    No cache to clear: _converter._docling_converter is keyed on
    _WORKER_DEVICE (read through worker_device()), so moving the device
    is what rebuilds it.
    """
    global _WORKER_DEVICE
    _WORKER_DEVICE = "cpu"
    # Deliberately still a bare print, not chitragupta.sync's logger: this runs
    # inside a docling worker *process* (forkserver/spawn, never plain
    # fork -- see _executor_for's docstring), which has no handler of its
    # own and no route back to the parent's without a QueueHandler this
    # project has chosen not to build for one rare message. It still
    # reaches the terminal via the worker's inherited stderr fd, same as
    # before; it just won't appear in logs/pipeline.log.
    print(
        "  WARNING a parse worker ran out of GPU memory -- it has fallen back "
        "to the CPU for the rest of this run, which is slower but finishes. "
        "Another process is most likely holding the card.",
        file=sys.stderr,
    )
