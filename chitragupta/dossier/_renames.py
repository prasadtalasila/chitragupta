"""Citekeys the corpus layer recorded as renamed, found in a draft and
swapped for their replacement (plans/1211-cg-collections-and-renames.md).

`chitragupta/sync_renames.py` records `old -> new` in the ledger when a
key leaves the bib and the same paper is there under another one; it
edits nothing. This is the drafting layer's half: `dossier status`
lists a draft's renamed keys, and `dossier apply-renames` swaps them in
the draft, `evidence.md`, `sections.md` and `rejected.md` -- the last so
a paper the draft declined stays declined under its new key.

**Nothing is invented.** The new key is the one the ledger recorded,
followed to the end of a chain (`a -> b -> c`), and it must be in the
ledger now; a cycle or a missing target refuses the whole swap and
writes nothing. A rename whose two PDFs differ (the importer said so,
the hashes did not) changes which text the draft's quotes came from, so
those are named for `review quotation` to re-check.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from chitragupta import ledger, ledger_tables
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
    paths = [draft, *(dossier_dir(draft) / name for name in SWAPPED_FILES)]
    return {path: path.read_text(encoding="utf-8") for path in paths if path.is_file()}


def _plan(draft: Path, texts: dict[Path, str]) -> list[tuple[str, str, bool]]:
    try:
        with ledger.reading() as con:
            renames, known = ledger_tables.renames(con), ledger.known_citekeys(con)
    except (ledger.NoLedger, ledger.StaleLedger, ledger.UnreadableLedger) as exc:
        raise DossierError(f"{exc}; run `chitragupta corpus sync` first") from exc
    plan = []
    for old in cited(texts.values(), renames):
        resolved = final(renames, old)
        if resolved is None:
            raise DossierError(
                f"the recorded renames of {old} form a cycle; nothing was changed. "
                "Ask which key the draft should cite."
            )
        if resolved[0] not in known:
            raise DossierError(
                f"{old} was renamed to {resolved[0]}, but {resolved[0]} is not in the "
                "ledger; nothing was changed. Run sync, or ask which key to cite."
            )
        plan.append((old, *resolved))
    return plan


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
    """Swap every recorded rename `draft` and its dossier cite, all or none."""
    draft = Path(draft)
    texts = _texts(draft)
    plan = _plan(draft, texts)
    if not plan:
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
    for path in changed:
        path.write_text(texts[path], encoding="utf-8")
    sections = sorted({title for old, _n, _s in plan for title in by_key.get(old, [])})
    _log(draft, applied, sections)
    return applied


def _cmd_apply_renames(args) -> int:
    applied = apply_renames(Path(args.draft))
    if args.json:
        print(json.dumps({"applied": [asdict(a) for a in applied]}, indent=2))
        return 0
    if not applied:
        print("No recorded rename applies to this draft.")
    for item in applied:
        print(f"renamed {item.old} -> {item.new} in {len(item.files)} file(s)")
    if any(not item.same_pdf for item in applied):
        print(
            "re-check quotes, a renamed paper's PDF changed: "
            f"python -m chitragupta.review quotation {args.draft}"
        )
    return 0
