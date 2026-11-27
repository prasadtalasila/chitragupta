"""Which backtick spans are mathematics, and by which rule.

A single operator regex was wrong both ways (#1115, #1116), so the decision is
a list of small named rules, each tested and named in the warning. Order:

1. **Known names** (`symbol`, `symbol-built`), first so a draft's symbols keep their kind.
2. **Anchored shapes** on the whole raw span, before blanking eats what they need.
3. **Blanking** paths, file names, URL queries, placeholders, dates and versions.
4. **Search shapes** over what is left.
5. **Context**: single letters, bare numbers, bare Greek names -- as often code
   as maths, so only in a draft with a `math.md`, whose "not mathematics"
   table silences the code ones.

Over 42 real drafts these notice 1,130 of 1,132 deleted `math.md` rows versus
~616 for the old regex (method: `plans/1115-1116-math-shape-rules.md`).
"""

import re

from chitragupta.render_output._math import _GREEK_NAMES

_GREEK = "|".join(sorted(_GREEK_NAMES | {name.capitalize() for name in _GREEK_NAMES}))

_ANCHORED = (
    # Numbers only: `-m` and `-v` are command-line flags.
    ("signed-number", re.compile(r"^[-+]\s*\d")),
    # Numbers only: `[DIGITAL MODEL]` is a label; two or more: `[1]` is a reference.
    ("vector", re.compile(r"^\[\s*[-+]?\d[\d.eE]*(\s*[,;]?\s*[-+]?\d[\d.eE]*)+\s*\](\^T)?$")),
    # A `;` row separator is matrix syntax, never Python's.
    ("matrix", re.compile(r"^\[[^\]]*;[^\]]*\](\^T)?$")),
    ("derivative", re.compile(r"^d\^?\d?[A-Za-z]\w*/d[A-Za-z]\w*(\^\d)?$")),
    ("conditional", re.compile(r"^[A-Za-z]\w*\([^()]*\|[^()]*\)$")),
    # A subscript makes a Greek name mathematics in any draft; a bare one is step 5's.
    ("greek-subscript", re.compile(rf"^({_GREEK})_\{{?[\w:,+-]+\}}?$")),
    # A one-character subscript on a plain name: `plant-1` is a name,
    # `plant_id+1` code, and an undated citekey's `-1` suffix is neither.
    ("index-step", re.compile(r"^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9][+-]1|_?\{\w+[+-]1\})$")),
    ("sci-number", re.compile(r"^[-+]?\d+(\.\d+)?e[-+]?\d+$")),
    # A space after each comma: `1,000` is one number.
    ("number-list", re.compile(r"^[-+]?\d[\d.]*(\s*,\s+[-+]?\d[\d.]*)+$")),
)

_TOKEN = r"(?:^|(?<=\s))[\w.~/-]*{}[\w.~/-]*(?=\s|$)"
_NOT_MATH = (
    # A slash and a three-letter run: `code/02-01-x/`. Three, so `dW/dt` is not a path.
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
        # A function counts by its own name: `sleep(5)` and `print(x)` are code.
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

    `has_mapping` (the draft has a `math.md`) gates the context rules.
    """
    found = (symbols and _known(span, symbols)) or shape_rule(span)
    if found or not has_mapping:
        return found or None
    return next((name for name, rule in _CONTEXT if rule.search(span)), None)
