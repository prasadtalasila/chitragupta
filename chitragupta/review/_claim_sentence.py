"""The sentence a citation sits in, with its citation markup tidied away:
what `citation_provenance.claims()` quotes and scores, and so what
`claim_support` hands the entailer.
"""

import re

from chitragupta import citation_gate, sentences


# Parenthetical markup, outside the sentence's grammar, so simply deleted.
_PARENTHETICAL_CITE = re.compile(r"\[@[^\]]+\]|\\citep?\{[^}]*\}")


# Narrative `\citet` is a noun phrase inside the grammar, so deleting it
# left "The vocabulary of sharpens the claim" (#570). Elided as `[...]`
# rather than author-year text: this claim is scored by word overlap with
# the cited paper, which contains its authors' names, so a surname would
# inflate the score; `[...]` adds no word. Only `\citet`, deliberately:
# `\textcite`, `\citealt` and bare `@key` are a separate, pre-existing gap.
_NARRATIVE_CITE = re.compile(r"\\citet\{[^}]*\}")


def sentence_around(text: str, citekey: str) -> str:
    """The sentence within `text` containing `citekey`, markup stripped.

    The split is `chitragupta/sentences.py`'s, shared with
    `overlap_embed.py`. Membership uses `citation_gate`'s extractor, not a
    substring test, which would also match a suffixed sibling `{citekey}a`.
    """
    for part in sentences.split(text):
        if citekey in citation_gate.extract_citekeys_from_line(part):
            return _tidy(part)
    return _tidy(text)


def _tidy(text: str) -> str:
    """Drop parenthetical markup, elide narrative markup, close the gap, so
    "processes [@key], or" does not quote back as "processes , or".
    """
    # Order is free: the patterns are disjoint and `[...]` matches neither.
    stripped = _PARENTHETICAL_CITE.sub("", _NARRATIVE_CITE.sub("[...]", text))
    # `\s++` (possessive, 3.11+): `\s+` backtracks quadratically on long
    # whitespace (Sonar S8786); the matches are identical.
    stripped = re.sub(r"\s++([.,;:!?)])", r"\1", stripped)
    stripped = re.sub(r"\(\s+", "(", stripped)
    return re.sub(r"\s{2,}", " ", stripped).strip(" ,;:")
