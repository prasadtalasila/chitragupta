"""`math.md`'s diagnostics: what the mapping and the draft disagree about.

Split from `chitragupta/render_output/_math.py` for the reason
DEVELOPER-AGENTS.md's "Module boundaries" gives, and at the boundary that
module's own docstring already implies: that file *resolves* mathematics
-- it reads `math.md`, substitutes markers, and refuses a displayed
equation it cannot render -- while everything here only *reports* on it
and rewrites nothing. The two were one module at 248 code lines, two
under docs/CODE-STANDARDS.md's C2 ceiling, so the split was owed before
#506 added a line to either.

The dependency runs one way only, `_math_findings` -> `_math`, which is
why the callers import this module by name rather than reaching it
through a re-export: a re-export would need `_math` to import this, and
the cycle is the thing the split is for.
"""

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
)
from chitragupta.render_output._math_shapes import rule_for, shape_rule


def _fence_gaps(masked: str) -> "list[str]":
    """Every untagged fence in `masked` that looks like a displayed equation.

    `masked` has the marked blocks already blanked out, so what this sees
    is the fences nobody claimed. An untagged one is the open question:
    a tag is the author saying "code", and §12 gives every other fence a
    `<!-- math -->` marker, so a bare fence holding a relation is either
    an unmarked equation or a tag somebody forgot -- and both are worth
    saying, because the two remedies are one word each.

    This is the shape #406 reported: `C x I  >  F` reached the pdf as
    `\\begin{verbatim}` between two inline equations, and every check
    §12 had agreed the chapter was clean. The span scan cannot see it --
    it blanks fences first, correctly, since a fence usually is code --
    and no post-render grep for `\\texttt{}` can, since a fence never
    becomes one.
    """
    found = []
    for match in _FENCE_RE.finditer(masked):
        if match.group("tag").strip():
            continue
        body = _body_of(match)
        lines = body.splitlines()
        if len(lines) > _MAX_EQUATION_LINES:
            continue
        # `lines[0]` is reached only once the body has matched, so an
        # empty fence cannot get here.
        # Shape alone, line by line: a fence is not a span, so the draft's
        # own symbols and the context rules have no say here.
        if any(shape_rule(line.strip()) for line in lines) and not _SNAKE_CASE_RE.search(body):
            found.append(
                f"`{lines[0]}` looks like a displayed equation but its fence has no "
                "`<!-- math -->` marker. Tag the fence if it is code."
            )
    return found


# One `warnings()` line plus what kind of finding it is. The kind exists
# because `dossier._draft_fingerprint._math_desync` wants the orphans and
# only the orphans, and used to select them by testing whether the
# *message* ended in "appears nowhere in the draft" (#506/m-66). That is
# this module's prose, not its contract: rewording the sentence -- a docs
# pass, a typo fix -- would have left the filter matching nothing and the
# staleness check silently reporting no desynced math at all, with every
# test here still green.
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
) -> "list[MathFinding]":
    """Every gap and orphan in `text`, each tagged with its kind.

    `warnings()` is this reduced to the message strings, for the callers
    that only print. Read this one to *select* a kind.

    A *gap* is a span that should have a row and has not: one a
    `_math_shapes` rule calls a quantity, or one that is, or is built
    from, a name the mapping already uses -- or, since #406, an untagged
    fence holding an equation nobody marked. A *orphan*
    is a row matching nothing, the tell that a revision reworded or
    deleted the sentence it belonged to.

    Fences are reported first, the way `substitute` rewrites them first:
    a displayed equation is the bigger thing to have got wrong, and the
    symbols in it usually explain the inline gaps underneath.

    `found_file` separates "this draft has no mathematics" from "this
    draft's mapping is gone" -- the second is what a rename looks like,
    and without the distinction they are the same silence. It also gates
    `_math_shapes`' context rules (a bare `404` or `t`), which only an
    author who keeps a `math.md` has asked for.

    `not_math` is that file's "not mathematics" table: spans the author
    has said are code, never reported as gaps.
    """
    masked = _BLOCK_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    found = [MathFinding("fence", message) for message in _fence_gaps(masked)]
    # m-56: `_fence_gaps` above needs ordinary fences left visible in
    # `masked` (it is what finds an untagged one holding an equation),
    # but the span scan below must not walk into one -- a `tau`-shaped
    # token shown inside a code example is code, not draft prose, the
    # same fence-body corruption `substitute` guards against.
    span_masked = _FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), masked)
    spans = {m.group("body").strip() for m in _SPAN_RE.finditer(span_masked)}
    symbols = _symbols_of(mapping)

    for span in sorted(spans - set(mapping) - not_math):
        if not _CITEKEY_RE.match(span):
            found.extend(_span_finding(span, rule_for(span, symbols, found_file)))

    if found_file:
        used = spans | {_body_of(m) for m in _BLOCK_RE.finditer(text)}
        found.extend(_unused_rows(set(mapping) - used, not_math - spans))
    return found


def _span_finding(span: str, rule: "str | None") -> "list[MathFinding]":
    """The finding `rule` makes of `span`: none, a symbol, or a gap."""
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
    """`math.md` rows matching nothing in the draft, of either table."""
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

    `load_mapping` keeps a repeated key's last row, which is right for
    rendering and silent about it. Repeating a row with the *same* LaTeX
    changes nothing, so only differing values are reported; so is a key
    that is both mapped and listed as not mathematics, which contradicts
    itself.
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
) -> "list[str]":
    """`findings()` as lines a caller can print, in the same order."""
    return [found.message for found in findings(text, mapping, has_mapping_file, not_math)]
