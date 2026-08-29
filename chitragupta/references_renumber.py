"""Rewriting a draft's `[@citekey]` markers as IEEE numbers.

Split from `chitragupta/references.py` (#441): `renumber` and its
supporting regexes/helper only ever touch a draft's text and a
citekey -> number map handed to them by `numbered_markdown`, never the
ledger or an entry's formatted fields -- a separate concern from
`chitragupta/references_ieee.py`'s entry formatting, and a separate
seam from it for the same reason.
"""

import re

from chitragupta import citation_gate

# A bracketed Pandoc citation containing nothing but citekeys separated
# by ";" -- `[@a]`, `[@a; @b; @c]`, `[-@a]`. Deliberately does NOT match a
# group carrying a prefix or locator (`[see @a, p. 33]`): collapsing that
# to a bare number would silently delete the words around it. Those are
# handled one key at a time by _BARE_KEY_RE below, which leaves the
# surrounding text alone.
_CITATION_GROUP_RE = re.compile(
    r"\[\s*-?@[A-Za-z][A-Za-z0-9_-]*(?:\s*;\s*-?@[A-Za-z][A-Za-z0-9_-]*)*\s*\]"
)
# citation_gate's own Pandoc-citation regex, not a second definition of
# one. Its negative lookbehind is what keeps `@` inside a larger token
# from reading as a citation -- this project's own tutorial draft carries
# an author's email address, and a looser pattern would rewrite the
# `@gmail` in it the moment a citekey happened to be named `gmail`.
# Sharing the gate's pattern also guarantees that what gets renumbered
# here is exactly what the gate verified and what used_citekeys() counted;
# two patterns that drifted apart would silently leave a real citation
# un-numbered, or number something that was never a citation.
_BARE_KEY_RE = citation_gate._PANDOC_CITE_RE
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


def renumber(text: str, numbers: dict[str, int]) -> str:
    """Rewrites `text`'s citekey markers as IEEE numbers from `numbers`.

    Scans a code-blanked copy to locate the citations, then edits the
    original at those offsets -- `citation_gate._blank_code` replaces a
    fenced block or code span with spaces while preserving every
    character position, so a `[@key]` shown inside an example (which the
    gate itself ignores) is left exactly as written here too.

    A key with no number -- which can only happen if a caller passes a
    partial map -- is left untouched rather than rendered as `[None]`.
    """
    blanked = citation_gate._blank_code(text)

    edits: list[tuple[int, int, str]] = []
    covered: list[tuple[int, int]] = []
    for match in _CITATION_GROUP_RE.finditer(blanked):
        keys = _BARE_KEY_RE.findall(match.group())
        # Marked covered either way, so that a group holding even one
        # unnumbered key is left exactly as written. Without this the
        # per-key pass below would still rewrite its *known* keys and
        # leave `[[1]; @zzz]` -- a mangling that is worse than the
        # untouched marker, which at least reads as an obvious omission.
        covered.append((match.start(), match.end()))
        if any(k not in numbers for k in keys):
            continue
        edits.append((match.start(), match.end(), _format_numbers([numbers[k] for k in keys])))

    # Anything left: a bare `@key`, or one inside a group with a prefix or
    # locator. Replaced individually so the words around it survive.
    for match in _BARE_KEY_RE.finditer(blanked):
        if any(start <= match.start() < end for start, end in covered):
            continue
        number = numbers.get(match.group(1))
        if number is not None:
            edits.append((match.start(), match.end(), f"[{number}]"))

    out = []
    position = 0
    for start, end, replacement in sorted(edits):
        out.append(text[position:start])
        out.append(replacement)
        position = end
    out.append(text[position:])
    return "".join(out)
