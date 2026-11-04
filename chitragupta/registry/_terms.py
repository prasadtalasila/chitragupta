"""The terminology registry's half of `registry build`/`check`: each
accepted unit's `scope.md` glossary, read into rows, and the three kinds
of finding those rows make possible (#1138).

The source is the dossier's `## Glossary`, not the unit's prose. Before
#1138 this registry matched `- **Term** -- definition` lines in the
draft, and the one real book it was measured on held none, so it was
empty; the glossary is where every genre skill already pins its terms.
Parsing is chitragupta/dossier/_glossary.py's, shared with the acronym
checks.

Split from chitragupta/registry/__init__.py, which holds the claim and
cross-reference halves, to keep both under docs/CODE-STANDARDS.md's C2
limit.
"""

import re
from pathlib import Path

from chitragupta.dossier import DossierError, _glossary
from chitragupta.render_output import _math

# One trailing parenthetical that is not a symbol: `Digital twin (DT)`
# and `digital twin` name one term.
_TRAILING_ABBREVIATION = re.compile(r"\s*\([^`()]*\)$")


def term_key(term: str) -> str:
    """What makes two glossary terms one term: lowercased, spacing
    collapsed, one trailing abbreviation dropped."""
    return " ".join(_TRAILING_ABBREVIATION.sub("", term).lower().split())


def _kind(entry) -> str:
    """`notation` for an entry that is only a symbol, the distinction the
    registry has drawn since #138. A term written as `$...$` maths is a
    `[glossary]` problem instead: it has no symbol to typeset."""
    return "notation" if entry.name is None else "term"


def read_unit(unit_id: str, draft: Path, built: dict) -> None:
    """Fold one accepted unit's glossary into `built`."""
    try:
        has_glossary = _glossary.has_glossary(draft)
    except DossierError:
        # A unit outside content/drafts/ has no dossier to read.
        has_glossary = False
    if not has_glossary:
        built["no_glossary"].append(unit_id)
        return
    mapping = _math.load_mapping(draft)
    for entry in _glossary.glossary_entries(draft):
        definition = " ".join(entry.definition.split())
        built["terms"].append(
            {
                "term": entry.term,
                "symbol": entry.symbol,
                "kind": _kind(entry),
                "unit": unit_id,
                "line": entry.line,
                "definition": definition,
                "typeset": mapping.get(entry.symbol) if entry.symbol else None,
                # The unit's own math.md applied here, per unit, so the
                # pages can convert a whole book in one pandoc call.
                "markdown": _math.substitute(definition, mapping),
                "symbol_markdown": _math.substitute(f"`{entry.symbol}`", mapping)
                if entry.symbol
                else None,
            }
        )
    for problem in _glossary.glossary_problems(draft):
        built["glossary"].append({"unit": unit_id, **problem._asdict()})


def _grouped(rows, key) -> "dict[str, list[dict]]":
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(key(row), []).append(row)
    return grouped


def _units(rows) -> str:
    """`a, b (2x)`: each unit once, with a count where it repeats."""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["unit"]] = counts.get(row["unit"], 0) + 1
    return ", ".join(f"{u} ({n}x)" if n > 1 else u for u, n in sorted(counts.items()))


def meaning(row: dict) -> str:
    """What a symbol stands for: its term, or for a bare symbol its
    definition."""
    return term_key(row["term"]) if row["kind"] == "term" else row["definition"].lower()


def _term_findings(built: dict) -> "list[tuple[str, str]]":
    named = [row for row in built["terms"] if row["kind"] == "term"]
    return [
        ("term", f"`{rows[0]['term']}` is defined more than once: {_units(rows)}")
        for rows in _grouped(named, lambda row: term_key(row["term"])).values()
        if len(rows) > 1
    ]


def _notation_findings(built: dict) -> "list[tuple[str, str]]":
    found = []
    with_symbol = [row for row in built["terms"] if row["symbol"]]
    for symbol, rows in _grouped(with_symbol, lambda row: row["symbol"]).items():
        meanings = _grouped(rows, meaning)
        if len({row["unit"] for row in rows}) > 1 and len(meanings) > 1:
            listed = "; ".join(f"{m} ({_units(r)})" for m, r in meanings.items())
            found.append(("notation", f"`{symbol}` names different things: {listed}"))
        typesets = _grouped(rows, lambda row: row["typeset"] or row["symbol"])
        if len(typesets) > 1:
            listed = "; ".join(f"{t} ({_units(r)})" for t, r in typesets.items())
            found.append(("notation", f"`{symbol}` is typeset differently: {listed}"))
    return found


def problem_findings(built: dict) -> "list[tuple[str, str]]":
    """One `[glossary]` finding per bullet the pages cannot print: what
    `registry build --glossary`/`--notation` refuses on."""
    return [
        (
            "glossary",
            f"{problem['unit']} scope.md:{problem['line']} `{problem['text']}` "
            f"-- {problem['reason']}",
        )
        for problem in built["glossary"]
    ]


def _glossary_findings(built: dict) -> "list[tuple[str, str]]":
    missing = [
        ("glossary", f"{unit} has no ## Glossary in scope.md") for unit in built["no_glossary"]
    ]
    return missing + problem_findings(built)


def findings(built: dict) -> "list[tuple[str, str]]":
    """`[term]`, `[notation]` and `[glossary]` findings, in that order."""
    return _term_findings(built) + _notation_findings(built) + _glossary_findings(built)
