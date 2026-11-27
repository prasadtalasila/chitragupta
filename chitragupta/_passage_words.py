"""The word set a passage is matched on: which words distinguish a claim.

Split from `chitragupta/passages.py`, which re-exports `distinctive`; the
vocabulary is `_tokens.DISTINCTIVE` (issue 845).
"""

from chitragupta import _tokens


def distinctive(text: str) -> set[str]:
    return set(_tokens.words(text, _tokens.DISTINCTIVE))
