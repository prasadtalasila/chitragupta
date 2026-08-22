"""Which sentences of a draft carry a claim -- and which are scaffolding.

The narrow question underneath `chitragupta/review/uncited_prose.py`,
kept apart from it because they are genuinely two: this module decides
what a draft is *asserting*, and that one decides what to say about the
assertions that rest on nothing. C2 (claim-support checking) needs the
first without the second -- docs/FEATURE-ROADMAP.md records it as
depending on C1 "for the sentence-splitting it shares" -- so the piece it
shares lives here rather than inside an aid it would have to import
whole.

**Every exclusion below was measured, not guessed.** Run over the four
real drafts in `content/drafts/digital-twins-for-software-engineers/`,
the naive reading -- every sentence carrying no citekey is a claim --
takes in 78% of a survey and 95% of a textbook chapter, and a report
that flags four fifths of a draft is one nobody opens twice.
plans/c1-uncited-prose-report.md carries the table and what each
exclusion cost.

Two things the measurement tempted us to add and that are deliberately
absent:

- **No topic-sentence or transition detection.** There is no honest
  deterministic test for one, and a keyword list of document deixis
  ("this section", "we now turn to") would be invented rather than
  measured. `Sentence.block_cites` is the answer instead: a caller can
  read the sentences whose paragraph rests on nothing first.
- **Table rows stay in.** `survey.md`'s comparison table attributes each
  row with a citekey in backticks, which is not a citation the gate can
  see -- and `survey-writer` step 9 already says to attribute "in the
  prose or the comparison table, **where the gate can see the key**".
  Suppressing the rows would hide a real instance of what that step
  warns about.

Stdlib-only, and reads only the draft -- no ledger, no corpus, no sync.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, sentences
from chitragupta.review import _blocks

# Where a draft's own bibliography starts. Everything from here to the end
# is uncited prose by construction -- 40 of survey.md's 87 naive findings
# -- and none of it is a claim the draft is making. The optional number
# is not decoration: the real drafts write `## 7. References`, so a
# pattern anchored straight after the hashes matches none of them.
REFERENCE_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s+|\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{)"
    r"\s*(?:[0-9A-Z]+[.)]\s*)?(?:references|bibliography|works\s+cited)\b",
    re.IGNORECASE,
)

# A caption names a figure or a table; it does not assert anything the
# draft has to support. Markdown has no caption syntax, so all three
# shapes the genre skills actually emit are recognised: an image line, a
# `Figure 1.`/`Table 2:` lead-in, and LaTeX's own command.
CAPTION = re.compile(
    r"^\s*(?:!\[|\\caption\*?\{|(?:figure|table|listing)\s+\d+\s*[.:])",
    re.IGNORECASE,
)

# A block that is only a comment. Includes WRITING-STANDARDS.md §11's
# `<!-- single-source: ... -->` marker, which must not be read as an
# uncited claim about the world -- the drafter is explaining a citation,
# not making an assertion.
COMMENT = re.compile(r"^\s*(?:<!--|%)")


@dataclass(frozen=True)
class Sentence:
    """One claim-bearing sentence of a draft.

    `cites` is whether this sentence carries a citation; `block_cites`
    whether anything in the block it sits in does. The two differ exactly
    where an uncited-prose report is most useful -- a paragraph with one
    citation at the end and four unrelated assertions before it.
    """

    line: int
    text: str
    cites: bool
    block_cites: bool


def _excluded(first_line: str, next_line: str) -> bool:
    """Whether the block opening at `first_line` carries no claim.

    `next_line` is the line after the block, and is needed for exactly
    one case: a markdown table's header row, which is a row like any
    other except that a separator row follows it. The column names are
    scaffolding; the rows beneath them are claims.
    """
    if _blocks.HEADING.match(first_line) or _blocks.TEX_HEADING.match(first_line):
        return True
    if CAPTION.match(first_line) or COMMENT.match(first_line):
        return True
    return bool(_blocks.TABLE_ROW.match(first_line)
                and _blocks.SEPARATOR_ROW.match(next_line))


def _body(text: str) -> list[str]:
    """The draft's lines up to its reference list, code already blanked.

    `citation_gate._blank_code` first, for the reason `_units.units`
    calls it: a fenced block demonstrating this project's own markup
    would otherwise be read as prose making a claim.
    """
    lines = citation_gate._blank_code(text).splitlines()
    for index, line in enumerate(lines):
        if REFERENCE_HEADING.match(line):
            return lines[:index]
    return lines


def claim_sentences(text: str) -> list[Sentence]:
    """Every sentence of `text` that carries a claim, in document order.

    The split is `chitragupta/sentences.py`'s, shared with tier 3 of the
    overlap scan and with `citation_provenance` -- C1's roadmap entry
    asks for a splitter "somewhere C2 can reuse it", and that module has
    been it since before C1 was planned. The blocks are `_blocks.spans`,
    so a table row and a list item are each their own claim rather than
    fragments of one paragraph, and a block left empty by stripping its
    list marker is no claim at all.
    """
    lines = _body(text)
    found = []
    for start, end, block in _blocks.spans(lines):
        after = lines[end] if end < len(lines) else ""
        if not block.strip() or _excluded(lines[start - 1], after):
            continue
        block_cites = bool(citation_gate.extract_citekeys_from_line(block))
        # No empty-sentence guard: `sentences.split` strips first and only
        # splits *between* a terminator and a following capital, so a
        # block with any content in it yields only non-empty parts. The
        # `block.strip()` test above is what rules out the other case.
        for sentence in sentences.split(block):
            found.append(Sentence(
                start, sentence,
                bool(citation_gate.extract_citekeys_from_line(sentence)),
                block_cites))
    return found
