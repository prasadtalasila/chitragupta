"""Which citekeys a draft's glossary, evidence and rejections mention --
the pipeline's other citekey surface besides the ledger itself.
"""

import re
from pathlib import Path

from chitragupta.dossier import (
    EVIDENCE_MD,
    REJECTED_MD,
    SECTIONS_MD,
    _ROW_SPLIT,
)
from chitragupta.dossier._sections import _LOOSE_KEY, _citekeys


def _citekeys_in(
    dossier: Path, names: tuple[str, ...], known: "set[str] | None" = None
) -> set[str]:
    found: set[str] = set()
    for name in names:
        path = dossier / name
        if path.is_file():
            found |= set(_citekeys(path.read_text(encoding="utf-8"), known))
    return found


# The files meaning "this draft *stands on* that paper", not "looked at
# it": a key leaving the ledger is a finding only for the former.
CITED_FILES = (EVIDENCE_MD, SECTIONS_MD)


MENTIONED_FILES = (EVIDENCE_MD, REJECTED_MD, SECTIONS_MD)


def cited_citekeys(dossier: Path, known: "set[str] | None" = None) -> set[str]:
    """Every citekey the dossier mentions, kept or rejected.

    Callers difference this against a ledger, so they should pass that
    ledger as `known` (see `_sections._citekeys`).
    """
    return _citekeys_in(dossier, MENTIONED_FILES, known)


def rejected_reasons(dossier: Path) -> dict[str, str]:
    """citekey -> why `rejected.md` says this draft turned it down.

    The reason matters: "nothing better in the corpus" is worth revisiting
    when the corpus grows, "different field" is not.
    """
    path = dossier / REJECTED_MD
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in _ROW_SPLIT.split(stripped.strip("|"))]
        if len(cells) != 3:
            continue
        for citekey in _citekeys(cells[0]):
            found[citekey] = cells[2]
    return found


def section_citekeys(dossier: Path, known: "set[str] | None" = None) -> dict[str, list[str]]:
    """citekey -> the `sections.md` sections that cite it.

    Scopes a reviser to the prose leaning on a departed key. Absent or
    mangled rows map nothing.
    """
    found: dict[str, list[str]] = {}
    for title, citekeys in citekeys_by_section(dossier, known).items():
        for citekey in citekeys:
            found.setdefault(citekey, []).append(title)
    return found


def citekeys_by_section(dossier: Path, known: "set[str] | None" = None) -> dict[str, list[str]]:
    """section -> the citekeys `sections.md` assigns to it, in row order.

    The file's one parser; `section_citekeys` is this inverted. An empty
    citekey cell maps to `[]`: `deep-research` writes the file before
    evidence is assigned, and "planned but empty" is not "no section".
    """
    path = dossier / SECTIONS_MD
    if not path.is_file():
        return {}
    found: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|-: \t"):
            continue
        # Unescape markdown's literal `\|` so the name matches the heading
        # as `sections()` reads it.
        cells = [cell.strip().replace(r"\|", "|") for cell in _ROW_SPLIT.split(stripped.strip("|"))]
        if len(cells) != 2 or [cell.lower() for cell in cells] == ["section", "citekeys"]:
            continue
        found[cells[0]] = _citekeys(cells[1], known)
    return found


# A heading that *opens* with a delimited token (optionally followed by a
# note). Structural: a citekey heading declares "this is a paper", which
# is why `declared_citekeys` may trust a shape `_sections._KEY` refuses.
# The anchor keeps prose from promoting a word to a citekey.
_KEY_HEADING = re.compile(rf"^(?:`({_LOOSE_KEY})`|@({_LOOSE_KEY}))(?:\s|$)")


def declared_citekeys(dossier: Path) -> set[str]:
    """The citekeys `evidence.md` declares by giving each one a heading.

    Used with the ledger as `known`: a key that *left* the ledger is not
    in it, so a separator-free key would otherwise stay invisible to
    `drift().missing` (#506/M-28). Only a heading that opens with the
    token counts, so prose cannot promote a word to a citekey.
    """
    path = dossier / EVIDENCE_MD
    if not path.is_file():
        return set()
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("## "):
            continue
        match = _KEY_HEADING.match(line[3:].strip())
        if match:
            found.add(match.group(1) or match.group(2))
    return found


def evidence_blocks(dossier: Path) -> dict[str, str]:
    """citekey -> its whole `## `citekey`` block in `evidence.md`.

    Verbatim, heading included: this module owns only the heading, not
    the block's shape. Keyed on the first citekey token in the heading
    (either delimiter), falling back to the heading text. The **first**
    block per key wins and duplicates are counted for
    `duplicate_evidence_keys` (#506/m-65): keeping the last silently
    displaced evidence a run had already been given.
    """
    return _parse_evidence(dossier)[0]


def duplicate_evidence_keys(dossier: Path) -> dict[str, int]:
    """citekey -> how many blocks `evidence.md` carries for it, for the
    keys carrying more than one. Empty when every key appears once."""
    return _parse_evidence(dossier)[1]


def evidence_block_spans(dossier: Path) -> dict[str, tuple[int, int]]:
    """citekey -> the `[start, end)` line range its block occupies.

    What `dossier prune` deletes by: `evidence_blocks` text is
    reconstructed, so substring matching fails on CRLF, a missing final
    newline or trailing whitespace and silently does nothing. Spans keep
    the file's line endings. First block per key, so `prune` refuses a
    duplicated heading rather than removing one of two.
    """
    return _parse_evidence(dossier)[2]


def _parse_evidence(
    dossier: Path,
) -> tuple[dict[str, str], dict[str, int], dict[str, tuple[int, int]]]:
    """`evidence.md` read once: its first block per key, the counts for
    any key that appeared more than once, and each key's line span."""
    path = dossier / EVIDENCE_MD
    if not path.is_file():
        return {}, {}, {}
    # Bound in one statement: this walk is at the C1 statement ceiling.
    found: dict[str, str] = {}
    counts, spans = {}, {}
    key: str | None = None
    body: list[str] = []
    start = 0

    def close(end: int) -> None:
        if key is None:
            return
        counts[key] = counts.get(key, 0) + 1
        found.setdefault(key, "\n".join(body).rstrip() + "\n")
        spans.setdefault(key, (start, end))

    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## "):
            close(index)
            heading = line[3:].strip()
            tokens = _citekeys(heading)
            key = tokens[0] if tokens else heading.strip("` ")
            body = [line]
            start = index
            continue
        if key is not None:
            body.append(line)
    close(len(lines))
    return found, {name: count for name, count in counts.items() if count > 1}, spans


# The acronym suggester lives in chitragupta/dossier/_acronyms.py.
