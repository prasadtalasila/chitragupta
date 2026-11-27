"""A draft's `## Glossary` in `scope.md`: its entries, and the bullets
that are not in the shape.

The one parser shared by the acronym checks (`glossary_terms()`) and
the book registries (`glossary_entries()`, `glossary_problems()`). The
shape is `- **Term** -- definition`. Symbols moved to `math.md`'s
`## Symbols` (#1143); the old spellings are still recognised so each
problem names the row to write instead. A definition continues on
indented lines and ends at a blank or margin line, so an off-format
bullet is never read into the definition above it. Not detectable: a
qualifier inside a well-formed bold term, or a definition reading "as
before".
"""

import re
from pathlib import Path
from typing import NamedTuple

from chitragupta.citation_gate import extract_citekeys_from_line
from chitragupta.dossier import SCOPE_MD, dossier_dir
from chitragupta.dossier._draft_fingerprint import _DRAFT_DIGEST_LINE
from chitragupta.render_output._math_symbols import glossary_section

# The symbol group stays optional after #1143 so a retired slot can be
# reported with its replacement, and so registry's `_prose()` still drops
# every definition bullet.
_GLOSSARY_TERM = re.compile(
    r"^-\s*\*\*(?P<term>[^*]+)\*\*(?:\s*\(`(?P<symbol>[^`]+)`\))?\s*--\s*", re.MULTILINE
)

# The other retired symbol spelling: a backticked parenthetical in bold.
_BOLD_SYMBOL = re.compile(r"^(?P<name>.*?)\s*\(`(?P<symbol>[^`]+)`\)$")

_BULLET = re.compile(r"^[-*+]\s")

# A bold phrase followed by a separator inside a definition: a second
# term in the same bullet. Bold that defines nothing passes.
_SECOND_TERM = re.compile(r"\*\*[^*]+\*\*(?:\s*\(`[^`]+`\))?\s*(?:--|:)")

_SHAPE = "not in the `- **Term** -- definition` shape"


class Entry(NamedTuple):
    """One glossary bullet: the bold term (minus a retired symbol slot),
    its definition and its line in `scope.md`."""

    term: str
    definition: str
    line: int


class _Parsed(NamedTuple):
    entry: Entry
    # A retired spelling's symbol, kept only to name its replacement row.
    symbol: "str | None"


class Problem(NamedTuple):
    line: int
    text: str
    reason: str


def _section(draft: Path) -> "tuple[int, str] | None":
    """`(line of the heading, body)` of `## Glossary`, or `None`.

    Shares `render_output._math_symbols`' section reader, so `render`
    counts the same spans.
    """
    scope = dossier_dir(draft) / SCOPE_MD
    if not scope.is_file():
        return None
    return glossary_section(scope.read_text("utf-8"))


def has_glossary(draft: Path) -> bool:
    return _section(draft) is not None


class _Bullet(NamedTuple):
    line: int
    text: str
    # A lazy continuation at the margin: valid Markdown that would
    # otherwise silently cut the definition at its first line.
    lazy: bool


def _bullets(draft: Path) -> "list[_Bullet]":
    section = _section(draft)
    if section is None:
        return []
    first_line, body = section
    found: list[list] = []
    in_bullet = False
    for offset, line in enumerate(body.splitlines()):
        # `dossier stamp` may append its digest line inside `## Glossary`,
        # the last section: metadata, not a term.
        if _DRAFT_DIGEST_LINE.match(line) or not line.strip():
            in_bullet = False
        elif _BULLET.match(line):
            found.append([first_line + offset + 1, [line], False])
            in_bullet = True
        elif in_bullet and line[:1].isspace():
            found[-1][1].append(line)
        elif in_bullet:
            found[-1][2] = True
            in_bullet = False
    return [_Bullet(line, "\n".join(lines), lazy) for line, lines, lazy in found]


def _parse(line: int, text: str) -> "_Parsed | None":
    match = _GLOSSARY_TERM.match(text)
    if match is None:
        return None
    term, symbol = match.group("term").strip(), match.group("symbol")
    inner = _BOLD_SYMBOL.match(term)
    if symbol is None and inner:
        term, symbol = inner.group("name"), inner.group("symbol")
    if symbol is None and term.startswith("`") and term.endswith("`"):
        symbol = term.strip("`")
    return _Parsed(Entry(term, text[match.end() :].strip(), line), symbol)


def _is_symbol_only(parsed: _Parsed) -> bool:
    return parsed.entry.term.startswith("`")


def glossary_entries(draft: Path) -> "list[Entry]":
    """Every term bullet with a definition, in file order. A bullet that
    is only a symbol names no term, so it is a problem and not here."""
    parsed = (_parse(bullet.line, bullet.text) for bullet in _bullets(draft))
    return [
        found.entry
        for found in parsed
        if found is not None and found.entry.definition and not _is_symbol_only(found)
    ]


def _retired(parsed: _Parsed) -> str:
    """The `## Symbols` row a retired symbol spelling becomes (#1143)."""
    if _is_symbol_only(parsed):
        row = f"| `{parsed.symbol}` | <its meaning in words> |"
        return f"symbols live in math.md now: add {row} under its ## Symbols and drop this bullet"
    row = f"| `{parsed.symbol}` | **{parsed.entry.term}** |"
    return f"symbols live in math.md now: add {row} under its ## Symbols and drop the symbol here"


def _reason(bullet: _Bullet) -> "str | None":
    parsed = _parse(bullet.line, bullet.text)
    if bullet.text[:1] != "-":
        return "a glossary bullet starts with `-`"
    if parsed is None:
        return _SHAPE
    entry = parsed.entry
    if entry.term[:1] == "$":
        return "a symbol is not a glossary term: give it a row in math.md's ## Symbols"
    if parsed.symbol is not None:
        return _retired(parsed)
    if not entry.definition:
        return "has no definition"
    if bullet.lazy:
        return "continues at the margin; indent the wrapped line"
    if _SECOND_TERM.search(entry.definition):
        return "defines a second term; one term per bullet"
    if extract_citekeys_from_line(" ".join(entry.definition.split())):
        return "holds a citekey; a glossary never cites, the chapter does"
    return None


def glossary_problems(draft: Path) -> "list[Problem]":
    problems = []
    for bullet in _bullets(draft):
        reason = _reason(bullet)
        if reason is not None:
            problems.append(Problem(bullet.line, bullet.text.splitlines()[0], reason))
    return problems


def glossary_terms(draft: Path) -> dict[str, str]:
    """Recorded `term -> definition` pairs from the draft's `## Glossary`.

    `{}` with no dossier, heading or well-shaped bullet; raises
    `DossierError` outside `content/drafts/`. A term defined twice keeps
    its last definition; `glossary_entries()` keeps every one.
    """
    return {entry.term: entry.definition for entry in glossary_entries(draft)}
