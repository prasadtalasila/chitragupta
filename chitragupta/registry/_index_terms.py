"""The index's term table: `registry build --index` (#1168).

The index is built from the glossary the terminology registry already
reads (`registry/_terms.py`), plus the author's exceptions in
`content/specs/<book>/index.toml`. This module validates that file and
writes `index-terms.json`, the one input both later stages read: the
pandoc filter (`assets/pandoc/index_terms.lua`), which places
`\\index{<id>}` in each chapter, and `registry/_index_finish.py`, which
turns ids into printed entries once the book is typeset.

**An id is a hash of the term's key, not a position.** A chapter rendered
before a term was added keeps its `\\index{<id>}`; a positional id would
then name a different term without anything noticing. A hashed one names
the same term or nothing.

**A bad `index.toml` refuses the build** and lists every problem, as
`build --glossary` refuses a page it would have to leave terms out of. A
build is not a check: everything that is judgement (a generic term, a
mention below the threshold) is the report's, `registry/_index_report.py`.
"""

import hashlib
import json
import re
import string

from chitragupta.registry._terms import _TRAILING_ABBREVIATION, term_key
from chitragupta.registry._index_toml import settings

TERMS_JSON = "index-terms.json"

# What the filter strips from a word's edges: ASCII punctuation and quotes.
_EDGES = string.punctuation + "\u201c\u201d\u2018\u2019\u00ab\u00bb"

# A trailing "(DT)": an abbreviation, which gets a "see" entry. Capitals
# and digits only (a plural `s` allowed), so "(also called X)" is not one.
_ABBREVIATION = re.compile(r"\(([A-Z][A-Z0-9&/]*s?)\)$")

# Tables whose values name terms.
_TERM_LISTS = ("variants", "restrict", "always", "see_also")


def term_id(key: str) -> str:
    """The id a term carries through `\\index{}`: stable across rebuilds."""
    return "t" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]


def spelling(text: str) -> str:
    """A spelling as `assets/pandoc/index_terms.lua` tokenises prose:
    each word loses a possessive and its edge punctuation, a hyphen or
    dash splits it, and it is lowercased. The two must agree word for
    word, or a term never matches."""
    words = []
    for raw in text.split():
        for part in re.split(r"[-\u2013\u2014]", re.sub(r"[\u2019']s$", "", raw)):
            word = part.strip(_EDGES)
            if word:
                words.append(word.lower())
    return " ".join(words)


def _glossary_terms(rows: "list[dict]") -> "dict[str, dict]":
    """Term key -> its glossary form, the chapters defining it in outline
    order, and its abbreviation if it carries one."""
    terms: dict[str, dict] = {}
    for row in rows:
        entry = terms.setdefault(
            term_key(row["term"]),
            {
                "glossary": _TRAILING_ABBREVIATION.sub("", row["term"]),
                "defined_in": [],
                "abbreviation": None,
            },
        )
        abbreviation = _ABBREVIATION.search(row["term"])
        if abbreviation and entry["abbreviation"] is None:
            entry["abbreviation"] = abbreviation.group(1)
        if row["unit"] not in entry["defined_in"]:
            entry["defined_in"].append(row["unit"])
    return terms


def _names(doc: dict) -> "list[tuple[str, str]]":
    """`(table, term)` for every term an `index.toml` table names."""
    names = [(table, name) for table in _TERM_LISTS + ("print",) for name in doc.get(table, {})]
    names += [(name, term) for name in ("drop",) for term in doc.get(name, {}).get("terms", [])]
    names += [
        ("see_also", term) for targets in doc.get("see_also", {}).values() for term in targets
    ]
    names += [("parent", term) for children in doc.get("parent", {}).values() for term in children]
    names += [("see", target) for target in doc.get("see", {}).values()]
    return names


def _reference_problems(doc: dict, glossary: dict, accepted: "list[str]") -> "list[str]":
    added = {term_key(term) for term in doc.get("add", {}).get("terms", [])}
    known = set(glossary) | added
    dropped = {term_key(term) for term in doc.get("drop", {}).get("terms", [])}
    problems = [
        f'`[{table}]` names "{name}", which is in no glossary and not in `[add]`.'
        for table, name in _names(doc)
        if term_key(name) not in known
    ]
    problems += [
        f'`[add]` term "{term}" is already a glossary term.'
        for term in doc.get("add", {}).get("terms", [])
        if term_key(term) in glossary
    ]
    problems += [
        f'`[always]` names chapter "{chapter}" for "{name}", which is not an accepted unit.'
        for name, chapters in doc.get("always", {}).items()
        for chapter in chapters
        if chapter not in accepted
    ]
    indexed = known - dropped
    problems += [
        f'`[see]` source "{source}" is an indexed term; a see entry has no page numbers of its own.'
        for source in doc.get("see", {})
        if term_key(source) in indexed
    ]
    problems += [
        f'`[parent]` child "{child}" is dropped.'
        for children in doc.get("parent", {}).values()
        for child in children
        if term_key(child) in dropped
    ]
    parents = {term_key(name) for name in doc.get("parent", {})}
    problems += [
        f'`[parent_only]` names "{name}", which is not a `[parent]`.'
        for name in doc.get("parent_only", {})
        if term_key(name) not in parents
    ]
    problems += [
        f'`[{table}]` "{name}": "{text}" leaves no word to match.'
        for table in ("variants", "restrict")
        for name, texts in doc.get(table, {}).items()
        for text in texts
        if not spelling(text)
    ]
    return problems


