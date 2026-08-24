"""The two checks that read a figure's source and never compile it.

Node text length and the edge list are properties of what an author
wrote, not of what TeX drew, so they need no toolchain and run on any
host. Keeping them here rather than beside the geometry checks is what
lets most of this aid work -- and most of its tests run -- where TeX Live
is not installed.

Deliberately regex over TikZ rather than a LaTeX parser, matching how
`render_output/_figures.py` already reads these same files. Each pattern
below says what that costs it.
"""

import re

# docs/TIKZ-STYLE.md's conciseness rule, as the number it is written as.
# One place, because the report quotes it back to the reader.
MAX_NODE_WORDS = 15

# A TeX comment: `%` to the end of the line. Stripped before any pattern
# below runs, and before `_probe.node_names()` runs -- #404, where every
# symptom was a *wrong* answer rather than a missing one. A commented-out
# `\draw` was reported as an edge the figure claims; a commented-out
# `\node`'s label was measured for length; and worst, a comment merely
# *mentioning* a node declaration made the probe ask pdflatex for a shape
# nothing had drawn, so the aid reported a figure that compiles fine as
# one that does not.
#
# `\%` is a literal percent sign and does not start a comment, hence the
# lookbehind. `\\%` -- an escaped backslash followed by a real comment --
# is read the wrong way by that lookbehind and is left alone: it needs a
# character-by-character scan rather than a regex, and no figure this
# pipeline draws has produced one.
_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")

# The two spellings TikZ has for declaring a node, as one fragment
# because both define a real, probe-able name and nothing downstream
# cares which was used. `_probe.py` builds its own pattern on this rather
# than repeating it -- the two want different things from a node (that
# one only ever needs the name), but "what a node declaration looks like"
# is one fact and belongs in one place.
#
# The second branch is the `child { node (a) {A} }` form, and also the
# mid-path label `-- node (mid) {x}`. The lookbehind is the guard that
# makes widening safe: without it the bare keyword matches prose inside a
# label -- `\node (a) {a node (of sorts)}` would declare a node called
# `of sorts`, and the probe would then fail to compile the figure over
# it, which is the very defect this widening is fixing. Requiring the
# character before the keyword to be one a label cannot start with
# ( `{`, a path operator, a closing bracket ) admits every real
# declaration and no sentence.
_NODE_KEYWORD = r"(?:\\node|(?<=[{;\]>|)\-])\s*node)"

_NODE_RE = re.compile(
    _NODE_KEYWORD + r"\s*(?:\[[^\]]*\])?\s*\((?P<name>[^)]+)\)"
    r"(?:\s*at\s*\([^)]*\))?\s*\{(?P<label>.*?)\}",
    re.DOTALL,
)


def strip_comments(source: str) -> str:
    """`source` with every TeX comment removed.

    The first thing every reader of a figure's source here does. See
    `_COMMENT_RE` for what that fixes and what it deliberately does not.
    """
    return _COMMENT_RE.sub("", source)


# A `\draw`/`\path` statement, up to its terminating semicolon.
_PATH_STATEMENT_RE = re.compile(r"\\(?:draw|path)\b(?P<body>[^;]*);", re.DOTALL)

# Every parenthesised token in such a statement, in source order.
_PAREN_TOKEN_RE = re.compile(r"\(([^)]*)\)")

# A bare coordinate rather than a node name: `(0,0)`, `(1.5, -2)`,
# `(2cm,0)`. `\draw (0,0) -- (2,0);` draws a line between two points and
# claims nothing about what connects to what, so reporting it as an edge
# would be noise in the one check that exists to be read closely.
#
# The comma is what identifies it: a TikZ node name cannot contain one,
# and a coordinate always does. That is deliberately broader than a
# numeric test, because a `\foreach` body writes coordinates like
# `(\x,-0.12)` and `(\x,\y)` -- macro-valued, not numeric, and still not
# an edge between two named things. A real drafted figure hit exactly
# this and reported `\x,-0.12 -> \x,0.12` as an edge.
_COORDINATE_RE = re.compile(r"^[^)]*,")

# An un-unrolled `\foreach` loop variable used as a coordinate on its
# own, with no comma to be caught by `_COORDINATE_RE`: `\draw
# (\p)--(\q);` inside `\foreach \p in {...}`. A TikZ node name is never
# spelled with a leading backslash -- that syntax is reserved for a
# macro -- so this token is the same "macro-valued, not a name" case,
# just without the second axis that gives it a comma. Left unexcluded,
# it reached a real report as the literal edge `\p -> \q`, which then
# failed to compile when the report itself was rendered: pandoc passes
# `\p` through and pdflatex rejects it as an undefined control sequence
# (#389).
_MACRO_TOKEN_RE = re.compile(r"^\s*\\")

