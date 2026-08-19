"""Which citekeys a draft's glossary, evidence and rejections mention --
the pipeline's other citekey surface besides the ledger itself.

Split out of src/dossier.py (#219). `glossary_terms` also backs
src/dossier/_acronyms.py's `suggest_acronyms`/`apply_suggestions` and
src/style_acronym_drift.py -- both read the same `## Glossary` this
module already parses for citekeys, rather than parsing it again.
"""

import re
from pathlib import Path

from src.dossier import EVIDENCE_MD, REJECTED_MD, SCOPE_MD, SECTIONS_MD, _ROW_SPLIT, dossier_dir
from src.dossier._sections import _citekeys

# `- **Term** -- definition` bullets under a `## Glossary` heading in
# scope.md. A forgiving parser, not a schema: #190's resolving comment
# found a real 15-chapter book had already converged on this exact shape
# with no format rule in force, so this reads what a genre skill's step 0
# already writes by hand rather than imposing a new one. A line that
# doesn't match -- a human typed it differently -- is skipped, the same
# "degrades to unavailable rather than to an error" policy
# docs/DRAFT-ITERATION.md states for the rest of this file.
_GLOSSARY_HEADING = re.compile(r"^## Glossary\s*$", re.MULTILINE)


_NEXT_HEADING = re.compile(r"^## ", re.MULTILINE)


_GLOSSARY_TERM = re.compile(r"^-\s*\*\*(?P<term>[^*]+)\*\*\s*--\s*", re.MULTILINE)


def glossary_terms(draft: Path) -> dict[str, str]:
    """Recorded `term -> definition` pairs from the draft's `## Glossary`.

    `{}` if there's no dossier yet, no `## Glossary` heading, or no
    bullet in the recognised shape -- never an error.
    """
    scope = dossier_dir(draft) / SCOPE_MD
    if not scope.is_file():
        return {}
    text = scope.read_text(encoding="utf-8")
    heading = _GLOSSARY_HEADING.search(text)
    if not heading:
        return {}
    next_heading = _NEXT_HEADING.search(text, heading.end())
    body = text[heading.end():next_heading.start() if next_heading else len(text)]

    matches = list(_GLOSSARY_TERM.finditer(body))
    terms: dict[str, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        definition = body[match.end():end].strip()
        if definition:
            terms[match.group("term").strip()] = definition
    return terms


def _citekeys_in(dossier: Path, names: tuple[str, ...]) -> set[str]:
    found: set[str] = set()
    for name in names:
        path = dossier / name
        if path.is_file():
            found |= set(_citekeys(path.read_text(encoding="utf-8")))
    return found


# The files that mean "this draft *stands on* that paper", as opposed to
# "this draft *looked at* it". The split matters for drift: a citekey
# that leaves the ledger is a finding when the draft cites it and a
# non-event when the draft turned it down, and `MENTIONED_FILES` would
# report the second as the first.
CITED_FILES = (EVIDENCE_MD, SECTIONS_MD)


MENTIONED_FILES = (EVIDENCE_MD, REJECTED_MD, SECTIONS_MD)


def cited_citekeys(dossier: Path) -> set[str]:
    """Every citekey the dossier mentions, kept or rejected.

    Used to answer "which papers in the corpus were never considered for
    this draft?" -- a more actionable drift signal than a count, because
    it names what to go and look at. Matched loosely (any backticked
    token that looks like a BibTeX key) so that a hand-edited
    `evidence.md` still contributes.
    """
    return _citekeys_in(dossier, MENTIONED_FILES)


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


def section_citekeys(dossier: Path) -> dict[str, list[str]]:
    """citekey -> the `sections.md` sections that cite it.

    The point is scope, not bookkeeping: a reviser handed "this citekey
    left the ledger" still has to find the prose that leans on it, and
    reading the whole draft to find out is the cost `sections` and this
    both exist to avoid. Absent or hand-mangled rows map nothing, like
    every other read here.
    """
    found: dict[str, list[str]] = {}
    for title, citekeys in citekeys_by_section(dossier).items():
        for citekey in citekeys:
            found.setdefault(citekey, []).append(title)
    return found


def citekeys_by_section(dossier: Path) -> dict[str, list[str]]:
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
        cells = [cell.strip().replace(r"\|", "|")
                 for cell in _ROW_SPLIT.split(stripped.strip("|"))]
        if len(cells) != 2 or [cell.lower() for cell in cells] == ["section", "citekeys"]:
            continue
        found[cells[0]] = _citekeys(cells[1])
    return found


def evidence_blocks(dossier: Path) -> dict[str, str]:
    """citekey -> its whole `## `citekey`` block in `evidence.md`.

    What a dispatched subagent reads instead of being handed the same
    text pasted into its prompt. The block is returned verbatim, heading
    included, because what a genre skill puts under one varies (a
    `relevance:`/`support:` pair, a claim list, a quotation) and this
    module does not own that shape -- only the heading that addresses it.

    Keyed on the first citekey-shaped token in the heading, so
    ``## `smith_x_2024` -- kept for section 3`` is addressable as
    `smith_x_2024`, and so is ``## @smith_x_2024`` -- either delimiter,
    since `_citekeys` reads both. A heading carrying no citekey token at
    all falls back to its own text: a hand-written dossier is a supported
    input everywhere else here, and a block nobody can address is a block
    the next run re-retrieves.
    """
    path = dossier / EVIDENCE_MD
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    key: str | None = None
    body: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if key is not None:
                found[key] = "\n".join(body).rstrip() + "\n"
            heading = line[3:].strip()
            tokens = _citekeys(heading)
            key = tokens[0] if tokens else heading.strip("` ")
            body = [line]
            continue
        if key is not None:
            body.append(line)
    if key is not None:
        found[key] = "\n".join(body).rstrip() + "\n"
    return found


# suggest_acronyms/NoUserAcronymsFile/apply_suggestions/_cmd_acronyms_suggest
# live in src/dossier/_acronyms.py, not here -- split out once --apply
# pushed this module past docs/CODE-STANDARDS.md's C2 line limit. That
# module imports glossary_terms from this one.
