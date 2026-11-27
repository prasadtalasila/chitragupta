"""Query-side acronym expansion for BM25 retrieval (#789).

BM25 is exact-match, so `DT fidelity` misses papers that only write
"digital twin". With `[retrieval].acronym_expansion` on (the default), an
acronym's expansion joins the query at full weight: the docs/RETRIEVAL.md
sweep put full weight ahead of 0.5 and 0.25 on every figure.

The vocabulary is `chitragupta/acronyms.py`'s, authored rather than
derived (not #771's `topics.json`), so ranking never depends on whether
the enrichment stage ran; nothing here may grow a second source. Off is
structural: `expand` returns `[]` before loading anything.

One direction only: document-side expansion was rejected in #789 as it
would rewrite the index on every acronym-file edit. Single-character
acronyms never reach here (`_tokenize`'s floor, #798).
"""

from typing import Callable

from chitragupta import acronyms, config


def expand(terms: list[str], tokenize: Callable[[str], list[str]]) -> list[tuple[str, str]]:
    """`(acronym, added term)` pairs to rank `terms` with, in query order.

    `tokenize` is passed in because `retrieval.py` imports this module,
    and so an expansion is tokenized exactly as the index was. A term
    already typed, or shared by two expansions, is added once, keeping
    full weight. The lookup is case-folded on the vocabulary side; a
    multi-token key matches nothing.
    """
    if not config.ACRONYM_EXPANSION:
        return []
    vocabulary = {key.lower(): value for key, value in acronyms.load_vocabulary().items()}
    present = set(terms)
    added: list[tuple[str, str]] = []
    for term in terms:
        expansion = vocabulary.get(term)
        if expansion is None:
            continue
        for token in tokenize(expansion):
            if token in present:
                continue
            present.add(token)
            added.append((term, token))
    return added
