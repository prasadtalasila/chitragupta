"""Rewriting a draft's `[@citekey]` markers as IEEE numbers (#441).

Touches only a draft's text and the citekey -> number map
`numbered_markdown` hands it, never the ledger.
"""

import bisect
import re

from chitragupta import _pandoc_cites, citation_gate

# Which citations to renumber is the gate's call: `renumber` takes its
# (start, end, key) spans, because two readings drifted apart (#1021,
# the braced form) and the spans keep an email `@` from reading as one.
#
# What is decided here is a bracket's shape: only citations separated by
# ";" collapse to numbers, one citation with a locator becomes
# `[3, p. 33]`, and anything else (a prefix word) is renumbered key by key
# so its words survive. Only a bracket holding no other bracket counts.
_BRACKET_RE = re.compile(r"\[[^\[\]]*\]")
_LOCATOR_RE = re.compile(r"\s*,\s*([^\[\]@;]+)")
# IEEE and the CSL style contract only runs of three or more, so the
# numbered Markdown matches the PDF.
_MIN_COLLAPSIBLE_RUN = 3


def _format_numbers(numbers: list[int]) -> str:
    """`[1]`, `[1], [2]`, `[3]–[6]` -- IEEE's own contraction rules."""
    runs: list[list[int]] = []
    for n in sorted(set(numbers)):
        if runs and n == runs[-1][-1] + 1:
            runs[-1].append(n)
        else:
            runs.append([n])

    out = []
    for run in runs:
        if len(run) >= _MIN_COLLAPSIBLE_RUN:
            out.append(f"[{run[0]}]–[{run[-1]}]")
        else:
            out.extend(f"[{n}]" for n in run)
    return ", ".join(out)


def _locator(text: str, blanked: str, bracket: re.Match, inner: list) -> "str | None":
    """`""` for a bracket of ";"-separated citations, the locator for one
    citation with a locator, None for any other shape.

    Words between citations are read from `text` (in `blanked` a comment
    is spaces and would be deleted). The locator is matched in `blanked`
    and sliced from `text`, so a code span inside it survives.
    """
    gaps = []
    pos = bracket.start() + 1
    for start, end, _ in inner:
        gaps.append(text[pos:start])
        pos = end
    if gaps[0].strip() or any(gap.strip() != ";" for gap in gaps[1:]):
        return None
    if not text[pos : bracket.end() - 1].strip():
        return ""
    found = _LOCATOR_RE.fullmatch(blanked, pos, bracket.end() - 1) if len(inner) == 1 else None
    return text[found.start(1) : found.end(1)].strip() if found else None


def _group_edits(text: str, blanked: str, cites: list, numbers: dict[str, int]) -> tuple:
    """A group's or a locator bracket's edit, and the citations it covers.

    A bracket with even one unnumbered key is covered and left as written:
    `[[1]; @zzz]` is worse than an obviously untouched marker.
    """
    starts = [start for start, _, _ in cites]
    edits: list[tuple[int, int, str]] = []
    covered: set[int] = set()
    for bracket in _BRACKET_RE.finditer(blanked):
        inner = cites[
            bisect.bisect_left(starts, bracket.start()) : bisect.bisect_left(starts, bracket.end())
        ]
        locator = _locator(text, blanked, bracket, inner) if inner else None
        if locator is None:
            continue
        covered.update(start for start, _, _ in inner)
        keys = [key for _, _, key in inner]
        if any(key not in numbers for key in keys):
            continue
        if locator:
            replacement = f"[{numbers[keys[0]]}, {locator}]"
        else:
            replacement = _format_numbers([numbers[key] for key in keys])
        edits.append((bracket.start(), bracket.end(), replacement))
    return edits, covered


def renumber(text: str, numbers: dict[str, int]) -> str:
    """Rewrites `text`'s citekey markers as IEEE numbers from `numbers`.

    Citations are found in `citation_gate.markdown_prose`'s offset-keeping
    blanked copy, so a `[@key]` in an example is left as written. A key
    with no number (a partial map) is left untouched, never `[None]`.
    """
    blanked, labels = citation_gate.markdown_prose(text)
    cites = _pandoc_cites.citations(blanked, labels, source=text)
    edits, covered = _group_edits(text, blanked, cites, numbers)
    edits.extend(
        (start, end, f"[{numbers[key]}]")
        for start, end, key in cites
        if start not in covered and key in numbers
    )

    out = []
    position = 0
    for start, end, replacement in sorted(edits):
        out.append(text[position:start])
        out.append(replacement)
        position = end
    out.append(text[position:])
    return "".join(out)
