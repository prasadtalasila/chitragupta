"""Masking and tokenizing a draft into the flat word stream every
detection tier scans: code fences, References, quote spans, citation
markers.

Split out of chitragupta/review/verbatim_check.py (#361) -- see
chitragupta/review/verbatim_check/_corpus.py's docstring for the split.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, references
from chitragupta.review.verbatim_check._corpus import WORD

# Straight or curly double-quoted spans, and Markdown blockquote lines --
# deliberately not cleverer than that (no nesting, no single quotes,
# which double as apostrophes and would flag most of the draft). Detecting
# *that* a run touches quote delimiters (`_run_is_quoted`, which reads
# these spans as overlap rather than containment) is a cheap,
# deterministic bit attached to a finding; whether that should downgrade
# severity (a legitimate page-anchored quotation vs. unmarked reuse) is
# Phase 2's policy call, not this one's.
_QUOTE_SPAN_RE = re.compile(r'["“]([^"”]{2,})["”]')


def _quote_char_spans(text: str) -> list[tuple[int, int]]:
    spans = [(m.start(), m.end()) for m in _QUOTE_SPAN_RE.finditer(text)]
    pos = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(">"):
            spans.append((pos, pos + len(line)))
        pos += len(line)
    return spans


def _char_in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _mask_for_scan(text: str) -> str:
    """Code-fence/inline-code and References-section blanking, sharing
    the corpus's own masking discipline rather than reinventing it:
    `citation_gate._blank_code` is what keeps a Python `@dataclass` or a
    `\\citep{...}`-shaped code example from reading as a real citation,
    and the same false-positive shape applies here -- code prose is not
    draft prose. The References section is generated from bib metadata
    (titles, venues), so scanning it would flag every source's own title
    page as "verbatim overlap with itself".

    `references.section_start` is handed the *original* lines (its own
    contract -- it blanks internally just to find the heading) and
    returns an index into them; `_blank_code` never changes line count,
    so that index still lines up with the blanked text's lines.
    """
    original_lines = text.splitlines(keepends=True)
    idx = references.section_start(original_lines)
    lines = citation_gate._blank_code(text).splitlines(keepends=True)
    if idx is not None:
        lines = lines[:idx] + [re.sub(r"[^\n]", " ", line) for line in lines[idx:]]
    return "".join(lines)


@dataclass
class _DraftWord:
    text: str
    paragraph: int
    quoted: bool
    # Where this word sits in the *original* text handed to
    # `_tokenize_draft` -- not in the masked, marker-blanked, lowercased
    # stream `text` came out of. `original[char:char_end]` is the word as
    # written, casing and all, which is what a remediation loop needs to
    # hand `Edit` (#129). See `_lower_offsets` for why the two can differ
    # by more than case.
    char: int
    char_end: int


_PARA_SPLIT_RE = re.compile(r"\n\s*\n")
_CITE_MARKER_RE = re.compile(r"\[@[^\]]+\]")


def _paragraphs(text: str) -> list[tuple[int, str]]:
    """`(offset, paragraph)` for each paragraph of `text`, splitting where
    `re.split(r"\\n\\s*\\n", text)` splits and keeping the offset that
    split throws away.

    The offset is the half of the answer a caller that means to *edit*
    needs: without it a word's position is known only within its own
    paragraph, and every paragraph after the first is off by however much
    preceded it.
    """
    out = []
    pos = 0
    for m in _PARA_SPLIT_RE.finditer(text):
        out.append((pos, text[pos:m.start()]))
        pos = m.end()
    out.append((pos, text[pos:]))
    return out


def _lower_offsets(text: str) -> tuple[str, list[int] | None]:
    """`text.lower()`, plus -- when lowercasing moved anything -- the
    index in `text` of every character of that result.

    `str.lower()` is not length-preserving: `"İ"` lowercases to two code
    points, so every offset after one is shifted. Everything else in this
    masking chain preserves offsets deliberately
    (`citation_gate._blank_code` says as much in its own comment), and
    this is the one step that cannot, so it reports the shift instead of
    hiding it.

    The lowercasing itself has to stay. `chitragupta/overlap_index.py`
    fingerprints the corpus with `WORD.findall(text.lower())`; matching
    the draft case-insensitively instead would read `"İstanbul"` as one
    word where the corpus reads two, and the two sides would stop
    agreeing on what a word is -- which is the whole basis of a match.

    `None` rather than a range-mapping list for the overwhelmingly common
    case where lowercasing changed no lengths: it says "offsets are their
    own indices" once, instead of every caller carrying a list it would
    only ever index by identity.
    """
    lowered = text.lower()
    if len(lowered) == len(text):
        return lowered, None
    parts = []
    offsets = []
    for i, ch in enumerate(text):
        low = ch.lower()
        parts.append(low)
        offsets.extend([i] * len(low))
    # Rebuilt character by character rather than reusing `lowered`, so the
    # string actually searched is the one these offsets describe.
    return "".join(parts), offsets


def _original_index(offsets: list[int] | None, i: int) -> int:
    return i if offsets is None else offsets[i]


def _blank_span(m: re.Match) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _tokenize_draft(text: str) -> tuple[list[_DraftWord], list[set[str]]]:
    """Every word of `text` (masked, citation markers blanked) as a flat
    list across the whole draft, plus which citekeys each paragraph
    cites. Each word carries where it sits in `text` itself.

    Flat rather than paragraph-scoped: an n-gram window can cross a
    paragraph break in the word stream this produces, unlike `overlap`'s
    per-paragraph scan. That is a deliberate trade -- catching reuse in
    the (much more common) single-paragraph case matters more than the
    rare false-candidate an adjacent-paragraph seam could produce, and a
    real match still has to line up with actual corpus text to survive.

    **Blanked, not stripped.** The citation marker used to be deleted,
    which shifted every character after it and was one of the two reasons
    a finding could not be located in the file it came from (the other
    being the paragraph split; see `_paragraphs`). Blanking it with
    spaces is `_blank_code`'s existing discipline, applied to the one
    place in this module that still deleted. It also stops
    `twins[@key]matter` from welding into a single token, which deleting
    did.
    """
    masked = _mask_for_scan(text)
    words = []
    paragraph_citekeys = []
    for p_idx, (para_start, para) in enumerate(_paragraphs(masked)):
        paragraph_citekeys.append({key for _, key in citation_gate.extract_citekeys(para)})
        clean = _CITE_MARKER_RE.sub(_blank_span, para)
        quote_spans = _quote_char_spans(clean)
        lowered, offsets = _lower_offsets(clean)
        for m in WORD.finditer(lowered):
            start = _original_index(offsets, m.start())
            end = _original_index(offsets, m.end() - 1) + 1
            words.append(_DraftWord(
                m.group(0), p_idx, _char_in_spans(start, quote_spans),
                para_start + start, para_start + end,
            ))
    return words, paragraph_citekeys
