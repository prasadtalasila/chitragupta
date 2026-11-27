"""Choosing and warming the multiprocessing start method before the pool
is actually needed.
"""

import importlib.util
import multiprocessing

from chitragupta import config
from chitragupta.pdf_text._gpu import cuda_is_initialised
from chitragupta.pdf_text._sizing import worker_ceiling

# Imported once in the forkserver and inherited by every worker: 3.2s of
# the ~8.5s a cold worker needs (A40 host). Submodules, not "docling",
# whose top level is mostly re-exports.
_PRELOAD_MODULES = (
    "torch",
    "docling.datamodel.base_models",
    "docling.datamodel.pipeline_options",
    "docling.datamodel.accelerator_options",
    "docling.document_converter",
)


def preload_modules() -> list[str]:
    """_PRELOAD_MODULES, minus anything this machine hasn't got installed.

    **Not a guard against a broken installation**: `find_spec` only
    locates a module, so a torch whose native library fails to load kills
    the forkserver. Left open because spawn fails too, one worker later,
    and probing properly would import torch in the parent.
    """
    available = []
    for name in _PRELOAD_MODULES:
        try:
            if importlib.util.find_spec(name) is not None:
                available.append(name)
        except (ImportError, ValueError):
            # A namespace-package parent, or an unimportable parent.
            pass
    return available


def start_method() -> tuple[str, str | None]:
    """(multiprocessing start method for the docling pool, complaint).

    "forkserver" where available, else "spawn": one shared torch/docling
    import instead of one per worker (the model load cannot be shared).
    The saving comes from prestart_pool.

    **Plain "fork" is not offered**: the parent holds the run lock and the
    ledger as live sqlite connections, which must not cross fork(); a
    child finalising one would roll back the parent's transaction. CUDA
    was not the reason (gpu_count no longer imports torch), and
    forkserver measured no slower. The CUDA check stays because a caller
    (embed_index) may initialise CUDA before the first pool starts.
    """
    requested = config.PARSER_START_METHOD
    available = multiprocessing.get_all_start_methods()
    wanted = "forkserver" if requested == "auto" else requested

    if wanted == "spawn":
        return "spawn", None
    if wanted not in available:
        # Windows has spawn only. Silent under "auto"; reported when the
        # method was named, or the key reads as honoured when it isn't.
        if requested == "auto":
            return "spawn", None
        return "spawn", (
            f"  NOTE [parser].start_method={requested!r} is not available on this "
            f"platform (only {', '.join(available)}) -- using spawn."
        )
    if cuda_is_initialised():
        return "spawn", (
            "  NOTE CUDA is already initialised in this process, so pool workers "
            "cannot be forked from it -- using spawn instead of "
            f"{wanted!r}, which costs 1-2s of pool startup."
        )
    return wanted, None


def prestart_pool() -> None:
    """Start the forkserver now, so its preload runs while the caller
    gets on with something else.

    Workers' concurrent imports are already overlapped; the preload is
    not, so started here it runs while the parent reads the bibliography
    and the pool is ready ~2.5s sooner. `ensure_running()` returns in
    ~0.02s; it is not public API, but a throwaway Process is worse.

    Silently declines when it would be pure cost: not docling,
    [parser].workers = 1, or a machine ceiling of 1 (why worker_ceiling
    exists, so "auto" on a four-core laptop doesn't import torch every
    sync). A run with nothing to parse still pays a background import;
    avoiding that would forgo the overlap.
    """
    if config.PARSER != "docling" or config.PARSER_WORKERS == 1:
        return
    if worker_ceiling(docling=True) <= 1:
        return  # pragma: no cover-windows
    if start_method()[0] != "forkserver":
        return
    # Unreachable on Windows (no forkserver there); see
    # tests/test_pdf_text.py::TestPrestartPool's class-level skip.
    from multiprocessing import forkserver  # pragma: no cover-windows

    ctx = multiprocessing.get_context("forkserver")  # pragma: no cover-windows
    ctx.set_forkserver_preload(preload_modules())  # pragma: no cover-windows
    try:  # pragma: no cover-windows
        forkserver.ensure_running()
    except Exception:  # noqa: BLE001 -- the pool will start one itself  # pragma: no cover-windows
        pass
