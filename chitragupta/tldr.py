"""Per-citekey TL;DR: a one-paragraph summary, so skimming a large corpus
does not mean opening every PDF. Written by a person, or -- for the
citekeys nobody has got to -- standing in as the authors' own abstract,
extracted verbatim.

**Nothing here composes prose, and the two halves of that are different
promises.** `write` only persists text someone else wrote and never calls
out to an LLM, which is unchanged. The fallback added beside it is
`chitragupta/_abstract.py`, which *extracts*: the words are the authors'
own, lifted out of the passage sidecar with no summarisation step, so it
introduces no LLM call either. Issue #401 proposed also sending the whole
text of a paper *without* an abstract to a model; that half is declined,
and such a paper reports that it has no abstract.

docs/FEATURE-ROADMAP.md's E1 named the placement as the whole design
decision. A hand-written summary may be LLM output -- a skill in the
current Claude Code session is one of the two things that compose one --
so it cannot live in the corpus layer, per SOUL.md's "no LLM and no
judgment calls". It belongs to the drafting layer, as an eleventh
`chitragupta/draft.py` verb, in its own sidecar under `content/tldr/` --
not `content/dossiers/`, because a summary belongs to a citekey, not to
any one draft's working state. `python -m chitragupta.corpus ledger` is
not touched by this at all.

**The two paragraphs below are about the written sidecar only.** An
extracted abstract is neither stored nor fingerprinted: it is re-derived
on every read, so it cannot go stale, and `resolve` has why that
asymmetry is right rather than lazy.

**The fingerprint is a content hash of the parsed text, not a stat of
the PDF.** Mirrors chitragupta/enrich/embed_index.py's `hash_text` /
unchanged-text skip, deliberately not
chitragupta/enrich/docling_parse.py's `(size, mtime_ns)` fingerprint of
the *input* PDF: what must go stale is the text a summary was written
against, and a backend switch or a `--reparse` can change that text
without the PDF on disk moving at all, which a PDF-stat fingerprint
can't see. A re-parse that happens to produce byte-identical text
therefore correctly leaves a summary fresh -- this is a fingerprint of
`content/parsed/<citekey>.txt`'s *content*, not of when it was written.

**Staleness is binary and always re-derived on read, never stored.**
`read()` recomputes the current fingerprint every time and compares it
to what was stored at `write` time; it never trusts a flag written
earlier, which is what makes "re-fingerprint on read" (this module) and
"cache the verdict at write time" (the bug this module exists to avoid)
different code. There is no third state: a fingerprint that can no
longer be computed at all -- the citekey left the ledger, or its parsed
text is gone -- counts as stale too, since a summary that cannot be
verified is not reported as trustworthy.

Usage:
    echo "<summary text>" | python -m chitragupta.draft tldr write <citekey>
    python -m chitragupta.draft tldr show <citekey> [--json]
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from chitragupta import _abstract, config, ledger


class TldrError(Exception):
    """A citekey the ledger doesn't hold, one with no parsed text yet, or
    an empty summary."""


def sidecar_path(citekey: str) -> Path:
    """Where `citekey`'s TL;DR lives -- one JSON file, named the same
    way passages.py's sidecar_path names its own."""
    return config.TLDR_DIR / f"{citekey}.json"


def _fingerprint(con, citekey: str) -> str:
    """sha256 hex of `citekey`'s current parsed text.

    Raises TldrError rather than returning None for "no parsed text
    yet": a summary must be keyed to *some* text, and a caller storing a
    fingerprint of nothing would produce a sidecar that can never be
    told stale from fresh.
    """
    row = con.execute("SELECT parsed_path FROM items WHERE citekey = ?", (citekey,)).fetchone()
    if row is None:
        raise TldrError(
            f"{citekey} is not in the ledger -- run `python -m chitragupta.corpus sync`. "
            "A TL;DR is keyed to a citekey that already exists; it never mints one."
        )
    parsed_path = row[0]
    if not parsed_path or not Path(parsed_path).is_file():
        raise TldrError(
            f"{citekey} has no parsed text yet -- run `python -m chitragupta.corpus "
            "sync` first, then summarise it."
        )
    text = Path(parsed_path).read_text(encoding="utf-8", errors="replace")
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
    """The raw payload `write` stored, or None for absent/unreadable --
    the same forgiving read passages.py's `_from_sidecar` gives a
    corrupted file: a missing summary is not an error."""
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
        # Uncomputable is stale, not fresh (#509/m-41). `current = None`
        # compared equal to a stored `fingerprint` of `None` -- a sidecar
        # written when the fingerprint could not be computed either --
        # and the pair reported `stale: False`, i.e. "this summary is of
        # the current parse", about a parse this cannot even see. The
        # docstring's promise is the opposite, and a summary nobody can
        # verify is exactly the one a reader should be told to re-check.
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

    **A hand-written summary wins.** Extraction runs only when `read`
    finds nothing, which is a stated decision rather than an
    implementation detail: someone who wrote a TL;DR chose to, and an
    author's abstract is the fallback for the papers nobody has got to.
    It also keeps the common path cheap -- a sidecar hit reads one small
    JSON file and never opens the passage records.

    The last two are separate answers on purpose. "This paper has no
    abstract" is a statement about the paper; "there is no sidecar" is a
    statement about how the paper was parsed, and reporting the first
    where the second is true would describe a document nobody read. See
    `chitragupta/_abstract.py`'s `UNKNOWN`.

    An extracted abstract is never `stale`, because it is re-derived on
    every call rather than stored -- there is no earlier text for it to
    have been written against. That is the whole reason it is not
    persisted: `write`'s fingerprint exists for a summary a person
    composed, which cannot be recovered if it goes stale, and an abstract
    can always just be read again.
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
    with ledger.connection() as con:
        path = write(con, args.citekey, summary)
    print(f"wrote {path}")
    return 0


def _describe(citekey: str, result: dict) -> str:
    """The one human-readable line `show` prints, per `source`.

    Each of the four says what a reader's next move is, which is the
    difference between the last two: a re-parse fixes `unknown` and
    nothing fixes `none`.
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
    with ledger.connection() as con:
        result = resolve(con, args.citekey)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(_describe(args.citekey, result))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m chitragupta.draft tldr",
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
