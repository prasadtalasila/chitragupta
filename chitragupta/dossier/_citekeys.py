"""Which citekeys a draft's glossary, evidence and rejections mention --
the pipeline's other citekey surface besides the ledger itself.

Split out of chitragupta/dossier.py (#219). The `## Glossary` parser that
used to live here is chitragupta/dossier/_glossary.py since #1138.
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


# The files that mean "this draft *stands on* that paper", as opposed to
# "this draft *looked at* it". The split matters for drift: a citekey
# that leaves the ledger is a finding when the draft cites it and a
# non-event when the draft turned it down, and `MENTIONED_FILES` would
# report the second as the first.
CITED_FILES = (EVIDENCE_MD, SECTIONS_MD)


MENTIONED_FILES = (EVIDENCE_MD, REJECTED_MD, SECTIONS_MD)


def cited_citekeys(dossier: Path, known: "set[str] | None" = None) -> set[str]:
    """Every citekey the dossier mentions, kept or rejected.

    Used to answer "which papers in the corpus were never considered for
    this draft?" -- a more actionable drift signal than a count, because
    it names what to go and look at. Matched loosely (any backticked
    token that looks like a BibTeX key) so that a hand-edited
    `evidence.md` still contributes.

    Every caller here differences the result against a ledger, so every
    caller should pass that ledger as `known` -- see `_sections._citekeys`
    for why separator-free keys need it to be seen at all.
    """
    return _citekeys_in(dossier, MENTIONED_FILES, known)


def rejected_reasons(dossier: Path) -> dict[str, str]:
    """citekey -> why `rejected.md` says this draft turned it down.

    The reason is the part that does not survive being reduced to a set.
    "Turned down because the corpus had nothing better" and "turned down
    because it is about a different field" age completely differently,
    and only the first is worth revisiting when the corpus grows -- so a
    re-grounding pass needs the sentence, not just the membership.
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

    The point is scope, not bookkeeping: a reviser handed "this citekey
    left the ledger" still has to find the prose that leans on it, and
    reading the whole draft to find out is the cost `sections` and this
    both exist to avoid. Absent or hand-mangled rows map nothing, like
    every other read here.
    """
    found: dict[str, list[str]] = {}
    for title, citekeys in citekeys_by_section(dossier, known).items():
        for citekey in citekeys:
            found.setdefault(citekey, []).append(title)
    return found


def citekeys_by_section(dossier: Path, known: "set[str] | None" = None) -> dict[str, list[str]]:
    """section -> the citekeys `sections.md` assigns to it, in row order.

    The file has one parser, and this is it -- `section_citekeys` is this
    inverted. They answer different questions for different callers:
    that one is "who leans on this paper?", for a reviser holding a
    citekey that left the ledger; this one is "what is this section's
    evidence?", for a section writer about to be dispatched. Row order is
    kept because it is the order the run itself chose.

    A section whose citekey cell is empty maps to `[]` rather than being
    dropped. `deep-research` writes this file at outline time, before
    every section has evidence assigned, and "planned but empty" and
    "not a section at all" want opposite fixes -- one is a gap to fill,
    the other a typo in the section name.
    """
    path = dossier / SECTIONS_MD
    if not path.is_file():
        return {}
    found: dict[str, list[str]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or set(stripped) <= set("|-: \t"):
            continue
        # `\|` is markdown's literal pipe, and a heading containing one is
        # written that way (by hand or by `sections --citekeys`). Splitting
        # already skips it; unescaping here is the other half, so the
        # section name read back is the heading as it appears in the draft
        # rather than its escaped spelling -- which is what a caller then
        # matches against `sections()` output.
        cells = [cell.strip().replace(r"\|", "|") for cell in _ROW_SPLIT.split(stripped.strip("|"))]
        if len(cells) != 2 or [cell.lower() for cell in cells] == ["section", "citekeys"]:
            continue
        found[cells[0]] = _citekeys(cells[1], known)
    return found


# A heading that *opens* with a delimited token: ``## `Doe2024` `` and
# ``## `Doe2024` -- kept for section 3`` both, since `evidence_blocks`'
# own docstring names the second as a normal form. Structural, not prose
# -- writing a citekey as an `evidence.md` heading is the dossier
# declaring "this is a paper", which is why `declared_citekeys` may trust
# a shape `_sections._KEY` refuses. The anchor is what keeps it
# structural: a token further along the line is prose about the block,
# and prose may not promote a word to a citekey.
_KEY_HEADING = re.compile(rf"^(?:`({_LOOSE_KEY})`|@({_LOOSE_KEY}))(?:\s|$)")


def declared_citekeys(dossier: Path) -> set[str]:
    """The citekeys `evidence.md` declares by giving each one a heading.

    Read alongside a ledger as the `known` set for every path that
    differences a dossier against one. The ledger alone is not enough for
    the question `drift().missing` asks -- "which cited papers have *left*
    the corpus?" -- because a key that left it is by definition not in it,
    so a separator-free citekey would have stayed invisible exactly in the
    case #506/M-28 reported (a `Doe2024` dropped from the bib was never
    reported as broken).

    Only a heading counts, and only one that *opens* with a delimited
    token. That is what keeps the false-positive line the separator
    requirement used to hold on its own: prose cannot promote a word to a
    citekey, because prose is not the start of a heading.
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

    What a dispatched subagent reads instead of being handed the same
    text pasted into its prompt. The block is returned verbatim, heading
    included, because what a genre skill puts under one varies (a
    `relevance:`/`claim:`/`quote:` set, a legacy `relevance:`/`support:`
    pair a pre-A2 dossier still carries, a claim list) and this module
    does not own that shape -- only the heading that addresses it.

    Keyed on the first citekey-shaped token in the heading, so
    ``## `smith_x_2024` -- kept for section 3`` is addressable as
    `smith_x_2024`, and so is ``## @smith_x_2024`` -- either delimiter,
    since `_citekeys` reads both. A heading carrying no citekey token at
    all falls back to its own text: a hand-written dossier is a supported
    input everywhere else here, and a block nobody can address is a block
    the next run re-retrieves.

    A key with more than one block keeps the **first** and the rest are
    counted for `duplicate_evidence_keys` to report. Both halves are the
    fix for #506/m-65: this used to keep the last silently, so a second
    block appended for the same paper -- the natural result of two
    retrieval passes, or of a hand edit that pasted a heading twice --
    displaced the evidence a drafting run had already been given, with
    nothing anywhere saying so.
    """
    return _parse_evidence(dossier)[0]


def duplicate_evidence_keys(dossier: Path) -> dict[str, int]:
    """citekey -> how many blocks `evidence.md` carries for it, for the
    keys carrying more than one. Empty when every key appears once.

    Separate from `evidence_blocks` rather than a second return value
    because the two answer different questions and almost every caller
    only wants the first -- but the count has to come from the same parse,
    which is why both go through `_parse_evidence`.
    """
    return _parse_evidence(dossier)[1]


def evidence_block_spans(dossier: Path) -> dict[str, tuple[int, int]]:
    """citekey -> the `[start, end)` line range its block occupies.

    What `dossier prune` deletes by, instead of matching the text
    `evidence_blocks` returns. That text is *reconstructed* --
    `"\\n".join(body).rstrip() + "\\n"` below -- so it is not in general
    a substring of the file it came from, and three ordinary shapes
    break the match outright: CRLF line endings (every block), no
    trailing newline at EOF (the last block), and trailing whitespace
    on the final line (the last block). A substring-matching prune
    reports "no matching block found" on a correct input and silently
    does nothing, which reads as "that key is not here" when it is.

    A span cannot drift from the file that way, and the caller joining
    `splitlines(keepends=True)` around one preserves whatever line
    endings the file had rather than rewriting them to `\\n`.

    Keyed like `evidence_blocks`, first block per key -- so a duplicated
    heading spans only its first occurrence, and `prune` refuses that
    case rather than removing one of two and reporting success.
    """
    return _parse_evidence(dossier)[2]


def _parse_evidence(
    dossier: Path,
) -> tuple[dict[str, str], dict[str, int], dict[str, tuple[int, int]]]:
    """`evidence.md` read once: its first block per key, the counts for
    any key that appeared more than once, and each key's line span.

    Three returns from one pass rather than three parses, and the span
    is information this walk already had and used to discard: it closes
    a block on the next `##` heading, which is exactly where the span
    ends. `evidence_blocks`/`duplicate_evidence_keys`/
    `evidence_block_spans` are the three thin accessors over it, and
    index `[0]`/`[1]`/`[2]` respectively.
    """
    path = dossier / EVIDENCE_MD
    if not path.is_file():
        return {}, {}, {}
    # Bound in one statement rather than three: this walk is at the
    # C1 statement ceiling, and three dict literals is where the
    # headroom went. `agenda.__init__._print_recheck` groups its own
    # locals the same way.
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


# suggest_acronyms/NoUserAcronymsFile/apply_suggestions/_cmd_acronyms_suggest
# live in chitragupta/dossier/_acronyms.py, not here -- split out once --apply
# pushed this module past docs/CODE-STANDARDS.md's C2 line limit. That
# module imports glossary_terms from chitragupta/dossier/_glossary.py.
