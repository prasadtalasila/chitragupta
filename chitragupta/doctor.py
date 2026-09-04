"""`chitragupta doctor`: probe the environment, report, never install.

An aid, not a gate (SOUL.md, docs/HOOKS.md): it never installs anything
and always exits 0, in the same shape `chitragupta/enrich/__main__.py`'s
per-stage probes already use -- a status word and a detail. The word
differs because the probe does: that layer reports `ok`/`skipped` for a
Python package, and only a probe for a binary on `PATH`, which is this
module's job and not that layer's, can report `missing-binary`. "Probe
for a toolchain; never assume one, in either direction"
(DEVELOPER-AGENTS.md).

Four checks, none of them fatal to run without:

1. **OS binaries pip cannot supply** -- pandoc, pdflatex, pdftotext, vale.
   `python -m chitragupta.draft render`/`style` already probe these
   themselves and report per-call; this is the same probe, run once, up
   front, so a user finds out before their first render rather than at it.
2. **Is the `enrich` extra importable?** `pip install chitragupta-cli`
   alone gives tier 1 and tier 2 (docs/CLI.md); this says whether tier 3
   is there too, without importing anything from `chitragupta.enrich`
   itself (this module stays standard-library-adjacent, like
   `chitragupta/hook_launchers.py`).
3. **Does the installed torch match this host's GPU driver?** The
   regression #265 accepts and only partially fixes: `pip install
   'chitragupta-cli[enrich]'` on a CUDA host still lands a CPU-only torch
   wheel, silently (`scripts/install_full_pipeline.sh`'s `ensure_gpu_torch`
   states why). Detected here; `chitragupta install gpu-torch` is the fix
   this names.
4. **Does another distribution provide `chitragupta`/`cg`?** The
   collision #269 accepts on the condition that it stops being silent --
   `chitragupta` 0.1.1 on PyPI (an unrelated "pytest for prompts" tool)
   declares the same console scripts and the same top-level import name.
"""

import argparse
import importlib.metadata
import importlib.util
import shutil
import sys

from chitragupta.progname import prog_for

DESCRIPTION = (
    "Report the toolchain's state -- OS binaries, the enrich "
    "extra, torch vs. the GPU driver, a competing distribution."
)

# What python -m chitragupta.draft render/style already probe for
# themselves, per call. Doctor probes the same four, once, up front.
BINARIES = ("pandoc", "pdflatex", "pdftotext", "vale")

THIS_DISTRIBUTION = "chitragupta-cli"
CONSOLE_SCRIPTS = ("chitragupta", "cg")


def _check_binaries() -> list[str]:
    found = []
    for binary in BINARIES:
        path = shutil.which(binary)
        if path:
            found.append(f"[ok] {binary} found: {path}")
        else:
            found.append(f"[missing-binary] {binary} not found on PATH")
    return found


# Every top-level import name the `enrich` extra installs, in
# `pyproject.toml`'s `[tool.poetry.extras]` order. Import names, not
# distribution names, because that is what a stage actually does and what
# a partial install actually breaks -- `sentence-transformers` imports as
# `sentence_transformers`.
ENRICH_MODULES = (
    "torch",
    "torchvision",
    "sentence_transformers",
    "chromadb",
    "bertopic",
    "docling",
    "adapters",
    "scipy",
    "pypdfium2",
)


def _check_enrich_extra() -> str:
    """Every module the extra installs, not one of them (#509/m-35).

    Probing `sentence_transformers` alone reported the whole tier ok on a
    host that had it and nothing else -- so `doctor` passed and the run
    then failed at the first stage that reached for `docling`, which is
    the opposite of what a preflight is for. A partial install is the
    likely state, not a contrived one: the packages are large, and a
    failed or interrupted `pip install ...[enrich]` leaves exactly this.
    """
    missing = [module for module in ENRICH_MODULES if importlib.util.find_spec(module) is None]
    if not missing:
        return "[ok] the enrich extra is importable"
    if len(missing) == len(ENRICH_MODULES):
        return (
            "[missing] the enrich extra is not installed -- pip install 'chitragupta-cli[enrich]'"
        )
    return (
        f"[missing] the enrich extra is installed but incomplete: {', '.join(missing)} "
        "-- pip install 'chitragupta-cli[enrich]'"
    )


def _check_gpu_torch() -> str:
    if not shutil.which("nvidia-smi"):
        return "[ok] no GPU detected (nvidia-smi absent) -- the default CPU wheel is correct"
    try:
        import torch  # pylint: disable=import-outside-toplevel
    except ImportError:
        return "[skipped] nvidia-smi is present but torch is not installed"
    if torch.cuda.is_available():
        return "[ok] torch sees the GPU"
    return (
        "[gpu-mismatch] nvidia-smi reports a GPU but torch cannot see it -- "
        "run: chitragupta install gpu-torch"
    )


def _competing_distributions() -> set[str]:
    """Every distribution besides this one that declares a `chitragupta`
    or `cg` console script -- the collision #269 accepts on the condition
    that it stops being silent."""
    found = set()
    for dist in importlib.metadata.distributions():
        name = dist.name
        if name == THIS_DISTRIBUTION:
            continue
        for entry_point in dist.entry_points:
            if entry_point.group == "console_scripts" and entry_point.name in CONSOLE_SCRIPTS:
                found.add(name)
    return found


def _check_competing_distribution() -> str:
    others = _competing_distributions()
    if not others:
        return "[ok] no competing chitragupta/cg distribution found"
    return (
        f"[collision] {', '.join(sorted(others))} also provides chitragupta/cg -- "
        "install into separate virtualenvs"
    )


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog=prog_for("doctor"), description=DESCRIPTION)


def main(argv=None) -> int:
    build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    lines = [
        *_check_binaries(),
        _check_enrich_extra(),
        _check_gpu_torch(),
        _check_competing_distribution(),
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
