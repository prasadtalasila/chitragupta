"""Per-citekey TL;DR: a one-paragraph summary, so skimming a large corpus
does not mean opening every PDF. Written by a person, or -- for the
citekeys nobody has got to -- standing in as the authors' own abstract,
extracted verbatim.

Nothing here composes prose: `write` persists text someone else wrote,
and the fallback `_abstract.py` extracts the authors' words. Sending an
abstract-less paper's text to a model (#401) was declined. A written
summary may be LLM output, so it belongs to the drafting layer (SOUL.md),
in `content/tldr/`, per citekey rather than per draft.

For the written sidecar only: the fingerprint is a hash of the parsed
text, not a PDF stat, since a reparse can change the text without
touching the PDF. Staleness is re-derived on every read, never stored,
and an uncomputable fingerprint counts as stale. Extracted abstracts are
never stored (see `resolve`).

Usage:
    echo "<summary text>" | python -m chitragupta.draft tldr write <citekey>
    python -m chitragupta.draft tldr show <citekey> [--json]
"""

import hashlib
import json
import sys
from pathlib import Path

from chitragupta import _abstract, config, ledger, ledger_paths
from chitragupta.citekey_safety import UnsafeCitekey, citekey_path
from chitragupta.help_format import ClickParser
from chitragupta.progname import prog_for


class TldrError(Exception):
    """A citekey the ledger doesn't hold, one with no parsed text yet, or
    an empty summary."""


def sidecar_path(citekey: str) -> Path:
    """Where `citekey`'s TL;DR lives, one JSON file named as passages.py
    names its sidecar. Raises TldrError for a citekey that cannot name a
    file, as `show` reads this before any ledger lookup (#975).
    """
    try:
        return citekey_path(config.TLDR_DIR, citekey, ".json")
    except UnsafeCitekey as exc:
        raise TldrError(str(exc)) from exc


def _fingerprint(con, citekey: str) -> str:
    """sha256 hex of `citekey`'s current parsed text. Raises TldrError
    rather than returning None, since a fingerprint of nothing could never
    be told stale from fresh.
    """
    row = con.execute("SELECT parsed_path FROM items WHERE citekey = ?", (citekey,)).fetchone()
    if row is None:
        raise TldrError(
            f"{citekey} is not in the ledger -- run `python -m chitragupta.corpus sync`. "
            "A TL;DR is keyed to a citekey that already exists; it never mints one."
        )
    # A path outside `content/parsed/` counts as no parsed text (issue
    # 821), loudly; the value is relative to `config.PARSED_DIR` (#966).
    parsed = ledger_paths.parsed_file(row[0])
    if parsed is None or not parsed.is_file():
        raise TldrError(
            f"{citekey} has no parsed text yet -- run `python -m chitragupta.corpus "
            "sync` first, then summarise it."
        )
    text = parsed.read_text(encoding="utf-8", errors="replace")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write(con, citekey: str, summary: str) -> Path:
    """Persist `summary` for `citekey`, keyed to its current parsed-text
    fingerprint. Overwrites whatever was recorded before."""
    summary = summary.strip()
    if not summary:
        raise TldrError("a TL;DR cannot be empty")
    fingerprint = _fingerprint(con, citekey)
    payload = {"citekey": citekey, "summary": summary, "fingerprint": fingerprint}
    path = sidecar_path(citekey)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_sidecar(citekey: str) -> dict | None:
    """The raw payload `write` stored, or None for absent or unreadable:
    a missing summary is not an error."""
    try:
        payload = json.loads(sidecar_path(citekey).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or not payload.get("summary"):
        return None
    return payload


def read(con, citekey: str) -> dict | None:
    """{"citekey", "summary", "fingerprint", "stale"} for `citekey`, or
    None if no summary has been written yet."""
    payload = _read_sidecar(citekey)
    if payload is None:
        return None
    try:
        current = _fingerprint(con, citekey)
    except TldrError:
        # Uncomputable is stale (#509/m-41): `None == None` once reported a
        # summary of an unseen parse as fresh.
        payload["stale"] = True
        return payload
    payload["stale"] = current != payload.get("fingerprint")
    return payload


def resolve(con, citekey: str) -> dict:
    """What `show` should report for `citekey`: one of four answers, in a
    dict that always carries `source`.

    | `source` | Meaning |
    | --- | --- |
    | `human` | Somebody wrote a TL;DR. `summary`, `fingerprint`, `stale` as `read` returns them |
    | `abstract` | Nobody did, so the authors' own abstract stands in |
    | `none` | Nobody did, and the paper has no abstract to fall back on |
    | `unknown` | Nobody did, and there is no structural sidecar, so nothing here can tell |

    A hand-written summary wins, and is the cheap path. `none` and
    `unknown` stay apart: one is about the paper, the other about how it
    was parsed (`_abstract.UNKNOWN`). An extracted abstract is never
    `stale`, being re-derived every call, which is why it is not stored.
    """
    payload = read(con, citekey)
    if payload is not None:
        payload["source"] = "human"
        return payload
    found = _abstract.extract(citekey)
    if found is _abstract.UNKNOWN:
        return {"citekey": citekey, "summary": None, "source": "unknown"}
    if found is None:
        return {"citekey": citekey, "summary": None, "source": "none"}
    return {"citekey": citekey, "summary": found, "source": "abstract", "stale": False}


def _cmd_write(args) -> int:
    summary = sys.stdin.read()
    with ledger.reading() as con:
        path = write(con, args.citekey, summary)
    print(f"wrote {path}")
    return 0


def _describe(citekey: str, result: dict) -> str:
    """The one human-readable line `show` prints, per `source`, each naming
    the reader's next move (a re-parse fixes `unknown`, nothing fixes `none`).
    """
    if result["source"] == "unknown":
        return (
            f"cannot tell whether {citekey} has an abstract: no structural passage "
            'sidecar. Re-parse it with `[parser].backend = "docling"`, which is '
            "what records reading order."
        )
    if result["source"] == "none":
        return f"abstract not available for {citekey}, and no TL;DR recorded"
    if result["source"] == "abstract":
        return f"{citekey} [the authors' own abstract, no TL;DR recorded]: {result['summary']}"
    note = " [STALE -- re-parsed since this was written]" if result["stale"] else ""
    return f"{citekey}{note}: {result['summary']}"


def _cmd_show(args) -> int:
    with ledger.reading() as con:
        result = resolve(con, args.citekey)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(_describe(args.citekey, result))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = ClickParser(
        prog=f"{prog_for('draft')} tldr",
        description="A one-paragraph summary per citekey, cached beside a "
        "fingerprint of its parsed text.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_write = sub.add_parser("write", help="Record a summary for one citekey, read from stdin")
    p_write.add_argument("citekey")
    p_write.set_defaults(func=_cmd_write)

    p_show = sub.add_parser("show", help="Print the recorded summary, if any, and its staleness")
    p_show.add_argument("citekey")
    p_show.add_argument("--json", action="store_true", help="Machine-readable output")
    p_show.set_defaults(func=_cmd_show)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TldrError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
