"""`math.md`'s `## Symbols`: what each mapped symbol means (#1143).

The mapping table above it stays the only source of a symbol's LaTeX;
this table only gives a mapped key a meaning, so a symbol is defined
once, in the dossier of the draft that typesets it:

    | Symbol | Meaning |
    | --- | --- |
    | `m_t`  | **Target moisture** |
    | `m_lo` | **Moisture thresholds**, lower |
    | `T_c`  | see 02-plant-demonstrator |
    | `e_q`  | quantisation error |

A bold term is a link to the glossary entry that defines it, optionally
followed by a note telling two symbols of one term apart; `see <unit>`
points at another unit's row for the same symbol; anything else is the
meaning in words. Resolving a link or a pointer needs the book and the
glossary parser, so that is `chitragupta/registry/_symbols.py`'s job:
this module only reads the table and reports what one draft can know.

It also owns the one reader of `scope.md`'s `## Glossary` section,
which `chitragupta/dossier/_glossary.py` calls. The glossary's spans use
mapping rows the way the draft's do, and this package may not import
`chitragupta/dossier/` (see `_math`'s docstring), while the dossier
package may import this one.

Imports `_math` and `_math_findings` only, one way.
"""

import re
from pathlib import Path
from typing import NamedTuple

from chitragupta.render_output._math import (
    MAPPING_FILENAME,
    SYMBOLS_SECTION_RE,
    _SPAN_RE,
    is_bare_symbol,
    mapping_path,
)
from chitragupta.render_output._math_findings import MathFinding

# A row: | `<symbol>` | <meaning> |. The meaning may hold `\|`.
_ROW_RE = re.compile(r"^\|\s*`(?P<symbol>[^`]+)`\s*\|(?P<meaning>(?:[^|\\\n]|\\.)*)\|\s*$", re.M)
_SEE_RE = re.compile(r"^see\s+(?P<unit>\S+)$")
_LINK_RE = re.compile(r"^\*\*(?P<term>[^*]+)\*\*(?:\s*,\s*(?P<note>.+))?$")

_GLOSSARY_HEADING = re.compile(r"^## Glossary[ \t]*$", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^## ", re.MULTILINE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# `dossier stamp`'s line inside `## Glossary`. The pattern's owner is
# `chitragupta/dossier/_draft_fingerprint._DRAFT_DIGEST_LINE`, which this
# package may not import: an all-digit digest is otherwise a quantity on
# some stamps and not others.
_DIGEST_LINE = re.compile(r"^-\s*draft digest:.*$", re.MULTILINE)
SCOPE_FILENAME = "scope.md"


class Meaning(NamedTuple):
    """One `## Symbols` row's meaning: `kind` is `link`, `see`, `text`
    or `malformed`; `text` the term, unit or words; `note` a link's
    note; `line` the row's line in `math.md`."""

    kind: str
    text: str
    note: str
    line: int


def has_symbols_section(text: str) -> bool:
    return SYMBOLS_SECTION_RE.search(text) is not None


def _meaning(cell: str, line: int) -> Meaning:
    cell = cell.replace("\\|", "|").strip()
    see, link = _SEE_RE.match(cell), _LINK_RE.match(cell)
    if see:
        return Meaning("see", see.group("unit"), "", line)
    if link:
        return Meaning("link", link.group("term").strip(), (link.group("note") or "").strip(), line)
    if not cell or cell.startswith("**"):
        return Meaning("malformed", cell, "", line)
    return Meaning("text", cell, "", line)


def load_symbols(text: str) -> "list[tuple[str, Meaning]]":
    """Every row of a `math.md`'s `## Symbols`, in file order; `[]`
    without one. Rows, not a dict, so a symbol written twice is seen."""
    section = SYMBOLS_SECTION_RE.search(text)
    if section is None:
        return []
    first = text.count("\n", 0, section.start()) + 1
    return [
        (
            row.group("symbol").strip(),
            _meaning(row.group("meaning"), first + section.group(0).count("\n", 0, row.start())),
        )
        for row in _ROW_RE.finditer(section.group(0))
    ]


def findings(rows: "list[tuple[str, str]]", text: str) -> "list[MathFinding]":
    """What `math.md`'s `text` says about meanings, given its mapping
    `rows`: a mapped symbol with none, a meaning with no mapping row, and
    a row that is empty, half bold or repeated."""
    symbols = load_symbols(text)
    mapped = dict(rows)
    found = _missing(mapped, {symbol for symbol, _ in symbols}, has_symbols_section(text))
    found += [
        MathFinding(
            "unmapped",
            f"`{symbol}` has a meaning in ## Symbols but no row in the mapping table, "
            "so it cannot be typeset",
        )
        for symbol, _ in symbols
        if symbol not in mapped
    ]
    return found + _malformed(symbols)


def _missing(mapped: "dict[str, str]", meant: "set[str]", has_section: bool):
    missing = [key for key in mapped if is_bare_symbol(key) and key not in meant]
    if missing and not has_section:
        return [
            MathFinding(
                "meaning",
                f"{MAPPING_FILENAME} has no ## Symbols: {len(missing)} mapped "
                + ("symbol has" if len(missing) == 1 else "symbols have")
                + " no meaning",
            )
        ]
    return [
        MathFinding(
            "meaning",
            f"`{key}` is mapped in {MAPPING_FILENAME} but has no meaning in its ## Symbols",
        )
        for key in missing
    ]


def _malformed(symbols: "list[tuple[str, Meaning]]") -> "list[MathFinding]":
    found = []
    for symbol, meaning in symbols:
        if meaning.kind == "malformed" and not meaning.text:
            found.append(MathFinding("malformed", f"`{symbol}` has a ## Symbols row with no meaning"))
        elif meaning.kind == "malformed":
            found.append(
                MathFinding(
                    "malformed",
                    f"`{symbol}`'s meaning `{meaning.text}` is half bold: a link is "
                    "**Term**, then an optional `, note`",
                )
            )
    counts: "dict[str, int]" = {}
    for symbol, _ in symbols:
        counts[symbol] = counts.get(symbol, 0) + 1
    found += [
        MathFinding("malformed", f"`{symbol}` has {count} ## Symbols rows")
        for symbol, count in counts.items()
        if count > 1
    ]
    return found


def glossary_section(text: str) -> "tuple[int, str] | None":
    """`(line of the heading, body)` of a `scope.md`'s `## Glossary`, or
    `None`; the body's first line is the line after the heading.

    HTML comments are blanked rather than removed, so line numbers stay
    the file's own: the template's worked example is in one.
    """
    text = _HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    heading = _GLOSSARY_HEADING.search(text)
    if not heading:
        return None
    end = _NEXT_HEADING.search(text, heading.end())
    first_line = text.count("\n", 0, heading.end()) + 1
    return first_line, text[heading.end() + 1 : end.start() if end else len(text)]


def glossary_spans(draft: Path) -> "frozenset[str]":
    """Every backticked span in `draft`'s glossary, which uses `math.md`
    rows the way the draft does; empty without one."""
    path = mapping_path(draft)
    scope = path.parent / SCOPE_FILENAME if path is not None else None
    if scope is None or not scope.is_file():
        return frozenset()
    section = glossary_section(scope.read_text(encoding="utf-8"))
    if section is None:
        return frozenset()
    body = _DIGEST_LINE.sub("", section[1])
    return frozenset(m.group("body").strip() for m in _SPAN_RE.finditer(body))
