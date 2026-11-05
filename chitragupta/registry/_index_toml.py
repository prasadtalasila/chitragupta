"""`content/specs/<book>/index.toml`: read it and check its shape (#1168).

The author's exceptions to an index built from the glossary. This module
checks only that each table and value has the shape
docs/book/book-index.md documents; whether the terms it names exist is
`registry/_index_terms.py`'s question, which needs the glossary.

Split from that module to keep both under docs/CODE-STANDARDS.md's C2
limit.
"""

import tomllib
from pathlib import Path

from chitragupta.spec._scaffold import INDEX_TOML

DEFAULTS = {
    "min_mentions": 2,
    "sort": "word",
    "letter_headings": False,
    "skip_sections": ["Exercises", "Solutions"],
}

# The shape of each table's values.
_SHAPES = {
    "variants": list,
    "restrict": list,
    "always": list,
    "see_also": list,
    "parent": list,
    "print": str,
    "see": str,
    "parent_only": bool,
}


def read(specs: Path) -> "tuple[dict, list[str]]":
    """`index.toml` from `specs`, and every problem with its shape. A
    missing file is no exceptions, not a problem."""
    path = Path(specs) / INDEX_TOML
    if not path.is_file():
        return {}, []
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return {}, [f"{path} is not valid TOML: {exc}"]
    return doc, _shape_problems(doc)


def _settings_problems(settings) -> "list[str]":
    if not isinstance(settings, dict):
        return ["`[settings]` must be a table."]
    problems = [f"`[settings]` has no key `{key}`." for key in settings if key not in DEFAULTS]
    minimum = settings.get("min_mentions", 1)
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        problems.append("`min_mentions` must be a whole number, 1 or more.")
    if settings.get("sort", "word") not in ("word", "letter"):
        problems.append('`sort` must be "word" or "letter".')
    if not isinstance(settings.get("letter_headings", False), bool):
        problems.append("`letter_headings` must be true or false.")
    if not _strings(settings.get("skip_sections", [])):
        problems.append("`skip_sections` must be a list of headings.")
    return problems


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _value_ok(shape, value) -> bool:
    if shape is list:
        return _strings(value) and bool(value)
    if shape is str:
        return isinstance(value, str) and bool(value)
    return isinstance(value, bool)


def _table_problems(name: str, table) -> "list[str]":
    if name in ("drop", "add"):
        if not isinstance(table, dict) or set(table) != {"terms"} or not _strings(table["terms"]):
            return [f"`[{name}]` must hold exactly `terms = [...]`, a list of terms."]
        return []
    if not isinstance(table, dict):
        return [f"`[{name}]` must be a table."]
    shape = _SHAPES[name]
    return [
        f"`[{name}]` entry `{key}` has the wrong shape: it must be "
        f"{ {list: 'a list of strings', str: 'a string', bool: 'true or false'}[shape] }."
        for key, value in table.items()
        if not _value_ok(shape, value)
    ]


def _shape_problems(doc: dict) -> "list[str]":
    problems = []
    for name, table in doc.items():
        if name == "settings":
            problems += _settings_problems(table)
        elif name in _SHAPES or name in ("drop", "add"):
            problems += _table_problems(name, table)
        else:
            problems.append(f"`index.toml` has no table `[{name}]`.")
    return problems


def settings(doc: dict) -> dict:
    """The settings in force: `[settings]` over the defaults."""
    return {**DEFAULTS, **doc.get("settings", {})}
