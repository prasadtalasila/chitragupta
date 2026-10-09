"""A verbatim digest read as citation-terminated runs (#991).

The digest format carries no markup: copied text is ordinary prose and a
citation ends each copied run. The attribution rule is the whole of this
module -- **a citation covers every sentence back to the previous
citation, or to the start of the block** -- so a block is split at its
citation brackets, not at its sentence boundaries, and each piece is
then sentence-split for the fallback `_digest_match.py` needs when a
run is not found whole.

The blocks are `_claims.claim_blocks`', so a heading, a caption, a code
fence and the reference list are read the way every other aid reads
them. A bracket counts as a citation only if the citekey extractor finds
a key in it: `[see 3]` and `[sic]` leave a run open.

What follows the last citation in a block is a run with no citekeys --
the drafter's own tail -- and a block with no citation at all is one such
run. A citation with nothing before it (two brackets in a row) covers
nothing and is dropped.

Stdlib only, interpreter tier 1 like the aid that reads it.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, sentences
from chitragupta.review import _blocks, _claims

# A bracket holding at least one `@`. Whether it is a citation is the
# extractor's call, not this pattern's.
_BRACKET = re.compile(r"\[[^\[\]]*@[^\[\]]*\]")

# `p. 4`, `pp. 4-5`, `page 4`, `pages 4–5`. The hint pandoc passes
# through as a locator; the aid treats it as a hint and reports the page
# the text was actually found on.
_PAGES = re.compile(r"\b(?:pp?\.|pages?)\s*(\d+)(?:\s*[-–—]+\s*(\d+))?")


@dataclass(frozen=True)
class Run:
    """One citation-terminated run, or the uncited tail of a block."""

    line: int
    sentences: tuple[str, ...]
    citekeys: tuple[str, ...]
    citation: str | None
    pages: tuple[int, int] | None

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    @property
    def words(self) -> int:
        return len(self.text.split())


def cited_pages(citation: str) -> tuple[int, int] | None:
    """`(first, last)` from the bracket's page locator, or None."""
    match = _PAGES.search(citation)
    if match is None:
        return None
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else first
    return (min(first, last), max(first, last))


def _segments(block: str) -> list[tuple[int, str, str | None]]:
    """`(offset, text, citation)` per piece of `block`: the text before
    each citation bracket with that bracket, then whatever trails the
    last one with None."""
    found, at = [], 0
    for match in _BRACKET.finditer(block):
        if not citation_gate.extract_citekeys_from_line(match.group(0)):
            continue
        found.append((at, block[at : match.start()], match.group(0)))
        at = match.end()
    found.append((at, block[at:], None))
    return found


def runs(text: str) -> list[Run]:
    """Every run of `text`, in document order."""
    found = []
    for start, raw_block, block in _claims.claim_blocks(text):
        for offset, segment, citation in _segments(block):
            spans = sentences.spans(segment)
            if not spans:
                continue
            keys = tuple(citation_gate.extract_citekeys_from_line(citation)) if citation else ()
            found.append(
                Run(
                    _blocks.line_of_offset(start, raw_block, offset + spans[0][0]),
                    tuple(segment[a:b] for a, b in spans),
                    keys,
                    citation,
                    cited_pages(citation) if citation else None,
                )
            )
    return found
