"""Start a figure from a scaffold: `chitragupta figure new` (#1052).

It replaces the figure-drawer skill's `cp` plus `figure sync` with one
command that knows where the scaffolds are and never overwrites a
figure. The drawing stays the agent's: this only gets it a known-good
starting file, its `% cg-layout:` line intact.

A layout id is a scaffold's file stem, and only a scaffold whose own
`% cg-layout:` line names that stem counts. The id is then what the
figure declares, what `figure check` reads its reference range by, and
what this command was asked for, with nothing to translate between
them; and `cg-figstyle.tex`, which declares no layout, is not one.

The twin is copied only where the layout ships one (none does before
#1056). A twin always has to be redrawn to match the relabelled figure,
so a missing one costs a starting point, not a figure.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from chitragupta import config
from chitragupta.figure._block import House
from chitragupta.figure._layout import declared_layout
from chitragupta.figure._sync import Outcome, sync_file

SCAFFOLD_DIR: Path = config.shipped("assets", "tikz")

# A bare file stem. No separator, so the figure cannot land outside the
# directory named, and no dot, so `flow.tex` is not taken as the stem of
# `flow.tex.tex`.
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
    """`{id: scaffold}` for every scaffold that declares its own stem."""
    return {
        path.stem: path
        for path in sorted(SCAFFOLD_DIR.glob("*.tex"))
        if declared_layout(path.read_text(encoding="utf-8")) == path.stem
    }


def _check(figures_dir: Path, name: str, layout: str, available: dict[str, Path]) -> None:
    """Raise `Refused` for anything that would write somewhere unasked."""
    if not _NAME_RE.fullmatch(name):
        raise Refused(f"{name!r} is not a bare file name: no path, no suffix, no spaces")
    # `figure sync`'s walk and the render's markers both find figures in
    # a directory of exactly this name (WRITING-STANDARDS §10).
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

    Exclusive creation, so a file or symlink that appears between the
    check and the write is refused rather than replaced or written
    through.
    """
    data = source.read_bytes()
    try:
        with target.open("xb") as handle:
            handle.write(data)
    except FileExistsError as exc:
        raise Refused(f"{target} already exists; figure new never overwrites") from exc


def new_figure(figures_dir: Path, name: str, layout: str, house: House) -> Created:
    """Copy `layout`'s scaffold (and its twin, if it ships one) to
    `figures_dir/name`, then bring its house block up to date."""
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
