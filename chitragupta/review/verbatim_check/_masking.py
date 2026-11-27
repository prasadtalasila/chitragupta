"""Masking and tokenizing a draft into the flat word stream every
detection tier scans: code fences, References, quote spans, citation
markers.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, quote_spans, references_section
from chitragupta.review.verbatim_check._corpus import WORD

# Double-quoted spans come from `chitragupta/quote_spans.py`, shared with
# the prose check so both agree on what a quotation is; blockquotes added here.


def _quote_char_spans(text: str) -> list[tuple[int, int]]:
    spans = quote_spans.double_quoted(text)
    pos = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith(">"):
            spans.append((pos, pos + len(line)))
        pos += len(line)
    return spans


def _char_in_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


def _mask_for_scan(text: str) -> str:
    """Blank code (`citation_gate._blank_code`: code is not draft prose)
    and the References section, which is bib metadata and would match
    every source's own title page.

    `references_section` gets the original lines; `_blank_code` keeps the
    line count, so its indices still apply. Only the section is blanked:
    an appendix after it must stay scannable (M-8/m-33/m-34).
    """
    original_lines = text.splitlines(keepends=True)
    idx = references_section.section_start(original_lines)
    lines = citation_gate._blank_code(text).splitlines(keepends=True)
    if idx is not None:
        end = references_section.section_end(original_lines, idx)
        lines = lines[:idx] + [re.sub(r"[^\n]", " ", line) for line in lines[idx:end]] + lines[end:]
    return "".join(lines)


@dataclass
class _DraftWord:
    text: str
    paragraph: int
    quoted: bool
    # Offsets in the *original* text, so `original[char:char_end]` is the
    # word as written for a remediation edit (#129); see `_lower_offsets`.
    char: int
    char_end: int


_PARA_SPLIT_RE = re.compile(r"\n\s*\n")
_CITE_MARKER_RE = re.compile(r"\[@[^\]]+\]")
# `\citep[p.~3]{key}` in a .tex draft (#1187): the command name and the key
# are not prose, and no rewording of the sentence removes them.
_LATEX_CITE_RE = re.compile(r"\\cite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}")


def _citekey_re(citekeys: frozenset[str]) -> re.Pattern | None:
    """One alternation over `citekeys`, longest first so a prefix key cannot
    shadow another, bounded so only a whole token matches."""
    if not citekeys:
        return None
    keys = "|".join(re.escape(k) for k in sorted(citekeys, key=lambda k: (-len(k), k)))
    return re.compile(rf"(?<![\w:.-])(?:{keys})(?![\w:-])")


def _paragraphs(text: str) -> list[tuple[int, str]]:
    """`(offset, paragraph)` for each paragraph, split as
    `re.split(r"\\n\\s*\\n", text)` would, keeping the offset an editing
    caller needs."""
    out = []
    pos = 0
    for m in _PARA_SPLIT_RE.finditer(text):
        out.append((pos, text[pos : m.start()]))
        pos = m.end()
    out.append((pos, text[pos:]))
    return out


def _lower_offsets(text: str) -> tuple[str, list[int] | None]:
    """`text.lower()`, plus -- when lowercasing moved anything -- the
    index in `text` of every character of that result.

    `str.lower()` is not length-preserving (`"İ"` becomes two code
    points), the one offset-shifting step in this chain. The lowercasing
    must stay: `overlap_index.py` fingerprints with `text.lower()`, so
    both sides must agree on what a word is. `None` in the common case
    where nothing moved.
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
    # Rebuilt so the searched string is the one these offsets describe.
    return "".join(parts), offsets


def _original_index(offsets: list[int] | None, i: int) -> int:
    return i if offsets is None else offsets[i]


def _blank_span(m: re.Match) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _tokenize_draft(
    text: str, *, latex: bool = False, citekeys: frozenset[str] = frozenset()
) -> tuple[list[_DraftWord], list[set[str]]]:
    """Every word of `text` (masked, citation markers blanked) as a flat
    list across the whole draft, plus which citekeys each paragraph
    cites. Each word carries where it sits in `text` itself.

    Flat: an n-gram may cross a paragraph seam, a deliberate trade for
    catching the common case. Markers are **blanked, not stripped**, so
    offsets hold and `twins[@key]matter` does not weld into one token.
    `latex` and `citekeys` also blank `\\cite...{key}` and bare known keys
    (#1187); both default off.
    """
    masked = _mask_for_scan(text)
    bare_re = _citekey_re(citekeys)
    words = []
    paragraph_citekeys = []
    for p_idx, (para_start, para) in enumerate(_paragraphs(masked)):
        paragraph_citekeys.append(set(citation_gate.extract_citekeys_from_line(para, latex=latex)))
        clean = _CITE_MARKER_RE.sub(_blank_span, para)
        if latex:
            clean = _LATEX_CITE_RE.sub(_blank_span, clean)
        if bare_re is not None:
            clean = bare_re.sub(_blank_span, clean)
        quote_spans = _quote_char_spans(clean)
        lowered, offsets = _lower_offsets(clean)
        for m in WORD.finditer(lowered):
            start = _original_index(offsets, m.start())
            end = _original_index(offsets, m.end() - 1) + 1
            words.append(
                _DraftWord(
                    m.group(0),
                    p_idx,
                    _char_in_spans(start, quote_spans),
                    para_start + start,
                    para_start + end,
                )
            )
    return words, paragraph_citekeys
