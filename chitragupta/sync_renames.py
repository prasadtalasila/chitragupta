"""A citekey that left the bib while the same paper arrived under another
one -- told apart from a removal, and remembered (plans/1211, D6, D7).

Without this, a renamed key reads as two unrelated events: one paper
stale, one paper new. The drafts citing the old key fail the citation
gate later with nothing to say which key replaced it, and once
`--remove-stale` has pruned the old row the answer is gone for good.

**Two sources, one rule each.**

- The importer's `cg-renames` table (`chitragupta/bib_tables.py`) says
  so outright. It wins whenever its new key is in the bib, because it is
  the only source for a duplicate merged in the reference manager whose
  copies had different PDFs.
- Otherwise the ledger's `pdf_hash`: a stale row whose hash is held by
  exactly one key still in the bib. Byte-identical PDFs are the same
  paper, whichever tool wrote the bib. A hash held by several keys (a
  book and its chapter sharing one file) is reported, never guessed.

**Recorded before any prune** (`ledger_tables`' `renames` table), so the
drafting layer can still find the replacement after the old row is gone.
Nothing here edits a draft: corpus-layer code reports, and a draft is
changed by `dossier apply-renames`, which a person or a skill runs.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from chitragupta import ledger_tables

PDF_HASH = "pdf_hash"
CG_RENAMES = "cg-renames"


@dataclass(frozen=True)
class Rename:
    old: str
    new: str
    source: str
    same_pdf: bool


def detect(
    con: sqlite3.Connection, stale: list[str], seen: set[str], declared: dict[str, str]
) -> tuple[list[Rename], dict[str, list[str]]]:
    """The 1:1 renames among `stale`, and `{old: [keys]}` for a hash
    several keys in the bib share."""
    hashes = dict(con.execute("SELECT citekey, pdf_hash FROM items"))
    holders: dict[str, list[str]] = defaultdict(list)
    for key, value in hashes.items():
        if value and key in seen:
            holders[value].append(key)
    renames, shared = [], {}
    for old in stale:
        value = hashes.get(old)
        new = declared.get(old)
        if new in seen:
            same = bool(value) and value == hashes.get(new)
            renames.append(Rename(old, new, CG_RENAMES, same))
            continue
        keys = sorted(holders.get(value, [])) if value else []
        if len(keys) == 1:
            renames.append(Rename(old, keys[0], PDF_HASH, True))
        elif keys:
            shared[old] = keys
    return renames, shared


def record(con: sqlite3.Connection, renames: list[Rename], seen: set[str]) -> None:
    """Upsert `renames`, keeping a row's first-seen date while its mapping
    holds, and drop every row whose old key is back in the bib."""
    con.executemany(
        "INSERT INTO renames VALUES (?, ?, ?, ?, ?) ON CONFLICT(old) DO UPDATE SET "
        "new = excluded.new, source = excluded.source, same_pdf = excluded.same_pdf, "
        "seen_at = excluded.seen_at WHERE renames.new != excluded.new "
        "OR renames.source != excluded.source",
        [(r.old, r.new, r.source, int(r.same_pdf), date.today().isoformat()) for r in renames],
    )
    undone = [(old,) for old in ledger_tables.renames(con) if old in seen]
    con.executemany("DELETE FROM renames WHERE old = ?", undone)
    con.commit()


def suffixes(renames: list[Rename], shared: dict[str, list[str]]) -> dict[str, str]:
    """`{old: text}` to append inside a stale or pruned line's brackets."""
    notes = {
        r.old: f"; renamed to {r.new}, {'same' if r.same_pdf else 'different'} PDF" for r in renames
    }
    notes.update({old: f"; same PDF as {', '.join(keys)}" for old, keys in shared.items()})
    return notes
