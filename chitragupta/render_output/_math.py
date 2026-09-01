"""Mathematics: ASCII in the draft, real equations in what pandoc sees.

`docs/WRITING-STANDARDS.md` §12 keeps a quantity out of a code span,
because pandoc turns `` `k = 4` `` into `\\texttt{k\\ =\\ 4}` -- upright,
typewriter, with `=` set as ordinary text -- while a real equation two
paragraphs away becomes `\\[...\\]`. One symbol, two typefaces, and the
Markdown source gives no hint which you are looking at.

Writing `$k = 4$` in the draft fixes the pdf and costs the Markdown:
`--format md` never reaches pandoc (docs/RENDERING-FLOW.md), so those
delimiters land verbatim in `content/rendered/`. Where that Markdown is
read rather than being a step on the way to a pdf, this module is the
other answer -- **the draft stays ASCII and the LaTeX lives beside it, in
the dossier's `math.md`**:

    | ASCII in the draft | LaTeX |
    | --- | --- |
    | `k = 4`            | `k = 4` |
    | `tau`              | `\\tau` |
    | `dW/dt = -W/tau`   | `\\frac{dW}{dt} = -\\frac{W}{\\tau}` |

The key is the backtick span **already in the draft**, so no new syntax
is added and nothing is inferred: a span with a row is mathematics
because the mapping says so, and `as_of` stays code because it has no
row. That is the whole reason this can be mechanical where a regex over
`` `k` `` versus `` `as_of` `` could not.

**One predicate, not a per-format table.** Substitution runs when the
render reaches pandoc, which is the line RENDERING-FLOW.md already draws.
`$...$` is what gets written -- *never* `\\(...\\)`, which pandoc's
Markdown reader does not read as mathematics at all: handed
`A $k = 4$ and B \\(k = 4\\)` it emits `A \\(k = 4\\) and B (k = 4)`, and
the second silently loses its backslashes. Each writer then renders
`$...$` in its own idiom, which is what makes the output format-native
rather than LaTeX-shaped.

**Imports are constrained, deliberately.** `_paths.py` commits this
package to stdlib plus `config`/`citation_gate`/`references` so a genre
skill can render under bare `python`, which rules out importing
`chitragupta/dossier/`. The dossier's *location* comes from
`config.mirrored_dir()`, which is inside that set -- a
module-dependency boundary, not a data one. Do not "simplify" this by
importing the dossier package; `tests/test_render_output_math.py` pins it.
"""

import re
from pathlib import Path

from chitragupta import config


MAPPING_FILENAME = "math.md"

# A row of the mapping table: | `<ascii>` | `<latex>` |. Both cells are
# backticked so a LaTeX value containing a pipe would still need escaping,
# and so the file stays readable as an ordinary Markdown table.
_ROW_RE = re.compile(r"^\|\s*`(?P<ascii>[^`]+)`\s*\|\s*`(?P<latex>[^`]+)`\s*\|\s*$", re.M)

# An inline code span. Deliberately single-line: a span never spans a
# blank line, and allowing it to would let one stray backtick swallow a
# paragraph.
_SPAN_RE = re.compile(r"(?<!`)`(?P<body>[^`\n]+)`(?!`)")

# `<!-- math -->` followed by a fence. The marker is what disambiguates a
# displayed equation from a code block -- see §12. An indent is allowed
# so the pair can sit inside a blockquote or a list item, which is where
# the one real-world instance was found (#406).
_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t>]*)<!--[ \t]*math[ \t]*-->[ \t]*\n"
    r"(?P=indent)```[ \t]*\n(?P<body>.*?)^(?P=indent)```[ \t]*$",
    re.M | re.S,
)

# A marker whose fence is missing or malformed -- counted separately, so
# "you wrote a marker and no equation followed" is not reported as "this
# equation has no row".
_LONE_MARKER_RE = re.compile(r"^[ \t>]*<!--[ \t]*math[ \t]*-->[ \t]*$", re.M)

# Any fence, with its info string. `_BLOCK_RE` above finds the ones a
# marker claims; this finds all of them, so what is left over after the
# marked ones are masked out is a fence nobody has said anything about.
#
# The info string is part of the *opening* pattern deliberately. Match a
# bare ``` instead and the delimiters stop pairing: a tagged block's
# closing fence reads as an opener, pairs with the next block's opener,
# and the equation between them is swallowed as a body.
_FENCE_RE = re.compile(
    r"^(?P<indent>[ \t>]*)```(?P<tag>[^\n]*)\n(?P<body>.*?)^(?P=indent)```[ \t]*$",
    re.M | re.S,
)

