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

__all__ = [
    "House",
    "Region",
    "State",
    "classify",
    "digest",
    "finding",
    "load_house",
    "newer_than_install",
    "stamp",
]
