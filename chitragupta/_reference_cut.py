"""A paper's own bibliography, kept out of what BM25 reads.

`chitragupta/retrieval.py` indexed the whole of
`content/parsed/<citekey>.txt`, reference list included, so every paper
carried dozens of *other* papers' titles as its own body text and a short
query naming a subject matched the bibliography of every paper that
merely cites work on it. Measured on this project's 497-item corpus,
792,963 of 4,231,367 indexed tokens sat after a reference header --
18.7%, median 17.9% of a document, maximum 80.8%. It cost twice: spurious
term frequencies, and an inflated `length`, so a paper with a long
reference list was penalised by BM25's own length normalization for text
that is not its own (#768).

**What identifies the span, since the label does not.** Docling has no
`reference` label -- `DocItemLabel` runs caption/chart/code/.../
section_header/table/text/title, the same caveat `chitragupta/_abstract.py`
records about there being no `abstract` label. So the cut is structural
rather than semantic: a `section_header` passage whose text *is* one of
the headings below, and everything from the last of them onward. Two
alternatives were weighed and declined in the issue: a regex over the
flattened `.txt` (pdftotext -layout splices two-column pages, so a header
can land mid-line, and nothing there marks the end of the body), and
dropping the `list_item` passages after the header (numbered references
are frequently plain `text`, so position after the heading is what
carries the signal, not the label).

**Rung 2 alone, deliberately.** `passages.corpus_passages` reads this
layer's own sidecar and never the enrichment layer's richer rung-1 parse,
because `chitragupta/retrieval.py`'s docstring promises that running
`chitragupta.enrich` does not change what BM25 ranks. A `pdftotext` parse
leaves no sidecar at all, and those items are indexed exactly as before
-- backend-dependent in the way that docstring already licenses.

**What the rule costs, measured rather than assumed.** 459 of 497 parsed
items have a locatable header; the other 38 are untouched. On 79 of those
459 a `section_header` follows the cut -- overwhelmingly
`Acknowledgements`, `Competing interests`, `Author contributions` and
author biographies, which is why "to the end of the document" is the
right rule and not a lazy one. Two outliers pay for it with real prose: a
working paper's appendix tables (`humlum_large_2025`) and a report whose
last chapter bibliography is followed by workshop summaries. A
per-chapter book keeps its *earlier* chapters' bibliographies indexed,
for the same reason. docs/RETRIEVAL.md carries these figures.

Stdlib only, like every other module `chitragupta/retrieval.py` reaches
for: BM25 is the tier-1 path that must run under bare `python` with no
venv (docs/ARCHITECTURE.md).
"""

import re
from pathlib import Path

from chitragupta import passages

# The headings this corpus actually uses, anchored at both ends so
# "Reference architecture" and "Bibliography of the author" are not cut
# points. Counts over 497 parsed items: `references` 500 headers,
# `bibliography` 8, `literature cited` 1, and 8 of those carry a section
# number ("7 REFERENCES"). `works cited` fires nowhere here and is kept
# because the issue names it and a corpus from another field will have it.
_HEADER = re.compile(
    r"^(\d+\s*[.)]?\s*)?(references|bibliography|works cited|literature cited)\s*[:.]?$",
    re.I,
)


def reference_cut_index(found: list) -> int | None:
    """The position of the last reference heading in `found`, or None.

    The same rule as `strip_references` below, reported as a position in
    the passage list rather than applied to flattened text. A
    passage-level index (#769) drops every passage from here on, and must
    cut on *this* boundary rather than re-deriving one: two rules for one
    span drift apart the first time a heading is added to `_HEADER`, and
    the drift would show up as a bibliography entry ranked as body text
    on one path and not the other.

    Public where `strip_references`'s own helper was private, because
    that is the difference: this is the shared rule, and the truncation
    below is one of its two consumers.
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

    Returned unchanged when there is no sidecar, no heading in it, or --
    the case a hand-edited sidecar could produce -- a heading whose text
    is nowhere in `text`. Truncating at position zero on the strength of
    a record the parse did not produce would index nothing at all, which
    is a worse answer than the bibliography this is here to drop.

    `parsed_path` rather than a citekey because the two other callers of
    `retrieval._full_text` (`retrieval_cli.evidence` and
    `dossier/_drift.py`) select `title, parsed_path, status` and have no
    citekey column to pass. The stem of that path is the citekey -- both
    are written by the corpus layer's own parse, side by side in
    `content/parsed/` -- so `passages.sidecar_path` still owns where the
    file lives, and nothing here rebuilds that knowledge. That stem is
    used to open a file and for nothing else: it is never returned, never
    cited, and never written anywhere a draft could read it, so no
    citekey is derived here in the sense SOUL.md forbids. It needs no
    `citekey_problem` check either, unlike `passages.source_passages`,
    whose callers hand it keys scraped out of a draft: a `Path.stem`
    holds no separator, and this one came from the ledger.
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
