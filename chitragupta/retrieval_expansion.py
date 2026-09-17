"""Query-side acronym expansion for BM25 retrieval (#789).

BM25 is exact-match lexical, so a query for `DT fidelity` reaches no
paper that spells "digital twin" out and never writes the abbreviation --
which in a digital-twin corpus is most of them. This module adds an
acronym's expansion to the query's terms, at a weight `[retrieval].
acronym_expansion` sets, so the abbreviation a field actually uses is not
the one form the ranker cannot see.

**Where the vocabulary comes from, and why it is this one.**
`chitragupta/acronyms.py` -- the vendored `assets/style/acronyms.toml`
merged with the user's own `[style].acronyms` file. That vocabulary is
tier-1 and stdlib-only, and it is *authored, not derived*, which is the
whole reason to prefer it over #771's `content/topics.json`: `retrieval.py`
promises that running the enrichment layer does not change what BM25
ranks, and expanding from an enrichment artefact would make a ranking
depend on whether an optional stage had run. Nothing here reads a model,
an index or a derived file, and nothing here may grow a second source.

**Off is structural, not asserted.** At weight 0 -- the shipped default,
see `config.ACRONYM_EXPANSION_WEIGHT` for why -- `expand` returns `[]`
before it loads a vocabulary at all, so `search` passes no added terms
and `retrieval_scoring.bm25_scores` takes the same path and the same
arithmetic it took before this module existed. "With it off, ranking is
identical to today" is then a property of the code rather than of a test.

**One direction only.** A query saying `DT` reaches documents saying
"digital twin"; a query saying "digital twin" still does not reach a
document that only ever writes `DT`, because nothing here touches the
index. That reverse direction is document-side expansion, which #789
rejects on cost: it would rewrite the index on every edit of the acronym
file, where this costs one dictionary lookup per query term.

**A single-character acronym can never expand.** `_tokenize`'s floor
drops it from the query before this module sees it, so it is not in
`terms` and no lookup is attempted. Two characters and up is the
interesting range and is exactly what #798 admitted to the index.
"""

import sys
from typing import Callable

from chitragupta import acronyms, config


def expand(terms: list[str], tokenize: Callable[[str], list[str]]) -> list[tuple[str, str]]:
    """`(acronym, added term)` pairs to rank `terms` with, in query order.

    `tokenize` is passed in rather than imported, the same seam
    `retrieval_scoring.field_freqs` uses and for the same reason: it
    lives in `retrieval.py`, which imports this module, and taking it as
    an argument is what keeps that one-directional. It also means an
    expansion is tokenized by exactly the rule the index was built with,
    so a term this adds is a term a document can be matched on -- an
    expansion tokenized any other way could add "co-simulation" as one
    string and match nothing anywhere.

    A term the caller already typed is never added twice: it stays at
    full weight rather than being demoted to the expansion weight, which
    is what would happen if "digital" arrived both ways and the added
    copy won. Two acronyms sharing a word of their expansions likewise
    contribute it once. Both are ordinary in the vocabularies this reads
    ("digital twin"/"digital model"), not edge cases.

    The lookup is case-folded on the vocabulary's side: its keys are
    written as the acronym is printed (`DT`), and `terms` has been
    through `_tokenize`, which lowercases. An entry whose key is not a
    single token -- punctuation, a space -- therefore matches nothing,
    which is the correct reading of a key no query can contain.
    """
    if not config.ACRONYM_EXPANSION_WEIGHT:
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


def weights(added: list[tuple[str, str]]) -> dict[str, float] | None:
    """The per-term multiplier `bm25_scores` takes, or `None` for nothing.

    `None` rather than an empty dict, so the ranker's "was anything
    added?" test is an identity check it can make once per call instead
    of a lookup per (document, term) pair -- the same shape
    `retrieval_scoring.field_deltas`'s empty list has, and the thing that
    keeps this free for everyone who has not turned it on.
    """
    if not added:
        return None
    return {token: config.ACRONYM_EXPANSION_WEIGHT for _, token in added}


def describe(added: list[tuple[str, str]]) -> str:
    """`added` as one line, for the caller that has to explain a result.

    #789 asks that the retrieval log record which terms were added, so
    that a caller can see *why* a result surfaced rather than inferring
    it. This is that record's one rendering, shared by the CLI's note and
    `retrieval.md`'s `expanded` column so the two cannot drift: an
    acronym, an arrow, the terms it contributed, semicolons between
    acronyms. Empty string for an empty list, which is what both callers
    write when nothing was added.
    """
    by_acronym: dict[str, list[str]] = {}
    for acronym, token in added:
        by_acronym.setdefault(acronym, []).append(token)
    return "; ".join(f"{a} -> {' '.join(tokens)}" for a, tokens in by_acronym.items())


def announce(terms: list[str], tokenize: Callable[[str], list[str]]) -> str:
    """Print the CLI's expansion note for `terms`, and return `describe`.

    Prints nothing and returns `""` when nothing was added, which is
    every call at the shipped default. `stderr`, beside the CLI's
    "too short to search on" note, for the same reason that one uses it:
    a genre skill parses this command's stdout as a documented contract,
    and a note about the query is not a result.

    Here rather than in `retrieval_cli.py`, which is at
    docs/CODE-STANDARDS.md's 250-code-line ceiling with nothing to give
    -- and it is not a bad home: the expansion, its one-line rendering
    and the note that shows it to a person are one fact stated three
    ways, and keeping them in one file is what stops the note drifting
    from what was actually added. `search()` never calls this: what a
    library adds to a query is the caller's business to *read*, through
    `expand`, not something a ranker should print from underneath them.
    """
    added = expand(terms, tokenize)
    if not added:
        return ""
    described = describe(added)
    print(f"  [note] acronym expansion added: {described}", file=sys.stderr)
    return described
