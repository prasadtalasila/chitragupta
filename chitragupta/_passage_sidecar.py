"""The corpus layer's passage sidecar on disk: where it lives, how it is
written, and whether what is there can be read at all.

Split out of `chitragupta/passages.py` for issue 844, which that module
had no room for under docs/CODE-STANDARDS.md's 250-line ceiling. The
boundary is the one `_passage_records.py` drew: everything here is about
the *file* and never touches `Passage`, while everything left there turns
a readable file's records into passages. Re-exported from
`chitragupta/passages.py`, so `passages.write_sidecar` and friends --
which `pdf_text` calls and the tests monkeypatch -- are unchanged.

Stdlib-only, like its parent.
"""

import json
import os
import uuid
from pathlib import Path

from chitragupta import config


def sidecar_path(citekey: str) -> Path:
    """The corpus layer's passage sidecar for `citekey` (rung 2).

    Built from the citekey in one place, so the writer in
    `chitragupta/pdf_text.py` and the reader in `passages` cannot drift
    apart. The enrichment layer's own sidecar (rung 1) is *not* this path
    -- it lives under `config.DOCLING_DIR`, written by that layer's own
    parse under its own OCR and figure settings, so the two must not share
    a file even though they now key on the same string.
    """
    return config.PARSED_DIR / f"{citekey}.passages.json"


def write_sidecar(citekey: str, records: list[dict]) -> Path:
    """Write `records` whole or not at all.

    Through a temp file and `os.replace`, the shape `retrieval_cache.
    _save_cache` and `enrich/_docling_cache.py` already use: a bare
    `write_text` killed mid-write left a torn file that every reader took
    for "no passages" (issue 844). The temp name is unique per process and
    call, so two writers cannot interleave into one file, and it does not
    end in `.passages.json`, so debris from a killed write is never read
    as a sidecar. An `OSError` still reaches the caller unchanged --
    `pdf_text.extract_text` reports it as a transient failure (#842).
    """
    path = sidecar_path(citekey)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        tmp.write_text(json.dumps(records, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return path


def clear_sidecar(citekey: str) -> None:
    """Drop any corpus-layer sidecar for `citekey`.

    Called before every re-parse rather than after a failed one. A
    sidecar quotes the PDF *as parsed at the time it was written*, so it
    outlives its own truth in three ways: the backend changes to one that
    produces no passages, the parse of an edited PDF fails outright, or
    the same backend re-runs and produces different text. Removing it up
    front makes all three land on "no sidecar" instead of "last week's
    sentences, attributed to today's document".
    """
    sidecar_path(citekey).unlink(missing_ok=True)


class SidecarUnreadable(Exception):
    """A sidecar is there, but is not the JSON list a writer produces."""


def read_records(path: Path) -> list | None:
    """The records at `path`, or None when there is no file.

    Raises `SidecarUnreadable` for a file that is there and cannot be
    read, including one that decodes to something other than a list.
    `UnicodeDecodeError` is in that set because a file truncated mid-write
    can split a multi-byte character, which fails before json sees it.
    An empty list is *readable*: `pdf_text.extract_text` writes one for a
    reading-order parse that found no prose, and it means "parsed".
    """
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SidecarUnreadable(f"{path}: {exc}") from exc
    if not isinstance(records, list):
        raise SidecarUnreadable(f"{path}: not a list of records")
    return records


def sidecar_state(path: Path) -> str:
    """`"absent"`, `"unreadable"` or `"ok"` -- what `sync` needs to know.

    A reader folds all three of absent, empty and torn into "no passages",
    which is right for a reader and wrong for `ledger_upsert.
    _parse_outputs_present`: only a torn file needs a re-parse, and an
    empty one must not get one on every run.
    """
    try:
        records = read_records(path)
    except SidecarUnreadable:
        return "unreadable"
    return "absent" if records is None else "ok"
