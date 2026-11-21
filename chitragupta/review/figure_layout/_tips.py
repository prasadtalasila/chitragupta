"""Which ends of a path statement carry a head, from its options (#1162).

`stranded-arrowhead` used to test a path's options for the substrings
`->` and `<-`. The house styles set their head inside the style
(`cgedge` is `-{Latex[...]}`), so a figure drawn in house idioms never
showed either, and the check was off for every scaffold.

The options are read as TikZ applies them: left to right, a later arrow
specification replacing an earlier one (`\\draw[cgweak, -]` draws no
head), and a style name standing for its body. Styles come from the
figure's own `name/.style={...}` definitions first, then from the
shipped house block, so a figure that carries the block, one that
`\\input`s it, and a snippet with neither all read the same.

Still regex over TikZ rather than a parser of it, and failing short
rather than wrong: a style defined in neither place, a `/.append style`,
a `/.style n args`, and a tip name outside `_TIP_NAMES` are not read,
and a path whose head comes from one of them is not reported.
"""

import functools
import re

from chitragupta import config
from chitragupta._tex_comments import strip_comments
from chitragupta.review.figure_layout._scan import braced

# `arrows.meta` tips and the legacy names still in use. Closed, so a
# style called `Flow-Edge` is not read as a tip at each end.
_TIP_NAMES = (
    "Classical TikZ Rightarrow",
    "Straight Barb",
    "triangle 45",
    "Rectangle",
    "Triangle",
    "Stealth",
    "stealth",
    "Circle",
    "Square",
    "Latex",
    "latex",
    "Hooks",
    "Kite",
    "Bar",
    "To",
    "to",
)
# One side of an arrow spec, after every top-level `{...}` and `[...]`
# has been replaced by `X`: empty, a run of `<`, `>`, `|` and groups
# (`|<`, `>>`, `{Latex}{Latex}`), or a tip name with optional options.
_NAMES = "|".join(re.escape(name) for name in _TIP_NAMES)
_SIDE = rf"(?:[<>|X]+|(?:{_NAMES})X?)?"
_SPEC_RE = re.compile(rf"(?P<start>{_SIDE})-(?P<end>{_SIDE})")

# `name/.style={`: a name may hold spaces and hyphens (`cg pic colour`,
# `my-arrow`) and is not the tail of a longer word.
_STYLE_RE = re.compile(r"(?<![\w-])([A-Za-z][\w -]*?)\s*/\.style\s*=\s*(?=\{)")

_CLOSERS = {"{": "}", "[": "]"}

Heads = tuple[bool, bool]


def style_definitions(text: str) -> dict[str, str]:
    """`{name: body}` for every `name/.style={body}` in `text`, whose
    comments the caller has stripped. A later definition wins."""
    styles = {}
    for match in _STYLE_RE.finditer(text):
        styles[_name(match.group(1))], _ = braced(text, match.end())
    return styles


@functools.cache
def house_styles() -> dict[str, str]:
    """The styles the shipped house block defines."""
    block = config.shipped("assets", "tikz", "cg-figstyle.tex")
    return style_definitions(strip_comments(block.read_text(encoding="utf-8")))


def tips(options: str, styles: dict[str, str]) -> Heads:
    """`(start head, end head)` for a path's leading options."""
    return _walk(options, styles, (False, False), frozenset())


def _walk(options: str, styles: dict[str, str], heads: Heads, seen: frozenset[str]) -> Heads:
    for token in _split(options):
        key, value = _key(token)
        if key in styles and key not in seen:
            heads = _walk(styles[key], styles, heads, seen | {key})
        elif key == "arrows" and value is not None:
            heads = _spec(_unwrap(value)) or heads
        elif value is None:
            heads = _spec(token) or heads
    return heads


def _spec(token: str) -> Heads | None:
    """The heads an arrow spec draws, or `None` if `token` is not one."""
    match = _SPEC_RE.fullmatch(_blank(token.strip()))
    if match is None:
        return None
    return bool(match.group("start")), bool(match.group("end"))


def _split(options: str) -> list[str]:
    """`options` at its top-level commas, blank tokens dropped."""
    tokens, depth, start = [], 0, 0
    for i, char in enumerate(options):
        depth += {"{": 1, "[": 1, "}": -1, "]": -1}.get(char, 0)
        if char == "," and not depth:
            tokens.append(options[start:i])
            start = i + 1
    tokens.append(options[start:])
    return [token for token in tokens if token.strip()]


def _key(token: str) -> tuple[str, str | None]:
    """`(key, value)` split at the token's first top-level `=`; the value
    is `None` where there is none."""
    depth = 0
    for i, char in enumerate(token):
        depth += {"{": 1, "[": 1, "}": -1, "]": -1}.get(char, 0)
        if char == "=" and not depth:
            return _name(token[:i]), token[i + 1 :]
    return _name(token), None


def _blank(token: str) -> str:
    """`token` with each top-level `{...}` and `[...]` replaced by `X`."""
    out, depth, opener = [], 0, ""
    for char in token:
        if depth:
            depth += (char == opener) - (char == _CLOSERS[opener])
            continue
        if char in _CLOSERS:
            depth, opener = 1, char
            out.append("X")
        else:
            out.append(char)
    return "".join(out)


def _unwrap(value: str) -> str:
    """`value` without one pair of braces around the whole of it."""
    value = value.strip()
    if value.startswith("{"):
        inner, end = braced(value, 0)
        if end == len(value):
            return inner
    return value


def _name(text: str) -> str:
    return " ".join(text.split())
