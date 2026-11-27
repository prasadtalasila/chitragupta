"""A paper's own bibliography, kept out of what BM25 reads.

Indexing the reference list (18.7% of tokens on a 497-item corpus) made
queries match the bibliographies of citing papers and penalised long
reference lists through length normalisation (#768).

Docling has no `reference` label, so the cut is structural: a
`section_header` passage that is one of the headings below, and
everything from the last one on. A regex over flattened text and
dropping `list_item`s were both declined in the issue.

Rung 2 only (`passages.corpus_passages`): retrieval.py promises that
running `chitragupta.enrich` does not change BM25. A `pdftotext` parse
has no sidecar and is indexed as before. Cutting to the end is right:
what follows is mostly acknowledgements and biographies; the measured
costs are in docs/RETRIEVAL.md.

Stdlib only: BM25 is tier 1, under bare `python` (docs/ARCHITECTURE.md).
"""

import re
from pathlib import Path

from chitragupta import passages

# Anchored at both ends so "Reference architecture" is not a cut point.
# `works cited` fires nowhere here but a corpus from another field has it.
_HEADER = re.compile(
    r"^(\d+\s*[.)]?\s*)?(references|bibliography|works cited|literature cited)\s*[:.]?$",
    re.I,
)


def reference_cut_index(found: list) -> int | None:
    """The position of the last reference heading in `found`, or None.

    The shared rule: the passage-level index (#769) cuts on this same
    boundary, since two rules for one span would drift apart.
    """
    for i in range(len(found) - 1, -1, -1):
        passage = found[i]
        if passage.label == "section_header" and _HEADER.match((passage.text or "").strip()):
            return i
    return None


def _last_header(found: list) -> str | None:
    """The text of the last reference heading in `found`, or None."""
    cut = reference_cut_index(found)
    return None if cut is None else (found[cut].text or "").strip()


def strip_references(text: str, parsed_path: str | None) -> str:
    """`text` truncated at the reference heading its sidecar records.

    Unchanged when there is no sidecar, no heading, or a heading absent
    from `text` (a hand-edited sidecar): indexing nothing would be worse
    than the bibliography. Takes `parsed_path` because two callers have no
    citekey column; its stem only opens the sidecar, is never cited or
    written, and came from the ledger, so no citekey is derived here.
    """
    if not parsed_path:
        return text
    found = passages.corpus_passages(Path(parsed_path).stem)
    if not found:
        return text
    header = _last_header(found)
    if header is None:
        return text
    cut = text.rfind(header)
    if cut == -1:
        return text
    return text[:cut]