# An underscore identifier: `as_of`, `predicted_next`, `sensor_id`. Code,
# never a quantity -- the same distinction §12 draws for spans, applied
# to a whole fence body. It is what keeps a tutorial's captured output
# and an untagged SQL query quiet, both of which the operator heuristic
# alone reads as mathematics. The cost is an ASCII subscript (`k_day`)
# in an *unmarked* fence, which goes unreported.
_SNAKE_CASE_RE = re.compile(r"\w_\w")

# A displayed equation is short, and that is the whole discriminator
# against the other thing a bare fence holds: an ASCII figure. A box
# border is not math-shaped, but a `->` arrow inside a 26-line diagram
# is, and the operator heuristic reads the body rather than the line.
#
# Measured over every untagged fence in this project's own drafts: the
# genuine equations run 1 to 4 lines, and the shortest false positive --
# a 7-line pseudocode listing -- is clear of the bar with margin to
# spare. The cost is a long aligned array left unreported, which is the
# shape a marker is worth writing by hand anyway.
_MAX_EQUATION_LINES = 4

# Enough of an operator to call a span a quantity rather than an
# identifier. Necessarily heuristic; the symbol closure below is what
# catches a bare `k`, which this cannot.
_MATH_SHAPED_RE = re.compile(r"[=<>]|\d\s*[-+*/^]\s*\d")

# A citekey is never mathematics, and `bottjer_review_2023` is otherwise
# math-shaped to nothing here -- but `zech_digital-twins-as--service_2024`
# is, once a hyphen run is involved. Excluded by shape, before the
# heuristic runs.
_CITEKEY_RE = re.compile(r"^[a-z][a-z0-9-]*(_[a-z0-9-]+)+_\d{4}(-\d+)?$")

# A symbol inside a mapped LaTeX value: a single letter, optionally
# subscripted, or a Greek control word. This is what closes the world --
# see `_symbols_of`.
_SYMBOL_RE = re.compile(r"(?<![A-Za-z\\])([A-Za-z])(?![A-Za-z])")
_GREEK_RE = re.compile(r"\\([a-z]+)")
_GREEK_NAMES = frozenset(
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
    "pi rho sigma tau upsilon phi chi psi omega".split()
)


class MathMappingError(Exception):
    """A draft whose mathematics cannot be rendered as mathematics.

    Raised only for the cases that are *certain* rather than heuristic --
    a `<!-- math -->` marker with no mapping to resolve it. A gap in the
    inline spans is reported and carried on with, because "this span
    looks like a quantity" is a guess and a wrong guess must not stop a
    render.
    """


def mapping_path(draft: Path) -> "Path | None":
    """Where `draft`'s `math.md` lives, or `None` if it can have none.

    Mirrors `dossier.dossier_dir()` without importing it (see the module
    docstring): `content/drafts/dt/survey.md` maps to
    `content/dossiers/dt/survey/math.md`. `None` for a draft outside
    `content/drafts/`, which is a review report or another caller's file
    rather than something a dossier was ever written for.
    """
    mirrored = config.mirrored_dir(draft, config.DRAFTS_DIR, config.DOSSIERS_DIR)
    if mirrored is None:
        return None
    target = mirrored / draft.stem / MAPPING_FILENAME
    # Same check `dossier_dir` makes, for the same reason: a topic
    # directory that is itself a symlink out of the tree would otherwise
    # let a render read a mapping from anywhere on disk.
    if not config.resolves_inside(target, config.DOSSIERS_DIR):
        return None
    return target


def load_mapping(draft: Path) -> "dict[str, str]":
    """`draft`'s ASCII -> LaTeX table, empty if it has none.

    Empty rather than raising, because an absent mapping is the ordinary
    state of every draft written before this existed and of every draft
    with no mathematics in it. `_math_findings.findings()` is what tells
    those two apart, through the `has_mapping_file` flag it takes.
    """
    path = mapping_path(draft)
    if path is None or not path.is_file():
        return {}
    return {
        m.group("ascii").strip(): m.group("latex").strip()
        for m in _ROW_RE.finditer(path.read_text(encoding="utf-8"))
    }


