"""What a *sentence* is on each side of tier 3's alignment.

The draft side reads a draft this pipeline wrote; the source side reads
a Docling sidecar via `passages.py`. A sentence is usable only if it can
say where it came from: a draft sentence carries its word range (#131's
coordinates), a source sentence its page. Page-level `pdftotext`
passages are dropped, since a sentence cut from column-spliced text is a
collage and would yield a confident finding about text nobody wrote.
Stdlib only.
"""

import bisect
import operator
import re
from dataclasses import dataclass

from chitragupta import dossier, passages, sentences

# --------------------------------------------------------------------------
# Draft side: sections, their sentences, and the word spans they cover
# --------------------------------------------------------------------------


# A segment longer than this is cut into overlapping windows of this
# many words, `WINDOW_STRIDE` apart; shorter sentences stay whole.
#
# The measurement that decides whether tier 3 works at all: #134's worked
# example scores 0.55 as a whole sentence, below three unrelated
# sentences of the same paper (0.59-0.61), because topical framing
# dominates the vector in a single-field corpus. Windowed at 18-20 words
# it scores 0.71 against 0.40 noise (docs/PLAGIARISM-DESIGN.md).
# Half-window stride, so any clause this long falls whole in some window.
WINDOW_WORDS = 20
WINDOW_STRIDE = 10


@dataclass(frozen=True)
class DraftSentence:
    """One draft segment (a sentence or a window of one): its text for the
    embedder, and the half-open `[word_start, word_end)` range it covers in
    `verbatim_check._tokenize_draft`'s word stream, for the finding."""

    text: str
    word_start: int
    word_end: int


@dataclass(frozen=True)
class DraftSection:
    title: str
    citekeys: list[str]
    sentences: list[DraftSentence]


def matched_words(section: DraftSection, matched: tuple[int, ...]) -> int:
    """How many *distinct* draft words the matched segments cover: a union,
    since windows overlap (a sum once reported 60 words in a 39-word span).
    """
    covered: set[int] = set()
    for index in matched:
        segment = section.sentences[index]
        covered |= set(range(segment.word_start, segment.word_end))
    return len(covered)


# Citation markers are dropped, not blanked as `verbatim_check` does:
# offsets live in `word_start`/`word_end`, and a marker is not prose.
_CITE_MARKER = re.compile(r"\[@[^\]]+\]|\\cite[tp]?\{[^}]*\}")


def _sentence_text(raw: str) -> str:
    return re.sub(r"\s{2,}", " ", _CITE_MARKER.sub(" ", raw)).strip()


# Words' first characters ascend, so two binary searches suffice, via
# `key=` rather than a per-call list (#511/m-76: O(words x sentences)).
_FIRST_CHAR = operator.itemgetter(0)


def _word_range(word_spans: list[tuple[int, int]], start: int, end: int) -> tuple[int, int]:
    """The half-open word-index range covering the characters `[start,
    end)`, given each word's `(first, last)` character span."""
    return (
        bisect.bisect_left(word_spans, start, key=_FIRST_CHAR),
        bisect.bisect_left(word_spans, end, key=_FIRST_CHAR),
    )


def draft_sections(
    text: str,
    word_spans: list[tuple[int, int]],
    citekeys_by_section: dict[str, list[str]],
) -> tuple[list[DraftSection], int]:
    """The draft's sections, each with the citekeys its dossier records
    and the sentences it is made of, plus how many of the dossier's
    recorded sections could not be matched to one of the draft's own
    headings.

    Sections come from `dossier.sections`, which skips fenced code. A
    section with no recorded citekeys is dropped, never scanned against
    the whole corpus (docs/PLAGIARISM-DESIGN.md). The unmatched count
    tells a renamed heading apart from a legitimately thin one (#499).
    """
    line_starts = _line_starts(text)
    draft_headings = dossier.sections(text)
    draft_titles = {heading.title for heading in draft_headings}
    # Only a title with real citekeys counts as unmatched; an empty list
    # is legitimately thin.
    unmatched = sum(
        1 for title, keys in citekeys_by_section.items() if keys and title not in draft_titles
    )
    found = []
    for section in draft_headings:
        citekeys = citekeys_by_section.get(section.title) or []
        if not citekeys:
            continue
        # The body starts after the heading, which is excluded: a label,
        # and nearly pure topic. Both ends clamped (#516/m-55): a final-line
        # heading with no newline raised IndexError.
        start = line_starts[section.start] if section.start < len(line_starts) else len(text)
        end = line_starts[section.end] if section.end < len(line_starts) else len(text)
        section_sentences = _sentences_in(text, word_spans, start, end)
        if section_sentences:
            found.append(DraftSection(section.title, list(citekeys), section_sentences))
    return found, unmatched


