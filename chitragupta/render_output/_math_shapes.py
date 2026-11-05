"""Which backtick spans are mathematics, and by which rule.

`_math_findings` reports a span with no `math.md` row when it is
mathematics, and this module is how it decides. It used to be one
operator regex, `[=<>]|\\d\\s*[-+*/^]\\s*\\d`, which was wrong both ways:
it read the hyphens in `02-01-create-mock-physical-twin/` as subtraction
(#1115), and it could not see `-1`, `[1 0]` or `A * P_est * A^T + Q`
(#1116).

So the decision is a list of small named rules, not one alternation.
Each gets its own test, the warning names the rule that fired, and a
false alarm points at the one line to change. The order, which
`rule_for` follows:

1. **Known names** (`symbol`, `symbol-built`), first so a symbol the
   draft's own mathematics uses keeps the `symbol` kind it always had.
2. **Anchored shapes**, matched against the whole raw span. They run
   before step 3 because blanking can eat what they need: `dV/dSoC` is
   path-shaped.
3. **Blanking**: tokens that are plainly paths, file names, URL queries,
   placeholders, dates or versions become a space.
4. **Search shapes** over what is left, so a command line naming
   `02-01-s.md` is judged on the rest of the command.
5. **Context**: a single letter, a bare number, a bare Greek name. These
   are as often code (`404`, `beta`) as mathematics, so they count only
   in a draft that has a `math.md` -- an author who declared mapped
   mathematics -- and its "not mathematics" table is the remedy for the
   ones that are code.

Measured over 42 real drafts with 1,132 `math.md` rows, deleting each row
in turn: these rules notice 1,130 of the forgotten rows, against roughly
616 for the old regex, and they warn on no code span the old one did not
except six bare numbers, which the table silences. `plans/1115-1116-math-shape-rules.md`
has the method.

Imports `_math` only, one way, for the same reason `_math_findings` does.
"""

import re

from chitragupta.render_output._math import _GREEK_NAMES

_GREEK = "|".join(sorted(_GREEK_NAMES | {name.capitalize() for name in _GREEK_NAMES}))

# Step 2. Each is matched against the whole span.
_ANCHORED = (
    # Numbers only: `-m` and `-v` are command-line flags.
    ("signed-number", re.compile(r"^[-+]\s*\d")),
    # Numbers only: `[DIGITAL MODEL]` is a label.
    ("vector", re.compile(r"^\[\s*[-+]?\d[\d.eE]*(\s*[,;]?\s*[-+]?\d[\d.eE]*)*\s*\](\^T)?$")),
    # A `;` row separator is matrix syntax, never Python's.
    ("matrix", re.compile(r"^\[[^\]]*;[^\]]*\](\^T)?$")),
    ("derivative", re.compile(r"^d\^?\d?[A-Za-z]\w*/d[A-Za-z]\w*(\^\d)?$")),
    ("conditional", re.compile(r"^[A-Za-z]\w*\([^()]*\|[^()]*\)$")),
    # A subscript is what makes a Greek name mathematics in any draft;
    # a bare one is step 5's.
    ("greek-subscript", re.compile(rf"^({_GREEK})_\{{?[\w:,+-]+\}}?$")),
    # A short subscript on a plain name: `plant-1` is a name, and
    # `noauthor_digital_nodate-1` an undated citekey.
    ("index-step", re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]{1,3}[+-]1|_?\{\w+[+-]1\})$")),
    ("sci-number", re.compile(r"^[-+]?\d+(\.\d+)?e[-+]?\d+$")),
    ("number-list", re.compile(r"^[-+]?\d[\d.]*(\s*,\s*[-+]?\d[\d.]*)+$")),
)

