"""`focal-count`'s reading of a figure's source: which nodes carry an accent,
`cgkey`, `cgkeystate` or `cgfocus` (#1053, #1062, #1064). docs/TIKZ-STYLE.md:
"if two things are accented, neither is".

A scanner, since node options nest (`label={[red]above:x}`) and may follow the
name or `at (x,y)`. The node keyword is `_source.py`'s. Read from source, so an
accent reached via a figure-defined style is not seen (a documented limit).
"""

import re

from chitragupta._tex_comments import strip_comments
from chitragupta.review.figure_layout._source import _NODE_KEYWORD

_NODE_START_RE = re.compile(_NODE_KEYWORD)
# An accent as a whole style name (not `cgkeyish`). A state cannot take `cgkey`
# (built on the card), so it has `cgkeystate` (#1062); a timeline tick takes
# `cgfocus`, defined by the timeline scaffold (#1064).
_CGKEY_RE = re.compile(r"(?<![\w-])(?:cgkey(?:state)?|cgfocus)(?![\w-])")
_AT_RE = re.compile(r"at\b")


def cgkey_nodes(source: str) -> list[str]:
    """Every accented node's name in source order; `(unnamed)` for none."""
    return styled_nodes(source, _CGKEY_RE)


def styled_nodes(source: str, style: re.Pattern[str]) -> list[str]:
    """Every node whose options match `style`, in source order; `(unnamed)`
    for none. `unnamed-pic` (#1016) reads the `cgwell`s through it."""
    text = strip_comments(source)
    found = []
    for match in _NODE_START_RE.finditer(text):
        options, name, _ = declaration(text, match.end())
        if style.search(options):
            found.append(name or "(unnamed)")
    return found


def declaration(text: str, start: int) -> tuple[str, str, int]:
    """`(options, name, end)` of the node declared from `start`, `end` being
    the label's `{`, the statement's `;`, or the text's end. Shared with
    `_wording.py`. All option lists are collected however nested; the name is
    the first parenthesised group not introduced by `at`.
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
            # A calc position, `($(a)!0.5!(b)$)`, reads to its `$)`, not
            # its first `)`, as `_scan.declaration` reads it (#1112).
            calc = text[i + 1 : i + 2] == "$"
            end = text.find("$)", i) + 1 if calc else text.find(")", i)
            name = name or ("" if after_at else text[i + 1 : end].strip())
            after_at, i = False, len(text) if end <= 0 else end
        elif _AT_RE.match(text, i) and not text[i - 1 : i].isalnum():
            after_at = True
        elif char in "{;":
            break
        i += 1
    return "".join(options), name, i
