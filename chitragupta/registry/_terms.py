"""The terminology registry's half of `registry build`/`check`: each
accepted unit's `scope.md` glossary, read into rows, and the two kinds
of finding those rows make possible (#1138).

The source is the dossier's `## Glossary`, not the prose: matching
definition lines in drafts found none in the real book. Parsing is
`dossier/_glossary.py`'s; symbols live in `registry/_symbols.py` (#1143).
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


def read_unit(unit_id: str, draft: Path, built: dict) -> None:
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
                "unit": unit_id,
                "line": entry.line,
                "definition": definition,
                # Converted per unit, so pages convert in one pandoc call.
                "markdown": _math.substitute(definition, mapping),
            }
        )
    for problem in _glossary.glossary_problems(draft):
        built["glossary"].append({"unit": unit_id, **problem._asdict()})


def _grouped(rows, key) -> "dict[str, list[dict]]":
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(key(row), []).append(row)
    return grouped


def units_counted(rows) -> str:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["unit"]] = counts.get(row["unit"], 0) + 1
    return ", ".join(f"{u} ({n}x)" if n > 1 else u for u, n in sorted(counts.items()))


def _term_findings(built: dict) -> "list[tuple[str, str]]":
    return [
        ("term", f"`{rows[0]['term']}` is defined more than once: {units_counted(rows)}")
        for rows in _grouped(built["terms"], lambda row: term_key(row["term"])).values()
        if len(rows) > 1
    ]


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
    # A hand-written preface has no dossier, so its missing glossary is no
    # finding; a term it *does* define is one, since its `\Cref` has no
    # chapter number to print (#1137).
    unnumbered = set(built.get("unnumbered", ()))
    missing = [
        ("glossary", f"{unit} has no ## Glossary in scope.md")
        for unit in built["no_glossary"]
        if unit not in unnumbered
    ]
    misplaced = [
        (
            "glossary",
            f"{row['unit']} is front or back matter, which LaTeX does not number, so a "
            "glossary definition's \\Cref to it prints no chapter: define "
            f"`{row['term']}` in a numbered chapter or appendix",
        )
        for row in built["terms"]
        if row["unit"] in unnumbered
    ]
    return missing + misplaced + problem_findings(built)


def findings(built: dict) -> "list[tuple[str, str]]":
    return _term_findings(built) + _glossary_findings(built)
