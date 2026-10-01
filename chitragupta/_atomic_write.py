"""Write a file whole or not at all: a temp sibling, then `os.replace`.

One implementation for the corpus layer's two per-document outputs, the
parsed text (`pdf_text`, #894) and the passage sidecar (`passages`,
#844), which both need the same three properties:

- **No torn file.** `os.replace` is atomic on POSIX and on Windows (same
  volume), so a reader sees the old file or the new one, never a prefix.
  A truncated file is worse than none here: `ledger_upsert.
  _parse_outputs_present` takes existence for a finished parse, so a torn
  one would never be re-parsed.
- **No collision.** The temp name is unique per process and per call, so
  two writers -- sync's pool workers -- cannot interleave into one file.
- **No debris read as output.** The temp name ends in `.tmp-<pid>-<hex>`,
  not in the target's own suffix, and is removed when the write fails.

The `OSError` still reaches the caller unchanged: what a failed write
*means* (transient, per #842) is the caller's to decide.

Not yet shared by the other writers of the same shape --
`_json_cache`, `overlap_index_doc` and the two enrichment caches --
which differ in whether they clean up after a failure.
"""

import os
import uuid
from pathlib import Path


def write_atomically(path: Path, data: bytes | str) -> None:
    """Write `data` to `path` through a temp sibling and `os.replace`.

    Bytes are written as given -- pdftotext's stdout, in whatever encoding
    poppler chose. Text is encoded UTF-8, never the locale codec, which is
    cp1252 on CI's Windows leg.
    """
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        if isinstance(data, bytes):
            tmp.write_bytes(data)
        else:
            tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
