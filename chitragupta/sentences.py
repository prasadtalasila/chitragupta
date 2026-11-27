"""One sentence splitter, shared by everything in this repo that needs
sentences rather than paragraphs.

Shared so the provenance report, tier 3, the uncited-prose aid, the
registry and the topic overview agree on where a sentence ends (a
separate copy in the overview kept splitting "Smith et al. (2020)" after
#835 fixed it here, #895). Stdlib only, since both bare-`python` and
embedding-stack callers import it. Deliberately not a tokenizer: callers
tolerate a seam landing a clause early or late, so `nltk`/`spacy` would
buy nothing.
"""

import re

# Split after . ! ? only when followed by whitespace and a capital or an
# opening bracket, and not after a known abbreviation or a single initial.
#
# Each lookbehind includes the period: they are evaluated after the
# terminator, so `(?<!\be\.g)` without it never matched ("e.g. Smith" split
# in three). `\b[A-Z]\.` for the initial, so "the USA. Next" still splits.
#
# `al.`, `vs.`, `Dr.`, `No.`, `Prof.`, `pp.` (#835): "Smith et al. (2020)"
# otherwise splits into a subjectless fragment. The cost, "was No. Then"
# staying joined, is the wider span callers already accept.
SENTENCE_SPLIT = re.compile(
    r"(?<!\b[A-Z]\.)(?<!\bFig\.)(?<!\bSect\.)(?<!\bEq\.)(?<!\bRef\.)"
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bcf\.)"
    r"(?<!\bal\.)(?<!\bvs\.)(?<!\bDr\.)(?<!\bNo\.)(?<!\bProf\.)(?<!\bpp\.)"
    r"(?<=[.!?])\s+(?=[A-Z\[(])"
)


def split(text: str) -> list[str]:
    """`text` as sentences. Stripped before splitting, so a leading
    newline cannot make the first "sentence" empty."""
    return SENTENCE_SPLIT.split(text.strip())


def spans(text: str) -> list[tuple[int, int]]:
    """The same split as `split`, as `(start, end)` character offsets
    into `text` itself -- **not** into a stripped copy of it.

    Tier 3 maps a sentence back to the draft as written (#129), which
    strings cannot do once a sentence repeats. Each span is tightened to
    its non-whitespace extent, so `[text[a:b] for a, b in spans(text)] ==
    split(text)` exactly; that equality is the contract.
    """
    found = []
    pos = 0
    for m in SENTENCE_SPLIT.finditer(text):
        found.append((pos, m.start()))
        pos = m.end()
    found.append((pos, len(text)))
    tightened = (_tighten(text, start, end) for start, end in found)
    # An empty span (trailing separator, all-whitespace text) is not a
    # sentence.
    return [(start, end) for start, end in tightened if end > start]


def _tighten(text: str, start: int, end: int) -> tuple[int, int]:
    """`(start, end)` narrowed past its own leading and trailing
    whitespace, or a zero-width span where there is nothing but."""
    lead = len(text[start:end]) - len(text[start:end].lstrip())
    body = text[start:end].strip()
    return (start + lead, start + lead + len(body))
