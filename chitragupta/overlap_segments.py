"""What a *sentence* is on each side of tier 3's alignment.

The draft side and the source side of `chitragupta/overlap_embed.py`, split out
because they are the two halves of the same question -- what unit gets
embedded, and where in the original does it sit -- and because the
answers come from completely different places. The draft side reads a
Markdown or LaTeX file this pipeline wrote, with sections, citation
markers and a word stream `chitragupta/review/verbatim_check.py` has already
tokenized. The source side reads a Docling passage sidecar through
`chitragupta/passages.py`'s ladder.

Both sides answer to one rule: a sentence is only usable if it can say
where it came from. A draft sentence carries the half-open word-index
range it covers in the scan's own word stream, because that is the
coordinate system a finding is reported in (#131, shared with tiers 1
and 2). A source sentence carries a page number, because that is what a
reviewer turns to. A passage with neither -- `chitragupta/passages.py`'s rungs 3
and 4, whole pages of `pdftotext -layout` output with `text=None` -- is
dropped rather than aligned: on a two-column paper every line of that
text splices two unrelated columns together, so a sentence cut from one
is a collage of two arguments and an alignment against it would be a
confident finding about text nobody wrote.

Stdlib only, like the two modules it draws on.
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
# many words, `WINDOW_STRIDE` apart. Sentences shorter than it are left
# whole.
#
# This is the single measurement that decides whether the tier works at
# all, so it is worth stating what was measured. #134's own worked
# example -- chapter 1 of the real book restating `singh_digital_2023`'s
# "save their ROI while adapting to modern technologies with minimal
# risk" as "protecting return on investment while adopting modern
# technology with minimal risk and investment" -- scores **0.55** as a
# whole sentence against the source sentence it restates, while three
# unrelated sentences of that same paper score 0.59-0.61 against it. At
# sentence granularity the true pair is *below* the topical noise of a
# single-field corpus, and no threshold recovers it. The same draft
# prose windowed at 18-20 words scores **0.71** against the true source
# sentence and 0.40 against the same noise.
#
# The reason is the framing. "A case study of a small-to-medium
# roll-to-roll label-printing manufacturer reports ..." is half the
# sentence and is pure topic; embedded together with the restated clause
# it dominates the vector, and every sentence in a paper about that
# manufacturer then looks equally close. A window is short enough that
# the restated clause is most of what is in it. This is the concrete
# form of the warning `docs/PLAGIARISM-DESIGN.md` records from
# `bench_overlap_df.py`: in a single-field corpus, topical similarity is
# high by default, so a detector has to compare something smaller than a
# topic.
#
# Stride is half the window, so any clause of at most this many words
# falls whole inside some window rather than being cut across two.
WINDOW_WORDS = 20
WINDOW_STRIDE = 10


@dataclass(frozen=True)
class DraftSentence:
    """One draft segment -- a sentence, or a window of one -- in both
    coordinate systems this tier has to speak: its text (for the
    embedder) and the half-open `[word_start, word_end)` range it covers
    in the draft word stream `verbatim_check._tokenize_draft` produced
    (for the finding)."""

    text: str
    word_start: int
    word_end: int


@dataclass(frozen=True)
class DraftSection:
    title: str
    citekeys: list[str]
    sentences: list[DraftSentence]


def matched_words(section: DraftSection, matched: tuple[int, ...]) -> int:
    """How many *distinct* draft words the matched segments cover.

    A union, not a sum. Segments overlap by construction -- a long
    sentence is cut into windows `WINDOW_STRIDE` apart, so consecutive
    windows share half their words -- and summing their lengths reported
    60 matched words inside a 39-word span on the first real run.
    `matched_words` is read as "how much of this span is evidence"
    (`_bucket` buckets on it), and a number larger than the span itself
    is not that.
    """
    covered: set[int] = set()
    for index in matched:
        segment = section.sentences[index]
        covered |= set(range(segment.word_start, segment.word_end))
    return len(covered)


# Citation markers are dropped from the text handed to the embedder, not
# blanked: `[@kritzinger_digital_2018]` is not prose and a bi-encoder has
# no way to know that. `verbatim_check` blanks them instead, because it
# needs every character offset after one to stay put; here the offsets
# are carried by `word_start`/`word_end`, which are already computed.
_CITE_MARKER = re.compile(r"\[@[^\]]+\]|\\cite[tp]?\{[^}]*\}")


def _sentence_text(raw: str) -> str:
    return re.sub(r"\s{2,}", " ", _CITE_MARKER.sub(" ", raw)).strip()


# Each word's first character is ascending -- `_tokenize_draft` walks
# paragraphs in order and words within each in order -- so this is a pair
# of binary searches rather than a scan of the draft per sentence.
#
# Bisected through `key=` rather than over a separate list of first
# characters (#511/m-76). That list was rebuilt from `word_spans` on every
# call, i.e. once per sentence, making this O(words x sentences) before a
# single embedding had been computed -- and it was the same list every
# time. Hoisting it to the caller would have worked too, at the cost of a
# fourth parameter threaded through two functions; not building it at all
# is cheaper in both senses.
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

    Sections come from `chitragupta.dossier.sections`, which is the repo's one
    outline parser and already skips fenced code and LaTeX verbatim --
    a `# Step 1` comment inside a code block is indistinguishable from a
    heading to anything that does not track fences.

    A section `sections.md` records no citekeys for is dropped, not
    scanned against the whole corpus: `docs/PLAGIARISM-DESIGN.md` argues at
    length that a whole-corpus search is the wrong shape for this corpus,
    and falling back to one wherever the dossier happened to be thin
    would reintroduce exactly that, silently.

    The second return value is a different failure from that one, and
    the caller needs to be able to tell them apart (#499). A recorded
    section title that matches no heading in `text` at all -- a heading
    renamed since `sections --citekeys --write` last ran -- silently
    scanned nothing for that source, and a caller comparing only the
    returned sections against a zero count could not distinguish "the
    dossier legitimately named this section thin" from "this section's
    heading moved and nothing was ever compared against its sources".
    """
    line_starts = _line_starts(text)
    draft_headings = dossier.sections(text)
    draft_titles = {heading.title for heading in draft_headings}
    # Only a title recording real citekeys counts as unmatched -- a
    # title the dossier records with an empty list is "legitimately
    # thin", the same case the loop below drops via `if not citekeys`,
    # not a heading that moved out from under the mapping.
    unmatched = sum(
        1 for title, keys in citekeys_by_section.items() if keys and title not in draft_titles
    )
    found = []
    for section in draft_headings:
        citekeys = citekeys_by_section.get(section.title) or []
        if not citekeys:
            continue
        # `section.start` is the heading's own line, and the body starts
        # on the next one. The heading is excluded deliberately: it is
        # already carried as `title`, it is a label rather than a claim,
        # and as a segment it is short enough that its embedding is
        # almost pure topic -- exactly the thing windowing exists to keep
        # out of the comparison.
        start = line_starts[section.start]
        end = line_starts[section.end] if section.end < len(line_starts) else len(text)
        section_sentences = _sentences_in(text, word_spans, start, end)
        if section_sentences:
            found.append(DraftSection(section.title, list(citekeys), section_sentences))
    return found, unmatched


