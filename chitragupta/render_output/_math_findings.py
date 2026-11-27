"""`math.md`'s diagnostics: what the mapping and the draft disagree about.

`_math` resolves mathematics; this module only reports. The dependency runs
one way, `_math_findings` -> `_math`, so callers import this by name: a
re-export from `_math` would close a cycle.
"""

import re
from typing import NamedTuple

from chitragupta.render_output._math import (
    MAPPING_FILENAME,
    _BLOCK_RE,
    _CITEKEY_RE,
    _FENCE_RE,
    _MAX_EQUATION_LINES,
    _SNAKE_CASE_RE,
    _SPAN_RE,
    _body_of,
    _symbols_of,
    is_bare_symbol,
)
from chitragupta.render_output._math_shapes import rule_for, shape_rule


def _fence_gaps(masked: str) -> "list[str]":
    """Every untagged fence in `masked` that looks like a displayed equation.

    `masked` has marked blocks blanked. A bare fence holding a relation is an
    unmarked equation or a forgotten tag; both have one-word remedies. The span
    scan cannot see this (it blanks fences first), nor can a post-render grep
    (#406).
    """
    found = []
    for match in _FENCE_RE.finditer(masked):
        if match.group("tag").strip():
            continue
        body = _body_of(match)
        lines = body.splitlines()
        if len(lines) > _MAX_EQUATION_LINES:
            continue
        # `lines[0]` is reached only once the body has matched. Shape alone:
        # a fence is not a span, so the draft's symbols and context rules have no say.
        if any(shape_rule(line.strip()) for line in lines) and not _SNAKE_CASE_RE.search(body):
            found.append(
                f"`{lines[0]}` looks like a displayed equation but its fence has no "
                "`<!-- math -->` marker. Tag the fence if it is code."
            )
    return found


# The kind exists so `dossier._draft_fingerprint._math_desync` can select orphans
# without matching this module's message wording, which would break silently (#506).
class MathFinding(NamedTuple):
    """A `warnings()` line and its kind: fence, gap, symbol, orphan,
    unused-code (a "not mathematics" row matching nothing) or duplicate."""

    kind: str
    message: str


def findings(
    text: str,
    mapping: "dict[str, str]",
    found_file: bool,
    not_math: "frozenset[str]" = frozenset(),
    glossary: "frozenset[str]" = frozenset(),
) -> "list[MathFinding]":
    """Every gap and orphan in `text`, each tagged with its kind.

    `warnings()` is this reduced to strings; read this one to select a kind.
    A *gap* is a span or untagged equation fence that should have a row; an
    *orphan* is a row matching nothing, the tell of a reworded sentence.
    Fences come first, as `substitute` rewrites them first.

    `found_file` tells "no mathematics" from "mapping gone" (what a rename looks
    like), and gates `_math_shapes`' context rules. `not_math` spans are never
    gaps; nor are `glossary` spans (#1143), which `registry check` handles.
    """
    masked = _BLOCK_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    found = [MathFinding("fence", message) for message in _fence_gaps(masked)]
    # m-56: `_fence_gaps` needs ordinary fences visible in `masked`, but the span
    # scan must not walk into one: a token in a code example is code, not prose.
    span_masked = _FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), masked)
    spans = {m.group("body").strip() for m in _SPAN_RE.finditer(span_masked)}
    symbols = _symbols_of(mapping)

    for span in sorted(spans - set(mapping) - not_math):
        if not _CITEKEY_RE.match(span):
            found.extend(_span_finding(span, rule_for(span, symbols, found_file)))

    if found_file:
        blocks = {_body_of(m) for m in _BLOCK_RE.finditer(text)}
        used = _used(spans | glossary | blocks, mapping)
        found.extend(_unused_rows(set(mapping) - used, not_math - spans - glossary))
    return found


def _used(bodies: "set[str]", mapping: "dict[str, str]") -> "set[str]":
    """The mapping keys `bodies` (spans and blocks) use.

    Since #1143 a symbol is also used as a whole token inside a *mapped* body
    (`T_r` in `T_r = 10`). Mapped bodies only, so a code span like `range(n)`
    keeps no single-letter row alive.
    """
    used = set(bodies)
    mapped = [body for body in bodies if body in mapping]
    for key in set(mapping) - used:
        token = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])")
        if is_bare_symbol(key) and any(token.search(body) for body in mapped):
            used.add(key)
    return used


def _span_finding(span: str, rule: "str | None") -> "list[MathFinding]":
    if rule is None:
        return []
    if rule == "symbol":
        return [
            MathFinding(
                "symbol",
                f"`{span}` is a symbol this draft's own equations use, "
                f"but has no row in {MAPPING_FILENAME}",
            )
        ]
    if rule == "symbol-built":
        return [
            MathFinding(
                "symbol",
                f"`{span}` is built from symbols this draft's own equations use, "
                f"but has no row in {MAPPING_FILENAME}",
            )
        ]
    gap = f"`{span}` looks like a quantity ({rule}) but has no row in {MAPPING_FILENAME}"
    return [MathFinding("gap", gap)]


def _unused_rows(orphans: "set[str]", unused_code: "frozenset[str]") -> "list[MathFinding]":
    found = [
        MathFinding(
            "orphan", f"`{orphan}` has a row in {MAPPING_FILENAME} but appears nowhere in the draft"
        )
        for orphan in sorted(orphans)
    ]
    # Its own kind, not `orphan`: `_math_desync` reads an orphan as the
    # mathematics having moved, and a stale code row says nothing of it.
    found.extend(
        MathFinding(
            "unused-code",
            f"`{unused}` is listed as not mathematics in {MAPPING_FILENAME} "
            "but appears nowhere in the draft",
        )
        for unused in sorted(unused_code)
    )
    return found


def duplicates(
    rows: "list[tuple[str, str]]", not_math: "frozenset[str]" = frozenset()
) -> "list[MathFinding]":
    """Every key `rows` resolves two ways (#1116).

    `load_mapping` silently keeps a repeated key's last row. Only differing
    values are reported, plus a key both mapped and listed as not mathematics.
    """
    values: "dict[str, list[str]]" = {}
    for ascii_, latex in rows:
        values.setdefault(ascii_, []).append(latex)
    found = []
    for ascii_, latex in values.items():
        distinct = list(dict.fromkeys(latex))
        if len(distinct) > 1:
            listed = ", ".join(f"`{value}`" for value in distinct)
            found.append(
                MathFinding(
                    "duplicate",
                    f"`{ascii_}` has {len(latex)} rows in {MAPPING_FILENAME} with different "
                    f"LaTeX: {listed}; the last is rendered",
                )
            )
        if ascii_ in not_math:
            found.append(
                MathFinding(
                    "duplicate",
                    f"`{ascii_}` has a row in {MAPPING_FILENAME} and is also listed as "
                    "not mathematics; the row is rendered",
                )
            )
    return found


def warnings(
    text: str,
    mapping: "dict[str, str]",
    has_mapping_file: bool,
    not_math: "frozenset[str]" = frozenset(),
    glossary: "frozenset[str]" = frozenset(),
) -> "list[str]":
    """`findings()` as lines a caller can print, in the same order."""
    found = findings(text, mapping, has_mapping_file, not_math, glossary)
    return [finding.message for finding in found]
