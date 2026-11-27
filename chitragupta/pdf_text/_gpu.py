"""Which CUDA devices exist and have room for a worker.

Pure discovery: claiming a device for a worker is `_worker.py`.
"""

import os
import subprocess
import sys

from chitragupta import programs

# A driver in a bad state hangs nvidia-smi, which must not hang a sync
# that could have run on the CPU.
_NVIDIA_SMI_TIMEOUT = 10.0

# Free device memory below which a card is not worth giving a worker: a
# docling worker sits at ~1.7 GiB plus its own CUDA context, with margin.
_GPU_MIN_FREE_MIB = 2560


def _parse_visible_devices(total: int) -> "tuple[int, list[int] | None]":
    """(how many devices this process sees, which physical cards they
    are) after CUDA_VISIBLE_DEVICES, which nvidia-smi ignores and every
    CUDA process obeys.

    Without the count, a restricted run would hand a worker a `cuda:3` that
    does not exist in its view. The mapping is needed because nvidia-smi
    reports physical indices (`=2,5` makes card 5 `cuda:1`); it is None
    when a UUID was named, since resolving one needs torch. Follows CUDA's
    parsing: enumeration stops at the first invalid entry, "-1" means none.
    """
    spec = os.environ.get("CUDA_VISIBLE_DEVICES")
    if spec is None:
        return total, list(range(total))
    count, order, resolvable = 0, [], True
    for entry in spec.split(","):
        entry = entry.strip()
        # UUIDs are accepted unchecked as named devices.
        if entry.startswith(("GPU-", "MIG-")):
            count += 1
            resolvable = False
        elif entry.isdigit() and int(entry) < total:
            count += 1
            order.append(int(entry))
        else:
            break
    # Clamped: six UUIDs on a four-card host would otherwise hand out cuda:5.
    return min(count, total), (order if resolvable else None)


def _visible_devices(total: int) -> int:
    """`total` narrowed by CUDA_VISIBLE_DEVICES."""
    return _parse_visible_devices(total)[0]


def _gpu_free_mib_nvidia_smi() -> "dict[int, int] | None":
    """Free memory per *physical* CUDA device in MiB, or None if
    nvidia-smi can't say. Not torch: importing it in the parent would stop
    it handing a usable CUDA context to a forked child.
    """
    smi = programs.resolve_program("nvidia-smi")
    if smi is None:
        return None
    try:
        result = subprocess.run(
            [smi, "--query-gpu=index,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=_NVIDIA_SMI_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    free = {}
    for line in result.stdout.splitlines():
        index, _, mib = line.partition(",")
        try:
            free[int(index)] = int(mib)
        except ValueError:
            # "[N/A]" for a card the driver can't report on: left out, so
            # usable_devices treats it as "can't tell".
            continue
    return free or None


def usable_devices(docling: bool) -> "tuple[list[int], str | None]":
    """(the CUDA device numbers worth giving a worker, a complaint), for
    a pool that will (`docling=True`) or will not run Docling workers.

    A full card must be skipped up front: a worker that cannot load a
    model fails in ~19s where a working one takes minutes, so the pool
    feeds poisoned workers preferentially (one run lost 334 of 456
    documents to a GPU full of orphaned workers). Forgiving like
    gpu_count: no reading or no mapping means "every device is usable".
    """
    n_gpus = gpu_count(docling)
    if n_gpus <= 0:
        return [], None
    free = _gpu_free_mib_nvidia_smi()
    if free is None:
        return list(range(n_gpus)), None
    # nvidia-smi numbers physical cards from 0 without gaps, so the highest
    # index is the last card. An omitted "[N/A]" card can undercount, which
    # leaves later devices unfiltered: the forgiving answer again.
    _, physical = _parse_visible_devices(max(free) + 1)
    if physical is None:
        return list(range(n_gpus)), None
    usable, skipped = [], []
    for device in range(n_gpus):
        mib = free.get(physical[device]) if device < len(physical) else None
        if mib is None or mib >= _GPU_MIN_FREE_MIB:
            usable.append(device)
        else:
            skipped.append(f"cuda:{device} ({mib / 1024:.1f} GiB free)")
    if not skipped:
        return usable, None
    detail = ", ".join(skipped)
    if usable:
        return usable, (
            f"  WARNING skipping {detail} -- under "
            f"{_GPU_MIN_FREE_MIB / 1024:.1f} GiB free, which is not enough for a "
            f"docling worker. Parsing on cuda:" + ",".join(str(d) for d in usable) + "."
        )
    # Every card is full. The CPU is slower (4.7x with OCR off, 1.8x on)
    # but it finishes.
    return [], (
        f"  WARNING every GPU is busy ({detail}) -- parsing on the CPU. "
        "Free a card or wait, then re-run to get the GPUs back."
    )


def _gpu_count_nvidia_smi() -> "int | None":
    """CUDA devices per the driver's own tool, or None if it can't say.

    Preferred over torch, whose import costs 1.2s and ~200MB and, above
    all, would stop the parent handing a usable CUDA context to a forked
    child (see start_method).
    """
    smi = programs.resolve_program("nvidia-smi")
    if smi is None:
        return None
    try:
        result = subprocess.run(
            [smi, "--list-gpus"],
            capture_output=True,
            text=True,
            timeout=_NVIDIA_SMI_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        # A driver mismatch makes nvidia-smi hang or die; not a reason to
        # fail a sync.
        return None
    if result.returncode != 0:
        return None
    return sum(1 for line in result.stdout.splitlines() if line.startswith("GPU "))


def gpu_count(docling: bool) -> int:
    """CUDA devices Docling could use, or 0.

    `docling` names whether *this pool* runs Docling workers, not whether
    `config.PARSER` says "docling": enrichment always runs Docling, and
    gating on the config hid every GPU on a pdftotext host (#502).
    Forgiving: any failure means 0, never a failed sync. Falls back to
    torch for hosts without nvidia-smi on PATH (slim containers), where 0
    would put every worker back on cuda:0.
    """
    if not docling:
        return 0
    counted = _gpu_count_nvidia_smi()
    if counted is not None:
        return _visible_devices(counted)
    try:
        import torch

        return torch.cuda.device_count()
    except Exception:  # noqa: BLE001 -- see docstring: any failure means 0
        return 0


def cuda_is_initialised() -> bool:
    """Has *this* process already got a live CUDA context?

    Checked through sys.modules, so asking can't make the answer true.
    About observed state, not who caused it: embed_index or a library
    caller may have touched CUDA, so only this is right for choosing a
    start method.
    """
    torch = sys.modules.get("torch")
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_initialized())
    except Exception:  # noqa: BLE001  # can't tell, so assume the worst
        return True
