"""The four checks that read a figure's source and never compile it.

Node text length, the edge list, stranded arrowheads and hand-rolled
library loads need no toolchain, so most of this aid runs where TeX Live
is not installed. Regex over TikZ, as `render_output/_figures.py` reads
these files; each pattern says what that costs.
"""

import re

from chitragupta._tex_comments import strip_comments
from chitragupta.review.figure_layout._scan import (
    NESTING,
    blank_groups,
    declaration,
    path_bodies,
    path_spans,
)
from chitragupta.review.figure_layout._tips import house_styles, style_definitions, tips

# docs/TIKZ-STYLE.md's conciseness rule; the report quotes it back.
MAX_NODE_WORDS = 15

# `strip_comments` is re-exported: its home is now `chitragupta/_tex_comments.py`
# (#781, #1013), but readers of figure source look for it here.
__all__ = [
    "MAX_NODE_WORDS",
    "edge_list",
    "loads_library_by_hand",
    "named_nodes",
    "overlong_nodes",
    "stranded_arrowheads",
    "strip_comments",
]

# Both node spellings define a probe-able name. The second branch covers
# `child { node (a) {A} }` and mid-path `-- node (mid) {x}`; the lookbehind
# keeps `node` inside a label (`{a node (of sorts)}`) from declaring a
# node, which would make the probe fail to compile the figure.
_NODE_KEYWORD = r"(?:\\node|(?<=[{;\]>|)\-])\s*node)"

_NODE_START_RE = re.compile(_NODE_KEYWORD)


def named_nodes(source: str) -> list[tuple[str, str]]:
    """`(name, label)` of every named node the source declares, in source
    order, comments stripped; `_scan.declaration` reads it (#1112)."""
    text = strip_comments(source)
    found = []
    for match in _NODE_START_RE.finditer(text):
        declared = declaration(text, match.end())
        if declared is not None and declared[0]:
            found.append((declared[0], declared[1]))
    return found


_PAREN_TOKEN_RE = re.compile(r"\(([^)]*)\)")

# An `edge` or a named on-path node makes consecutive tokens not the two
# ends of one line. `cgedge` has no word boundary before `edge`.
_ON_PATH_RE = re.compile(r"\bedge\b|\bnode\b\s*(?:\[[^\]]*\]\s*)?\(")

# A coordinate, not a node name: a name can never contain a comma, and a
# comma also catches macro-valued `\foreach` coordinates like `(\x,-0.12)`
# that a numeric test would report as an edge.
_COORDINATE_RE = re.compile(r"^[^)]*,")

# A lone loop variable `(\p)`: node names never start with a backslash,
# and `\p -> \q` in a report broke its pdf render (#389).
_MACRO_TOKEN_RE = re.compile(r"^\s*\\")

# Stripped before counting words, so `\textbf{alpha}` is one word.
_CONTROL_SEQUENCE_RE = re.compile(r"\\[a-zA-Z]+\s*")


def _label_words(label: str) -> int:
    """How many words a reader sees in a node's label."""
    plain = _CONTROL_SEQUENCE_RE.sub(" ", label).replace("{", " ").replace("}", " ")
    return len(plain.split())


def overlong_nodes(source: str) -> list[tuple[str, int]]:
    """`(node name, word count)` for every node past `MAX_NODE_WORDS`.

    The fix is to cut the text or split the node, never a smaller font
    (docs/TIKZ-STYLE.md).
    """
    return [
        (name, count)
        for name, label in named_nodes(source)
        if (count := _label_words(label)) > MAX_NODE_WORDS
    ]


def edge_list(source: str) -> list[tuple[str, str]]:
    """Every node-to-node connection the figure draws, in source order.

    Reported for the author to confirm against the prose, never judged. A
    chain becomes consecutive pairs; the operator is ignored; bare
    coordinates are dropped. Unlike the other checks a wrong entry is
    worse than a missing one, since the author trusts it as the wiring.

    Known limits of the regex: only `\\draw`/`\\path` are scanned
    (`\\graph`, `\\arrow`, `join` are silently missed); anchors ride along
    (`a.south -> b.north`); a `\\foreach` body is read once, literally, so
    comma or backslash tokens are dropped; brace groups are emptied so a
    label is text (#1112). Correct on every drafted figure checked, which
    is evidence, not proof.
    """
    edges = []
    for body in path_bodies(strip_comments(source)):
        edges += _pairs(body)
    return edges


