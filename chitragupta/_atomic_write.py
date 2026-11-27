"""Write a file whole or not at all: a temp sibling, then `os.replace`.

For the parsed text (#894) and the passage sidecar (#844): no torn file
(a torn one would read as a finished parse and never be re-parsed), no
collision between pool workers (unique temp name), and no debris read
as output (the temp suffix differs, and is removed on failure). The
`OSError` reaches the caller, which decides what it means (#842).
`temp_sibling` alone serves all-or-none multi-file writers
(`dossier/_renames.py`).
"""

import os
import uuid
from pathlib import Path


def temp_sibling(path: Path) -> Path:
    """A temp path beside `path`, unique per process and per call."""
    return path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")


def write_atomically(path: Path, data: bytes | str) -> None:
    """Write `data` to `path` through a temp sibling and `os.replace`.
    Text is UTF-8, never the locale codec (cp1252 on Windows CI).
    """
    tmp = temp_sibling(path)
    try:
        if isinstance(data, bytes):
            tmp.write_bytes(data)
        else:
            tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
