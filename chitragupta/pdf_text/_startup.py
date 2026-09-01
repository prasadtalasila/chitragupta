"""Choosing and warming the multiprocessing start method before the pool
is actually needed.

Split out of chitragupta/pdf_text.py (#361). `prestart_pool` is the one
piece of this seam that reaches outside it: it calls
`_sizing.worker_ceiling` to decide whether starting a forkserver is worth
doing at all.
"""

import importlib.util
import multiprocessing

from chitragupta import config
from chitragupta.pdf_text._gpu import cuda_is_initialised
from chitragupta.pdf_text._sizing import worker_ceiling

# Imported once in the forkserver process and inherited by every worker
# it forks, instead of imported separately in each. Measured on the
# documented A40 host: 3.2s of the ~8.5s a cold worker needs to reach its
# first parsed page (1.2s torch, 2.1s docling).
#
# Named submodules rather than bare "docling" because docling's top-level
# package is mostly re-exports -- these are the modules
# _docling_converter actually imports.
_PRELOAD_MODULES = (
    "torch",
    "docling.datamodel.base_models",
    "docling.datamodel.pipeline_options",
    "docling.datamodel.accelerator_options",
    "docling.document_converter",
)


def preload_modules() -> list[str]:
    """_PRELOAD_MODULES, minus anything this machine hasn't got installed.

    Keeps the preload list honest on a pdftotext-only install, where
    naming docling modules would be asking the forkserver to import
    packages that were never installed.

    **This is not a guard against a broken installation**, and it is
    worth being exact about that. `find_spec` only answers "can this
    module be located", not "does importing it work" -- an installed
    torch whose native library fails to load passes this check and then
    raises OSError inside the forkserver, which `forkserver.main()` does
    not swallow (it catches ImportError only). Such a machine gets a dead
    forkserver, and the pool fails when it tries to use it. That is a
    real gap; it is left open because the same installation fails under
    `spawn` too, one worker later, and because probing it properly would
    mean importing torch in the parent -- the exact cost this whole path
    exists to avoid.
    """
    available = []
    for name in _PRELOAD_MODULES:
        try:
            if importlib.util.find_spec(name) is not None:
                available.append(name)
        except (ImportError, ValueError):
            # A namespace-package parent, or a module whose *parent*
            # can't be imported -- either way, not preloadable.
            pass
    return available


def start_method() -> tuple[str, str | None]:
    """(multiprocessing start method for the docling pool, complaint).

    "forkserver" where the platform has it, "spawn" otherwise. The
    difference is one shared import of torch and docling instead of one
    per worker -- 3.2s of the ~8.5s a cold worker needs before its first
    parsed page. The other ~5s is Docling's model load, which no start
    method can share, since `initialized_pipelines` lives on the
    converter instance.

    Choosing forkserver is not on its own worth anything; see
    prestart_pool, which is what turns it into a measured saving.

    **Plain "fork" is not offered**, and the reason is not the one this
    code used to give. The old comment said counting GPUs initialised
    CUDA in the parent, so a forked child would inherit a broken context;
    measured against torch 2.7.1, `torch.cuda.device_count()` goes
    through NVML and leaves `torch.cuda.is_initialized()` False, so that
    hazard was not real here -- and gpu_count no longer imports torch at
    all, so it cannot become real. What rules fork out is the other
    inheritance: this process holds the run lock and the ledger open as
    live sqlite connections, and SQLite's own documentation says not to
    carry an open connection across fork(). A forked worker finalising
    an inherited connection on the way out would be rolling back a
    transaction belonging to a process it is not. forkserver has neither
    problem -- its server is a fresh interpreter, so workers inherit the
    preloaded modules and nothing else -- and it measured *faster* than
    fork (9.6s against 9.7s at four workers), so there is nothing to
    trade off.

    The CUDA check survives anyway, because a caller can initialise CUDA
    in this process by other means (chitragupta/enrich/embed_index does), and
    forkserver's own server process is started by the first pool -- which
    is well after that could have happened.
    """
    requested = config.PARSER_START_METHOD
    available = multiprocessing.get_all_start_methods()
    wanted = "forkserver" if requested == "auto" else requested

    if wanted == "spawn":
        return "spawn", None
    if wanted not in available:
        # Windows has spawn and nothing else. Silent under "auto",
        # because picking what the platform has is exactly what "auto"
        # was asked to do; said out loud when the method was named,
        # because otherwise the key reads as honoured and isn't.
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

    This is where the saving actually comes from, and it is worth being
    precise about why. Workers import torch and docling *concurrently*,
    so on a host with CPUs to spare their import cost is already
    overlapped -- measured, forkserver's preload against spawn's
    per-worker imports is a wash (22.4s against 22.9s over 8 documents at
    4 workers). What is not overlapped is the preload itself: it happens
    when the pool is built, with the parent blocked on it. Started here
    instead, it runs during the ~2.5s the parent spends reading a
    646-entry bibliography, and the pool is ready 2.5s sooner (4.4s
    against 6.9s from process start to four live workers).

    `ensure_running()` returns in ~0.02s -- it launches the server and
    does not wait for its imports -- so this costs the caller nothing to
    call. It is not public API; the alternative is creating a throwaway
    Process purely for its side effect, which is worse.

    Deliberately silent about every reason it might decline: this is an
    optimisation, and a caller that gets a slower pool than it could have
    is not a caller with a problem to report.

    Declines in three cases, because starting a torch-importing process
    for a run that will not use one is pure cost:

    - not the docling backend (pdftotext gets threads, and has no use for
      torch at all);
    - [parser].workers left at its default of 1, i.e. the serial path;
    - this machine's ceiling is 1 regardless of what was asked for, which
      is `workers = "auto"` on anything up to four available CPUs. That
      case is the reason worker_ceiling() exists separately: without it,
      "auto" on a four-core laptop would launch a forkserver and import
      torch on every sync, then run serially anyway.

    What it still cannot know is how many documents need parsing -- that
    needs the bibliography this call is meant to overlap with. So a run
    with nothing to do has paid for a forkserver. That is the one case
    left, it costs a background import rather than any wall clock the
    user waits on, and closing it would mean giving up the overlap that
    is the entire point.
    """
    if config.PARSER != "docling" or config.PARSER_WORKERS == 1:
        return
    if worker_ceiling(docling=True) <= 1:
        return  # pragma: no cover-windows
    if start_method()[0] != "forkserver":
        return
    # Unreachable on Windows: start_method() never returns "forkserver"
    # there (multiprocessing has no such start method on that platform),
    # so this line is always past the return above -- see
    # tests/test_pdf_text.py::TestPrestartPool's own class-level skip for
    # the same fact stated on the test side.
    from multiprocessing import forkserver  # pragma: no cover-windows

    ctx = multiprocessing.get_context("forkserver")  # pragma: no cover-windows
    ctx.set_forkserver_preload(preload_modules())  # pragma: no cover-windows
    try:  # pragma: no cover-windows
        forkserver.ensure_running()
    except Exception:  # noqa: BLE001 -- the pool will start one itself  # pragma: no cover-windows
        pass