def _line_starts(text: str) -> list[int]:
    """Character offset of every line, so a `dossier.Section`'s 1-based
    line range can be turned into a character range."""
    starts = [0]
    for m in re.finditer("\n", text):
        starts.append(m.end())
    return starts


# A line that opens a block of its own: a bullet or numbered item, a
# table row, a heading, a blockquote, a LaTeX item or sectioning command.
#
# `chitragupta/review/citation_provenance.py` has a similar-looking `_OPENS_BLOCK`
# doing a different job, and the two are deliberately not shared -- the
# same call `chitragupta/dossier/` makes about its own heading regexes, for the
# same kind of reason. That one segments *claim-bearing* blocks for
# lexical scoring against a source, and a blockquote is claim-bearing
# prose it must keep whole; this one cuts *embedding units*, where a
# quoted block is a different voice and belongs in its own vector. Making
# one regex serve both would mean changing what the provenance report
# quotes back to a reviewer in order to improve an alignment, which is
# the wrong trade in the wrong direction.
#
# What both are for is the same: those constructs carry no
# sentence-ending punctuation, so a splitter that only looks for `.!?`
# welds a paragraph onto the bullet list beneath it.
#
# Measured, not assumed: without this, the one hand-checked
# close-paraphrase pair in chapter 1 of the real book
# (`singh_digital_2023`, #134's own worked example) came out as a
# 60-word "sentence" running from the middle of a paragraph through three
# bullets of an unrelated list, and its best cosine against the source
# sentence it actually restates was 0.62 -- indistinguishable from the
# topical background of a single-field corpus. Segmentation was the
# whole of that gap.
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
    at every line that opens a block.

    Sentences are found *within* a block, never across two. A paragraph
    break is not a sentence boundary any regex over `.!?` can see, and
    neither is the start of a bullet -- but both end a unit of prose, and
    an embedding of two units welded together is an embedding of neither.
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
    word of the draft word stream.

    That drop is what keeps the masked regions out without this module
    having to know how they were masked: `_tokenize_draft` already
    excluded the References section, fenced code and citation markers
    from the word stream, so a "sentence" sitting entirely inside one covers
    no words and is not a sentence of this draft's prose.
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

    Windows are cut in the *word-index* domain rather than by splitting
    the text on whitespace, because the two do not agree: `roll-to-roll`
    is one whitespace token and three of the word stream's tokens, and a
    segment whose `word_start`/`word_end` were counted the other way
    would report a finding at the wrong offset in the draft.
    """
    word_start, word_end = _word_range(word_spans, start, end)
    # No empty-body guard: a window runs from one word's first character
    # to another's last, so it always contains at least those words, and
    # `_sentence_text` only ever removes a citation marker -- which
    # cannot be the whole of a window, because a marker's closing brace
    # falls outside the span and the marker therefore never matches on
    # its own. An empty range is already handled by `_windows` returning
    # nothing.
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
    # The stride rarely divides the range exactly, so the tail would
    # otherwise be covered only by whatever the last full window reached.
    # A final window ending at `end` costs one extra segment and is what
    # makes "every clause falls whole inside some window" true at the end
    # of a sentence as well as in the middle.
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
    """A source sentence as itself, or as overlapping windows when it is
    long enough to need them -- the source-side counterpart of
    `_windows`.

    Split on whitespace here, unlike the draft side, which has to cut in
    the word-index domain to keep its offsets. Nothing downstream needs
    a source segment's position within its passage: a finding reports the
    source's *page*, which the passage already carries and every window
    of it inherits.

    Both sides have to be windowed, not just the draft. A window is what
    stops a topic from swamping a claim, and a 40-word source sentence
    whose second half is the restated claim has the same problem in the
    same direction.
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

    Only *quotable* passages with a page number qualify -- rungs 1 and 2
    of `chitragupta/passages.py`'s ladder, the Docling sidecars. Rungs 3 and 4
    hand back whole pages with `text=None` for a reason this tier cannot
    work around: they are `pdftotext -layout` output, where a two-column
    paper's every line splices two unrelated columns together, so a
    sentence cut from one is a collage of two arguments. Aligning against
    that would produce confident findings over text that was never
    written.
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
