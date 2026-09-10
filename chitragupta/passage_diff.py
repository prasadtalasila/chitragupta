"""Word-level markup for the two sides of a finding: which words the
draft and its source share, and which one substituted, dropped or added.

Reading two paragraphs side by side and spotting that `"is sent to the
machine's DT via its"` became `"reaches a machine's twin through its"` is
work, and a reader doing it forty times over a report will stop doing it
carefully. The overlap is what makes a finding a finding; the
substitutions are what decide whether it is a lift, a paraphrase or a
coincidence. Both should be visible without collation.

**The comparison runs on normalised tokens; the markup lands on the real
ones.** The draft side of a finding is already normalised (`fragment` --
lowercased, punctuation dropped) and the source side is raw. Diffing
those two directly marks nearly every token as substituted --
`"Configuration"` against `"configuration"`, `"machine's DT"` against
`"machine s dt"` -- which looks convincing and means nothing. So each
side is tokenised, compared in its normalised form, and marked up in
place in its original text: the source keeps its real casing and
punctuation on the page while the comparison runs on streams that are
actually comparable.

Markdown only, deliberately. `chitragupta/` prints no ANSI anywhere, and
the terminal form of a scan is read once in a shell where `**` and `~~`
are noise rather than emphasis; the filed `.md` is the copy read next to
the draft weeks later, and is the one that renders.

Here rather than inside `review/verbatim_check/`, though that is where it
was written and is still its main caller, because `review/agenda/` needs
it too and must not import an aid to get it: that package is built to
read the aids' *filed JSON and nothing else*, so an agenda can be
assembled from reports on disk without the tool that wrote them being
importable (`review/agenda/_items_findings.py` says so directly). This
module is stdlib-only and knows nothing about either caller, so it sits
in the shared layer both already depend on and the property holds.
"""

import re
from difflib import SequenceMatcher

# Case-preserving word tokeniser, matching `overlap_source_text`'s -- and
# not `overlap_index.WORD`, which is `[a-z0-9]+` and splits on capitals.
_WORD = re.compile(r"[A-Za-z0-9]+")

# `**` for a word this side has and the other does not (substituted or
# added); `*` for one the source had and the draft dropped.
#
# Emphasis and strong emphasis, and nothing else, because every one of
# these reports is rendered to PDF through pandoc and pdflatex. `~~` was
# the obvious mark for a dropped word and is the wrong one: pandoc
# compiles strikeout to `\st{}`, which needs `soul.sty` (or `ulem` on
# older pandoc), and a TeX install carrying neither is not exotic --
# this project's own host has no `soul.sty`, `ulem.sty` or
# `soulutf8.sty`, and the failure is a skipped PDF with the report's
# other three formats written as normal. Underline is out for a
# different reason: it is not Markdown at all, and the `<u>` people
# reach for renders as literal HTML in a plain-text viewer.
_CHANGED = "**"
_DROPPED = "*"


def _tokens(text: str) -> list[tuple[int, int, str]]:
    """`(char_start, char_end, normalised)` per word in `text`.

    One pass produces both what the diff compares and where to put the
    markup, so the two cannot disagree about which word is which.
    """
    return [(m.start(), m.end(), m.group().lower()) for m in _WORD.finditer(text)]


def _wrap(text: str, tokens: list[tuple[int, int, str]], runs: list[tuple[int, int, str]]) -> str:
    """`text` with each `(first, last, mark)` run's delimiters around
    tokens `first..last` inclusive.

    One pair of delimiters per run, not per word: `**is sent to**` is one
    substituted phrase, which is what happened, where `**is** **sent**
    **to**` is three separate emphases the reader has to reassemble.

    Applied back-to-front so each insertion's character offsets are still
    valid when the next is made -- the alternative, adjusting every later
    offset by the length of what was just inserted, is the same
    computation with an accumulator to get wrong. Everything between the
    tokens (punctuation, hyphens, line breaks) is carried through
    untouched, which is the point of marking up in place rather than
    re-joining a token list. The delimiters land on word boundaries, so
    trailing punctuation stays outside them and Markdown does not see
    `**word.**` where the emphasis was meant to cover the word alone.
    """
    out = text
    for first, last, mark in sorted(runs, reverse=True):
        start, end = tokens[first][0], tokens[last][1]
        out = out[:start] + mark + out[start:end] + mark + out[end:]
    return out


def one_line(text: str) -> str:
    """`text` with every run of whitespace collapsed to one space.

    Both callers render a passage into a Markdown blockquote, which is a
    single `> ...` line -- so a newline inside the passage ends the quote
    and renders the remainder as an ordinary paragraph beside it. Source
    passages routinely contain them: most of a real
    `content/parsed/*.txt` is hard-wrapped somewhere around 110-156
    characters depending on the parser backend that wrote it, so any span
    of more than a few words is likely to cross a line break.

    Applied at the point of rendering and never to the stored passage:
    `source_text` in the payload is the source's real text, and a
    consumer matching it back against the parsed file needs the
    whitespace it actually has. Only the blockquote needs it flat.
    """
    return " ".join(text.split())


def annotate(draft_text: str, source_text: str) -> tuple[str, str]:
    """`(draft, source)`, each with its differing words marked up.

    Runs adjacent opcodes of the same kind together rather than marking
    word by word: `**is** **sent** **to**` is three emphasised words, and
    `**is sent to**` is one substituted phrase, which is what actually
    happened and reads as one thing.

    Words present on one side only are marked on that side, since there
    is nothing to mark on the other; words the two say differently in the
    same place are marked on both. What is left bare is the overlap, and
    leaving it bare is the point: on a marked-up finding it is the only
    unmarked text on the page, so it is what the eye finds first.
    """
    draft_tokens, source_tokens = _tokens(draft_text), _tokens(source_text)
    matcher = SequenceMatcher(
        # `autojunk` off: it discards any token appearing in more than 1%
        # of a sequence over 200 elements, which on prose is every
        # stopword -- exactly the words whose substitution this markup
        # exists to show, silently treated as unmatchable on long
        # findings and not on short ones.
        None,
        [t[2] for t in draft_tokens],
        [t[2] for t in source_tokens],
        autojunk=False,
    )
    draft_runs: list[tuple[int, int, str]] = []
    source_runs: list[tuple[int, int, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        # `difflib`'s tags name what turns `a` (the draft) into `b` (the
        # source), which is the reverse of how a reader thinks about it,
        # so each one is translated rather than passed through:
        #
        #   replace -> the two texts say something different here; mark
        #              both sides.
        #   delete  -> in the draft, absent from the source. From the
        #              reader's side that is the draft *adding* words,
        #              not deleting them; mark the draft.
        #   insert  -> in the source, absent from the draft: the draft
        #              dropped them; mark the source struck through.
        #
        # `i2`/`j2` are exclusive and `_wrap` wants the last token, hence
        # `x2 - 1`, which is a real index because an opcode is never
        # empty on the side it is being applied to here.
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
