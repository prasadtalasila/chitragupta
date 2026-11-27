"""Where a draft quotes a source inline: its double-quoted spans.

Shared so the verbatim scan and the prose check (`style_quotes.py`) agree
on what a quotation is. A quotation of one character or none is a span:
a two-character minimum let a closing mark open a span to the next
quotation, hiding the words between.
"""

import re

# Straight or curly double quotes only: single quotes double as
# apostrophes. Two guards on unpaired delimiters (#516/m-54), since a stray
# quote otherwise demoted every finding up to the next quotation into the
# "quoted" bucket, hiding reuse:
#   - a double quote straight after a digit is an inch mark (`a 6" pipe`);
#   - a span may not cross a blank line, so an unclosed one costs at most
#     its paragraph.
# Mixed delimiters (`"` ... `”`) are tolerated, as a half-applied
# smart-quote pass produces them.
_BODY = r'(?:(?!\n[ \t]*\n)[^"”])'
DOUBLE_QUOTED = re.compile(rf'(?<![0-9])["“]{_BODY}*["”]')


def double_quoted(text: str) -> list[tuple[int, int]]:
    """The (start, end) character offsets of each double-quoted span,
    quote marks included."""
    return [(m.start(), m.end()) for m in DOUBLE_QUOTED.finditer(text)]
