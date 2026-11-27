"""Tell a run of copied proper names from copied prose (#1187).

A name like a standards body's has no other form, so the agenda must not
mark such a run unattended; the scan flags it for a person. The flag
only downgrades: no finding is dropped.
"""

import re

from chitragupta.overlap_skipgram import STOPWORDS

_WORD = re.compile(r"[^\W\d_][\w'-]*")
_SENTENCE_BREAK = re.compile(r"[.!?:]\s+$")


def names_heavy(text: str) -> bool:
    """True when at least two content words remain and half or more of
    them are capitalised words that do not open a sentence.

    Stopwords are left out of both counts, since names carry "of" and
    "and" (#1187). Sentence-initial is decided before stopwords drop.
    """
    matches = list(_WORD.finditer(text))
    content = capitalised = 0
    for i, m in enumerate(matches):
        if m.group().lower() in STOPWORDS:
            continue
        content += 1
        initial = i == 0 or _follows_sentence_end(text, matches[i - 1].end(), m.start())
        capitalised += m.group()[0].isupper() and not initial
    return capitalised * 2 >= content >= 2


def _follows_sentence_end(text: str, prev_end: int, start: int) -> bool:
    """Whether the gap before a word is `[.!?:]` plus whitespace."""
    return _SENTENCE_BREAK.search(text[prev_end:start]) is not None
