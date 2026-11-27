r"""TeX comment stripping, the first step of every reader of figure source.

Every reader strips `%` comments before matching (#404): commented-out
`\draw`s and `\node`s gave wrong answers, and a commented-out
`\usetikzlibrary` could fail a whole render. `\%` is literal, hence the
lookbehind; `\\%` is misread and left alone, as no figure has produced
one. A leaf module, so its importers cannot form a cycle.
"""

import re

_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")


def strip_comments(source: str) -> str:
    """`source` with every TeX comment removed, line breaks kept."""
    return _COMMENT_RE.sub("", source)
