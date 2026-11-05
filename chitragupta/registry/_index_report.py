"""The index report (#1168): `content/specs/<book>/registries/index.md` and
`index.json`, beside the other registries.

Every finding ends with the `index.toml` line that answers it, so acting
on one is a paste, or one sentence to an agent that reads `index.json`.
None of it refuses anything: a generic term or a mention below the
threshold is a judgement for the author, which is why these live here
and not in `registry/_index_terms.py`'s validation, which does refuse.

Then the whole index as a table, so the author can review every term's
chapters, not only the ones a rule caught.
"""

import json
import math
from pathlib import Path

from chitragupta.registry import _pages
from chitragupta.registry._index_entries import ARTICLES, guessed
from chitragupta.registry._index_terms import spelling, term_id
from chitragupta.registry._terms import term_key

_BANNER = (
    "<!-- Derived from the typeset book by `registry index`. Evidence for a "
    "judgement, not a verdict: nothing here blocks anything. Each fix is a "
    "line for content/specs/<book>/index.toml; see docs/book/book-index.md. -->"
)

_ORDER = (
    "no-locator",
    "generic",
    "below-threshold",
    "mixed-case",
    "casing-guessed",
    "family",
    "unused",
    "not-indexable",
    "dangling-see",
)


def _chapters(sidecars: dict) -> "dict[str, dict[str, dict]]":
    """Term id -> unit -> that chapter's sidecar entry."""
    found: dict[str, dict[str, dict]] = {}
    for unit, side in sidecars.items():
        for tid, entry in (side["terms"] or {}).items():
            found.setdefault(tid, {})[unit] = entry
    return found


def _q(text: str) -> str:
    """`text` as a TOML string: JSON's escaping is TOML's, so a key holding
    `\\` or `"` (a maths term) still pastes as valid `index.toml`."""
    return json.dumps(text, ensure_ascii=False)


def _finding(kind: str, key: str, message: str, fix: str) -> dict:
    return {"kind": kind, "term": key, "message": message, "fix": fix}


def _term_findings(term: dict, seen: "dict[str, dict]", units: list, minimum: int) -> list:
    key, found = term["key"], []
    indexed = [unit for unit, entry in seen.items() if entry["indexed"]]
    if not seen:
        found.append(
            _finding(
                "no-locator",
                key,
                f'"{key}" occurs nowhere in the indexed chapters.',
                f"[drop] terms = [{_q(key)}]  # or a [variants] spelling",
            )
        )
    if len(indexed) >= max(3, math.ceil(0.75 * len(units))):
        found.append(
            _finding(
                "generic",
                key,
                f'"{key}" has page numbers in {len(indexed)} of {len(units)} chapters.',
                f'[drop] terms = [{_q(key)}]  # or [restrict] {_q(key)} = ["..."]',
            )
        )
    below = sorted(unit for unit, entry in seen.items() if not entry["indexed"])
    if below:
        found.append(
            _finding(
                "below-threshold",
                key,
                f'"{key}" is mentioned fewer than {minimum} times in {", ".join(below)}.',
                f"[always] {_q(key)} = {json.dumps(below, ensure_ascii=False)}",
            )
        )
    return found + _casing(term, seen)


def _casing(term: dict, seen: "dict[str, dict]") -> list:
    key, counts = term["key"], {}
    for entry in seen.values():
        for surface, count in entry["midsentence"].items():
            counts[surface] = counts.get(surface, 0) + count
    if term["print"] is None and guessed(term["glossary"], counts):
        return [
            _finding(
                "casing-guessed",
                key,
                f'"{term["glossary"]}" is never cased mid-sentence, so its first '
                "word prints lowercase.",
                f"[print] {_q(key)} = {_q(term['glossary'])}  # if it is a proper noun",
            )
        ]
    patterns = {tuple(word[:1].isupper() for word in surface.split()) for surface in counts}
    if len(patterns) < 2:
        return []
    common = max(sorted(counts), key=lambda surface: counts[surface])
    return [
        _finding(
            "mixed-case",
            key,
            f'"{key}" is cased several ways mid-sentence: {", ".join(sorted(counts))}.',
            f"[print] {_q(key)} = {_q(common)}",
        )
    ]