def _line_starts(text: str) -> list[int]:
    """Character offset of every line, to turn a `dossier.Section`'s
    1-based line range into a character range."""
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())
    return starts


# A line that opens a block of its own: a bullet or numbered item, a
# table row, a heading, a blockquote, a LaTeX item or sectioning command.
# These carry no `.!?`, so without this a paragraph welds onto the list
# below it; #134's worked example became a 60-word "sentence" scoring
# 0.62, lost in topical noise. Deliberately not `citation_provenance`'s
# `_OPENS_BLOCK`, which must keep blockquotes whole as claims.
_BLOCK_OPENER = re.compile(
    r"^[ \t]*(?:"
    r"[-*+][ \t]|\d+[.)][ \t]|#{1,6}[ \t]|\||>"
    r"|\\item\b|\\(?:begin|end)\{"
    r"|\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{"
    r")",
    re.MULTILINE,
)


def _blocks(text: str) -> list[tuple[int, int]]:
    """`text` as `(start, end)` character spans, cut at blank lines and
    at every line that opens a block; sentences never cross two blocks.
    """
    cuts = {0, len(text)}
    for m in re.finditer(r"\n[ \t]*\n", text):
        cuts |= {m.start(), m.end()}
    for m in _BLOCK_OPENER.finditer(text):
        cuts.add(m.start())
    ordered = sorted(cuts)
    return list(zip(ordered, ordered[1:]))


def _sentences_in(
    text: str, word_spans: list[tuple[int, int]], start: int, end: int
) -> list[DraftSentence]:
    """`text[start:end]` as `DraftSentence`s, dropping any that covers no
    word of the draft word stream, which is how the regions
    `_tokenize_draft` masked stay out.
    """
    found = []
    section = text[start:end]
    for block_start, block_end in _blocks(section):
        for sentence_start, sentence_end in sentences.spans(section[block_start:block_end]):
            found += _one_sentence(
                text,
                word_spans,
                start + block_start + sentence_start,
                start + block_start + sentence_end,
            )
    return found


def _one_sentence(
    text: str, word_spans: list[tuple[int, int]], start: int, end: int
) -> list[DraftSentence]:
    """`text[start:end]` as one segment per window, or an empty list where
    there is no prose there.

    Cut in the word-index domain, not on whitespace: `roll-to-roll` is one
    whitespace token but three stream tokens, and offsets must match.
    """
    word_start, word_end = _word_range(word_spans, start, end)
    # No empty-body guard: a window spans whole words, and a citation
    # marker can never be all of one.
    return [
        DraftSentence(
            _sentence_text(text[word_spans[span_start][0] : word_spans[span_end - 1][1]]),
            span_start,
            span_end,
        )
        for span_start, span_end in _windows(word_start, word_end)
    ]


def _windows(start: int, end: int) -> list[tuple[int, int]]:
    """`[start, end)` as itself when short, or as overlapping
    `WINDOW_WORDS`-long windows when not. Empty when the range is."""
    if end <= start:
        return []
    if end - start <= WINDOW_WORDS:
        return [(start, end)]
    cuts = range(start, end - WINDOW_WORDS + 1, WINDOW_STRIDE)
    windows = [(cut, cut + WINDOW_WORDS) for cut in cuts]
    # A final window ending at `end` covers the tail the stride missed.
    if windows[-1][1] < end:
        windows.append((end - WINDOW_WORDS, end))
    return windows


# --------------------------------------------------------------------------
# Source side: sentences off the Docling passage sidecar
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceSentence:
    text: str
    page: int


def _source_windows(text: str) -> list[str]:
    """A source sentence as itself, or as overlapping windows when long:
    the source-side `_windows`. Split on whitespace, since a finding needs
    only the passage's page. Windowed for the same topic-swamping reason.
    """
    words = text.split()
    if len(words) <= WINDOW_WORDS:
        return [text] if text else []
    cuts = range(0, len(words) - WINDOW_WORDS + 1, WINDOW_STRIDE)
    windows = [" ".join(words[cut : cut + WINDOW_WORDS]) for cut in cuts]
    if len(words) % WINDOW_STRIDE:
        windows.append(" ".join(words[-WINDOW_WORDS:]))
    return windows


def source_sentences(con, citekey: str) -> list[SourceSentence]:
    """A source's prose as sentences, each carrying the page it sits on.
    Only quotable, paged passages (rungs 1 and 2); see the module docstring.
    """
    found, _reason = passages.source_passages(con, citekey)
    out = []
    for passage in found:
        if passage.text is None or passage.page is None:
            continue
        for start, end in sentences.spans(passage.text):
            for body in _source_windows(passage.text[start:end].strip()):
                out.append(SourceSentence(body, passage.page))
    return out
