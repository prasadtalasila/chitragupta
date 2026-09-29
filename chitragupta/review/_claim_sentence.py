"""The sentence a citation sits in, with its citation markup tidied away.

What `citation_provenance.claims()` quotes back to a reviewer and scores
against the cited source, and so what `claim_support` hands the entailer.
Split from `citation_provenance.py`, which decides *where* a claim is --
which block, which citation -- while this module decides what its text
reads as once found.
"""

import re

from chitragupta import citation_gate, sentences


# Parenthetical citation markup, which stands *outside* the sentence's
# grammar -- an aside the reader could skip -- so the sentence is only
# grammatical once it is gone.
_PARENTHETICAL_CITE = re.compile(r"\[@[^\]]+\]|\\citep?\{[^}]*\}")


# Narrative `\citet`, which is the opposite case and used to be swept up
# by the pattern above (#570): it renders as "Smith et al. (2024)", a
# noun phrase *inside* the grammar, so deleting it left "The vocabulary
# of sharpens the claim" -- a dangling "of" quoted back at a reviewer as
# though the draft had written it.
#
# An elision rather than the author-year text it stands for, for a reason
# specific to this aid. `_claims.INLINE_TABLE_REF` faces the same
# missing-noun problem and substitutes the word ("Table"), but C1 does
# not *score* its sentences; this claim is scored by word overlap against
# the cited paper's own text, which contains its own authors' names. A
# substituted surname would hand every narrative citation a free hit
# unrelated to the claim, inflating exactly the band that flags weak
# support. `[...]` contributes no word to `passages.distinctive`
# (`[a-z0-9]+`), so the score is unchanged and only the quoted text moves.
#
# Only `\citet`, deliberately narrow: `\textcite`, `\citealt`, `\Citet`
# and pandoc's bare `@key` are narrative too, but the pattern above never
# matched them, so they leak markup instead -- a pre-existing defect of
# its enumerated shape, not this one, and not this diff's to fix.
_NARRATIVE_CITE = re.compile(r"\\citet\{[^}]*\}")


def sentence_around(text: str, citekey: str) -> str:
    """The sentence within `text` containing `citekey`, citation markup
    stripped so the markers themselves don't score as content.

    The split itself is `chitragupta/sentences.py`'s, shared with tier 3 of the
    overlap scan (`chitragupta/overlap_embed.py`) -- see that module on why the
    two aids must not each keep their own idea of where a sentence ends.

    Membership is a real citekey match, via `citation_gate`'s own
    extractor, not a bare substring test: BibTeX disambiguation suffixes
    are routine in a real export, so `citekey in part` would also match a
    sentence citing only the suffixed sibling `f"{citekey}a"` -- scoring
    the wrong claim against the source.
    """
    for part in sentences.split(text):
        if citekey in citation_gate.extract_citekeys_from_line(part):
            return _tidy(part)
    return _tidy(text)


def _tidy(text: str) -> str:
    """Drop parenthetical markup, elide narrative markup, close the gap.

    Removing `[@key]` from "processes [@key], or equivalently" otherwise
    leaves "processes , or equivalently" -- a space before the comma and
    a double space where the marker was. Small, but this text is quoted
    back to a reviewer, and the artefacts read as sloppiness in the
    *draft* rather than in this tool.
    """
    # Either order would do, which is the thing worth knowing before
    # anyone reorders these: the two patterns are disjoint, and the
    # inserted `[...]` carries no `[@` and no `\cite`, so neither
    # substitution can match the other's output.
    stripped = _PARENTHETICAL_CITE.sub("", _NARRATIVE_CITE.sub("[...]", text))
    # `\s++` (possessive, 3.11+): the backtracking `\s+` re-tries every
    # shorter run of a long whitespace stretch before giving up at each
    # scan position, which is quadratic on whitespace-heavy input (Sonar
    # S8786). Possessive changes no match -- whitespace then punctuation
    # is found identically -- only the wasted re-tries.
    stripped = re.sub(r"\s++([.,;:!?)])", r"\1", stripped)
    stripped = re.sub(r"\(\s+", "(", stripped)
    return re.sub(r"\s{2,}", " ", stripped).strip(" ,;:")
