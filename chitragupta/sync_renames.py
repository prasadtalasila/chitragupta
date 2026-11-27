"""A citekey that left the bib while the same paper arrived under another
one -- told apart from a removal, and remembered (plans/1211, D6, D7).

Without this, the drafts citing the old key fail the gate with nothing
saying what replaced it, and `--remove-stale` would erase the answer.

- The importer's `cg-renames` table wins whenever its new key is in the
  bib: it is the only source for a merged duplicate whose copies had
  different PDFs. Chains are followed; a loop or an end outside the bib
  falls back to the hash.
- Otherwise `pdf_hash`: a stale row whose hash exactly one bib key holds,
  that key new this sync. Two entries already sharing a file (a book and
  its chapter) are two works: deleting one is a removal, never a rename.

Recorded before any prune. Nothing here edits a draft; that is
`dossier apply-renames`, run by a person or a skill.
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


def _declared_target(declared: dict[str, str], old: str, seen: set[str]) -> str | None:
    """Where `declared` takes `old`, followed to a key in the bib; None
    when it says nothing, loops, or ends outside the bib."""
    visited, key = {old}, declared.get(old)
    while key is not None and key not in seen and key not in visited:
        visited.add(key)
        key = declared.get(key)
    return key if key in seen else None


def detect(
    con: sqlite3.Connection,
    stale: list[str],
    seen: set[str],
    declared: dict[str, str],
    arrived: set[str],
) -> tuple[list[Rename], dict[str, list[str]]]:
    """The 1:1 renames among `stale`, and `{old: [keys]}` for a hash that
    keys in the bib share. `arrived` is the keys new to the ledger this
    sync: only one of those can be a hash rename's target."""
    hashes = dict(con.execute("SELECT citekey, pdf_hash FROM items"))
    holders: dict[str, list[str]] = defaultdict(list)
    for key, value in hashes.items():
        if value and key in seen:
            holders[value].append(key)
    renames, shared = [], {}
    for old in stale:
        value = hashes.get(old)
        new = _declared_target(declared, old, seen)
        if new is not None:
            same = bool(value) and value == hashes.get(new)
            renames.append(Rename(old, new, CG_RENAMES, same))
            continue
        keys = sorted(holders.get(value, [])) if value else []
        if len(keys) == 1 and keys[0] in arrived:
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
        "OR renames.source != excluded.source OR renames.same_pdf != excluded.same_pdf",
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
