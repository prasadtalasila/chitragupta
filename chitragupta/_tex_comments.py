r"""TeX comment stripping, the first step of every reader of figure source.

`_COMMENT_RE` is a TeX comment: `%` to the end of the line. Every reader
of figure source strips it before any pattern runs -- #404, where every
symptom was a *wrong* answer rather than a missing one. A commented-out
`\draw` was reported as an edge the figure claims; a commented-out
`\node`'s label was measured for length; and worst, a comment merely
*mentioning* a node declaration made the probe ask pdflatex for a shape
nothing had drawn, so the aid reported a figure that compiles fine as
one that does not. For the renderer's library collection the same rule
has a second edge: a commented-out `\usetikzlibrary` would otherwise put
a library in the preamble no figure uses, and a misspelled name inside a
comment would fail the whole render (docs/TIKZ-STYLE.md -- a missing
name takes the whole call down).

`\%` is a literal percent sign and does not start a comment, hence the
lookbehind. `\\%` -- an escaped backslash followed by a real comment --
is read the wrong way by that lookbehind and is left alone: it needs a
character-by-character scan rather than a regex, and no figure this
pipeline draws has produced one.

This is the canonical definition; `render_output/_tikz_libraries.py`,
`review/figure_layout/_source.py` and `chitragupta/figure/` import it
from here. It is a leaf so that any of them can import it without an
import cycle.
"""

import re

_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")


def strip_comments(source: str) -> str:
    """`source` with every TeX comment removed, line breaks kept.

    See the module docstring for what that fixes and what it deliberately
    does not.
    """
    return _COMMENT_RE.sub("", source)
