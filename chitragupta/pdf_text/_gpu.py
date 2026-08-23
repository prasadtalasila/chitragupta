"""Which CUDA devices exist and have room for a worker.

Split out of chitragupta/pdf_text.py (#361). Pure discovery: nothing here
mutates process state or claims a device for a particular worker -- that
is `_worker.py`, which calls `usable_devices` at pool-build time via
`_pool.docling_process_pool`.
"""

import os
import shutil
import subprocess
import sys

from chitragupta import config

# nvidia-smi normally answers in tens of milliseconds; a driver in a bad
# state is what makes it hang, and that must not hang a sync that would
# otherwise have run on the CPU.
_NVIDIA_SMI_TIMEOUT = 10.0

# Free device memory below which a card is not worth giving a worker.
#
# Measured on this project's own corpus: a docling worker holding the
# layout, table and OCR models sits at ~1.7 GiB of device memory, on top
# of a CUDA context of its own. 2.5 GiB is that figure with room to be
# wrong in the direction that costs a little speed rather than the one
# that costs the run.
_GPU_MIN_FREE_MIB = 2560


def _parse_visible_devices(total: int) -> "tuple[int, list[int] | None]":
    """(how many devices this process sees, which physical cards they
    are) after CUDA_VISIBLE_DEVICES, which nvidia-smi ignores and every
    CUDA process obeys.

    Without the count, restricting a run to one card would still hand
    worker 3 a `cuda:3` that does not exist in its view, and the worker
    would die on the first convert. torch.cuda.device_count() applies the
    same filter internally, so this is what keeps the nvidia-smi count
    interchangeable with the torch one.

    The second element is the mapping the *count* alone can't give:
    `CUDA_VISIBLE_DEVICES=2,5` makes physical card 2 into `cuda:0` and
    physical card 5 into `cuda:1`, so anything reading per-device figures
    out of nvidia-smi -- which reports physical indices -- has to go
    through it to name the right card. It is None when a UUID was named,
    because resolving one to an index needs torch; usable_devices then
    declines to filter rather than guessing at which card is which.

    Follows CUDA's own documented parsing: enumeration stops at the first
    entry that is not a valid device, so "0,foo,1" means one device, not
    two, and "-1" means none.
    """
    spec = os.environ.get("CUDA_VISIBLE_DEVICES")
    if spec is None:
        return total, list(range(total))
    count, order, resolvable = 0, [], True
    for entry in spec.split(","):
        entry = entry.strip()
        # UUIDs (GPU-..., MIG-...) are accepted as named devices: this
        # cannot check they exist, and over-counting them is no worse
        # than the pre-nvidia-smi behaviour.
        if entry.startswith(("GPU-", "MIG-")):
            count += 1
            resolvable = False
        elif entry.isdigit() and int(entry) < total:
            count += 1
            order.append(int(entry))
        else:
            break
    # Clamped because a UUID cannot be checked against anything: six of
    # them named on a four-card host would otherwise hand out a cuda:5.
    return min(count, total), (order if resolvable else None)


def _visible_devices(total: int) -> int:
    """`total` narrowed by CUDA_VISIBLE_DEVICES."""
    return _parse_visible_devices(total)[0]


