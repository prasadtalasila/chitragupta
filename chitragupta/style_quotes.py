"""Inline quotations are exempt from the prose rules.

WRITING-STANDARDS.md §9 exempts quoted spans; `vale.ini` can exempt only
block quotations, and in the 2026-11-20 bench (bench/RESULTS.md) 9 of 17
wrong findings sat inside an inline one.

Done here on Vale's findings, not as a `TokenIgnores` pattern: measured,
a multi-line pattern lost real findings, and `TokenIgnores` applies to
every rule, so `Acronyms` reported 14 expanded acronyms as unexpanded.
`chitragupta.Acronyms` is never dropped, as in `style_exceptions`.

A quotation is a double-quoted span as `quote_spans.py` finds it, or
LaTeX's ``` ``...'' ```, never across a blank line, so an unclosed mark
cannot silence the next paragraph. Only findings wholly inside one drop.
"""

import re

from chitragupta import quote_spans

# LaTeX's own quotation marks, which the verbatim scan does not read: an
# apostrophe inside ("it's") does not close it, and a blank line does.
LATEX_QUOTED = re.compile(r"``(?:[^'\n]|'(?!')|\n(?![ \t]*\n))+''")


def drop_quoted(findings: list[dict], text: str) -> list[dict]:
    """`findings` minus those lying wholly inside an inline quotation.

    Vale's `Line` is 1-based and counts "\\n" only, and its `Span`
    columns are 1-based and inclusive (see `style_exceptions`).
    """
    starts = [0]
    for line in text.split("\n"):
        starts.append(starts[-1] + len(line) + 1)
    quotes = quote_spans.double_quoted(text)
    # Narrowed by one each side, so a finding must start after both backticks.
    quotes += [(m.start() + 1, m.end() - 1) for m in LATEX_QUOTED.finditer(text)]
    return [f for f in findings if not _quoted(f, starts, quotes)]


def _quoted(finding: dict, starts: list[int], quotes: list[tuple[int, int]]) -> bool:
    number, span = finding.get("Line", 0), finding.get("Span")
    if finding.get("Check") == "chitragupta.Acronyms" or not span:
        return False
    if not 1 <= number < len(starts):
        return False
    start = starts[number - 1] + span[0] - 1
    end = starts[number - 1] + span[1]
    return any(open_at < start and end < close_at for open_at, close_at in quotes)