def ambiguous_edges(source: str) -> list[tuple[str, str]]:
    """The `edge_list` pairs whose path has an `edge` operator or a named
    on-path node, so consecutive tokens are not ends of one line
    (`(hub) edge (s1) edge (s2)`). `figure check`'s `size-squash` (#1057)
    lists these rather than measure them.
    """
    return [
        pair
        for body in path_bodies(strip_comments(source))
        if _ON_PATH_RE.search(body)
        for pair in _pairs(body)
    ]


def _pairs(body: str) -> list[tuple[str, str]]:
    """Consecutive named tokens of one path statement's body."""
    names = [
        token.strip()
        for token in _PAREN_TOKEN_RE.findall(body)
        if token.strip() and not _COORDINATE_RE.match(token) and not _MACRO_TOKEN_RE.match(token)
    ]
    return list(zip(names, names[1:]))


# Only the leading option group: a whole-statement scan would find `->`
# inside a mid-path label. `edge[->]` is therefore missed: short, not wrong.
def _split_options(statement: str) -> tuple[str, str]:
    """A path statement's leading option group, and the rest with brace
    groups emptied.

    Split so `shift={(1,0)}` is not read as the first point; options nest
    so `arrows={->}` and `-{Latex[...]}` reach the tip reader whole
    (#1162). A group left open takes the whole statement.
    """
    text = statement.lstrip()
    if not text.startswith("["):
        return "", blank_groups(statement)
    depth = 0
    for i, char in enumerate(text):
        depth += NESTING.get(char, 0)
        if not depth:
            return text[1:i], blank_groups(text[i + 1 :])
    return text[1:], ""


def _point(token: str) -> str:
    """A parenthesised token with its whitespace normalised; text, not
    `float()`, so units and `\\foreach` macros still compare."""
    return ",".join(part.strip() for part in token.strip().split(","))


def stranded_arrowheads(source: str) -> list[str]:
    """Every bare coordinate where an arrowhead lands mid-stroke (#399).

    docs/TIKZ-STYLE.md's "one arrow is one `\\draw`": a line built in
    pieces each carrying a head renders a head at the joint. Heads come
    from `_tips.py` (#1162).

    The junction must be a bare coordinate: chaining through a named node
    is clipped at its border and is how scaffolds draw pipelines. Only a
    second statement *starting* at the junction counts (not a tick mark
    touching it), and not one drawing its own head there: two `<->`
    dimension bars sharing an end are fine, the one false positive the
    drafted book's figures showed.
    """
    text = strip_comments(source)
    styles = {**house_styles(), **style_definitions(text)}
    ends_with_head, opens_at = [], set()
    for start, end in path_spans(text):
        options, body = _split_options(text[start:end])
        points = [_point(token) for token in _PAREN_TOKEN_RE.findall(body)]
        if not points:
            continue
        start_head, end_head = tips(options, styles)
        if not start_head:
            opens_at.add(points[0])
        if end_head:
            ends_with_head.append(points[-1])
    found = []
    for point in ends_with_head:
        if point in opens_at and point not in found and _COORDINATE_RE.match(point):
            found.append(point)
    return found


# TeX internals a figure has no business naming (#781): the library
# `@loaded` flag and `positioning`'s global reset hook. Either is a
# workaround for a float-grouping bug the renderer now fixes, and misbehaves
# once a second figure exists. Matched with or without the backslash
# (`\csname` spelling); a library name may hold a dot.
_BY_HAND_RE = re.compile(r"\\?(tikz@library@[A-Za-z.]+@loaded|tikz@node@reset@hook)")


def loads_library_by_hand(source: str) -> list[str]:
    r"""Every TeX internal this figure file touches to manage a library
    load itself, in source order, deduped. Comments are stripped: a
    commented-out workaround is inert.
    """
    found: list[str] = []
    for name in _BY_HAND_RE.findall(strip_comments(source)):
        if name not in found:
            found.append(name)
    return found
