"""A draft's `## Glossary` in `scope.md`: its entries, the symbol each one
names, and the bullets that are not in the shape.

Split out of chitragupta/dossier/_citekeys.py (#1138), which was at its
C2 line limit. Three readers share this one parser rather than each
keeping a regex: chitragupta/dossier/_acronyms.py and
chitragupta/style_acronym_drift.py through `glossary_terms()`, and the
book's terminology registry, glossary and list of symbols
(chitragupta/registry/) through `glossary_entries()` and
`glossary_problems()`.

The shape, which `dossier init`'s template shows by example:

    - **Term** -- definition
    - **Term** (`symbol`) -- definition
    - **`symbol`** -- definition

plus, read for compatibility, the symbol inside the bold:
``- **Baseline (`M_0`)** -- ...``. A bullet is `-`, `*` or `+` at the
margin; its definition is the rest of that line and every following line
indented by at least one space, and it ends at a blank line or a line at
the margin. So an off-format bullet is never read as part of the
definition above it, which the earlier match-to-the-next-match reading
did.

**What `glossary_problems()` cannot see**, stated rather than implied: a
qualifier inside a well-formed bold term ("**Digital twin (DT), working
definition for Part I** -- ...") and a well-formed definition that reads
"as before". Both are text, and the person reading the generated page is
what catches them.
"""

import re
from pathlib import Path
from typing import NamedTuple

from chitragupta.citation_gate import extract_citekeys_from_line
from chitragupta.dossier import SCOPE_MD, dossier_dir
from chitragupta.dossier._draft_fingerprint import _DRAFT_DIGEST_LINE

_GLOSSARY_HEADING = re.compile(r"^## Glossary[ \t]*$", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^## ", re.MULTILINE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# Every bullet the pre-#1138 pattern matched still matches: the symbol
# group is optional and sits between the bold and the ` -- `. Also used
# line by line by chitragupta/registry/__init__.py's `_prose()`.
_GLOSSARY_TERM = re.compile(
    r"^-\s*\*\*(?P<term>[^*]+)\*\*(?:\s*\(`(?P<symbol>[^`]+)`\))?\s*--\s*", re.MULTILINE
)

# A bold term ending in a backticked parenthetical: the compatible
# spelling of a symbol, `**Baseline (`M_0`)**`.
_BOLD_SYMBOL = re.compile(r"^(?P<name>.*?)\s*\(`(?P<symbol>[^`]+)`\)$")

_BULLET = re.compile(r"^[-*+]\s")

# A bold phrase followed by a separator inside a definition: a second
# term defined in the same bullet, which is what several terms written in
# one bullet become once only the first separator is fixed. Bold that
# defines nothing ("the chapter says **actual twin**, borrowed") passes.
_SECOND_TERM = re.compile(r"\*\*[^*]+\*\*(?:\s*\(`[^`]+`\))?\s*(?:--|:)")

_SHAPE = "not in the `- **Term** -- definition` shape"


class Entry(NamedTuple):
    """One glossary bullet. `term` is the bold text minus any symbol;
    `name` is `None` for a bullet that is only a symbol."""

    term: str
    symbol: "str | None"
    definition: str
    line: int

    @property
    def name(self) -> "str | None":
        return None if self.term.startswith("`") else self.term


class Problem(NamedTuple):
    line: int
    text: str
    reason: str


def _section(draft: Path) -> "tuple[int, str] | None":
    """`(line of the first body line, body)` of `## Glossary`, or `None`.

    HTML comments are blanked rather than removed, so line numbers stay
    the file's own: the template's worked example is in one.
    """
    scope = dossier_dir(draft) / SCOPE_MD
    if not scope.is_file():
        return None
    text = _HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), scope.read_text("utf-8"))
    heading = _GLOSSARY_HEADING.search(text)
    if not heading:
        return None
    end = _NEXT_HEADING.search(text, heading.end())
    first_line = text.count("\n", 0, heading.end()) + 1
    return first_line, text[heading.end() + 1 : end.start() if end else len(text)]


def has_glossary(draft: Path) -> bool:
    """Whether `draft`'s `scope.md` has a `## Glossary` at all."""
    return _section(draft) is not None


class _Bullet(NamedTuple):
    line: int
    text: str
    # A non-blank line at the margin straight after the bullet: valid
    # Markdown (lazy continuation), and a definition this parser would
    # otherwise cut off at its first line without saying so.
    lazy: bool


def _bullets(draft: Path) -> "list[_Bullet]":
    """Every bullet at the margin, continuation lines included."""
    section = _section(draft)
    if section is None:
        return []
    first_line, body = section
    found: list[list] = []
    in_bullet = False
    for offset, line in enumerate(body.splitlines()):
        # `dossier stamp` appends its digest line at the end of a scope.md
        # that predates the field, which is inside `## Glossary`, the last
        # section: metadata, not a term.
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


def _entry(line: int, text: str) -> "Entry | None":
    match = _GLOSSARY_TERM.match(text)
    if match is None:
        return None
    term, symbol = match.group("term").strip(), match.group("symbol")
    inner = _BOLD_SYMBOL.match(term)
    if symbol is None and inner:
        term, symbol = inner.group("name"), inner.group("symbol")
    if symbol is None and term.startswith("`") and term.endswith("`"):
        symbol = term.strip("`")
    return Entry(term, symbol, text[match.end() :].strip(), line)


def glossary_entries(draft: Path) -> "list[Entry]":
    """Every well-formed bullet with a definition, in file order."""
    entries = (_entry(bullet.line, bullet.text) for bullet in _bullets(draft))
    return [entry for entry in entries if entry is not None and entry.definition]


def _reason(bullet: _Bullet) -> "str | None":
    """Why `bullet` cannot be printed, or `None` if it can."""
    entry = _entry(bullet.line, bullet.text)
    if bullet.text[:1] != "-":
        return "a glossary bullet starts with `-`"
    if entry is None:
        return _SHAPE
    if entry.term[:1] == "$":
        return "write a symbol in backticks, `- **`x`** -- ...`, not as maths"
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
    """Every bullet the book's glossary cannot print, with the reason."""
    problems = []
    for bullet in _bullets(draft):
        reason = _reason(bullet)
        if reason is not None:
            problems.append(Problem(bullet.line, bullet.text.splitlines()[0], reason))
    return problems


def glossary_terms(draft: Path) -> dict[str, str]:
    """Recorded `term -> definition` pairs from the draft's `## Glossary`.

    `{}` if there's no dossier yet, no `## Glossary` heading, or no
    bullet in the recognised shape. Raises `DossierError` for a draft
    outside `content/drafts/`, as it always has. A term defined
    twice keeps its last definition: the dict view the acronym checks
    were written against. `glossary_entries()` keeps every one.
    """
    return {entry.term: entry.definition for entry in glossary_entries(draft)}
