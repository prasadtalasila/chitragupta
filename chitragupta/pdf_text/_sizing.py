"""How many docling workers to run: CPU arithmetic only, no process or
GPU state.
"""

import os

from chitragupta import config

# Logical CPUs one docling worker is *charged*: the `workers = "auto"`
# divisor and the clamp for an explicit request. A full-corpus sweep says
# it is much too large (32 workers ~1.4x faster than 12 on 48 CPUs;
# docs/PERFORMANCE.md, bench/results/2026-08-04-full-corpus/), but it is
# left at 4 because that was validated on one machine and one corpus; see
# bench/PARALLELISM-PLAN.md for what must be measured before moving it.
_CPUS_PER_DOCLING_WORKER = 4

# Docling's own default num_threads: separate from the divisor above,
# which is a CPU budget expected to shrink, so it doesn't move the cap.
_DOCLING_DEFAULT_THREADS = 4


def allowed_cpus() -> int:
    """How many CPUs this *process* may run on -- not how many the
    machine has.

    `os.sched_getaffinity(0)` honours containers, `taskset` and batch
    schedulers (96 CPUs, 48 permitted on the dev host); it is Linux-only,
    hence the getattr (CI has a Windows leg). A cgroup CPU *quota* is not
    seen; an explicit [parser].workers is the answer there.
    """
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is not None:
        return len(getaffinity(0))
    return os.cpu_count() or 1


def worker_ceiling(docling: bool) -> int:
    """The most workers this machine can sustain, whatever the run holds.

    `docling` names whether *this* pool runs Docling workers, not what
    `config.PARSER` says (#502). Independent of the document count, so
    prestart_pool can ask before the bibliography is read.
    """
    cpus = allowed_cpus()
    if docling:
        return max(1, cpus // _CPUS_PER_DOCLING_WORKER)
    # A pdftotext is a short single-threaded subprocess: no docling budget.
    return cpus


def resolve_workers(n_docs: int, docling: bool) -> tuple[int, str | None]:
    """(workers, complaint) for a run that has `n_docs` to parse.

    The smallest of what was asked for, what the machine sustains, and the
    document count (12 model loads for 3 documents is waste), floored at
    1. A request above the ceiling is clamped *and reported*, so nobody
    believes they configured something they didn't.
    """
    cpus = allowed_cpus()
    ceiling = worker_ceiling(docling)

    requested = config.PARSER_WORKERS
    wanted = ceiling if requested == "auto" else requested
    workers = max(1, min(wanted, ceiling, n_docs or 1))

    complaint = None
    if requested != "auto" and requested > ceiling:
        complaint = (
            f"  WARNING [parser].workers={requested} exceeds what this host can "
            f"sustain ({cpus} CPUs available to this process"
            + (f", ~{_CPUS_PER_DOCLING_WORKER} per docling worker" if docling else "")
            + f") -- using {workers}."
        )
    return workers, complaint


def docling_threads(workers: int) -> int:
    """Docling's per-worker thread count, divided down so that
    workers x threads still fits the machine.

    Capped at Docling's default of 4, so a single-worker run is unchanged.
    It barely matters (1-8 threads moved a full-corpus run 1.9%, per
    docs/PERFORMANCE.md); it is kept as the correct division, not for speed.
    """
    return max(1, min(_DOCLING_DEFAULT_THREADS, allowed_cpus() // max(workers, 1)))