def _target_problems(doc: dict, unholdable: "set[str]") -> "list[str]":
    """A see or see-also target with no entry of its own to point at."""
    targets = [("see", target) for target in doc.get("see", {}).values()]
    targets += [("see_also", t) for names in doc.get("see_also", {}).values() for t in names]
    return [
        f'`[{table}]` target "{target}" is dropped or has no plain spelling, '
        "so it has no entry to point at."
        for table, target in targets
        if term_key(target) in unholdable
    ]


def _parent_only(doc: dict) -> "list[str]":
    """`[parent_only]`'s parents, each named as `[parent]` writes it."""
    wanted = {term_key(name) for name in doc.get("parent_only", {})}
    return sorted(name for name in doc.get("parent", {}) if term_key(name) in wanted)


def _spellings(key: str, doc: dict) -> "list[str]":
    """What counts as the term in prose: its `[restrict]` phrases alone,
    or its own key (unless it holds maths) and its `[variants]`."""
    restrict = _keyed(doc, "restrict").get(key)
    if restrict:
        return sorted({spelling(phrase) for phrase in restrict})
    own = [] if "`" in key or "$" in key else [key]
    return sorted({spelling(text) for text in own + _keyed(doc, "variants").get(key, [])})


def _keyed(doc: dict, table: str) -> dict:
    """An `index.toml` table with its keys as term keys."""
    return {term_key(name): value for name, value in doc.get(table, {}).items()}


def _clash_problems(spellings: "dict[str, list[str]]") -> "list[str]":
    owner: dict[str, str] = {}
    problems = []
    for key, texts in sorted(spellings.items()):
        for text in texts:
            if text in owner:
                problems.append(f'"{text}" is a spelling of both "{owner[text]}" and "{key}".')
            owner[text] = key
    return problems


def _entry(key: str, base: dict, doc: dict, linked: dict) -> dict:
    symbols = [symbol for unit in base["defined_in"] for symbol in linked.get((unit, key), [])]
    return {
        "key": key,
        "glossary": base["glossary"],
        "defined_in": base["defined_in"],
        "always": _keyed(doc, "always").get(key, []),
        "symbols": list(dict.fromkeys(symbols)),
        "print": _keyed(doc, "print").get(key),
        "parents": sorted(
            parent
            for parent, children in doc.get("parent", {}).items()
            if key in {term_key(child) for child in children}
        ),
    }


def _see(doc: dict, glossary: dict, indexed: "set[str]") -> "dict[str, str]":
    """See entries: each abbreviation to its term, then `[see]` over them."""
    see = {
        base["abbreviation"]: term_id(key)
        for key, base in glossary.items()
        if key in indexed and base["abbreviation"] and term_key(base["abbreviation"]) not in indexed
    }
    see.update({source: term_id(term_key(target)) for source, target in doc.get("see", {}).items()})
    return dict(sorted(see.items()))


def table(
    rows: "list[dict]", linked: dict, accepted: "list[str]", doc: dict
) -> "tuple[dict, list[str]]":
    """The term table `index-terms.json` holds, and every problem that
    refuses it. `rows` are the registry's glossary rows in outline order,
    `linked` maps `(unit, term key)` to the symbols that unit links to the
    term, `doc` is the parsed `index.toml`."""
    glossary = _glossary_terms(rows)
    problems = _reference_problems(doc, glossary, accepted)
    for term in doc.get("add", {}).get("terms", []):
        glossary.setdefault(
            term_key(term), {"glossary": term, "defined_in": [], "abbreviation": None}
        )
    dropped = {term_key(term) for term in doc.get("drop", {}).get("terms", [])}
    indexed = set(glossary) - dropped
    spellings = {key: _spellings(key, doc) for key in sorted(indexed)}
    problems += _clash_problems(spellings)
    problems += _target_problems(doc, dropped | {key for key in indexed if not spellings[key]})
    terms = {
        term_id(key): {**_entry(key, glossary[key], doc, linked), "spellings": spellings[key]}
        for key in sorted(indexed)
        if spellings[key]
    }
    return {
        **settings(doc),
        "terms": terms,
        "see": _see(doc, glossary, indexed),
        "see_also": {
            term_id(term_key(name)): sorted(term_id(term_key(target)) for target in targets)
            for name, targets in sorted(doc.get("see_also", {}).items())
        },
        "parent_only": _parent_only(doc),
        "not_indexable": sorted(key for key in indexed if not spellings[key]),
        "dropped": sorted(dropped),
    }, problems


def dumps(data: dict) -> str:
    """`index-terms.json`'s text: sorted, so a rebuild over unchanged
    units is byte-identical."""
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
