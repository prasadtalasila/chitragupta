"""Rewriting a draft's `[@citekey]` markers as IEEE numbers.

Split from `chitragupta/references.py` (#441): `renumber` and its
supporting regexes/helper only ever touch a draft's text and a
citekey -> number map handed to them by `numbered_markdown`, never the
ledger or an entry's formatted fields -- a separate concern from
`chitragupta/references_ieee.py`'s entry formatting, and a separate
seam from it for the same reason.
"""

import bisect
import re

from chitragupta import _pandoc_cites, citation_gate

# Which citations to renumber is not decided here: `renumber` takes the
# gate's own (start, end, key) spans, from the gate's own prose blanking.
# Two readings that drift apart leave a real citation un-numbered or
# number something that was never one, and they did drift (#1021): this
# module restated the gate's pattern and never learned the braced form,
# so `[@{brace.one}]` came out raw, and `[@plain; @{brace.one}]` as
# `[[3]; @{brace.one}]`, while the reference list numbered `brace.one`.
# Sharing the spans is also what keeps `@` inside a larger token from
# reading as a citation -- this project's own tutorial draft carries an
# author's email address, and a citekey could be named `gmail`.
#
# What *is* decided here is a bracket's shape. A bracket holding nothing
# but citations separated by ";" -- `[@a]`, `[@a; @b; @c]`, `[-@a]` --
# collapses to its numbers. One citation with a locator -- `[@a, p. 33]`
# -- becomes `[3, p. 33]`. Anything else, a prefix word included (`[see
# @a, p. 33]`), is renumbered one key at a time, so the words around it
# survive: collapsing that bracket would silently delete them. Only a
# bracket holding no other bracket is a candidate, as before.
_BRACKET_RE = re.compile(r"\[[^\[\]]*\]")
_LOCATOR_RE = re.compile(r"\s*,\s*([^\[\]@;]+)")
# IEEE, and the CSL style's own `collapse="citation-number"`, only
# contract a run of *three or more*: [1], [2] stays as it is, [3]-[5]
# collapses. Matching that keeps the numbered Markdown identical to what
# the same draft's PDF shows.
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

    The words between the citations are read from `text`: in `blanked` a
    comment is spaces, and a bracket holding one collapsed to its number,
    deleting the comment from the numbered copy. The locator is matched
    in `blanked`, where a code span inside it cannot hold an `@` or `;`,
    and sliced from `text`, so the code span survives.
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

    A bracket holding even one unnumbered key is covered all the same, so
    it is left exactly as written. Without that the per-key pass would
    still rewrite its *known* keys and leave `[[1]; @zzz]` -- a mangling
    worse than the untouched marker, which at least reads as an obvious
    omission.
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

    Finds the citations in a blanked copy, then edits the original at
    those offsets -- `citation_gate.markdown_prose` replaces code and
    other non-prose with spaces while preserving every character
    position, so a `[@key]` shown inside an example (which the gate
    itself ignores) is left exactly as written here too.

    A key with no number -- which can only happen if a caller passes a
    partial map -- is left untouched rather than rendered as `[None]`.
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
