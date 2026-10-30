"""`focal-count`'s reading of a figure's source: which nodes carry an
accent, the `cgkey` style or the accented state `cgkeystate` (#1053,
#1062). docs/TIKZ-STYLE.md: "if two things are accented, neither is".

A scanner rather than one regex, because a node's options are not a
regular language. They nest (`label={[red]above:x}`), so a `[^\\]]*`
stops at the inner `]` and never reaches a `cgkey` after it. They may
also come after the name or after `at (x,y)`, and a coordinate in
parentheses must not be read as the node's name. The declaration's own
keyword is `_source.py`'s, so what counts as "a node" stays one fact.

Read from source, so a `cgkey` reached only through a style the figure
defines itself is not seen: a limit stated in the rule's documentation
rather than guessed at here.
"""

import re

from chitragupta._tex_comments import strip_comments
from chitragupta.review.figure_layout._source import _NODE_KEYWORD

_NODE_START_RE = re.compile(_NODE_KEYWORD)
# `cgkey` or `cgkeystate` as a whole style name: not `cgkeyish`, not
# `my-cgkey`. A state cannot take `cgkey` itself, which is built on the
# card, so the state has its own accent and both count (#1062).
_CGKEY_RE = re.compile(r"(?<![\w-])cgkey(?:state)?(?![\w-])")
# `at` as a word, which makes the next parenthesised group a position.
_AT_RE = re.compile(r"at\b")


def cgkey_nodes(source: str) -> list[str]:
    """The name of every node whose options include an accent, in source
    order; `(unnamed)` for one with no name."""
    text = strip_comments(source)
    keyed = []
    for match in _NODE_START_RE.finditer(text):
        options, name, _ = declaration(text, match.end())
        if _CGKEY_RE.search(options):
            keyed.append(name or "(unnamed)")
    return keyed


def declaration(text: str, start: int) -> tuple[str, str, int]:
    """`(options, name, end)` of the node declared from `start` up to its
    label, `end` being where the label's `{` (or the statement's `;`, or
    the text's end) is. Shared with `_wording.py`, which reads the label.

    Every bracketed option list is collected, however deeply it nests,
    and the first parenthesised group not introduced by `at` is the
    name. The label's opening brace, or the statement's `;`, ends it.
    """
    options, name, depth, after_at, i = [], "", 0, False, start
    while i < len(text):
        char = text[i]
        if depth:
            depth += {"[": 1, "{": 1, "]": -1, "}": -1}.get(char, 0)
            options.append(char if depth else ",")
        elif char == "[":
            depth = 1
        elif char == "(":
            end = text.find(")", i)
            name = name or ("" if after_at else text[i + 1 : end].strip())
            after_at, i = False, len(text) if end < 0 else end
        elif _AT_RE.match(text, i):
            after_at = True
        elif char in "{;":
            break
        i += 1
    return "".join(options), name, i
