"""How many docling workers to run: CPU arithmetic only, no process or
GPU state.

Split out of chitragupta/pdf_text.py (#361). `allowed_cpus` is the one
function every other name below (and `_startup.prestart_pool`, across
the package boundary) ultimately calls, so it lives with its three
direct callers rather than the module that only reads its answer.
"""

import os

from chitragupta import config

# Logical CPUs one docling worker is *charged*. Used both as the divisor
# for `workers = "auto"` and as the ceiling an explicit request is
# clamped to.
#
# The 4 came from a single docling process measured holding ~300% CPU, on
# the reasoning that "one worker per CPU" would then oversubscribe by
# about 4x.
#
# **A full-corpus sweep does not support it.** Measured over all 501 PDFs
# (docs/PERFORMANCE.md, bench/results/2026-08-04-full-corpus/):
#   - 32 workers is ~1.4x faster than the 12 this constant allows on a
#     48-CPU machine, and 48 workers is no worse;
#   - docling's own num_threads changes a run by 1.9% -- noise -- so a
#     worker is not doing four CPUs of parallel work.
# Past ~32 workers the curve plateaus rather than reversing (32 and 48
# land within 0.9% over three runs each), so the finding is "this divisor
# is much too large", not "it should be 1.5".
#
# Left at 4 deliberately: changing it alters what every run does on every
# machine, and it has been validated on exactly one machine and one
# corpus. See bench/PARALLELISM-PLAN.md's open questions for what would
# have to be measured before moving it.
_CPUS_PER_DOCLING_WORKER = 4

# Docling's own default num_threads. Equal to the divisor above today,
# and deliberately a separate constant: that one is a CPU budget and the
# roadmap expects it to shrink, while this one tracks upstream's default.
# Sharing a literal would have quietly changed the thread cap the first
# time the budget moved.
_DOCLING_DEFAULT_THREADS = 4


def allowed_cpus() -> int:
    """How many CPUs this *process* may run on -- not how many the
    machine has.

    `os.cpu_count()` reports the machine. `os.sched_getaffinity(0)`
    reports the affinity mask actually in force, which a container,
    `taskset`, or a batch scheduler will have narrowed. On the host this
    was developed on the two disagree badly: 96 CPUs exist, 48 are
    permitted, so sizing a pool off `cpu_count()` would spawn twice as
    many workers as there are CPUs to run them.

    `sched_getaffinity` is Linux-only -- it does not exist on Windows or
    macOS, and this project's CI has a windows-latest leg -- hence the
    getattr rather than a bare call.

    Not covered: a cgroup CPU *quota* (`docker --cpus=2`) throttles
    without narrowing the affinity mask, so this still reports the full
    set there. config.toml.example says so, and an explicit
    [parser].workers is the answer on such a host.
    """
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is not None:
        return len(getaffinity(0))
    return os.cpu_count() or 1


def worker_ceiling() -> int:
    """The most workers this machine can sustain, whatever the run holds.

    Split out from resolve_workers because it is the one ceiling that
    does *not* depend on how many documents there are, so it can be asked
    before the bibliography has been read -- which is what lets
    prestart_pool decline on a machine that will end up serial anyway.
    """
    cpus = allowed_cpus()
    if config.PARSER == "docling":
        return max(1, cpus // _CPUS_PER_DOCLING_WORKER)
    # Each pdftotext is a short, single-threaded subprocess, so charging
    # it a docling worker's CPU budget would under-use the machine.
    return cpus


def resolve_workers(n_docs: int) -> tuple[int, str | None]:
    """(workers, complaint) for a run that has `n_docs` to parse.

    The resolved count is the smallest of three independent ceilings,
    floored at 1: what was asked for, what the machine can sustain, and
    how many documents there actually are. The third matters more than it
    looks -- standing up 12 docling workers to parse 3 documents pays 12
    model loads to save two documents' worth of work.

    An explicit request above the machine's ceiling is clamped *and
    reported*. Obeying it thrashes; ignoring it silently leaves someone
    believing they configured something they didn't.
    """
    cpus = allowed_cpus()
    ceiling = worker_ceiling()

    requested = config.PARSER_WORKERS
    wanted = ceiling if requested == "auto" else requested
    workers = max(1, min(wanted, ceiling, n_docs or 1))

    complaint = None
    if requested != "auto" and requested > ceiling:
        complaint = (
            f"  WARNING [parser].workers={requested} exceeds what this host can "
            f"sustain ({cpus} CPUs available to this process"
            + (f", ~{_CPUS_PER_DOCLING_WORKER} per docling worker"
               if config.PARSER == "docling" else "")
            + f") -- using {workers}."
        )
    return workers, complaint


def docling_threads(workers: int) -> int:
    """Docling's per-worker thread count, divided down so that
    workers x threads still fits the machine.

    Capped at Docling's own default of 4, so the single-worker default
    resolves to exactly what Docling would have picked on its own and
    this function changes nothing until someone raises [parser].workers.

    **This matters far less than it looks.** Forcing the value to 1, 2, 4
    or 8 at 12 workers moved a full-corpus run by 1.9% -- noise (see
    docs/PERFORMANCE.md). The 8 case needed a temporary bench override,
    since the cap above puts it out of reach of any shipped
    configuration. It is kept because dividing down is still the
    correct thing to do when workers x threads would exceed the machine,
    not because it buys measurable throughput.
    """
    return max(1, min(_DOCLING_DEFAULT_THREADS, allowed_cpus() // max(workers, 1)))
