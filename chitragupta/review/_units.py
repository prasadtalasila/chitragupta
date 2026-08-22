"""What a "unit" is, per genre -- the scale the multi-source rule binds at.

`docs/WRITING-STANDARDS.md` §11 states the rule: a unit cites two or more
citekeys wherever the evidence set allows, and a single-source unit is a
deliberate choice the drafter states. What differs between genres is not
the rule but the *unit*, and this module is the one place that mapping
lives.

A multi-source paragraph is what a survey wants and what a textbook
chapter finds distracting; a tutorial cannot have one at all, because its
body carries no citations by design. Applying the paragraph everywhere
would either damage three genres' prose or exempt them from the
guarantee, and neither is necessary -- see
`plans/b2-multi-source-synthesis.md`.

**Two scales for a section, not one.** A section that cites two papers by
running one out before starting the next spans two sources and fuses
neither, so spread alone cannot tell a fused section from a
block-structured one. `Unit.longest_run` is what does: the longest run of
consecutive paragraphs resting on the same single citekey. It makes an
existing instruction observable rather than adding a new one --
`textbook-chapter-writer` step 4 already says not to let one citekey
carry a whole section.

Serves `chitragupta/review/synthesis.py` and nothing else today. Split
out of it so that both stay under docs/CODE-STANDARDS.md's C2, and
because "what counts as a unit" and "what the report says about them" are
genuinely two questions.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from chitragupta import citation_gate, dossier

# The genre-to-unit table, and the whole of the per-genre policy. Keyed by
# what `dossier init --genre` writes into scope.md, which
# tests/test_review_units.py pins against `dossier.GENRES` so a sixth
# genre cannot arrive here as a silent fallback to the paragraph.
UNITS = {
    "survey": "paragraph",
    "thesis-chapter": "paragraph",
    "deep-research": "paragraph",
    "textbook-chapter": "section",
    "tutorial": "document",
}

KINDS = ("paragraph", "section", "document")

# What an unknown or unrecorded genre is measured at. The paragraph
# rather than a refusal: a report that judges nothing is more useful
# reporting at the wrong scale *and saying so* than not running -- and
# `resolve_unit` returns "nothing" as the source precisely so the report
# can say it.
FALLBACK_KIND = "paragraph"

# `<!-- single-source: why -->` in Markdown, `% single-source: why` in
# LaTeX. Deliberately carries no `@` sigil and no `\cite`, so the reason
# a drafter gives -- which usually names the citekey in prose -- cannot
# be read back as a citation and inflate the count it exists to explain.
_MARKER_RE = re.compile(r"(?:<!--|%)\s*single-source:\s*(.*?)\s*(?:-->|$)")

# A section opens at a heading, in either markup. The same shapes
# `citation_provenance` recognises, minus the list and table openers: a
# table row does not start a section.
_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s|\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{)"
)


@dataclass(frozen=True)
class Unit:
    """One unit of a draft, at whatever scale its genre binds at.

    `text` is marker-stripped, which is what keeps a finding's identity
    from changing the moment someone declares it -- see `_prose`.
    `longest_run` is 0 for every kind but `section`, which is the only
    one with an inside that can be block-structured.
    """

    kind: str
    line: int
    text: str
    citekeys: tuple[str, ...]
    declared: str | None
    longest_run: int


def genre_of(draft: Path) -> str | None:
    """The genre recorded in this draft's dossier `scope.md`, or None.

    None covers three situations that all want the same treatment -- no
    dossier, no `- genre:` line, and an empty value. Each means *nobody
    recorded a genre*, and the honest response is to measure at the
    fallback and name it. Mirrors `style_check.language_of`, which
    resolves the dialect from the same file the same way.
    """
    try:
        scope = dossier.dossier_dir(Path(draft)) / dossier.SCOPE_MD
    except dossier.DossierError:
        return None  # a draft outside content/drafts/ has no dossier path
    if not scope.is_file():
        return None
    for line in scope.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- genre:"):
            return stripped.split(":", 1)[1].strip() or None
    return None


def resolve_unit(draft: Path, override: str | None = None) -> tuple[str, str]:
    """The unit to measure `draft` at, and where that came from.

    Three sources, most specific first, because that is the order in
    which someone's intent gets more specific -- `style_check`'s policy,
    and for the same reason: the report must be able to say whether a
    draft was measured at its own recorded scale or at a fallback.
    """
    if override:
        return override, "--unit"
    genre = genre_of(draft)
    if genre in UNITS:
        return UNITS[genre], "scope.md"
    return FALLBACK_KIND, "nothing"


def _declaration(lines: list[str]) -> str | None:
    """The reason a drafter stated for this unit resting on one source."""
    for line in lines:
        found = _MARKER_RE.search(line)
        if found:
            return found.group(1) or None
    return None


def _prose(lines: list[str]) -> str:
    """A unit's lines as one string, markers removed.

    The removal is load-bearing rather than cosmetic. `synthesis`'s
    finding identity is keyed on this text, so leaving the marker in
    would mean *declaring* a single-source unit changed the name of the
    finding describing it -- and the declared/undeclared split would
    rename every finding it touched, which is what R2 exists to prevent.
    """
    stripped = (_MARKER_RE.sub("", line).strip() for line in lines)
    return " ".join(part for part in stripped if part)


def _citekeys(prose: str) -> tuple[str, ...]:
    return tuple(sorted({key for _, key in citation_gate.extract_citekeys(prose)}))


def blocks(lines: list[str], offset: int = 1) -> list[tuple[int, list[str]]]:
    """(first line number, the block's lines) per blank-line-separated block.

    Public because `citation_provenance._paragraph_spans` is the joined
    view of this same walk. Raw lines rather than joined text, because
    `synthesis` has to find a declaration marker among them before they
    are joined -- and joining is the cheaper of the two to add on top.
    """
    blocks: list[tuple[int, list[str]]] = []
    start, buffer = None, []
    for index, line in enumerate(lines, offset):
        if line.strip():
            start = index if start is None else start
            buffer.append(line)
        elif start is not None:
            blocks.append((start, buffer))
            start, buffer = None, []
    if start is not None:
        blocks.append((start, buffer))
    return blocks


def _paragraph(start: int, lines: list[str]) -> Unit | None:
    """One paragraph, or None for a block that is only a marker.

    A marker split off from its unit by a blank line becomes a block of
    its own, and counting it as an uncited unit would be worse than
    dropping it: the drafter's mistake would show up as prose that cites
    nothing rather than as a declaration that attached to nothing.
    """
    prose = _prose(lines)
    if not prose:
        return None
    return Unit("paragraph", start, prose, _citekeys(prose), _declaration(lines), 0)


def _longest_run(paragraphs: list[Unit]) -> int:
    """The longest run of consecutive paragraphs on the same single citekey.

    A paragraph citing nothing, and a paragraph citing two or more
    sources, both break a run -- the first because it is original prose
    and the second because it is exactly the fusion the rule asks for.
    """
    longest = current = 0
    previous = None
    for unit in paragraphs:
        key = unit.citekeys[0] if len(unit.citekeys) == 1 else None
        if key is None:
            current = 0
        else:
            current = current + 1 if key == previous else 1
        previous = key
        longest = max(longest, current)
    return longest


def _sections(lines: list[str]) -> list[tuple[int, list[str]]]:
    """(first line number, the section's lines) per heading-delimited section.

    Prose before the first heading is a section of its own, and a draft
    with no headings is one section -- both are the honest reading, and
    both keep every line of the draft inside exactly one unit.
    """
    sections: list[tuple[int, list[str]]] = []
    start, buffer = 1, []
    for index, line in enumerate(lines, 1):
        if _HEADING_RE.match(line) and buffer:
            sections.append((start, buffer))
            start, buffer = index, [line]
        elif buffer:
            buffer.append(line)
        elif line.strip():
            # Blank lines before the first section open nothing. Counting
            # them as a section of their own would file a draft that
            # happens to start with a blank line as having one more unit
            # than it has, every one of them uncited.
            start, buffer = index, [line]
    if buffer:
        sections.append((start, buffer))
    return sections


def _section(start: int, lines: list[str]) -> Unit:
    paragraphs = [p for p in
                  (_paragraph(at, block) for at, block in blocks(lines, start))
                  if p is not None]
    prose = _prose(lines)
    return Unit("section", start, prose, _citekeys(prose),
                _declaration(lines), _longest_run(paragraphs))


def units(text: str, kind: str) -> list[Unit]:
    """`text` split into units of `kind`.

    Fenced code and LaTeX verbatim are blanked first, by the same
    `citation_gate` helper `references.py` and `verbatim_check.py`
    already share. That is what keeps a `<!-- single-source: ... -->`
    inside a fenced block -- a textbook chapter demonstrating this very
    markup -- from being read as a declaration of the paragraph
    containing it.
    """
    if kind not in KINDS:
        raise ValueError(f"Unknown unit kind {kind!r}; expected one of {sorted(KINDS)}.")
    lines = citation_gate._blank_code(text).splitlines()
    if kind == "document":
        prose = _prose(lines)
        return [Unit("document", 1, prose, _citekeys(prose), _declaration(lines), 0)]
    if kind == "paragraph":
        found = (_paragraph(at, block) for at, block in blocks(lines))
        return [unit for unit in found if unit is not None]
    return [_section(at, block) for at, block in _sections(lines)]
