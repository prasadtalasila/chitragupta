"""Scanners over a figure's TikZ source where one regex is not enough
(#1112): a brace group, a node's declaration, a path statement.

A node's label and options nest, and the characters that end things in
TikZ's grammar -- `;` ends a statement, `(` opens a name -- are ordinary
text inside a label. `node[cgtag] {0.1 (repaired)}` is not a node called
`repaired`, and `node {events in;\\\\actions out}` does not end its path.
A regex over the statement (`[^;]*`, `\\([^)]*\\)`) read both wrong.

Below `_source.py` and `figure/_labels.py`, which both read through it:
`_labels.py` had the declaration scanner first (#1056) and it moved down
here so the probe's node names and `figure check`'s labels agree.
"""

import re

_PATH_RE = re.compile(r"\\(?:draw|path)\b")
# `at` as a word, which makes the next parenthesised group a position.
_AT_RE = re.compile(r"at\b")


def braced(text: str, start: int) -> tuple[str, int]:
    """The content of the `{...}` opening at `start`, and the offset past
    it. A group left open runs to the end of the text."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        if not depth:
            return text[start + 1 : i], i + 1
        i += 1
    return text[start + 1 :], len(text)


def declaration(text: str, start: int) -> tuple[str, str, int] | None:
    """`(name, label, end of label)` of the node declared from `start`,
    or `None` where its label never opens. Options nest, the first
    parenthesised group not introduced by `at` is the name, before or
    after the position (`(b) at (0,-2)`, `at (0,-2) (b)`), and a calc
    `($...$)` is read to its close."""
    name, depth, after_at, i = "", 0, False, start
    while i < len(text):
        char = text[i]
        if depth:
            depth += {"[": 1, "]": -1}.get(char, 0)
        elif char == "[":
            depth = 1
        elif char == "(":
            calc = text[i + 1 : i + 2] == "$"
            end = text.find("$)", i) + 1 if calc else text.find(")", i)
            if end <= 0:
                return None
            name = name or ("" if after_at else text[i + 1 : end].strip())
            after_at, i = False, end
        elif _AT_RE.match(text, i) and not text[i - 1 : i].isalnum():
            after_at = True
        elif char == "{":
            return name, *braced(text, i)
        elif char == ";":
            return None
        i += 1
    return None


def path_spans(text: str) -> list[tuple[int, int]]:
    """Each `\\draw`/`\\path` statement's body, as offsets from just
    after its keyword to its `;`. A `;` in a braced label does not end
    it, and an escaped `\\{` or `\\;` is text."""
    spans = []
    for match in _PATH_RE.finditer(text):
        i = match.end()
        while i < len(text) and text[i] != ";":
            if text[i] == "\\":
                i += 2
                continue
            i = braced(text, i)[1] if text[i] == "{" else i + 1
        spans.append((match.end(), i))
    return spans


def path_bodies(text: str) -> list[str]:
    """Each `\\draw`/`\\path` statement after its keyword, up to its
    `;`, with every brace group emptied to `{}`: what is left is the
    path's options, points and operators, never a label's text."""
    return [blank_groups(text[start:end]) for start, end in path_spans(text)]


def blank_groups(body: str) -> str:
    """`body` with every outermost brace group emptied to `{}`."""
    out, i = [], 0
    while i < len(body):
        if body[i] == "{":
            i = braced(body, i)[1]
            out.append("{}")
            continue
        out.append(body[i])
        i += 1
    return "".join(out)
