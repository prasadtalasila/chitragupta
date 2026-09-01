"""Issue 457: an opt-in equation number, and the `equationref` that reads it.

`docs/WRITING-STANDARDS.md` §12 keeps most displayed equations unnumbered
on purpose -- a derivation's intermediate steps are noise if every one of
them gets a number. A Markdown draft opts a *specific* equation in with a
marker directly above `_math.py`'s own `<!-- math -->` marker:

    <!-- equation: energy -->
    <!-- math -->
    ```
    E = m * c^2
    ```

and refers to it with `<!-- equationref: energy -->`, mirroring
`_tables.py`'s `tableref` and `_figure_captions.py`'s `figureref`. An
unmarked `<!-- math -->` block -- a derivation step -- is untouched by
every function in this module; that is the whole mechanism, not an edge
case of it.

**This module runs after `_math.substitute`, not before.** A table's or
figure's caption sits *beside* content nothing else touches; an
equation's marker sits above content `_math.py` itself rewrites into real
`$$...$$` -- so this module has to recognise whichever shape
`_math.substitute` left behind, and that shape depends on the format:

- **Every format except `md`** reaches pandoc with a real, checked
  mapping (`render()`'s `_checked_math_mapping` runs `_math.check()`
  before either substitution), so a marked block is always `$$...$$` by
  the time this module sees it.
- **`md`** never reaches pandoc, so `render()` passes an empty mapping
  and `_math.substitute(text, {})` changes nothing -- this module sees
  the original ascii-plus-fence shape, unchanged.

Because this module is the *last* pass in `_substitution.py`'s chain, no
earlier pass moves an equation marker's position relative to the others,
so counting matches in the text this module receives gives the same
document order as counting them in the pristine draft -- unlike
`_figure_captions.py`, this module needs no precomputed `declared` list
threaded in from outside; it is self-contained, the same as `_math.py`.

**Numbering breaks §12's own "the `md` path is a no-op for math" rule,
on purpose and only for numbering.** A marked equation's *content* is
exactly as untouched on the `md` path as an unmarked one always was; its
*number* is not, because a hand-counted `**Equation N:**` label is
written there the same way `_tables.py` already writes `**Table N:**` on
that path. §12 states both halves explicitly rather than leaving the
exception to be discovered by reading this module.

**Findings about a marker/reference nobody can resolve are
`chitragupta/style_equations.py`'s job, not this module's.**
`warnings()` here mirrors `_tables.warnings`/`_figure_captions.warnings`
for the same reason those exist: a caller printing to stderr at render
time needs the same three checks a style report needs, computed once.
"""

import itertools
import re
from typing import NamedTuple

from chitragupta.render_output._tables import line_of

# The formats that go through LaTeX, and so the only ones with an
# `equation` counter to defer numbering to -- a third, deliberate copy of
# `_tables._LATEX_BOUND`/`_figure_captions._LATEX_BOUND`; see either
# module's own comment for why these are not shared.
_LATEX_BOUND = {"tex", "latex", "pdf"}

# The pristine, pre-`_math.substitute` shape: `equation:` directly above
# `math`, directly above a fence -- what a draft actually contains, and
# what every format except `md` no longer looks like once `_math` has
# run. `block` captures the `math`-marker-plus-fence portion whole, so the
# `md`-path substitution can reuse it byte-for-byte.
_EQUATION_ASCII_RE = re.compile(
    r"^(?P<indent>[ \t>]*)<!--[ \t]*equation:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*\n"
    r"(?P<block>(?P=indent)<!--[ \t]*math[ \t]*-->[ \t]*\n"
    r"(?P=indent)```[ \t]*\n.*?^(?P=indent)```[ \t]*)$",
    re.M | re.S,
)

# What `_math.substitute` turns the block above into, on every format
# that reaches pandoc with a real mapping. `latex` is the bare content, for
# wrapping in a real `equation` environment; `block` is the whole
# `$$...$$` form, kept verbatim for a format with no LaTeX counter.
_EQUATION_DOLLAR_RE = re.compile(
    r"^(?P<indent>[ \t>]*)<!--[ \t]*equation:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*\n"
    r"(?P<block>(?P=indent)\$\$\n(?P<latex>.*?)\n(?P=indent)\$\$)[ \t]*$",
    re.M | re.S,
)

# A marker with no valid block after it -- matched separately so "you
# wrote a marker and it names nothing" is reported as itself, the same
# split `_math._LONE_MARKER_RE`/`_tables._MARKER_RE` make.
_MARKER_RE = re.compile(r"^[ \t>]*<!--[ \t]*equation:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*$", re.M)

# The inline reference, mirroring `_tables._REF_RE`/`_figure_captions._FIGUREREF_RE`.
_REF_RE = re.compile(r"<!--[ \t]*equationref:[ \t]*(?P<id>\S+?)[ \t]*-->")


class Equation(NamedTuple):
    """One marked, declared equation: its id, the number it takes in a
    format that has to be told, and where its marker sits."""

    id: str
    number: int
    line: int


def equations(text: str) -> "list[Equation]":
    """Every marked equation in `text`, numbered in document order.

    Matched against the pristine ascii-plus-fence shape, so this is the
    function both `style_equations.py` (which reads a draft nothing has
    substituted) and this module's own `md`-path substitution (where
    `_math.substitute` is a no-op) can share.
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
    # m-57: numbered by position, not by a dict keyed on id -- the same
    # reason `_tables.substitute` numbers captions by position instead of
    # a dict: two equations sharing an id would otherwise both look up
    # the *same* (last-written) dict entry and render the same number.
    # `sub` visits matches in document order, so a plain counter numbers
    # each one correctly regardless of what id it claims.
    counter = itertools.count(1)

    def _replace(match: "re.Match[str]") -> str:
        indent = match.group("indent")
        number = next(counter)
        return f"{indent}**Equation {number}:**\n{match.group('block')}"

    return _EQUATION_ASCII_RE.sub(_replace, text)


def _substitute_dollar(text: str, output_format: str) -> str:
    """`text` on every path `_math.substitute` has already run real math
    through: a real `equation` environment for a LaTeX-bound format, a
    written number beside the kept `$$...$$` for everything else."""
    # m-57: same positional fix as _substitute_ascii above. A LaTeX-bound
    # format's \label still keys off the id, not the number -- two
    # equations sharing an id still produce a multiply-defined label, but
    # that is a draft-authoring error `warnings` below already reports
    # ("declared by more than one equation"), not a numbering bug.
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
    """The phrase an `equationref` marker expands to, or `raw` unchanged
    if the id it names is not a declared equation."""
    if number is None:
        return raw
    if output_format in _LATEX_BOUND:
        return f"`Equation~\\ref{{eq:{eq_id}}}`{{=latex}}"
    return f"Equation {number}"


def substitute(text: str, output_format: str) -> str:
    """`text` with every marked equation numbered and every `equationref`
    resolved for `output_format`.

    `text` is whatever `_substitution.py`'s chain has produced by the time
    mathematics has been substituted -- the last step before this one, per
    this module's own docstring on why the order is fixed.
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

    Printed to stderr by `_draft_warnings`, like `_tables.warnings` and
    `_figure_captions.warnings` -- none of these stops a render.
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
