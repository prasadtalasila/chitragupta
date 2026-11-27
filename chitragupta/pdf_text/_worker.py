"""Which GPU *this* worker process claimed, and what to do when it runs
out of room on it.
"""

import sys

# The CUDA device this worker was assigned, or None to leave Docling's
# AUTO resolution alone. Set once per worker at pool startup.
_WORKER_DEVICE = None


def worker_device() -> str | None:
    """The CUDA device this worker claimed, or None if it claimed none."""
    return _WORKER_DEVICE


def _reset_worker_device() -> None:
    """Test hook -- module state otherwise leaks between tests."""
    global _WORKER_DEVICE
    _WORKER_DEVICE = None
    # Deferred: _converter imports this module, so top-level is circular.
    from chitragupta.pdf_text._converter import _reset_docling_converter

    _reset_docling_converter()


def init_worker(counter, lock, devices) -> None:
    """Pool initialiser: claim one GPU for this worker, round-robin.

    Docling's AUTO resolves to `cuda:0` in *every* process (12 workers
    measured no faster than 4, GPU 0 pinned). `devices` is
    usable_devices()'s list, so a full card is never handed out. A shared
    counter under a lock, not PID or position: the executor starts
    workers lazily and does not number them.
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

    Matched on the message: a driver refusal arrives as a bare
    `RuntimeError` with no dedicated type (240 of 334 in the run this
    comes from), not only as `torch.OutOfMemoryError`.
    """
    text = str(exc)
    return "CUDA out of memory" in text or "CUDA error: out of memory" in text


def _demote_to_cpu() -> None:
    """Give up on this worker's GPU and carry on without one.

    A worker with no device memory fails documents fast, so the pool feeds
    it preferentially (334 of 456 documents failed on one full card);
    the CPU makes it merely slower. Changing _WORKER_DEVICE rebuilds the
    cached converter, whose key includes it.
    """
    global _WORKER_DEVICE
    _WORKER_DEVICE = "cpu"
    # A bare print, not sync's logger: this runs in a worker process with
    # no route back to the parent's handlers; it reaches the terminal via
    # stderr but not logs/pipeline.log.
    print(
        "  WARNING a parse worker ran out of GPU memory -- it has fallen back "
        "to the CPU for the rest of this run, which is slower but finishes. "
        "Another process is most likely holding the card.",
        file=sys.stderr,
    )
