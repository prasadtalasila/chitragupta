"""What Vale is handed for a `.tex` draft: the draft with its LaTeX
markup blanked to spaces of the same width.

Vale reads a `.tex` fragment as Markdown (`vale.ini`'s `tex = md`), and
two faults followed, both measured on a real 8.7k-word thesis chapter:

- Two ``...'' in one paragraph made a Markdown code span of everything
  between them, so the draft's own words there were never checked.
- `vale.ini`'s `TokenIgnores` entries for LaTeX (citation commands,
  `$...$`, command names) lost findings in long paragraphs. With one
  defect marker planted on each prose line, 636 of 839 were reported;
  with the same spans blanked here first, all 839 were. It is the same
  fault that #1187 met when two entries hid every finding beside a
  `\\begin` line.

So `style_check.run_vale` hands Vale this text on stdin instead of the
file. Each blanked span keeps its newlines and becomes spaces, so the
line and column of every finding are the draft's own. What is blanked is
what `vale.ini` ignores for LaTeX, with the same patterns: a verbatim
environment whole (its `BlockIgnores` entry, which would no longer find
the block once `\\begin{verbatim}` is blank), then citation commands
with their arguments, inline math, and command names (an argument such
as `\\emph{this}`'s stays prose). Each `` becomes `""`: two ASCII
columns, because Vale lost findings when it was given multi-byte curly
quotes. `style_quotes.drop_quoted` reads the original text, so a
quotation stays exempt.
"""

import re
from collections.abc import Callable

VERBATIM = re.compile(
    r"(?s)\\begin\{(verbatim|lstlisting|minted|Verbatim|lstinputlisting)\}.*?\\end\{\1\}"
)
CITATION = re.compile(r"\\cite[a-zA-Z]*\s*(\[[^\]]*\])*\{[^}]*\}")
MATH = re.compile(r"\$[^$]*\$")
COMMAND = re.compile(r"\\(?:(?:begin|end)\{[^}]*\}|[A-Za-z]+\*?)")


def _blank_in(text: str) -> Callable[[re.Match], str]:
    """A `re.sub` replacement that blanks a match within `text`. A match
    that opens its line keeps its first column as `.`: four leading spaces
    are a Markdown code block, so blanking `\\emph{...}` at the start of a
    line to spaces would hide the line from Vale."""

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
