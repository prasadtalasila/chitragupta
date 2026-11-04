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
from chitragupta.dossier import SCOPE_MD, DossierError, dossier_dir
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
    try:
        scope = dossier_dir(draft) / SCOPE_MD
    except DossierError:
        # A draft outside content/drafts/ has no dossier to read.
        return None
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


def _bullets(draft: Path) -> "list[tuple[int, str]]":
    """`(line, text)` of every bullet at the margin, continuation lines
    included."""
    section = _section(draft)
    if section is None:
        return []
    first_line, body = section
    found: list[tuple[int, list[str]]] = []
    in_bullet = False
    for offset, line in enumerate(body.splitlines()):
        # `dossier stamp` appends its digest line at the end of a scope.md
        # that predates the field, which is inside `## Glossary`, the last
        # section: metadata, not a term.
        if _DRAFT_DIGEST_LINE.match(line):
            in_bullet = False
        elif _BULLET.match(line):
            found.append((first_line + offset + 1, [line]))
            in_bullet = True
        elif in_bullet and line[:1].isspace() and line.strip():
            found[-1][1].append(line)
        else:
            in_bullet = False
    return [(line, "\n".join(lines)) for line, lines in found]


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
    entries = (_entry(line, text) for line, text in _bullets(draft))
    return [entry for entry in entries if entry is not None and entry.definition]


def glossary_problems(draft: Path) -> "list[Problem]":
    """Every bullet the book's glossary cannot print, with the reason."""
    problems = []
    for line, text in _bullets(draft):
        entry = _entry(line, text)
        if entry is None:
            reason = _SHAPE
        elif not entry.definition:
            reason = "has no definition"
        elif _SECOND_TERM.search(entry.definition):
            reason = "defines a second term; one term per bullet"
        elif extract_citekeys_from_line(" ".join(entry.definition.split())):
            reason = "holds a citekey; a glossary never cites, the chapter does"
        else:
            continue
        problems.append(Problem(line, text.splitlines()[0], reason))
    return problems


def glossary_terms(draft: Path) -> dict[str, str]:
    """Recorded `term -> definition` pairs from the draft's `## Glossary`.

    `{}` if there's no dossier yet, no `## Glossary` heading, or no
    bullet in the recognised shape -- never an error. A term defined
    twice keeps its last definition: the dict view the acronym checks
    were written against. `glossary_entries()` keeps every one.
    """
    return {entry.term: entry.definition for entry in glossary_entries(draft)}
