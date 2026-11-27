"""Issue 457: an opt-in equation number, and the `equationref` that reads it.

§12 keeps most displayed equations unnumbered on purpose. A draft opts one in
with a marker directly above `_math.py`'s `<!-- math -->` marker:

    <!-- equation: energy -->
    <!-- math -->
    ```
    E = m * c^2
    ```

and refers to it with `<!-- equationref: energy -->`. Unmarked blocks are untouched.

Runs after `_math.substitute`, as the last pass in `_substitution.py`, so it
sees `$$...$$` on every format but `md` (which keeps the ascii-plus-fence
shape), and document order is unchanged, so no `declared` list is needed.
On `md` the number is written as `**Equation N:**`, the one deliberate
exception to §12's "md is a no-op for math". Unresolvable markers are
reported by `chitragupta/style_equations.py`; `warnings()` shares the checks.
"""

import itertools
import re
from typing import NamedTuple

from chitragupta.render_output._tables import line_of

# Formats with a LaTeX `equation` counter: a deliberate third copy of
# `_tables._LATEX_BOUND` (see that module for why they are not shared).
_LATEX_BOUND = {"tex", "latex", "pdf"}

# The pristine, pre-`_math.substitute` shape (and the `md` path's). `block`
# captures marker-plus-fence whole so the `md` substitution reuses it byte-for-byte.
_EQUATION_ASCII_RE = re.compile(
    r"^(?P<indent>[ \t>]*)<!--[ \t]*equation:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*\n"
    r"(?P<block>(?P=indent)<!--[ \t]*math[ \t]*-->[ \t]*\n"
    r"(?P=indent)```[ \t]*\n.*?^(?P=indent)```[ \t]*)$",
    re.M | re.S,
)

# The block after `_math.substitute`: `latex` is the bare content for an
# `equation` environment; `block` is the whole `$$...$$` for non-LaTeX formats.
_EQUATION_DOLLAR_RE = re.compile(
    r"^(?P<indent>[ \t>]*)<!--[ \t]*equation:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*\n"
    r"(?P<block>(?P=indent)\$\$\n(?P<latex>.*?)\n(?P=indent)\$\$)[ \t]*$",
    re.M | re.S,
)

# A marker with no valid block after it, matched separately so it is reported
# as itself, as `_math._LONE_MARKER_RE`/`_tables._MARKER_RE` do.
_MARKER_RE = re.compile(r"^[ \t>]*<!--[ \t]*equation:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*$", re.M)

_REF_RE = re.compile(r"<!--[ \t]*equationref:[ \t]*(?P<id>\S+?)[ \t]*-->")


class Equation(NamedTuple):
    """One marked, declared equation: its id, number, and marker position."""

    id: str
    number: int
    line: int


def equations(text: str) -> "list[Equation]":
    """Every marked equation in `text`, numbered in document order.

    Matches the pristine shape, shared by `style_equations.py` and the `md` path.
    """
    return [
        Equation(m.group("id"), number, line_of(text, m.start()))
        for number, m in enumerate(_EQUATION_ASCII_RE.finditer(text), start=1)
    ]


def references(text: str) -> "list[tuple[str, int]]":
    """Every `equationref` marker in `text`, as (id, 1-based line)."""
    return [(m.group("id"), line_of(text, m.start())) for m in _REF_RE.finditer(text)]


def _substitute_ascii(text: str) -> str:
    """`text` on the `md` path: a numbered label above each untouched block."""
    # m-57: numbered by position, not a dict keyed on id, so two equations
    # sharing an id do not both render the last-written number.
    counter = itertools.count(1)

    def _replace(match: "re.Match[str]") -> str:
        indent = match.group("indent")
        number = next(counter)
        return f"{indent}**Equation {number}:**\n{match.group('block')}"

    return _EQUATION_ASCII_RE.sub(_replace, text)


def _substitute_dollar(text: str, output_format: str) -> str:
    """`text` after `_math.substitute`: an `equation` environment for a
    LaTeX-bound format, a written number beside `$$...$$` for the rest."""
    # m-57: numbered by position as above. A shared id still makes a duplicate
    # \label, which `warnings` reports as an authoring error.
    counter = itertools.count(1)

    def _replace(match: "re.Match[str]") -> str:
        indent = match.group("indent")
        number = next(counter)
        if output_format in _LATEX_BOUND:
            return (
                f"{indent}\\begin{{equation}}\n{match.group('latex')}\n"
                f"{indent}\\label{{eq:{match.group('id')}}}\n{indent}\\end{{equation}}"
            )
        return f"{indent}**Equation {number}:**\n{match.group('block')}"

    return _EQUATION_DOLLAR_RE.sub(_replace, text)


def _reference_for(number: "int | None", eq_id: str, raw: str, output_format: str) -> str:
    """The phrase an `equationref` expands to, or `raw` if the id is undeclared."""
    if number is None:
        return raw
    if output_format in _LATEX_BOUND:
        return f"`Equation~\\ref{{eq:{eq_id}}}`{{=latex}}"
    return f"Equation {number}"


def substitute(text: str, output_format: str) -> str:
    """`text` with every marked equation numbered and every `equationref`
    resolved for `output_format`; must run after mathematics substitution.
    """
    is_md = output_format == "md"
    pattern = _EQUATION_ASCII_RE if is_md else _EQUATION_DOLLAR_RE
    numbers = {m.group("id"): n for n, m in enumerate(pattern.finditer(text), start=1)}
    text = _substitute_ascii(text) if is_md else _substitute_dollar(text, output_format)

    def _reference(match: "re.Match[str]") -> str:
        eq_id = match.group("id")
        return _reference_for(numbers.get(eq_id), eq_id, match.group(0), output_format)

    return _REF_RE.sub(_reference, text)


def warnings(text: str) -> "list[str]":
    """Every equation marker and reference in `text` that cannot resolve.

    Printed to stderr; none of these stops a render.
    """
    ids = [equation.id for equation in equations(text)]
    declared_starts = {m.start() for m in _EQUATION_ASCII_RE.finditer(text)}
    found = [
        f"`{marker.group('id')}` names no `<!-- math -->` block directly below it, "
        "so nothing numbers it"
        for marker in _MARKER_RE.finditer(text)
        if marker.start() not in declared_starts
    ]
    found += [
        f"`{eq_id}` is declared by more than one equation"
        for eq_id in sorted(set(ids))
        if ids.count(eq_id) > 1
    ]
    found += [
        f"`{ref}` is referred to but no equation declares it"
        for ref in sorted({m.group("id") for m in _REF_RE.finditer(text)} - set(ids))
    ]
    return found
