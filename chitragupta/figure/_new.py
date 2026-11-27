"""Start a figure from a scaffold: `chitragupta figure new` (#1052).

Copies a known-good scaffold (never overwriting a figure); the drawing stays
the agent's. A layout id is a scaffold stem whose own `% cg-layout:` line
names it, so the id needs no translation (and `cg-figstyle.tex` is not one).
The twin is copied where shipped; a missing one costs only a starting point.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config
from chitragupta.figure._block import House
from chitragupta.figure._layout import declared_layout
from chitragupta.figure._sync import Outcome, sync_file

SCAFFOLD_DIR: Path = config.shipped("assets", "tikz")

# A bare file stem: no separator, so the figure cannot land outside the
# directory, and no dot, so `flow.tex` is not taken as a stem.
_NAME_RE = re.compile(r"[\w-]+")


class Refused(ValueError):
    """A usage error: nothing was written, and the message says why."""


@dataclass(frozen=True)
class Created:
    """What `new_figure` wrote. `twin` is `None` where the layout ships
    no twin, and `sync` is what `figure sync` did to the new file."""

    figure: Path
    twin: Path | None
    sync: Outcome


def layouts() -> dict[str, Path]:
    return {
        path.stem: path
        for path in sorted(SCAFFOLD_DIR.glob("*.tex"))
        if declared_layout(path.read_text(encoding="utf-8")) == path.stem
    }


def _check(figures_dir: Path, name: str, layout: str, available: dict[str, Path]) -> None:
    """Raise `Refused` for anything that would write somewhere unasked."""
    if not _NAME_RE.fullmatch(name):
        raise Refused(f"{name!r} is not a bare file name: no path, no suffix, no spaces")
    # `figure sync` and the render's markers find figures only in a directory
    # of exactly this name (WRITING-STANDARDS §10).
    if figures_dir.name != "figures":
        raise Refused(f"{figures_dir} is not a directory named `figures`")
    if not figures_dir.parent.is_dir():
        raise Refused(f"{figures_dir.parent} does not exist")
    if not available:
        raise Refused("no layouts are installed; `chitragupta doctor` checks the install")
    if layout not in available:
        raise Refused(f"no layout {layout!r}; the layouts are: {', '.join(available)}")
    for target in (figures_dir / f"{name}.tex", figures_dir / f"{name}.txt"):
        # `exists()` follows a symlink, so a dangling one would pass it.
        if target.exists() or target.is_symlink():
            raise Refused(f"{target} already exists; figure new never overwrites")


def _copy(source: Path, target: Path) -> None:
    """`source`'s bytes to a `target` that must not exist yet.

    Exclusive creation, so a file or symlink appearing between check and
    write is refused rather than replaced or written through.
    """
    data = source.read_bytes()
    try:
        with target.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise Refused(f"{target} already exists; figure new never overwrites") from exc


def new_figure(figures_dir: Path, name: str, layout: str, house: House) -> Created:
    """Copy `layout`'s scaffold (and twin) to `figures_dir/name`, then bring
    its house block up to date."""
    available = layouts()
    _check(figures_dir, name, layout, available)
    figures_dir.mkdir(exist_ok=True)
    figure_path = figures_dir / f"{name}.tex"
    _copy(available[layout], figure_path)
    twin_source = available[layout].with_suffix(".txt")
    twin = None
    if twin_source.is_file():
        twin = figures_dir / f"{name}.txt"
        _copy(twin_source, twin)
    return Created(figure_path, twin, sync_file(figure_path, house, check=False))
