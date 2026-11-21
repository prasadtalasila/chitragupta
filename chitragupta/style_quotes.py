"""Inline quotations are exempt from the prose rules.

WRITING-STANDARDS.md §9 says quoted spans are exempt from every row: a
draft quotes its sources by construction, and a source's own "in order
to", "significant" or British spelling is not the draft's to fix.
`vale.ini` exempts a block quotation, which Vale's Markdown scoping can
see, but not a quotation inside a sentence, and in the 2026-11-20 bench
(bench/RESULTS.md) 9 of the 17 wrong findings sat inside one.

The exemption is applied here, to Vale's findings, rather than as a
`TokenIgnores` pattern in `vale.ini`. Measured on the same drafts, a
pattern that spans lines (as a quotation wrapped in Markdown or LaTeX
does) lost three real findings outside any quote and moved a fourth,
and `TokenIgnores` applies to every rule, so `Acronyms` stopped seeing
an expansion written inside a quotation and reported 14 acronyms as
unexpanded. Here the test is a span test on the draft's own text, and
`chitragupta.Acronyms` is never dropped, as in `style_exceptions`.

A quotation is a double-quoted span as `chitragupta/quote_spans.py`
finds it for the verbatim scan too (straight or curly marks, never across
a blank line, never opened by an inch mark), or LaTeX's ``` ``...'' ```
under the same blank-line bound, so a quote mark left unclosed cannot
silence the paragraph after it. A finding is dropped only when it lies
wholly inside one; a match that runs past the closing mark is partly the
draft's and stays.
"""

import re

from chitragupta import quote_spans

# LaTeX's own quotation marks, which the verbatim scan does not read: an
# apostrophe inside ("it's") does not close it, and a blank line does.
LATEX_QUOTED = re.compile(r"``(?:[^'\n]|'(?!')|\n(?![ \t]*\n))+''")


def drop_quoted(findings: list[dict], text: str) -> list[dict]:
    """`findings` minus those lying wholly inside an inline quotation.

    Vale's `Line` is 1-based and counts "\\n" only, and its `Span`
    columns are 1-based and inclusive (see `style_exceptions`), so a
    finding's offsets in `text` follow from the line starts.
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
