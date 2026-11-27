"""A verbatim digest read as citation-terminated runs (#991).

A citation covers every sentence back to the previous citation or the
block start, so a block splits at its citation brackets, then each piece
into sentences for `_digest_match.py`'s fallback. Blocks are
`_claims.claim_blocks`'; a bracket is a citation only if the extractor
finds a key (`[sic]` leaves a run open). Trailing text is an uncited run;
a citation with nothing before it is dropped.

A run is `own` (checked for support, not copying, #1172) when closed by
`[see @key]`, under an `<!-- own: why -->` line, or a table row. Each run
also records the citekeys before it and whether it follows a displayed
equation, for `_digest_dangling.py`.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, sentences
from chitragupta.review import _blocks, _claims

# At least one `@`; whether it is a citation is the extractor's call.
_BRACKET = re.compile(r"\[[^\[\]]*@[^\[\]]*\]")

# Pandoc's `see` prefix: the drafter's sentence, pointing at the sources.
_SEE = re.compile(r"^\[\s*see\b", re.IGNORECASE)

# The line directly above a block that declares it the drafter's own.
_OWN = re.compile(r"^\s*<!--\s*own:.*-->\s*$")

# A displayed equation's close; a block right after one may open on "where".
_MATH_CLOSE = re.compile(r"^\s*(?:```|\$\$|\\\])\s*$")
_MATH_OPEN = re.compile(r"^\s*<!--\s*math\s*-->\s*$")

# An inline code span is the house form of a symbol (`T_h`, see `math.md`)
# in a copied run; `_claims` would blank it into a copy-mismatch (#1172),
# so backticks become spaces (same length, no offset moves). A span with
# `@` stays code: a citekey shown as code is not a citation.
_INLINE_CODE = re.compile(r"(?<!`)`([^`\n@]+)`(?!`)")

# `Figure 3.5 of [@key]`, review-digest's caption form: a run naming that
# figure points at something the reader can see.
_SHOWN = re.compile(r"\b(?:Figure|Fig\.)\s*(\d+(?:\.\d+)*)\s+of\s+\[@([^\s,;\]]+)")

# A page locator: treated as a hint, with the found page reported.
_PAGES = re.compile(r"\b(?:pp?\.|pages?)\s*(\d+)(?:\s*[-–—]+\s*(\d+))?")

# Citekeys are blanked first, so a key that begins with `page` is not read as a locator.
_CITEKEY_TOKEN = re.compile(r"@[^\s,;\]]+")

# A wordless sentence (the `.` after `[@key].`) belongs to the closed run.
_HAS_WORD = re.compile(r"\w")


@dataclass(frozen=True)
class Run:
    """One citation-terminated run, or the uncited tail of a block.

    `lines` has one line per sentence (#496), `line` is the first.
    `citekeys` is empty exactly for an uncited tail; `cited` is the page
    hint `(first, last)` or None.
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
    """`(offset, text, citation)` per piece of `block`, the trailing piece
    with None."""
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
    readable = _INLINE_CODE.sub(lambda m: f" {m[1]} ", text)
    for start, raw_block, block in _claims.claim_blocks(readable):
        own_block = _own_block(lines, start, raw_block)
        after_math = _after_math(lines, start)
        # A citekey cell attributes the whole row, wherever the column sits.
        row_keys = (
            tuple(citation_gate.extract_citekeys_from_line(block))
            if _blocks.TABLE_ROW.match(raw_block[0])
            else ()
        )
        follows: tuple[str, ...] | None = None
        for offset, segment, citation in _segments(block):
            spans = [(a, b) for a, b in sentences.spans(segment) if _HAS_WORD.search(segment[a:b])]
            if not spans:
                continue
            at = tuple(_blocks.line_of_offset(start, raw_block, offset + a) for a, _ in spans)
            keys = (
                tuple(citation_gate.extract_citekeys_from_line(citation)) if citation else row_keys
            )
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
