"""Where a draft quotes a source inline: its double-quoted spans.

Two checks exempt a quotation, and they must agree on what one is: the
verbatim scan (`review/verbatim_check/_masking.py`, which adds Markdown
blockquote lines) and the prose check (`style_quotes.py`, which adds
LaTeX's ``...''). Moved here from the first of them, with one change:
a quotation of a single character ("A") is a span. The old two-character
minimum left its closing mark to open a span that ran to the next
quotation, which hid the draft's own words in between from the prose
check, and demoted them in the verbatim scan.
"""

import re

# Straight or curly double-quoted spans, and Markdown blockquote lines --
# deliberately not cleverer than that about what a quotation *is* (no
# nesting, no single quotes, which double as apostrophes and would flag
# most of the draft). The two guards below are not an exception to that:
# they are about how far an *unpaired* delimiter may reach, which is a
# different question and one the simple rule got wrong (#516/m-54). Detecting
# *that* a run touches quote delimiters (`_run_is_quoted`, which reads
# these spans as overlap rather than containment) is a cheap,
# deterministic bit attached to a finding; whether that should downgrade
# severity (a legitimate page-anchored quotation vs. unmarked reuse) is
# Phase 2's policy call, not this one's.
#
# Two guards on what may open and how far a span may run, both from
# #516/m-54. Without them a *single* stray double quote opened a span
# that ran to the next quotation's **opening** mark, so every real
# finding in the stretch between was demoted into the low-priority
# "quoted" bucket -- the failure direction that hides reuse rather than
# over-reporting it.
#
#   - A double quote straight after a digit is an inch or second mark
#     (`a 6" pipe`), not a quotation opener. This is the shape the report
#     was actually about, and the guard is exact for it.
#   - A span may not cross a blank line. Anything else unpaired -- a
#     typo, a quotation the author never closed -- then costs at most the
#     paragraph it sits in instead of the rest of the section.
#
# Mixed delimiters stay tolerated (`"` opening, `”` closing): a
# half-applied smart-quote pass produces exactly that, and refusing it
# would lose real quotations to punctuation hygiene.
_BODY = r'(?:(?!\n[ \t]*\n)[^"”])'
DOUBLE_QUOTED = re.compile(rf'(?<![0-9])["“]{_BODY}+["”]')


def double_quoted(text: str) -> list[tuple[int, int]]:
    """The (start, end) character offsets of each double-quoted span,
    quote marks included."""
    return [(m.start(), m.end()) for m in DOUBLE_QUOTED.finditer(text)]
