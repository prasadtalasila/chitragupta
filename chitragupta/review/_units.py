"""What a "unit" is, per genre -- the scale the multi-source rule binds at.

`docs/WRITING-STANDARDS.md` §11: a unit cites two or more citekeys where
the evidence allows, and a single-source unit is a stated choice. Genres
differ in the unit, not the rule: a paragraph everywhere would damage
three genres' prose or exempt them (`plans/b2-multi-source-synthesis.md`).

A section has two scales: spread alone cannot tell a fused section from
one citing two papers in turn, so `Unit.longest_run` counts consecutive
paragraphs on one citekey, making `textbook-chapter-writer` step 4
observable.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from chitragupta import _code_regions, citation_gate, dossier

# The genre-to-unit table, the whole per-genre policy. Keyed by `dossier
# init --genre`'s scope.md value; tests/test_review_units.py pins it to
# `dossier.GENRES` so a new genre cannot silently fall back.
UNITS = {
    "survey": "paragraph",
    "thesis-chapter": "paragraph",
    "deep-research": "paragraph",
    "textbook-chapter": "section",
    "tutorial": "document",
    # A digest braids one-source runs into paragraphs, as a survey (#1172).
    "digest": "paragraph",
    # Related work fuses sources as a thesis chapter's does (plans/1179-research-paper-genre.md).
    "research-paper": "paragraph",
}

KINDS = ("paragraph", "section", "document")

# Whether uncited prose is exceptional in a genre (a finding every time) or
# ordinary. Keyed and pinned like UNITS (tests/test_review_uncited.py).
# §11: a tutorial body cites nothing by design and a textbook chapter is
# not citation-dense; measured, `book-chapter.md` yields 81 uncited
# sentences, none actionable. `synthesis.single_source_pct` excludes the
# same two genres.
UNCITED_PROSE = {
    "survey": "exceptional",
    "thesis-chapter": "exceptional",
    "deep-research": "exceptional",
    "textbook-chapter": "ordinary",
    "tutorial": "ordinary",
    # The `digest` aid judges a digest's own sentences (#991, #1172).
    "digest": "ordinary",
    # Design and evaluation describe the author's own software, uncited by design.
    "research-paper": "ordinary",
}

STANDINGS = ("exceptional", "ordinary")

# Unknown genre gets the strict reading, deliberately unlike FALLBACK_KIND:
# a wrong scale is a visible wrong number, but no findings reads as an
# answer, so the fallback that speaks is the safer.
FALLBACK_STANDING = "exceptional"

# Unknown genre is measured at the paragraph rather than refused: a wrong
# scale, said so, beats not running; `resolve_unit` names the source.
FALLBACK_KIND = "paragraph"

# No `@` and no `\cite` in the marker, so a reason naming the citekey
# cannot be read as a citation and inflate the count it explains.
_MARKER_RE = re.compile(r"(?:<!--|%)\s*single-source:\s*(.*?)\s*(?:-->|$)")

# A section opens at a heading, in either markup (not at a table row).
_HEADING_RE = re.compile(r"^\s*(?:#{1,6}\s|\\(?:chapter|(?:sub){0,2}section|paragraph)\*?\{)")


@dataclass(frozen=True)
class Unit:
    """One unit of a draft, at whatever scale its genre binds at.
    `text` is marker-stripped (see `_prose`); `longest_run` is 0 for every
    kind but `section`.
    """

    kind: str
    line: int
    text: str
    citekeys: tuple[str, ...]
    declared: str | None
    longest_run: int


def genre_of(draft: Path) -> str | None:
    """The genre recorded in this draft's dossier `scope.md`, or None for
    no dossier, no `- genre:` line or an empty value, all measured at the
    fallback and named. Mirrors `style_language.language_of`.
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
    """The unit to measure `draft` at, and where that came from, most
    specific source first, so the report can say whether a fallback won.
    """
    if override:
        return override, "--unit"
    genre = genre_of(draft)
    if genre in UNITS:
        return UNITS[genre], "scope.md"
    return FALLBACK_KIND, "nothing"


