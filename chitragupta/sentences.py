"""One sentence splitter, shared by everything in this repo that needs
sentences rather than paragraphs.

There was exactly one before this module existed --
`chitragupta/review/citation_provenance.py`'s, which found "the sentence around
this citation marker" so a claim could be scored against a source
passage. `chitragupta/overlap_embed.py` (tier 3) needs the same split on both
sides of an alignment, and a second regex tuned separately would mean
the two aids disagree about where a sentence ends: the provenance report
would quote one span back to a reviewer and the overlap scan would
report a finding over a different one, on the same draft, from the same
prose. So this is the definition, and both import it.

Stdlib only (`re`), like citation_gate.py, references.py and
passages.py -- it is imported by a module that must run under a bare
`python` (provenance) *and* by one that only runs where the optional
embedding stack is installed (tier 3), so it can afford to depend on
neither.

Deliberately not a sentence *tokenizer*. No abbreviation list beyond the
handful these drafts actually contain, no model, no attempt at
quotations or nested parentheses. Both callers want the same thing --
a span of prose short enough to be one claim and long enough to carry
its own subject -- and both degrade gracefully when a split lands a
clause early or late: provenance quotes a slightly wider sentence, and
an alignment absorbs the seam into an adjacent cell. A dependency on
`nltk`/`spacy` to move those seams would buy neither caller anything
its own tolerance does not already provide.
"""

import re

# Split after . ! ? only when followed by whitespace and a capital or an
# opening bracket, and not when the preceding token is a known
# abbreviation or a single initial. The abbreviations are the ones these
# drafts actually contain -- "Fig. 1", "e.g.", "Sect. 1.2" -- since
# splitting there reintroduces the fragment problem one level down.
#
# **Each lookbehind includes the period**, which the version inherited
# from `citation_provenance` did not, and that was an off-by-one: the
# lookbehinds are evaluated at the position *after* the terminator, so
# `(?<!\be\.g)` asked whether the three characters ending there were
# "e.g" when they were in fact ".g." and never matched. Measured on the
# strings the comment above names: "Written e.g. Smith" split into three
# fragments and "Named for J. Smith" into two. It went unnoticed because
# the two abbreviations these drafts use most, "Fig. 1" and "Sect. 1.2",
# are followed by a digit and so were already excluded by the
# `(?=[A-Z\[(])` lookahead rather than by their own lookbehind.
#
# `\b[A-Z]\.` rather than `[A-Z]\.` for the initial, so a sentence really
# ending in an acronym ("... adoption in the USA. Next") still splits:
# the `A` there is preceded by `S`, which is not a word boundary.
SENTENCE_SPLIT = re.compile(
    r"(?<!\b[A-Z]\.)(?<!\bFig\.)(?<!\bSect\.)(?<!\bEq\.)(?<!\bRef\.)"
    r"(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bcf\.)"
    r"(?<=[.!?])\s+(?=[A-Z\[(])"
)


def split(text: str) -> list[str]:
    """`text` as sentences. The strip-then-split order is
    `citation_provenance`'s own and is kept: a leading newline would
    otherwise make the first "sentence" empty."""
    return SENTENCE_SPLIT.split(text.strip())


def spans(text: str) -> list[tuple[int, int]]:
    """The same split as `split`, as `(start, end)` character offsets
    into `text` itself -- **not** into a stripped copy of it.

    Offsets rather than strings because tier 3 has to map a sentence back
    to the draft as written: a finding names `char_start`/`char_end` in
    the original file (`scan_payload`'s contract, #129), and a list of
    strings has thrown away exactly the number needed to get there.
    `split` cannot be reimplemented on top of this without re-slicing, and
    this cannot be reimplemented on top of that without re-finding each
    sentence in the text -- which is ambiguous the moment a draft repeats
    a sentence. So both exist, over one regex.

    Each span is tightened to its own non-whitespace extent, so
    `[text[a:b] for a, b in spans(text)] == split(text)` exactly --
    including across the leading and trailing whitespace of the whole
    text, which `split`'s `.strip()` removes and an untightened first
    span would keep. That equality is the contract: the two functions
    exist so a caller can have the strings *or* the offsets, not two
    different segmentations.
    """
    found = []
    pos = 0
    for m in SENTENCE_SPLIT.finditer(text):
        found.append((pos, m.start()))
        pos = m.end()
    found.append((pos, len(text)))
    tightened = (_tighten(text, start, end) for start, end in found)
    # A trailing separator can leave an empty final span, and a text that
    # is entirely whitespace leaves one empty span overall. Neither is a
    # sentence, and a consumer that embeds one would be embedding "".
    return [(start, end) for start, end in tightened if end > start]


def _tighten(text: str, start: int, end: int) -> tuple[int, int]:
    """`(start, end)` narrowed past its own leading and trailing
    whitespace, or a zero-width span where there is nothing but."""
    lead = len(text[start:end]) - len(text[start:end].lstrip())
    body = text[start:end].strip()
    return (start + lead, start + lead + len(body))
