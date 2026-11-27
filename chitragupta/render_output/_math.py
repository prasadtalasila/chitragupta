"""Mathematics: ASCII in the draft, real equations in what pandoc sees.

§12 keeps quantities out of code spans (pandoc sets them as `\\texttt`), and
`$k = 4$` in the draft would land verbatim in `--format md`. So **the draft
stays ASCII and the LaTeX lives beside it, in the dossier's `math.md`**:

    | ASCII in the draft | LaTeX |
    | --- | --- |
    | `k = 4`            | `k = 4` |
    | `tau`              | `\\tau` |
    | `dW/dt = -W/tau`   | `\\frac{dW}{dt} = -\\frac{W}{\\tau}` |

The key is a backtick span already in the draft, so nothing is inferred: a
span with a row is mathematics, `as_of` without one stays code.

Substitution runs when the render reaches pandoc, and always writes `$...$`,
never `\\(...\\)`, which pandoc's Markdown reader mangles silently.

Imports are constrained: this package must render under bare `python`, so it
may not import `chitragupta/dossier/`; the location comes from
`config.mirrored_dir()`. `tests/test_render_output_math.py` pins it.
"""

import re
from pathlib import Path

from chitragupta import config


MAPPING_FILENAME = "math.md"

# A mapping row: | `<ascii>` | `<latex>` |, both cells backticked so the file
# stays readable as an ordinary Markdown table.
_ROW_RE = re.compile(r"^\|\s*`(?P<ascii>[^`]+)`\s*\|\s*`(?P<latex>[^`]+)`\s*\|\s*$", re.M)

# A row of the one-column "not mathematics" table (`404`). One cell where
# `_ROW_RE` needs two, so the two tables never read each other's rows.
_NOT_MATH_ROW_RE = re.compile(r"^\|\s*`(?P<ascii>[^`]+)`\s*\|\s*$", re.M)

# `## Symbols` (#1143), up to the next `## `, cut out before either table is
# read: a backticked meaning like `| `f_s` | `1 / T_s` |` would read as a row.
SYMBOLS_SECTION_RE = re.compile(r"^## Symbols[ \t]*$.*?(?=^## |\Z)", re.M | re.S)

# A key that is one symbol (`m`, `T_oil`, `x_hat`). A function application like
# `r(t)` is an expression and needs no meaning (#1143).
_BARE_SYMBOL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*$")

# Single-line, so one stray backtick cannot swallow a paragraph.
_SPAN_RE = re.compile(r"(?<!`)`(?P<body>[^`\n]+)`(?!`)")

# `<!-- math -->` then a fence: the marker tells an equation from a code block
# (§12). An indent is allowed for blockquotes and list items (#406).
_BLOCK_RE = re.compile(
    r"^(?P<indent>[ \t>]*)<!--[ \t]*math[ \t]*-->[ \t]*\n"
    r"(?P=indent)```[ \t]*\n(?P<body>.*?)^(?P=indent)```[ \t]*$",
    re.M | re.S,
)

# A marker whose fence is missing or malformed, counted separately so it is not
# reported as "this equation has no row".
_LONE_MARKER_RE = re.compile(r"^[ \t>]*<!--[ \t]*math[ \t]*-->[ \t]*$", re.M)

# Any fence, with its info string, so what is left after masking marked ones is
# a fence nobody claimed. The info string is in the opening pattern because
# matching a bare ``` would mis-pair a tagged block's closer with the next opener.
_FENCE_RE = re.compile(
    r"^(?P<indent>[ \t>]*)```(?P<tag>[^\n]*)\n(?P<body>.*?)^(?P=indent)```[ \t]*$",
    re.M | re.S,
)

# An underscore identifier (`as_of`): code, never a quantity, which keeps
# captured output and untagged SQL quiet. Cost: `k_day` in an unmarked fence
# goes unreported.
_SNAKE_CASE_RE = re.compile(r"\w_\w")

# Length is what separates a displayed equation from an ASCII figure, whose `->`
# arrows look math-shaped. Measured over this project's drafts: equations run
# 1-4 lines; the shortest false positive is 7. A long aligned array goes unreported.
_MAX_EQUATION_LINES = 4

# A citekey is never mathematics, but one with a hyphen run is math-shaped, so
# citekey shapes are excluded before the heuristic runs.
_CITEKEY_RE = re.compile(r"^[a-z][a-z0-9-]*(_[a-z0-9-]+)+_\d{4}(-\d+)?$")

# A symbol inside a mapped LaTeX value: a single letter, optionally subscripted,
# or a Greek control word. This closes the world -- see `_symbols_of`.
_SYMBOL_RE = re.compile(r"(?<![A-Za-z\\])([A-Za-z])(?![A-Za-z])")
_GREEK_RE = re.compile(r"\\([a-z]+)")
# A name in a mapping key: `T` of `T_k`, `SoC` of `OCV(SoC)`; not a subscript.
_ASCII_NAME_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9]*")
_GREEK_NAMES = frozenset(
    "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi "
    "pi rho sigma tau upsilon phi chi psi omega".split()
)


class MathMappingError(Exception):
    """A draft whose mathematics cannot be rendered as mathematics.

    Only for the certain cases (a marker with no mapping); heuristic gaps are
    reported and a wrong guess must not stop a render.
    """


