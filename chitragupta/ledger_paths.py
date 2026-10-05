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

import sqlite3
from pathlib import Path

from chitragupta import config


def read_only_uri(path: Path) -> str:
    """`path` as a sqlite URI that opens it read-only and creates nothing.

    Made absolute, not resolved: `as_uri()` accepts only an absolute
    path, and `resolve()` on Windows turns a mapped drive (`H:\\proj`)
    into its UNC target, which `as_uri()` writes as `file://server/...`
    -- an authority sqlite refuses, so every reader of a ledger on a
    mapped drive would fail (#966, #963). `absolute()` keeps the drive
    letter, and a path that is UNC to begin with goes through
    `_sqlite_file_uri`."""
    return _sqlite_file_uri(path.absolute().as_uri()) + "?mode=ro"


def _sqlite_file_uri(uri: str) -> str:
    """An `as_uri()` result in the form sqlite accepts. sqlite takes only
    an empty or `localhost` authority, so a UNC path's
    `file://server/share/...` becomes `file:////server/share/...`, with
    the server moved into the path; every other URI passes unchanged."""
    if not uri.startswith("file:///"):
        return "file:////" + uri[len("file://") :]
    return uri


def stored(path: str | Path | None, root: Path) -> str | None:
    """`path` as this ledger stores it: relative to `root`, `/`-separated.
    Raises `ValueError` outside `root`: an unconfined path handed to a
    writer is a bug, not data."""
    if not path:
        return None
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def resolved(value: str | None, root: Path) -> Path | None:
    """A stored value as a path a reader may open, or `None`.

    `root / value` is the whole of the anchoring: a legacy absolute value
    collapses to itself (pathlib), so a ledger an older release wrote
    still reads in place, and `confined_path` refuses -- loudly -- one
    that lands outside `root`, `..` included (issue 821)."""
    if not value:
        return None
    return config.confined_path(root / value, root)


def pdf_root() -> Path:
    """The directory `pdf_path` is stored relative to: the bib file's own,
    symlinks followed, which is where bib_reader confines attachments.
    A function, not a constant: config is patched at call time."""
    return config.BIB_FILE_PATH.resolve().parent


def stored_parsed(path: str | Path | None) -> str | None:
    """`path` relative to `config.PARSED_DIR`, as `parsed_path` stores it.

    `PARSED_DIR` is `parsed/` under `[content].dir`, so the stored value
    follows that setting rather than a fixed `content/`.
    """
    return stored(path, config.PARSED_DIR)


def stored_pdf(path: str | Path | None) -> str | None:
    """`path` relative to the bib file's directory, as `pdf_path` stores it."""
    return stored(path, pdf_root())


def parsed_file(value: str | None) -> Path | None:
    """The file a stored `parsed_path` names, confined to `config.PARSED_DIR`."""
    return resolved(value, config.PARSED_DIR)


def pdf_file(value: str | None) -> Path | None:
    """The file a stored `pdf_path` names, confined to the bib directory."""
    return resolved(value, pdf_root())


def mark_parsed(con: sqlite3.Connection, citekey: str, parsed_path: Path) -> None:
    """Record a finished parse; commits, which `sync._record_result` relies on."""
    con.execute(
        "UPDATE items SET status = 'parsed', parsed_path = ?, parse_error = NULL WHERE citekey = ?",
        (stored_parsed(parsed_path), citekey),
    )
    con.commit()


# The file a parse writes is fully determined by its citekey
# (pdf_text.extract_text), so a legacy host-absolute value is rewritten
# to that name whatever host it named. Idempotent: once every row is
# relative, the WHERE matches nothing. A legacy absolute `pdf_path` is not
# rewritten here: upsert_reference rewrites it for every bib entry on the
# next sync.
_NORMALISE_PARSED = (
    "UPDATE items SET parsed_path = citekey || '.txt' "
    "WHERE parsed_path IS NOT NULL AND parsed_path <> citekey || '.txt'"
)


def normalise_legacy(con: sqlite3.Connection) -> None:
    """Rewrite what an older release stored host-absolute (#966)."""
    con.execute(_NORMALISE_PARSED)
