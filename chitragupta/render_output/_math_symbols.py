"""`math.md`'s `## Symbols`: what each mapped symbol means (#1143).

The mapping table stays the only source of a symbol's LaTeX; this table only
gives a mapped key a meaning:

    | Symbol | Meaning |
    | --- | --- |
    | `m_t`  | **Target moisture** |
    | `T_c`  | see 02-plant-demonstrator |
    | `e_q`  | quantisation error |

A bold term links to a glossary entry; `see <unit>` points to another unit's
row. Resolving those is `chitragupta/registry/_symbols.py`'s job. Also owns the
reader of `scope.md`'s `## Glossary`, since this package may not import
`chitragupta/dossier/` but the reverse is allowed.
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
# A table line that is a separator, `|---|---|`, or the header above one.
_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|\s*$")

_GLOSSARY_HEADING = re.compile(r"^## Glossary[ \t]*$", re.MULTILINE)
_NEXT_HEADING = re.compile(r"^## ", re.MULTILINE)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# `dossier stamp`'s line inside `## Glossary`, owned by
# `dossier/_draft_fingerprint._DRAFT_DIGEST_LINE`, which this package may not import.
_DIGEST_LINE = re.compile(r"^-\s*draft digest:.*$", re.MULTILINE)
SCOPE_FILENAME = "scope.md"


class Meaning(NamedTuple):
    """One `## Symbols` row's meaning: `kind` is `link`, `see`, `text` or `malformed`."""

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
    """Every `## Symbols` row in file order; a list so a duplicate is seen."""
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
    """Missing meanings, meanings without a mapping row, and empty, half-bold
    or repeated rows."""
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
    return found + _malformed(symbols) + _stray(text)


def _stray(text: str) -> "list[MathFinding]":
    """A non-row line under `## Symbols`, which would otherwise drop its meaning silently."""
    section = SYMBOLS_SECTION_RE.search(text)
    lines = section.group(0).splitlines() if section else []
    found = []
    for i, line in enumerate(lines):
        header = i + 1 < len(lines) and _SEPARATOR_RE.match(lines[i + 1])
        if line.startswith("|") and not (header or _SEPARATOR_RE.match(line)):
            if not _ROW_RE.match(line):
                found.append(
                    MathFinding(
                        "malformed",
                        f"`{line.strip()}` under ## Symbols is not a | `symbol` | meaning | row",
                    )
                )
    return found


def _missing(mapped: "dict[str, str]", meant: "set[str]", has_section: bool) -> "list[MathFinding]":
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
            found.append(
                MathFinding("malformed", f"`{symbol}` has a ## Symbols row with no meaning")
            )
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
    """`(line of the heading, body)` of a `scope.md`'s `## Glossary`, or `None`.

    HTML comments are blanked, not removed, so line numbers stay the file's own.
    """
    text = _HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    heading = _GLOSSARY_HEADING.search(text)
    if not heading:
        return None
    end = _NEXT_HEADING.search(text, heading.end())
    first_line = text.count("\n", 0, heading.end()) + 1
    return first_line, text[heading.end() + 1 : end.start() if end else len(text)]


def glossary_spans(draft: Path) -> "frozenset[str]":
    """Every backticked span in `draft`'s glossary; empty without one."""
    path = mapping_path(draft)
    scope = path.parent / SCOPE_FILENAME if path is not None else None
    if scope is None or not scope.is_file():
        return frozenset()
    section = glossary_section(scope.read_text(encoding="utf-8"))
    if section is None:
        return frozenset()
    body = _DIGEST_LINE.sub("", section[1])
    return frozenset(m.group("body").strip() for m in _SPAN_RE.finditer(body))