def _families(data: dict) -> list:
    groups: dict[str, list[str]] = {}
    for term in data["terms"].values():
        words = term["key"].split()
        if term["parents"] or len(words) < 2:
            continue
        for word in {words[0], words[-1]} - set(ARTICLES):
            groups.setdefault(word, []).append(term["key"])
    return [
        _finding(
            "family",
            word,
            f'{len(keys)} terms share "{word}": {", ".join(sorted(keys))}.',
            f"[parent] {_q(word)} = {json.dumps(sorted(keys), ensure_ascii=False)}",
        )
        for word, keys in sorted(groups.items())
        if len(keys) >= 3
    ]


def _unused(data: dict, doc: dict, seen: "dict[str, dict]") -> list:
    found = []
    for table in ("variants", "restrict"):
        for name, texts in doc.get(table, {}).items():
            matched = {
                text
                for entry in seen.get(term_id(term_key(name)), {}).values()
                for text, count in entry["spellings"].items()
                if count
            }
            found += [
                _finding(
                    "unused",
                    term_key(name),
                    f'[{table}] "{text}" never occurs.',
                    f'remove "{text}" from [{table}] "{name}"',
                )
                for text in texts
                if spelling(text) not in matched
            ]
    for name, chapters in doc.get("always", {}).items():
        mentioned = seen.get(term_id(term_key(name)), {})
        found += [
            _finding(
                "unused",
                term_key(name),
                f'[always] "{name}" names {chapter}, which never mentions it.',
                f'remove "{chapter}" from [always] "{name}"',
            )
            for chapter in chapters
            if chapter not in mentioned
        ]
    return found


def findings(data: dict, sidecars: dict, doc: dict, units: list, dangling: list) -> list:
    """Every finding, in `_ORDER` and then term order."""
    seen = _chapters(sidecars)
    found = []
    for tid, term in sorted(data["terms"].items(), key=lambda item: item[1]["key"]):
        found += _term_findings(term, seen.get(tid, {}), units, data["min_mentions"])
    found += _families(data) + _unused(data, doc, seen)
    found += [
        _finding(
            "not-indexable",
            key,
            f'"{key}" holds maths, which prose matching cannot find.',
            f'[variants] {_q(key)} = ["a plain spelling"]',
        )
        for key in data["not_indexable"]
    ]
    found += [
        _finding(
            "dangling-see",
            name,
            f'A cross-reference to "{name}" was left out: it has no page in the book.',
            "fix or remove its [see] / [see_also] entry",
        )
        for name in dangling
    ]
    return sorted(found, key=lambda finding: _ORDER.index(finding["kind"]))


def summary(entries: int, found: int, path) -> str:
    """The one line `registry index` prints."""
    entry_word = "entry" if entries == 1 else "entries"
    finding_word = "finding" if found == 1 else "findings"
    return f"index: {entries} {entry_word}, {found} {finding_word} -> {path} (+ .json)"


def _rows(data: dict, seen: "dict[str, dict]") -> list:
    rows = []
    for tid, term in sorted(data["terms"].items(), key=lambda item: item[1]["key"]):
        chapters = seen.get(tid, {})
        rows.append(
            {
                "term": term["glossary"],
                "key": term["key"],
                "chapters": {
                    unit: {"count": entry["count"], "indexed": entry["indexed"]}
                    for unit, entry in sorted(chapters.items())
                },
            }
        )
    return rows


def _cell(chapters: dict, indexed: bool) -> str:
    return ", ".join(
        f"{unit} ({entry['count']})"
        for unit, entry in chapters.items()
        if entry["indexed"] is indexed
    )


def write(
    directory: Path, data: dict, sidecars: dict, found: list, entries: int
) -> "tuple[Path, Path]":
    """`index.md` and `index.json` under `directory`; both paths."""
    rows = _rows(data, _chapters(sidecars))
    lines = [
        f"# index\n\n{_BANNER}\n",
        summary(entries, len(found), "this file") + "\n",
        "## Findings\n",
    ]
    lines += [f"- [{f['kind']}] {f['message']}\n  fix: `{f['fix']}`" for f in found] or ["None."]
    lines += ["\n## Every term\n", "| term | page numbers in | mentioned below the threshold in |"]
    lines += ["| --- | --- | --- |"]
    lines += [
        f"| {row['term']} | {_cell(row['chapters'], True)} | {_cell(row['chapters'], False)} |"
        for row in rows
    ]
    md, js = Path(directory) / "index.md", Path(directory) / "index.json"
    _pages.write(md, "\n".join(lines) + "\n")
    payload = {
        "summary": {"entries": entries, "findings": len(found)},
        "findings": found,
        "terms": rows,
    }
    _pages.write(js, json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    return md, js
