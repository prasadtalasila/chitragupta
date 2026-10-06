"""The house figure-style block inside figure files (#1013).

`_block` reads the installed block and classifies and stamps one file's
region; `_sync` walks figure files and writes. `python -m chitragupta
figure sync` is the command.
"""

from chitragupta.figure._block import (
    House,
    Region,
    State,
    classify,
    digest,
    finding,
    load_house,
    newer_than_install,
    stamp,
)
from chitragupta.figure._sync import Outcome, figure_files, run, sync_file

__all__ = [
    "House",
    "Outcome",
    "Region",
    "State",
    "classify",
    "digest",
    "figure_files",
    "finding",
    "load_house",
    "newer_than_install",
    "run",
    "stamp",
    "sync_file",
]