def mapping_path(draft: Path) -> "Path | None":
    """Where `draft`'s `math.md` lives, or `None` if it can have none.

    Mirrors `dossier.dossier_dir()` without importing it:
    `content/drafts/dt/survey.md` -> `content/dossiers/dt/survey/math.md`.
    `None` outside `content/drafts/`.
    """
    mirrored = config.mirrored_dir(draft, config.DRAFTS_DIR, config.DOSSIERS_DIR)
    if mirrored is None:
        return None
    target = mirrored / draft.stem / MAPPING_FILENAME
    # As `dossier_dir` does: a symlinked topic directory would otherwise let
    # a render read a mapping from anywhere on disk.
    if not config.resolves_inside(target, config.DOSSIERS_DIR):
        return None
    return target


def mapping_text(draft: Path, path: "Path | None" = None) -> str:
    """`draft`'s `math.md`, or "" if it has none or can have none.

    `path` names the file directly, for a copy outside `content/drafts/` (#1194).
    """
    path = mapping_path(draft) if path is None else path
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def mapping_rows(text: str) -> "list[tuple[str, str]]":
    """Every ASCII -> LaTeX row in file order; a list so
    `_math_findings.duplicates()` sees a repeated key (#1116).
    """
    text = without_symbols(text)
    return [(m.group("ascii").strip(), m.group("latex").strip()) for m in _ROW_RE.finditer(text)]


def without_symbols(text: str) -> str:
    """`text` with its `## Symbols` section blanked, line count kept."""
    return SYMBOLS_SECTION_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def is_bare_symbol(key: str) -> bool:
    """Whether a mapping key is one symbol (needing a `## Symbols` meaning)."""
    return _BARE_SYMBOL_RE.match(key) is not None


def load_mapping(draft: Path) -> "dict[str, str]":
    """`draft`'s ASCII -> LaTeX table, empty if it has none.

    Empty, not raising: most drafts have no mapping. A repeated key keeps its
    last row.
    """
    return dict(mapping_rows(mapping_text(draft)))


def not_math(text: str) -> "frozenset[str]":
    rows = _NOT_MATH_ROW_RE.finditer(without_symbols(text))
    return frozenset(m.group("ascii").strip() for m in rows)


def _symbols_of(mapping: "dict[str, str]") -> "frozenset[str]":
    """Every symbol the mapping's LaTeX values mention.

    This closes the world: the gap heuristic keys on operators, so a bare `j`
    is invisible to it, yet single symbols were the dominant shape (~296 of 515
    conversions measured). A new symbol nearly always arrives inside an
    equation first, so a later bare mention can be flagged without guessing.

    Keys are read too (#1116), since `\\mathit{SoC}` gives the LaTeX scan
    nothing: one letter, a capital, or a Greek name counts. Lowercase words
    don't, or `level` in a formula key would flag every prose `level` (and
    citekey-shaped keys contribute nothing).
    """
    symbols: set[str] = set()
    for ascii_, latex in mapping.items():
        symbols.update(_SYMBOL_RE.findall(latex))
        symbols.update(g for g in _GREEK_RE.findall(latex) if g in _GREEK_NAMES)
        symbols.update(n for n in _ASCII_NAME_RE.findall(ascii_) if _symbol_like(n))
    return frozenset(symbols)


def _symbol_like(name: str) -> bool:
    return len(name) == 1 or name != name.lower() or name.lower() in _GREEK_NAMES


def _body_of(match: "re.Match[str]") -> str:
    """A fence's body, stripped of the indent every line carries: the
    blockquote or list indent belongs to the document, not the equation.
    """
    return re.sub(r"^[ \t>]*", "", match.group("body"), flags=re.M).strip()


def substitute(text: str, mapping: "dict[str, str]") -> str:
    """`text` with every mapped span and block rewritten as `$...$`.

    Blocks before spans, load-bearingly: the inline pass would otherwise
    rewrite symbols inside a fence body. Anything without a row is untouched.
    """

    def _block(match: "re.Match[str]") -> str:
        indent = match.group("indent")
        latex = mapping.get(_body_of(match))
        if latex is None:
            return match.group(0)
        return f"{indent}$$\n{indent}{latex}\n{indent}$$"

    text = _BLOCK_RE.sub(_block, text)

    # m-56: marked blocks are gone by now, so any fence left is a code example
    # whose spans the span pass below must not walk into.
    fence_spans = [(m.start(), m.end()) for m in _FENCE_RE.finditer(text)]

    def _in_a_fence(pos: int) -> bool:
        return any(start <= pos < end for start, end in fence_spans)

    def _span(match: "re.Match[str]") -> str:
        if _in_a_fence(match.start()):
            return match.group(0)
        latex = mapping.get(match.group("body").strip())
        return match.group(0) if latex is None else f"${latex}$"

    return _SPAN_RE.sub(_span, text)


def check(text: str, draft: Path, mapping: "dict[str, str]", path: "Path | None" = None) -> None:
    """Raises `MathMappingError` on a displayed equation that cannot render.

    Only certain cases: an unresolved marker would silently emit
    `\\begin{verbatim}`, the defect §12 exists to prevent (#406). No mapping
    file (what a draft rename looks like; there is no `dossier rename`) and a
    missing row are reported apart: different cause, different fix. `path`
    is the caller-named mapping file.
    """
    blocks = list(_BLOCK_RE.finditer(text))
    lone = len(_LONE_MARKER_RE.findall(text)) - len(blocks)
    if not blocks and not lone:
        return

    path = mapping_path(draft) if path is None else path
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
