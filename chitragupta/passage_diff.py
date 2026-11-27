"""Word-level markup for the two sides of a finding: which words the
draft and its source share, and which one substituted, dropped or added.

Compared on normalised tokens, marked up on the real ones: the draft
side is already normalised and the source is raw, so a direct diff would
mark nearly everything. Markdown only (`chitragupta/` prints no ANSI).
Lives in the shared layer, not `review/verbatim_check/`, because
`review/agenda/` must not import an aid (`_items_findings.py`).
"""

import re
from difflib import SequenceMatcher

# Case-preserving, as `overlap_source_text`'s; `overlap_index.WORD` splits
# on capitals.
_WORD = re.compile(r"[A-Za-z0-9]+")

# `**` for a word this side has and the other does not; `*` for one the
# draft dropped. Not `~~`: pandoc compiles it to `\st{}`, needing
# `soul.sty`, which a TeX install (this host's included) may lack, and the
# PDF is then skipped. Not underline, which is not Markdown.
_CHANGED = "**"
_DROPPED = "*"


def _tokens(text: str) -> list[tuple[int, int, str]]:
    """`(char_start, char_end, normalised)` per word in `text`, so the diff
    and the markup cannot disagree about which word is which."""
    return [(m.start(), m.end(), m.group().lower()) for m in _WORD.finditer(text)]


def _wrap(text: str, tokens: list[tuple[int, int, str]], runs: list[tuple[int, int, str]]) -> str:
    """`text` with each `(first, last, mark)` run's delimiters around
    tokens `first..last` inclusive.

    One pair per run, so a substituted phrase reads as one. Applied
    back-to-front so offsets stay valid. Delimiters land on word
    boundaries, keeping trailing punctuation outside them.
    """
    out = text
    for first, last, mark in sorted(runs, reverse=True):
        start, end = tokens[first][0], tokens[last][1]
        out = out[:start] + mark + out[start:end] + mark + out[end:]
    return out


def one_line(text: str) -> str:
    """`text` with every run of whitespace collapsed to one space.

    A newline would end the one-line Markdown blockquote both callers
    render into, and parsed text is hard-wrapped. Render-time only: the
    stored `source_text` keeps its real whitespace.
    """
    return " ".join(text.split())


def annotate(draft_text: str, source_text: str) -> tuple[str, str]:
    """`(draft, source)`, each with its differing words marked up.

    Adjacent opcodes of one kind are joined into one run. One-sided words
    are marked on their side, differing words on both; the bare text left
    is the overlap, which is what the eye should find first.
    """
    draft_tokens, source_tokens = _tokens(draft_text), _tokens(source_text)
    matcher = SequenceMatcher(
        # `autojunk` off: on long sequences it treats every stopword as
        # junk, hiding exactly the substitutions this shows.
        None,
        [t[2] for t in draft_tokens],
        [t[2] for t in source_tokens],
        autojunk=False,
    )
    draft_runs: list[tuple[int, int, str]] = []
    source_runs: list[tuple[int, int, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        # difflib's tags turn `a` (draft) into `b` (source), the reverse
        # of a reader's view: replace marks both; delete is the draft
        # adding words; insert is the draft dropping them (mark the source).
        # `x2 - 1` because `_wrap` wants the last token; an opcode is never
        # empty on the side it is applied to.
        if tag in ("replace", "delete"):
            draft_runs.append((i1, i2 - 1, _CHANGED))
        if tag == "replace":
            source_runs.append((j1, j2 - 1, _CHANGED))
        elif tag == "insert":
            source_runs.append((j1, j2 - 1, _DROPPED))
    return (
        _wrap(draft_text, draft_tokens, draft_runs),
        _wrap(source_text, source_tokens, source_runs),
    )