# Step 3. A whole whitespace-separated token, made of path characters.
_TOKEN = r"(?:^|(?<=\s))[\w.~/-]*{}[\w.~/-]*(?=\s|$)"
_NOT_MATH = (
    # A slash and, anywhere in the token, a three-letter run:
    # `code/02-01-x/`. Three, so that `dW/dt` is not a path.
    re.compile(r"(?:^|(?<=\s))(?=[\w.~/-]*[A-Za-z]{3})[\w.~-]*/[\w.~/-]*(?=\s|$)"),
    re.compile(_TOKEN.format(r"\.[A-Za-z][A-Za-z0-9]{0,4}(?=\s|$)")),
    # A hyphen beside a word: `02-01-create`, `fastapi-0.115.12`.
    re.compile(_TOKEN.format(r"(?:[A-Za-z]{2}-|-[A-Za-z]{2})")),
    re.compile(r"[?&]\w+=\S*"),
    re.compile(r"<[A-Za-z_]+>"),
    # WRITING-STANDARDS.md §12: dates, versions and timestamps are not math.
    re.compile(r"\b\d{4}-\d{2}-\d{2}(T[\d:.]+Z?)?\b"),
    re.compile(r"\bv?\d+\.\d+\.\d+\b"),
)

# Step 4. Matched anywhere in the blanked span.
_SEARCH = (
    ("relation", re.compile(r"[=<>]")),
    ("digit-op-digit", re.compile(r"\d\s*[-+*/^]\s*\d")),
    ("star-caret", re.compile(r"[\w)\]]\s*[*^]\s*[-\w(\[{]")),
    # Spaced, so `Ctrl+C` stays a key name.
    ("spaced-op", re.compile(r"[\w)\]]\s+[-+/]\s+[-\w(\[]")),
)

# Step 5, only where a `math.md` exists.
_CONTEXT = (
    ("single-letter", re.compile(r"^[A-Za-z]$")),
    ("bare-number", re.compile(r"^[-+]?\d+(\.\d+)?$")),
    ("greek", re.compile(rf"^({_GREEK})$")),
)

_NAMED = re.compile(r"[A-Za-z][A-Za-z0-9]*(_\{?[\w:]+\}?)?")
_APPLIED = re.compile(r"(?P<name>[A-Za-z]\w*)?[(\[](?P<args>[^()\[\]]*)[)\]](\^T)?")
_NUMBER = re.compile(r"[-+]?\d[\d.]*")


def _base(name: str) -> str:
    """`T_k` -> `T`: the name a subscript hangs from."""
    return re.sub(r"^[-+]\s*", "", name).split("_", 1)[0]


def _known(span: str, symbols: "frozenset[str]") -> "str | None":
    """Step 1: the span is, or is built from, a name the draft already uses."""
    if span in symbols:
        return "symbol"
    bare = re.sub(r"^[-+]\s*", "", span)
    if _NAMED.fullmatch(bare) and _base(bare) in symbols:
        return "symbol-built"
    applied = _APPLIED.fullmatch(bare)
    if applied is None:
        return None
    args = [arg.strip() for arg in re.split(r"[,;]", applied["args"]) if arg.strip()]
    if applied["name"]:
        # A function counts by its own name: `sleep(5)` is code, and so
        # is `print(x)` beside a known `x`.
        return "symbol-built" if _base(applied["name"]) in symbols else None
    named = [arg for arg in args if _base(arg) in symbols]
    if named and all(arg in named or _NUMBER.fullmatch(arg) for arg in args):
        return "symbol-built"
    return None


def shape_rule(text: str) -> "str | None":
    """Steps 2-4: the rule that calls `text` mathematics by shape alone."""
    for name, rule in _ANCHORED:
        if rule.search(text):
            return name
    for blank in _NOT_MATH:
        text = blank.sub(" ", text)
    for name, rule in _SEARCH:
        if rule.search(text):
            return name
    return None


def rule_for(span: str, symbols: "frozenset[str]", has_mapping: bool) -> "str | None":
    """The name of the first rule that calls `span` mathematics, or None.

    `symbols` is `_math._symbols_of(mapping)`. `has_mapping` is whether
    the draft has a `math.md` at all, which is what the context rules
    turn on.
    """
    found = (symbols and _known(span, symbols)) or shape_rule(span)
    if found or not has_mapping:
        return found or None
    return next((name for name, rule in _CONTEXT if rule.search(span)), None)