def resolve_standing(draft: Path, override: str | None = None) -> tuple[str, str | None, str]:
    """How `draft`'s genre treats uncited prose, the genre, and where it
    came from, in `resolve_unit`'s order. The genre travels even when an
    override won: strict reading of a recorded tutorial is worth naming.
    """
    if override:
        return UNCITED_PROSE[override], override, "--genre"
    genre = genre_of(draft)
    if genre in UNCITED_PROSE:
        return UNCITED_PROSE[genre], genre, "scope.md"
    return FALLBACK_STANDING, genre, "nothing"


# A Markdown image on a line of its own: `![caption](path)`.
_IMAGE = re.compile(r"^\s*!\[.*\]\([^)]*\)\s*$")


def _declaration(lines: list[str]) -> str | None:
    for line in lines:
        found = _MARKER_RE.search(line)
        if found:
            return found.group(1) or None
    return None


def _prose(lines: list[str]) -> str:
    """A unit's lines as one string, markers removed: `synthesis` keys
    finding identity on this text, so declaring a unit single-source must
    not rename its finding (R2).
    """
    stripped = (_MARKER_RE.sub("", line).strip() for line in lines)
    return " ".join(part for part in stripped if part)


def _citekeys(lines: list[str], prose: str, latex: bool) -> tuple[str, ...]:
    # LaTeX reads the unjoined lines: a `%` comment ends at its newline, and
    # in `prose` it would run on through every line joined after it.
    text = "\n".join(lines) if latex else prose
    return tuple(sorted({key for _, key in citation_gate.extract_citekeys(text, latex=latex)}))


def blocks(lines: list[str], offset: int = 1) -> list[tuple[int, list[str]]]:
    """(first line number, the block's lines) per blank-line-separated block.
    Raw lines, since `synthesis` finds a declaration marker before joining.
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


def _paragraph(start: int, lines: list[str], latex: bool) -> Unit | None:
    """One paragraph, or None for a block that is only a marker or an image.

    A marker split off by a blank line is dropped, not counted as uncited
    prose. An image line is a figure (#1172): a digest's figure captions
    cite one source by construction.
    """
    prose = _prose(lines)
    if not prose or all(_IMAGE.match(line) for line in lines if line.strip()):
        return None
    return Unit("paragraph", start, prose, _citekeys(lines, prose, latex), _declaration(lines), 0)


def _longest_run(paragraphs: list[Unit]) -> int:
    """The longest run of consecutive paragraphs on the same single citekey;
    uncited and multi-source paragraphs both break it.
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
    Prose before the first heading is its own section, so every line sits
    in exactly one unit.
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
            # Leading blank lines open no extra, uncited section.
            start, buffer = index, [line]
    if buffer:
        sections.append((start, buffer))
    return sections


def _section(start: int, lines: list[str], latex: bool) -> Unit:
    found = (_paragraph(at, block, latex) for at, block in blocks(lines, start))
    paragraphs = [p for p in found if p is not None]
    prose = _prose(lines)
    citekeys = _citekeys(lines, prose, latex)
    return Unit("section", start, prose, citekeys, _declaration(lines), _longest_run(paragraphs))


def units(text: str, kind: str, *, latex: bool = False) -> list[Unit]:
    """`text` split into units of `kind`. Code and LaTeX verbatim are
    blanked first (`citation_gate`), so a fenced example of the
    single-source marker declares nothing.
    """
    if kind not in KINDS:
        raise ValueError(f"Unknown unit kind {kind!r}; expected one of {sorted(KINDS)}.")
    # LaTeX pre-blanks verbatim only: Markdown's rules would read a
    # backtick quote as code, and `%` stays for `_declaration`'s markers.
    blanked = _code_regions.blank_latex_verbatim(text) if latex else citation_gate._blank_code(text)
    lines = blanked.splitlines()
    if kind == "document":
        prose = _prose(lines)
        return [Unit("document", 1, prose, _citekeys(lines, prose, latex), _declaration(lines), 0)]
    if kind == "paragraph":
        found = (_paragraph(at, block, latex) for at, block in blocks(lines))
        return [unit for unit in found if unit is not None]
    return [_section(at, block, latex) for at, block in _sections(lines)]
