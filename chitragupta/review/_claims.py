"""Which sentences of a draft carry a claim -- and which are scaffolding.

Kept apart from `uncited_prose.py`: this decides what a draft asserts,
which C2 claim-support needs without the rest of C1.

Every exclusion was measured, not guessed: on four real drafts the naive
reading flagged 78% of a survey and 95% of a textbook chapter
(plans/c1-uncited-prose-report.md). Deliberately absent: topic-sentence
detection (no honest deterministic test; `Sentence.block_cites` lets a
caller read unsupported paragraphs first), and dropping table rows (a
backtick citekey in a table is invisible to the gate, and hiding the rows
would hide that).

Stdlib-only, and reads only the draft -- no ledger, no corpus, no sync.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, references_section, sentences
from chitragupta.review import _blocks

# A bibliography heading, matched on the title `_blocks` already strips.
# Titles are `references_section.REFERENCE_TITLE`'s (#951); its optional
# number matters, since real drafts write `## 7. References`.
REFERENCE_TITLE = re.compile(
    rf"^[ \t]*{references_section.REFERENCE_TITLE}[ \t]*$",
    re.IGNORECASE,
)

# A caption asserts nothing. Four shapes: an image line, a `Figure 1.` /
# `Table 2:` / `Equation 3:` lead-in (equation: #457), LaTeX's command, and
# pandoc's `: caption` line (WRITING-STANDARDS.md §13), whose required
# space keeps a sentence opening on a colon.
CAPTION = re.compile(
    r"^\s*(?::[ \t]|!\[|\\caption\*?\{|(?:figure|table|listing|equation)\s+\d+\s*[.:])",
    re.IGNORECASE,
)

# §13's reference marker sits inside a sentence, where `COMMENT` cannot see
# it. Replaced by its word ("Table"), not nothing, so no noun goes missing;
# the number is the renderer's and is not guessed.
INLINE_TABLE_REF = re.compile(r"[ \t]*<!--[ \t]*tableref:[ \t]*\S+?[ \t]*-->[ \t]*")

# Issue 411's `figureref`, same reason.
INLINE_FIGURE_REF = re.compile(r"[ \t]*<!--[ \t]*figureref:[ \t]*\S+?[ \t]*-->[ \t]*")

# Issue 457's `equationref`, same reason.
INLINE_EQUATION_REF = re.compile(r"[ \t]*<!--[ \t]*equationref:[ \t]*\S+?[ \t]*-->[ \t]*")

# A comment-only block, including §11's `<!-- single-source: ... -->`,
# which explains a citation rather than asserting anything.
COMMENT = re.compile(r"^\s*(?:<!--|%)")

# Paragraph-declaring markers (`single-source:`, the digest's `own:`) are
# peeled off a block's edges, not matched as `COMMENT`, which dropped the
# adjoining paragraph with them (#1172). A `figure:` marker is meant to
# take its caption out.
MARKER_LINE = re.compile(r"^\s*(?:<!--\s*(?:single-source|own):.*-->|%\s*single-source:.*)\s*$")

# Booktabs' rule above a LaTeX header row, the counterpart of markdown's
# `|---|` below one. An `\hline` table's header is not detected and is
# reported as a claim: `\hline` separates every row, so it marks nothing.
TEX_HEADER_RULE = re.compile(r"\\toprule\b")


@dataclass(frozen=True)
class Sentence:
    """One claim-bearing sentence of a draft. `cites` and `block_cites`
    differ exactly where an uncited-prose report helps most: one citation
    closing a paragraph of unrelated assertions.
    """

    line: int
    text: str
    cites: bool
    block_cites: bool


def _is_heading(line: str) -> bool:
    return bool(_blocks.HEADING.match(line) or _blocks.TEX_HEADING.match(line))


def _opens_the_reference_list(line: str) -> bool:
    """Whether `line` is the heading a draft's bibliography starts under."""
    return _is_heading(line) and bool(REFERENCE_TITLE.match(_blocks.text_of([line])))


def _excluded(block: list[str], next_line: str) -> bool:
    """Whether `block` carries no claim; column names do not, rows do.
    Markdown's `|---|` follows a header, so `next_line` decides it;
    booktabs' `\\toprule` precedes it, inside the header's block.
    """
    first_line = block[0]
    if _is_heading(first_line):
        return True
    if CAPTION.match(first_line) or COMMENT.match(first_line):
        return True
    if _blocks.TABLE_ROW.match(first_line) and _blocks.SEPARATOR_ROW.match(next_line):
        return True
    return any(TEX_HEADER_RULE.search(line) for line in block)


def _body(text: str) -> list[str]:
    """The draft's lines up to its reference list, code already blanked.

    To the draft's end, as all six genres put the bibliography last.
    Code is blanked as `_units.units` does, so a fenced markup example is
    not a claim.
    """
    lines = [
        line
        if COMMENT.match(line)
        else INLINE_EQUATION_REF.sub(
            " Equation ", INLINE_FIGURE_REF.sub(" Figure ", INLINE_TABLE_REF.sub(" Table ", line))
        )
        for line in citation_gate._blank_code(text).splitlines()
    ]
    for index, line in enumerate(lines):
        if _opens_the_reference_list(line):
            return lines[:index]
    return lines


def claim_blocks(text: str) -> list[tuple[int, list[str], str]]:
    """(first line, raw lines, prose text) for every claim-carrying block,
    in document order. Exposed for `_digest_runs.py`, which splits at
    citation brackets but must read exactly the blocks every aid reads.
    """
    lines = _body(text)
    found = []
    for start, end, block in _blocks.spans(lines):
        after = lines[end] if end < len(lines) else ""
        first, raw_block = _without_markers(start, lines[start - 1 : end])
        if not raw_block:
            continue
        if len(raw_block) != end - start + 1:
            block = _blocks.text_of(raw_block)
        if block.strip() and not _excluded(raw_block, after):
            found.append((first, raw_block, block))
    return found


def _without_markers(start: int, raw_block: list[str]) -> tuple[int, list[str]]:
    """The block's first line and lines with whole-line markers peeled off
    both edges; empty when the block was only markers."""
    first, last = 0, len(raw_block)
    while first < last and MARKER_LINE.match(raw_block[first]):
        first += 1
    while last > first and MARKER_LINE.match(raw_block[last - 1]):
        last -= 1
    return start + first, raw_block[first:last]


def claim_sentences(text: str) -> list[Sentence]:
    """Every sentence of `text` that carries a claim, in document order.

    The split is `chitragupta/sentences.py`'s, shared with the overlap scan
    and `citation_provenance`. Blocks are `claim_blocks`, so a row or list
    item is its own claim.
    """
    found = []
    for start, raw_block, block in claim_blocks(text):
        block_cites = bool(citation_gate.extract_citekeys(block))
        for sent_start, sent_end in sentences.spans(block):
            found.append(
                Sentence(
                    _blocks.line_of_offset(start, raw_block, sent_start),
                    block[sent_start:sent_end],
                    bool(citation_gate.extract_citekeys(block[sent_start:sent_end])),
                    block_cites,
                )
            )
    return found
