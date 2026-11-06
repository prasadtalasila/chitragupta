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

**A run is the drafter's own words, `own`, in three shapes (#1172)**,
and `_digest_match.py` checks it for support rather than for copying:
the citation closing it carries pandoc's `see` prefix (`[see @key]`);
its block sits directly under an `<!-- own: why -->` line; or it is a
table row, since a comparison table's cells are never a copied run.
Each run also records what stands before it -- the citekeys of the run
before it in the same block, and whether its block follows a displayed
equation -- which is all `_digest_dangling.py` needs to tell a run that
opens on "where" or "thus" from one that continues its own source.

Stdlib only, interpreter tier 1 like the aid that reads it.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, sentences
from chitragupta.review import _blocks, _claims

# A bracket holding at least one `@`. Whether it is a citation is the
# extractor's call, not this pattern's.
_BRACKET = re.compile(r"\[[^\[\]]*@[^\[\]]*\]")

# Pandoc's prefix `see`, `see also`, before the first key: the sentence
# it closes is the drafter's, pointing at where the sources say it.
_SEE = re.compile(r"^\[\s*see\b", re.IGNORECASE)

# The line directly above a block that declares it the drafter's own.
_OWN = re.compile(r"^\s*<!--\s*own:.*-->\s*$")

# What closes a displayed equation: the fence of a `<!-- math -->` block,
# `$$`, or LaTeX's `\]`. A block right after one may open on "where".
_MATH_CLOSE = re.compile(r"^\s*(?:```|\$\$|\\\])\s*$")
_MATH_OPEN = re.compile(r"^\s*<!--\s*math\s*-->\s*$")

# A figure the digest shows, as its caption cites it: `Figure 3.5 of
# [@key]` (review-digest's caption form). A run naming that figure of
# that source points at something the reader can see.
_SHOWN = re.compile(r"\b(?:Figure|Fig\.)\s*(\d+(?:\.\d+)*)\s+of\s+\[@([^\s,;\]]+)")

# `p. 4`, `pp. 4-5`, `page 4`, `pages 4–5`. The hint pandoc passes
# through as a locator; the aid treats it as a hint and reports the page
# the text was actually found on.
_PAGES = re.compile(r"\b(?:pp?\.|pages?)\s*(\d+)(?:\s*[-–—]+\s*(\d+))?")

# A citekey inside the bracket, blanked before the locator is searched
# for: `[@page2020web]` would otherwise read as "page 2020".
_CITEKEY_TOKEN = re.compile(r"@[^\s,;\]]+")

# A sentence with no word character in it -- the `.` left after
# `[@key].`, which is pandoc's and the survey's convention -- is
# punctuation belonging to the run just closed, not a sentence of the
# next one.
_HAS_WORD = re.compile(r"\w")


@dataclass(frozen=True)
class Run:
    """One citation-terminated run, or the uncited tail of a block.

    `lines` carries one line per sentence (#496's rule: a finding names
    the line the sentence is on, not the block's first line), and `line`
    is the first of them, for the whole-run outcomes. `citekeys` is
    empty exactly for an uncited tail, and `cited` is the citation's page
    hint, `(first, last)`, or None where the bracket carried none or
    there was no bracket.
    """

    line: int
    lines: tuple[int, ...]
    sentences: tuple[str, ...]
    citekeys: tuple[str, ...]
    cited: tuple[int, int] | None
    own: bool = False
    follows: tuple[str, ...] | None = None
    after_math: bool = False

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    @property
    def words(self) -> int:
        return len(self.text.split())


def cited_pages(citation: str) -> tuple[int, int] | None:
    """`(first, last)` from the bracket's page locator, or None."""
    match = _PAGES.search(_CITEKEY_TOKEN.sub(" ", citation))
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


def _before(lines: list[str], start: int) -> tuple[str, int]:
    """The nearest non-blank line above line `start`, and its index."""
    index = start - 2
    while index >= 0 and not lines[index].strip():
        index -= 1
    return (lines[index], index) if index >= 0 else ("", -1)


def _after_math(lines: list[str], start: int) -> bool:
    """Whether the block at line `start` follows a displayed equation."""
    line, index = _before(lines, start)
    if not _MATH_CLOSE.match(line):
        return False
    if line.strip() != "```":
        return True
    opener = index - 1
    while opener >= 0 and lines[opener].strip() != "```":
        opener -= 1
    return opener > 0 and bool(_MATH_OPEN.match(lines[opener - 1]))


def _own_block(lines: list[str], start: int, raw_block: list[str]) -> bool:
    above = lines[start - 2] if start >= 2 else ""
    return bool(_OWN.match(above) or _blocks.TABLE_ROW.match(raw_block[0]))


def shown_figures(text: str) -> frozenset[tuple[str, str]]:
    """`(citekey, figure number)` for every source figure the digest shows."""
    return frozenset((key, number) for number, key in _SHOWN.findall(text))


def runs(text: str) -> list[Run]:
    """Every run of `text`, in document order."""
    found = []
    lines = text.splitlines()
    for start, raw_block, block in _claims.claim_blocks(text):
        own_block = _own_block(lines, start, raw_block)
        after_math = _after_math(lines, start)
        follows: tuple[str, ...] | None = None
        for offset, segment, citation in _segments(block):
            spans = [(a, b) for a, b in sentences.spans(segment) if _HAS_WORD.search(segment[a:b])]
            if not spans:
                continue
            at = tuple(_blocks.line_of_offset(start, raw_block, offset + a) for a, _ in spans)
            keys = tuple(citation_gate.extract_citekeys_from_line(citation)) if citation else ()
            found.append(
                Run(
                    at[0],
                    at,
                    tuple(segment[a:b] for a, b in spans),
                    keys,
                    cited_pages(citation) if citation else None,
                    own_block or bool(citation and _SEE.match(citation)),
                    follows,
                    after_math,
                )
            )
            follows = keys
    return found