def _gpu_free_mib_nvidia_smi() -> "dict[int, int] | None":
    """Free memory per *physical* CUDA device in MiB, or None if
    nvidia-smi can't say.

    Same forgiving contract as _gpu_count_nvidia_smi, and the same reason
    for preferring the driver's own tool to torch: this runs in the
    parent, which must be able to hand a usable CUDA context to a forked
    child, and importing torch here would take that away.
    """
    smi = shutil.which("nvidia-smi")
    if smi is None:
        return None
    try:
        result = subprocess.run(
            [smi, "--query-gpu=index,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True,
            timeout=_NVIDIA_SMI_TIMEOUT, check=False)
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
            # A card the driver can't currently report on prints "[N/A]"
            # rather than a number. Leaving it out of the mapping is what
            # makes usable_devices treat it as "can't tell", which is the
            # same answer it gives when nvidia-smi is missing entirely.
            continue
    return free or None


def usable_devices() -> "tuple[list[int], str | None]":
    """(the CUDA device numbers worth giving a worker, a complaint).

    Round-robin over `range(gpu_count())` assumes every card has room for
    a worker. The run this was written for found GPU 0 already holding
    44.4 GiB of a previous run's orphaned workers: the four workers
    assigned to it could not load a model at all, and -- because a worker
    that fails takes about 19s where a working one takes minutes -- those
    four went on to claim, and fail, 334 of the corpus's 456 documents. A
    poisoned worker is not merely useless, it is *faster* than a working
    one, so the pool feeds it preferentially. Skipping a full card up
    front is the difference between a slower run and a ruined one.

    Forgiving in exactly the way gpu_count is: no nvidia-smi, a reading
    it won't give, or a device list this can't map back to physical cards
    all mean "assume every device is usable". Refusing a GPU on the
    strength of a measurement we don't have would be worse than the
    occasional bad assignment, which _extract_docling now recovers from
    anyway.
    """
    n_gpus = gpu_count()
    if n_gpus <= 0:
        return [], None
    free = _gpu_free_mib_nvidia_smi()
    if free is None:
        return list(range(n_gpus)), None
    # nvidia-smi numbers physical cards from 0 without gaps, so the
    # highest index it reported is the last card -- which is what
    # _parse_visible_devices needs to range-check a CUDA_VISIBLE_DEVICES
    # entry. A card omitted above (an "[N/A]" reading) can make this an
    # undercount, which shortens the mapping and so leaves the devices
    # past it unfiltered: the forgiving answer again.
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
            f"docling worker. Parsing on cuda:"
            + ",".join(str(d) for d in usable) + ".")
    # Every card is full. The CPU is slower -- measured 4.7x over 100
    # documents with OCR off, and 1.8x with it on, since OCR is CPU work
    # either way -- but it is a run that finishes, which is more than the
    # alternative.
    return [], (
        f"  WARNING every GPU is busy ({detail}) -- parsing on the CPU. "
        "Free a card or wait, then re-run to get the GPUs back.")


def _gpu_count_nvidia_smi() -> "int | None":
    """CUDA devices per the driver's own tool, or None if it can't say.

    Preferred over torch because it answers the question without
    importing torch into *this* process: a 1.2s import and ~200MB of RSS
    in a parent that has no other use for it, and -- the reason this
    exists -- a parent that has touched CUDA cannot hand a usable context
    to a forked child. See start_method for what that buys.
    """
    smi = shutil.which("nvidia-smi")
    if smi is None:
        return None
    try:
        result = subprocess.run(
            [smi, "--list-gpus"], capture_output=True, text=True,
            timeout=_NVIDIA_SMI_TIMEOUT, check=False)
    except (OSError, subprocess.SubprocessError):
        # A driver mismatch makes nvidia-smi hang or die rather than
        # print an empty list, and neither is a reason to fail a sync.
        return None
    if result.returncode != 0:
        return None
    return sum(1 for line in result.stdout.splitlines() if line.startswith("GPU "))


def gpu_count() -> int:
    """CUDA devices Docling could use, or 0.

    Deliberately forgiving: no nvidia-smi, no torch, a torch without
    CUDA, or a driver mismatch all mean "no GPUs to spread across", which
    is a perfectly good answer -- not a reason to take down a sync that
    would otherwise have run on the CPU.

    nvidia-smi first, torch second. The fallback matters on a host whose
    driver tools aren't on PATH (a slim container that still passes
    /dev/nvidia* through), where dropping to 0 would silently undo the
    per-worker GPU assignment and put every worker back on cuda:0.
    """
    if config.PARSER != "docling":
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

    Checked through sys.modules rather than by importing torch, so asking
    the question can never be what makes the answer true.

    Deliberately about the observed state rather than about who caused
    it: gpu_count is no longer the only candidate (chitragupta/enrich/embed_index
    runs sentence-transformers, and a library caller may have done
    anything at all before calling in), and a start method chosen from
    "did anyone touch CUDA" is right in all of those cases while one
    chosen from "did we call device_count" is right in none of them.
    """
    torch = sys.modules.get("torch")
    if torch is None:
        return False
    try:
        return bool(torch.cuda.is_initialized())
    except Exception:  # noqa: BLE001  # can't tell, so assume the worst
        return True
