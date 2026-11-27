"""Where a figure's labels are in its source (#1056): every node with its
name, label and whether it sits on a path, and the house macros that set text.

Read from source, so it holds whether or not the figure compiles. A scanner,
not a regex, because labels and options nest and a `;` or `node` inside a
label must not end or start anything. The node keyword is
`review/figure_layout/_source.py`'s, widened for `to node`; the scanners live
in `review/figure_layout/_scan.py` (#1112). `_twin.py` consumes this.
"""

import re
from dataclasses import dataclass

from chitragupta._tex_comments import strip_comments
from chitragupta.figure._block import _END_RE
from chitragupta.review.figure_layout._scan import blank_groups, braced, declaration, path_spans
from chitragupta.review.figure_layout._source import _NODE_KEYWORD

_NODE_START_RE = re.compile(_NODE_KEYWORD)
# Inside a path, `node` after any operator (`to`, `..`, `edge`), which
# `_source.py`'s lookbehind leaves out; a declaration follows it.
_PATH_NODE_RE = re.compile(r"(?<!\\)\bnode\b(?=\s*(?:[\[({]|at\b))")
_LOOP_VAR_RE = re.compile(r"(?:\\foreach\s*|/\s*)(\\[a-zA-Z]+)(?=[\s/]|in\b)")


# A name in a path: `(a)`, `(a.south)`, `([xshift=2mm]a.south)`. Not a
# coordinate, which has a comma, and not a calc `($...$)`.
_END_TOKEN_RE = re.compile(r"\(\s*(?:\[[^\]]*\]\s*)?([A-Za-z][\w-]*)(?:\.[\w ]+)?\s*\)")


def drawing(source: str) -> str:
    """The figure's drawing, comments stripped: everything after the house
    block, whose `\\node` lines define macros rather than draw."""
    ends = list(_END_RE.finditer(source))
    return strip_comments(source[ends[-1].end() :] if ends else source)


@dataclass(frozen=True)
class Node:
    name: str
    label: str
    on_path: bool
    ends: str  # `a->b` for a node on a path between two names, else ""


def nodes(text: str) -> list[Node]:
    """Every node declared in `text`, in source order. A keyword inside
    an earlier node's label (`{\\cglab{node}{a vertex}}`) is prose."""
    paths = path_spans(text)
    variables = "|".join(map(re.escape, _LOOP_VAR_RE.findall(text)))
    loop = re.compile(rf"(?:{variables})(?![a-zA-Z])" if variables else r"(?!)")
    keywords = {match.end() for match in _NODE_START_RE.finditer(text)}
    keywords |= {m.end() for s, e in paths for m in _PATH_NODE_RE.finditer(text, s, e)}
    found, covered = [], 0
    for end in sorted(keywords):
        declared = declaration(text, end)
        if end < covered or declared is None:
            continue
        name, label, covered = declared
        # A macro parameter, or a loop variable whose every pass sets a
        # different label: the source text is none of them.
        if "#" in label or loop.search(label):
            continue
        span = next((s for s in paths if s[0] < end < s[1]), None)
        child = text[: end - 4].rstrip().endswith("{")
        on_path = span is not None and not child and text[end - 5 : end] != "\\node"
        found.append(Node(name, label, on_path, _ends(text[span[0] : span[1]]) if on_path else ""))
    return found


def _ends(statement: str) -> str:
    """`first->last` named ends of a path statement, or `""`; labels and
    nodes placed on it are not ends."""
    text = re.sub(r"\bnode\b\s*(?:\[[^\]]*\]\s*)?\([^)]*\)", "node", blank_groups(statement))
    ends = _END_TOKEN_RE.findall(text)
    return f"{ends[0]}->{ends[-1]}" if len(ends) > 1 else ""


def macro_calls(text: str, macro: str, arity: int, name: int, label: int) -> list[tuple[str, str]]:
    """`(name, label)` from each full call of `\\<macro>` with `arity`
    braced arguments."""
    found = []
    for match in re.finditer(rf"\\{macro}(?![a-zA-Z])", text):
        args, _ = arguments(text, match.end(), arity)
        if len(args) == arity and "#" not in args[label]:
            found.append((args[name].strip(), args[label]))
    return found


def arguments(text: str, start: int, count: int) -> tuple[list[str], int]:
    """Up to `count` braced arguments from `start`, and the offset past
    the last; fewer where the next thing is not a brace."""
    args, i = [], start
    while len(args) < count:
        while i < len(text) and text[i].isspace():
            i += 1
        if text[i : i + 1] != "{":
            break
        arg, i = braced(text, i)
        args.append(arg)
    return args, i