# A LaTeX control sequence in a node label. Stripped before counting
# words: `\textbf{alpha}` reads as one word, and counting the macro as a
# second would flag figures a human would call concise.
_CONTROL_SEQUENCE_RE = re.compile(r"\\[a-zA-Z]+\s*")


def _label_words(label: str) -> int:
    """How many words a reader sees in a node's label.

    Control sequences are stripped rather than counted, and braces with
    them, so `\\textbf{alpha} beta` is two words -- the count the
    conciseness rule is actually about.
    """
    plain = _CONTROL_SEQUENCE_RE.sub(" ", label).replace("{", " ").replace("}", " ")
    return len(plain.split())


def overlong_nodes(source: str) -> list[tuple[str, int]]:
    """`(node name, word count)` for every node past `MAX_NODE_WORDS`.

    Binary and safe for anything to act on: a node either exceeds the
    line or it does not. The fix is never to shrink the font --
    docs/TIKZ-STYLE.md is explicit that doing so is the same defect
    wearing a smaller typeface -- but to cut the text or split the node.
    """
    found = []
    for match in _NODE_RE.finditer(strip_comments(source)):
        count = _label_words(match.group("label"))
        if count > MAX_NODE_WORDS:
            found.append((match.group("name").strip(), count))
    return found


def edge_list(source: str) -> list[tuple[str, str]]:
    """Every node-to-node connection the figure draws, in source order.

    Reported for a human to confirm against the prose, never judged:
    nothing here knows which edges *should* exist, which is exactly why
    it is the author who has to read it.

    A chain (`\\draw (a) -- (b) -- (c);`) becomes consecutive pairs, and
    the operator between the tokens is deliberately ignored -- `--`,
    `->` and `edge` are rendering differences over one claim about what
    connects to what. Bare coordinates are dropped: a line between two
    points is not an edge between two named things.

    **This is a regex over TikZ, not a parser of it, and the difference
    matters more here than anywhere else in this package.** The other
    checks fail safe: an under-counted node label is a finding missed, and
    a missed finding is what an advisory aid does anyway. This one is
    *read as a list of what the figure claims*, so a wrong entry is worse
    than a missing one -- an author confirming an edge list against their
    prose is trusting it to be the figure's actual wiring.

    What that costs, stated so the next reader does not have to
    rediscover it:

    - **Only `\\draw` and `\\path` are scanned.** An edge drawn by a
      library that wraps them -- `\\graph`, a `matrix` with `\\arrow`,
      `chains`'s `join` -- is invisible here, so the list is silently
      short rather than wrong. A missing edge and a figure that genuinely
      has none look identical.
    - **Anchors ride along.** `(a.south) -- (b.north)` reports
      `a.south -> b.north`, not `a -> b`. Real drafted figures do this
      often enough to see, and stripping the anchor would be a guess
      about which side of the dot is a node name.
    - **`to[...]`/`edge[...]` options are not distinguished** from the
      nodes around them, and a `node` placed *on* a path (a mid-edge
      label) is a parenthesised token like any other only when it is
      named.
    - **A `\\foreach` body is read literally, once.** The loop is not
      unrolled, so an edge drawn n times appears once with its macro
      names intact -- which is why anything containing a comma, or
      starting with a backslash, is dropped as a coordinate rather than
      reported: a real node name is never spelled either way.

    Widening any of these means parsing TikZ's path grammar properly.
    That is a real piece of work and not obviously worth it: the check
    exists because a *wrong* edge is invisible to every check over pixels,
    and it earns that on the ordinary `\\draw (a) -- (b);` figures this
    pipeline actually produces. Verified against every figure in this
    repository's own `content/drafts/` -- correct on all of them, which is
    evidence about those figures and not a proof about TikZ.
    """
    edges = []
    for statement in _PATH_STATEMENT_RE.finditer(strip_comments(source)):
        names = [
            token.strip()
            for token in _PAREN_TOKEN_RE.findall(statement.group("body"))
            if token.strip()
            and not _COORDINATE_RE.match(token)
            and not _MACRO_TOKEN_RE.match(token)
        ]
        edges += list(zip(names, names[1:]))
    return edges
