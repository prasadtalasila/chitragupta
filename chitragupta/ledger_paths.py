"""How a path goes into the ledger and comes back out (#966, #963).

Every path this module hands sqlite, or reads back out of a ledger
column, crosses here, so the two rules hold in one place:

- a URI is built by `Path.as_uri()`, never by formatting. `?`, `#` and
  `%` are URI syntax, and a raw path holding one names a different
  file; and
- a stored path is relative to the root its readers confine it to,
  never host-absolute. A moved project, a renamed `content/`, or the
  same ledger read from a container and then from the host all name the
  file that is actually there.
"""

from __future__ import annotations

from pathlib import Path


def read_only_uri(path: Path) -> str:
    """`path` as a sqlite URI that opens it read-only and creates nothing.
    Resolved first: `as_uri()` accepts only an absolute path, and on
    Windows this yields the `file:///C:/...` form sqlite expects."""
    return path.resolve().as_uri() + "?mode=ro"
