"""The word set a passage is matched on: which words distinguish a claim.

Split from `chitragupta/passages.py`, which was 262 code lines against
docs/CODE-STANDARDS.md's 250 ceiling and carried a register entry saying
so. The boundary is the one that module's own docstring already draws:
everything there is about *where a citekey's text comes from* -- sidecars,
the ledger, form feeds, `pdftotext` -- while this is a word set read off
that ladder's output rather than part of finding it.

The vocabulary itself -- the stopwords and the floor -- moved to
`chitragupta/_tokens.py` as its `DISTINCTIVE` setting (issue 845), beside
the `INDEX` setting BM25 reads, so the two are one rule with two named
settings rather than two copies that drift.

`passages.distinctive` still resolves: the name is re-exported there, the
way `chitragupta/enrich/embed_index.py` re-exports `embed_text`'s, so no
caller changes. The dependency runs one way, `passages` -> here.
"""

from chitragupta import _tokens


def distinctive(text: str) -> set[str]:
    return set(_tokens.words(text, _tokens.DISTINCTIVE))
