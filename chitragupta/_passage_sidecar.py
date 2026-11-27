"""The corpus layer's passage sidecar on disk: where it lives, how it is
written, and whether what is there can be read at all.

About the file, never `Passage` (issue 844); re-exported from
`chitragupta/passages.py`, so tests' monkeypatches are unchanged.
Stdlib-only.
"""

import json
from pathlib import Path

from chitragupta import config
from chitragupta._atomic_write import write_atomically
from chitragupta.citekey_safety import citekey_path


def sidecar_path(citekey: str) -> Path:
    """The corpus layer's passage sidecar for `citekey` (rung 2).

    Not the enrichment layer's rung-1 sidecar under `config.DOCLING_DIR`,
    whose OCR and figure settings differ.
    """
    return citekey_path(config.PARSED_DIR, citekey, ".passages.json")


def write_sidecar(citekey: str, records: list[dict]) -> Path:
    """Write `records` whole or not at all (#894): a torn file read as "no
    passages" (issue 844). The temp name never ends in `.passages.json`.
    An `OSError` reaches `pdf_text.extract_text` as a transient failure
    (#842).
    """
    path = sidecar_path(citekey)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, json.dumps(records, indent=2))
    return path


def clear_sidecar(citekey: str) -> None:
    """Drop any corpus-layer sidecar for `citekey`.

    Before every re-parse, not after a failed one: otherwise a changed
    backend, a failed parse or new text leaves last week's sentences
    attributed to today's document.
    """
    sidecar_path(citekey).unlink(missing_ok=True)


class SidecarUnreadable(Exception):
    """A sidecar is there, but is not the JSON list a writer produces."""


def read_records(path: Path) -> list | None:
    """The records at `path`, or None when there is no file.

    Raises `SidecarUnreadable` for a file that is there and cannot be
    read; `UnicodeDecodeError` covers truncation mid-character. An empty
    list is readable: it means "parsed, no prose".
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
    """`"absent"`, `"unreadable"` or `"ok"` -- what `sync` needs to know:
    only a torn file needs a re-parse, never an empty one.
    """
    try:
        records = read_records(path)
    except SidecarUnreadable:
        return "unreadable"
    return "absent" if records is None else "ok"
