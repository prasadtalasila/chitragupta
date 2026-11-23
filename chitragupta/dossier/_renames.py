"""Citekeys the corpus layer recorded as renamed, found in a draft and
swapped for their replacement (plans/1211-cg-collections-and-renames.md).

`chitragupta/sync_renames.py` records `old -> new` in the ledger when a
key leaves the bib and the same paper is there under another one; it
edits nothing. This is the drafting layer's half: `dossier status`
lists a draft's renamed keys, and `dossier apply-renames` swaps them in
the draft, `evidence.md`, `sections.md` and `rejected.md` -- the last so
a paper the draft declined stays declined under its new key.

**Nothing is invented.** The new key is the one the ledger recorded,
followed to the end of a chain (`a -> b -> c`), and it must be citable
now -- a parsed row, the set the citation gate accepts. A cycle or a
target that is not citable refuses that key alone, changing nothing for
it, so one bad rename does not hold back the rest. A rename whose two
PDFs differ (the importer said so, the hashes did not) changes which
text the draft's quotes came from, so those are named for
`review quotation` to re-check.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from chitragupta import ledger, ledger_tables
from chitragupta._atomic_write import temp_sibling
from chitragupta.ledger_citable import citable_citekeys
from chitragupta.citekey_safety import citekey_pattern
from chitragupta.dossier import (
    EVIDENCE_MD,
    REJECTED_MD,
    REVISIONS_MD,
    SECTIONS_MD,
    DossierError,
    dossier_dir,
)
from chitragupta.dossier._citekeys import section_citekeys

SWAPPED_FILES = (EVIDENCE_MD, SECTIONS_MD, REJECTED_MD)


class RenamesRefused(DossierError):
    """Some renames could not be applied; `applied` were, `refused` maps
    each old key to why not."""

    def __init__(self, applied: list, refused: dict[str, str]) -> None:
        self.applied, self.refused = applied, refused
        super().__init__("; ".join(refused.values()))


@dataclass(frozen=True)
class AppliedRename:
    old: str
    new: str
    same_pdf: bool
    files: tuple[str, ...]


def final(renames: dict[str, tuple[str, str, bool]], old: str) -> tuple[str, bool] | None:
    """`(the last key in old's chain, whether every step kept the same
    PDF)`, or None when `old` has no rename or its chain is a cycle."""
    if old not in renames:
        return None
    seen, key, same = {old}, old, True
    while key in renames:
        key, _source, same_pdf = renames[key]
        same = same and same_pdf
        if key in seen:
            return None
        seen.add(key)
    return key, same


def cited(texts, renames) -> list[str]:
    """The renamed keys any of `texts` mentions, bounded as a citekey."""
    return sorted(old for old in renames if any(citekey_pattern(old).search(t) for t in texts))


def renamed_in(texts, renames, citekeys: set[str], sections: dict[str, list[str]]) -> dict:
    """`dossier status`'s `renamed`: each cited old key whose chain ends
    at a key in `citekeys`, with its sections."""
    found = {}
    for old in cited(texts, renames):
        resolved = final(renames, old)
        if resolved and resolved[0] in citekeys:
            new, same = resolved
            found[old] = {"new": new, "same_pdf": same, "sections": sections.get(old, [])}
    return found


def _texts(draft: Path) -> dict[Path, str]:
    if not draft.is_file():
        raise DossierError(f"no draft at {draft}")
    paths = [draft, *(dossier_dir(draft) / name for name in SWAPPED_FILES)]
    texts = {}
    for path in (p for p in paths if p.is_file()):
        try:
            texts[path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise DossierError(f"{path} is not UTF-8 text; nothing was changed") from exc
    return texts


def _write_all(texts: dict[Path, str]) -> None:
    """Write every file or none: each goes to a temp sibling first
    (`_atomic_write.temp_sibling`), and only once all are written is each
    moved into place, so a full disk or a permission error midway changes
    nothing."""
    temps: dict[Path, Path] = {}
    try:
        for path, text in texts.items():
            temps[path] = temp_sibling(path)
            temps[path].write_text(text, encoding="utf-8")
    except OSError as exc:
        for temp in temps.values():
            temp.unlink(missing_ok=True)
        raise DossierError(f"could not write {path}: {exc}; nothing was changed") from exc
    for path, temp in temps.items():
        os.replace(temp, path)


def _plan(texts: dict[Path, str]) -> tuple[list[tuple[str, str, bool]], dict[str, str]]:
    """The swaps to make, and `{old: reason}` for the ones refused."""
    try:
        with ledger.reading() as con:
            renames = ledger_tables.renames(con)
            citable = citable_citekeys(con) - ledger_tables.stale(con)
    except (ledger.NoLedger, ledger.StaleLedger, ledger.UnreadableLedger) as exc:
        raise DossierError(f"{exc}; run `chitragupta corpus sync` first") from exc
    plan, refused = [], {}
    for old in cited(texts.values(), renames):
        resolved = final(renames, old)
        if resolved is None:
            refused[old] = f"the recorded renames of {old} form a cycle; {old} was not changed"
        elif resolved[0] not in citable:
            refused[old] = (
                f"{old} was renamed to {resolved[0]}, but {resolved[0]} is not citable "
                f"(no parsed ledger row); {old} was not changed"
            )
        else:
            plan.append((old, *resolved))
    return plan, refused


def _log(draft: Path, applied: list[AppliedRename], sections: list[str]) -> None:
    pairs = ", ".join(f"{a.old} -> {a.new}" for a in applied)
    recheck = [a.new for a in applied if not a.same_pdf]
    lines = [
        f"## {date.today().isoformat()} -- apply-renames: {pairs}",
        "",
        "Swapped citekeys sync recorded as renamed (`dossier apply-renames`). "
        + (f"Quotes to re-check: {', '.join(recheck)}." if recheck else "Same PDFs."),
    ]
    if sections:
        lines.append(f"Sections: {', '.join(sections)}")
    with (dossier_dir(draft) / REVISIONS_MD).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n\n")


def apply_renames(draft: Path) -> list[AppliedRename]:
    """Swap every recorded rename `draft` and its dossier cite. Raises
    `RenamesRefused`, after applying the rest, when any was refused."""
    draft = Path(draft)
    texts = _texts(draft)
    plan, refused = _plan(texts)
    if not plan:
        if refused:
            raise RenamesRefused([], refused)
        return []
    by_key = section_citekeys(dossier_dir(draft), {old for old, _new, _same in plan})
    applied, changed = [], set()
    for old, new, same in plan:
        files = []
        for path, text in texts.items():
            texts[path], count = citekey_pattern(old).subn(lambda _m, new=new: new, text)
            if count:
                files.append(str(path))
                changed.add(path)
        applied.append(AppliedRename(old, new, same, tuple(files)))
    _write_all({path: texts[path] for path in changed})
    sections = sorted({title for old, _n, _s in plan for title in by_key.get(old, [])})
    _log(draft, applied, sections)
    if refused:
        raise RenamesRefused(applied, refused)
    return applied


def _cmd_apply_renames(args) -> int:
    try:
        applied, refused = apply_renames(Path(args.draft)), {}
    except RenamesRefused as exc:
        applied, refused = exc.applied, exc.refused
    if args.json:
        print(json.dumps({"applied": [asdict(a) for a in applied], "refused": refused}, indent=2))
        return 1 if refused else 0
    if not applied and not refused:
        print("No recorded rename applies to this draft.")
    for reason in refused.values():
        print(f"[refused] {reason}; handle it as missing.", file=sys.stderr)
    for item in applied:
        print(f"renamed {item.old} -> {item.new} in {len(item.files)} file(s)")
    if any(not item.same_pdf for item in applied):
        print(
            "re-check quotes, a renamed paper's PDF changed: "
            f"chitragupta review quotation {args.draft}"
        )
    return 1 if refused else 0
