"""What Vale is handed for a `.tex` draft: the draft with its LaTeX
markup blanked to spaces of the same width.

Vale reads `.tex` as Markdown (`vale.ini`'s `tex = md`). Measured on a
real thesis chapter, two ``...'' in a paragraph became one code span, and
`TokenIgnores` for LaTeX lost findings in long paragraphs (636 of 839
planted defects reported; all 839 with this blanking; cf. #1187).

`style_check.run_vale` hands Vale this text on stdin. Blanked spans keep
their newlines, so every finding's line and column are the draft's own.
The patterns are `vale.ini`'s LaTeX ignores. Each `` becomes `""`: Vale
lost findings on multi-byte curly quotes. `style_quotes.drop_quoted`
reads the original text, so quotations stay exempt.
"""

import re
from collections.abc import Callable

VERBATIM = re.compile(
    r"(?s)\\begin\{(verbatim|lstlisting|minted|Verbatim|lstinputlisting)\}.*?\\end\{\1\}"
)
CITATION = re.compile(r"\\cite[a-zA-Z]*\s*(\[[^\]]*\])*\{[^}]*\}")
# Applied to the whole draft, so it must neither open on an escaped `\$`
# nor cross a blank line: either would turn the math after it into prose.
MATH = re.compile(r"(?<!\\)\$(?:(?!\n[ \t]*\n)[^$])*\$")
COMMAND = re.compile(r"\\(?:(?:begin|end)\{[^}]*\}|[A-Za-z]+\*?)")


def _blank_in(text: str) -> Callable[[re.Match], str]:
    """A `re.sub` replacement that blanks a match within `text`. A match
    that opens its line keeps its first column as `.`: four leading spaces
    would be a Markdown code block, hiding the line from Vale."""

    def blank(match: re.Match) -> str:
        spaces = re.sub(r"[^\n]", " ", match.group(0))
        line_start = text.rfind("\n", 0, match.start()) + 1
        if text[line_start : match.start()].strip() or spaces.startswith("\n"):
            return spaces
        return "." + spaces[1:]

    return blank


def for_vale(text: str) -> str:
    """`text` as Vale should read it, column for column."""
    text = text.replace("``", '""')
    for pattern in (VERBATIM, CITATION, MATH, COMMAND):
        text = pattern.sub(_blank_in(text), text)
    return text