def _symbols_of(mapping: "dict[str, str]") -> "frozenset[str]":
    """Every symbol the mapping's LaTeX values mention.

    This is what closes the world. The gap heuristic keys on an operator,
    so a bare `` `j` `` introduced by a revision is invisible to it -- and
    in the corpus this was measured against, single symbols were the
    *dominant* shape (roughly 296 of 515 conversions: `k` 55, `h` 50,
    `Ts` 47, `g` 42). Since a genuinely new symbol almost always arrives
    inside an equation, it arrives in the value space in the same
    revision, and a later bare mention of it can be flagged with no
    guessing at all.
    """
    symbols: set[str] = set()
    for latex in mapping.values():
        symbols.update(_SYMBOL_RE.findall(latex))
        symbols.update(g for g in _GREEK_RE.findall(latex) if g in _GREEK_NAMES)
    return frozenset(symbols)


def _body_of(match: "re.Match[str]") -> str:
    """A fence's body, stripped of the indent every line carries.

    The indent is whatever put the fence inside a blockquote or a list
    item, so it belongs to the document rather than to the equation --
    a mapping row keyed on `> C x I > F` would be keyed on the quoting.
    """
    return re.sub(r"^[ \t>]*", "", match.group("body"), flags=re.M).strip()


def substitute(text: str, mapping: "dict[str, str]") -> str:
    """`text` with every mapped span and block rewritten as `$...$`.

    Blocks before spans, and that order is load-bearing: inline
    substitution run first walks into a fence body and rewrites the
    symbols there, corrupting the block before the display rule ever sees
    it. Anything without a row is left exactly as it was.
    """

    def _block(match: "re.Match[str]") -> str:
        indent = match.group("indent")
        latex = mapping.get(_body_of(match))
        if latex is None:
            return match.group(0)
        return f"{indent}$$\n{indent}{latex}\n{indent}$$"

    text = _BLOCK_RE.sub(_block, text)

    # m-56: every marked math block is gone from `text` by now (rewritten
    # to `$$...$$` above), so any fence _FENCE_RE still finds here is a
    # genuine code example -- a tutorial showing its own Markdown source,
    # say -- whose backtick spans are code, not draft prose, and must not
    # be walked into by the span pass below.
    fence_spans = [(m.start(), m.end()) for m in _FENCE_RE.finditer(text)]

    def _in_a_fence(pos: int) -> bool:
        return any(start <= pos < end for start, end in fence_spans)

    def _span(match: "re.Match[str]") -> str:
        if _in_a_fence(match.start()):
            return match.group(0)
        latex = mapping.get(match.group("body").strip())
        return match.group(0) if latex is None else f"${latex}$"

    return _SPAN_RE.sub(_span, text)


def check(text: str, draft: Path, mapping: "dict[str, str]") -> None:
    """Raises `MathMappingError` on a displayed equation that cannot render.

    Only the certain cases, never the heuristic ones. A `<!-- math -->`
    marker is a statement by the author that a displayed equation is
    here; if it cannot be resolved, the render would silently emit
    `\\begin{verbatim}` instead of an equation, which is the exact defect
    §12 exists to prevent (#406).

    The two are reported apart because they mean different things. No
    mapping *file* at all, for a draft that markers say has mathematics,
    is what renaming a draft looks like -- the dossier is tied to the
    draft by path alone and there is no `dossier rename`. A file that
    exists but lacks the row is an unmaintained mapping. Different cause,
    different fix.
    """
    blocks = list(_BLOCK_RE.finditer(text))
    lone = len(_LONE_MARKER_RE.findall(text)) - len(blocks)
    if not blocks and not lone:
        return

    path = mapping_path(draft)
    if path is None or not path.is_file():
        raise MathMappingError(
            f"{draft.name} marks a displayed equation with `<!-- math -->`, but "
            f"there is no {path if path else MAPPING_FILENAME}. If the draft was "
            "renamed or moved, its dossier did not follow -- the two are tied by "
            "path alone."
        )
    if lone > 0:
        raise MathMappingError(
            f"{draft.name} has {lone} `<!-- math -->` marker(s) with no fenced "
            "block after them. The marker names the equation that follows it."
        )
    missing = [body for body in (_body_of(m) for m in blocks) if body not in mapping]
    if missing:
        listed = ", ".join(f"`{m}`" for m in missing)
        raise MathMappingError(
            f"{draft.name}: displayed equation(s) with no row in {MAPPING_FILENAME}: "
            f"{listed}. Without a row the render emits verbatim text, not mathematics."
        )
