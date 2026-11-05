"""The notation half of the terminology registry: each accepted unit's
`math.md` `## Symbols`, resolved across the book (#1143).

A symbol's meaning lives in the `math.md` of the unit that typesets it
(`chitragupta/render_output/_math_symbols.py` reads the table). Here the
book resolves what one draft cannot: a bold link to the glossary term it
names, in any accepted unit, and a `see <unit>` pointer to that unit's
row for the same symbol. Every row then has a *meaning key* -- the
linked term's `term_key` or the words, plus the note -- which both the
`[notation]` findings and the List of Symbols group by, so the check and
the page cannot disagree.

Also here, not in `render_output/_math_findings.py`: the glossary-maths
finding, a glossary span the shape rules call mathematics that has no
row in its own unit's mapping and so prints as code. Rows are never
borrowed from another unit.
"""

from pathlib import Path

from chitragupta.registry._terms import term_key, units_counted
from chitragupta.render_output import _math, _math_symbols
from chitragupta.render_output._math_shapes import rule_for

# The `render` findings that also stop `registry build --notation`: a
# symbol that would print as code, and a row whose meaning is undefined.
_BLOCKING_KINDS = frozenset({"unmapped", "malformed"})


def read_unit(unit_id: str, draft: Path, built: dict) -> None:
    """Fold one accepted unit's `## Symbols`, its `math.md` findings and
    its glossary's unmapped maths into `built`."""
    text = _math.mapping_text(draft)
    rows = _math.mapping_rows(text)
    mapping = dict(rows)
    for symbol, meaning in _math_symbols.load_symbols(text):
        built["symbols"].append(_row(unit_id, symbol, meaning, mapping))
    if text:
        for finding in _math_symbols.findings(rows, text):
            built["math"].append({"unit": unit_id, **finding._asdict()})
    not_math = _math.not_math(text)
    names = _math._symbols_of(mapping)
    for span in sorted(_math_symbols.glossary_spans(draft) - set(mapping) - not_math):
        rule = rule_for(span, names, True)
        if rule is not None and not _math._CITEKEY_RE.match(span):
            built["glossary_maths"].append({"unit": unit_id, "span": span, "rule": rule})


def _row(unit_id: str, symbol: str, meaning, mapping: "dict[str, str]") -> dict:
    return {
        "symbol": symbol,
        "unit": unit_id,
        "kind": meaning.kind,
        "text": meaning.text,
        "note": meaning.note,
        "line": meaning.line,
        "typeset": mapping.get(symbol),
        # The unit's own mapping applied here, per unit, as `_terms` does
        # for definitions, so the pages convert a whole book in one call.
        "symbol_markdown": _math.substitute(f"`{symbol}`", mapping),
        "note_markdown": _math.substitute(meaning.note, mapping),
        "text_markdown": _math.substitute(meaning.text, mapping),
    }


def _defined_terms(built: dict) -> "dict[str, str]":
    """`term_key` -> the term as the first unit in outline order spells it."""
    spelled: dict[str, str] = {}
    for row in built["terms"]:
        spelled.setdefault(term_key(row["term"]), row["term"])
    return spelled


def resolve(built: dict) -> "list[tuple[str, str]]":
    """Give every resolvable `## Symbols` row its `key` and `label`, and
    return a `[notation]` finding for each one that does not resolve.

    Run once, by `registry.build`, after every unit is read: a link may
    name a term a later unit defines."""
    spelled = _defined_terms(built)
    problems = []
    for row in built["symbols"]:
        if row["kind"] == "link":
            if term_key(row["text"]) not in spelled:
                problems.append(_unresolved_link(row))
                continue
            key = term_key(row["text"])
            note = f", {row['note_markdown']}" if row["note"] else ""
            _settle(row, f"{key}|{row['note'].lower()}", spelled[key] + note)
        elif row["kind"] == "text":
            _settle(row, f"{row['text'].lower()}|", row["text_markdown"])
    by_place = {(row["unit"], row["symbol"]): row for row in built["symbols"]}
    for row in built["symbols"]:
        if row["kind"] == "see":
            problem = _pointer_problem(row, by_place.get((row["text"], row["symbol"])), built)
            if problem:
                problems.append(problem)
            else:
                target = by_place[(row["text"], row["symbol"])]
                _settle(row, target["key"], target["label"])
    return problems


def _settle(row: dict, key: str, label: str) -> None:
    row["key"], row["label"] = key, label


def _unresolved_link(row: dict) -> "tuple[str, str]":
    return (
        "notation",
        f"{row['unit']} math.md `{row['symbol']}` links to **{row['text']}**, "
        "which no glossary in the book defines",
    )


def _pointer_problem(row: dict, target: "dict | None", built: dict) -> "tuple[str, str] | None":
    start = f"{row['unit']} math.md `{row['symbol']}` points at {row['text']}, which"
    if row["text"] not in built["accepted"]:
        return ("notation", f"{start} is not an accepted unit")
    if target is None:
        return ("notation", f"{start} has no ## Symbols row for it")
    if target["kind"] == "see":
        return ("notation", f"{start} points on itself; point at the row that defines it")
    if "key" not in target:
        return ("notation", f"{start} does not resolve either")
    return None


def resolved(built: dict) -> "list[dict]":
    """The rows with a meaning key and LaTeX: what the List of Symbols prints."""
    return [row for row in built["symbols"] if "key" in row and row["typeset"] is not None]


def _grouped(rows, key) -> "dict[str, list[dict]]":
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(key(row), []).append(row)
    return grouped


def _clashes(built: dict) -> "list[tuple[str, str]]":
    """A symbol naming two things, and a symbol typeset two ways."""
    found = []
    for symbol, rows in _grouped(resolved(built), lambda row: row["symbol"]).items():
        meanings = _grouped(rows, lambda row: row["key"])
        if len(meanings) > 1:
            listed = "; ".join(f"{r[0]['label']} ({units_counted(r)})" for r in meanings.values())
            found.append(("notation", f"`{symbol}` names different things: {listed}"))
        typesets = _grouped(rows, lambda row: row["typeset"])
        if len(typesets) > 1:
            listed = "; ".join(f"{t} ({units_counted(r)})" for t, r in typesets.items())
            found.append(("notation", f"`{symbol}` is typeset differently: {listed}"))
    return found


def _unit_findings(built: dict, kinds=None) -> "list[tuple[str, str]]":
    return [
        ("notation", f"{found['unit']} {found['message']}")
        for found in built["math"]
        if kinds is None or found["kind"] in kinds
    ]


def _glossary_maths(built: dict) -> "list[tuple[str, str]]":
    return [
        (
            "notation",
            f"{found['unit']} glossary span `{found['span']}` looks like mathematics "
            f"({found['rule']}) but has no row in its math.md, so it prints as code",
        )
        for found in built["glossary_maths"]
    ]


def findings(built: dict) -> "list[tuple[str, str]]":
    """Every `[notation]` finding, in the order `registry check` prints."""
    unresolved = built["unresolved_symbols"]
    return unresolved + _clashes(built) + _unit_findings(built) + _glossary_maths(built)


def blocking(built: dict) -> "list[tuple[str, str]]":
    """What stops `registry build --glossary/--notation`: a link or
    pointer that does not resolve, a symbol that would print as code,
    and a row whose meaning is undefined."""
    return built["unresolved_symbols"] + _unit_findings(built, _BLOCKING_KINDS)
