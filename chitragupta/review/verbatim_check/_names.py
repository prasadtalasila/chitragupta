"""Tell a run of copied proper names from copied prose (#1187).

A short verbatim run that is an organisation's or a standard's name
("National Institute of Standards and Technology") is copied because it
has no other form, not because a sentence was lifted. The agenda must not
mark such a run unattended -- an agent editing it away would be guessing
-- so the scan flags it and a person decides. The flag only downgrades:
no finding is dropped.
"""

import re

from chitragupta.overlap_skipgram import STOPWORDS

_WORD = re.compile(r"[^\W\d_][\w'-]*")
_SENTENCE_BREAK = re.compile(r"[.!?:]\s+$")


def names_heavy(text: str) -> bool:
    """True when at least two content words remain and half or more of
    them are capitalised words that do not open a sentence.

    Stopwords are left out of both counts: a name carries function words
    ("Institute of Standards and Technology"), and counting the lowercase
    "of" and "and" against it would hide exactly the runs this flag is
    for (#1187). A sentence-initial word is capitalised by grammar, so
    it is never counted as capitalised; "initial" is decided on the full
    word sequence, before stopwords are dropped.
    """
    matches = list(_WORD.finditer(text))
    content = capitalised = 0
    for i, m in enumerate(matches):
        if m.group().lower() in STOPWORDS:
            continue
        content += 1
        initial = i == 0 or _follows_sentence_end(text, matches[i - 1].end(), m.start())
        capitalised += m.group()[0].isupper() and not initial
    return content >= 2 and capitalised * 2 >= content


def _follows_sentence_end(text: str, prev_end: int, start: int) -> bool:
    """Whether the gap before a word is `[.!?:]` plus whitespace."""
    return _SENTENCE_BREAK.search(text[prev_end:start]) is not None
