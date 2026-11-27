"""The `python -m chitragupta.draft style` findings about typesetting.

Two checks on whether a line fits the page (docs/WRITING-STANDARDS.md
§14): a bare URL shown as prose, and a fenced code line wider than the
page. Plain Python, since both look where Vale's scoping hides.

A wide fenced line is the one overflow nothing downstream fixes: inline
code gets break points from `breakable_inline_code.lua`, but a verbatim
line is one unbreakable box. It was 58 of 89 overfull-box warnings on a
428-page book. Long prose words are deliberately not checked: TeX
hyphenates them fine, and every candidate had no better word.
"""

import re
from pathlib import Path

from chitragupta import _code_regions, citation_gate, references_section, style_elements
from chitragupta.render_output import _paths
from chitragupta.render_output._tables import line_of

RULES = {
    "bare-url": "chitragupta.BareUrl",
    "wide-code-line": "chitragupta.WideCodeLine",
}

# The widest verbatim line that fits: 79 in the book style, 76 under
# `render()`'s defaults (12pt, 1in), so 76, as a draft must fit both.
# Measured through pandoc's template, whose `lmodern` is narrower than
# Computer Modern; re-measure the same way if the template or font changes.
MAX_CODE_COLUMNS = 76

# A URL as displayed text, scheme required (a bare domain is a judgement
# call). The last character is constrained so trailing punctuation is not
# swallowed into a misquoted URL.
_URL_RE = re.compile(r"""https?://[^\s<>"']*[^\s<>"'.,;:!?)\]}]""")

# An inline code span holding only a URL is being shown, so it wants a
# link too. A span with other tokens (`curl https://...`) is code, and
# rewriting it would corrupt the command.
_URL_ONLY_SPAN_RE = re.compile(r"`(https?://[^`\s]+)`")

# Link targets, blanked so a correct link's URL is not itself reported.
_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
_LINK_DEFINITION_RE = re.compile(r"^[ \t]*\[[^\]]+\]:[ \t]*\S+", re.MULTILINE)

# The quoted-span exemption (WRITING-STANDARDS.md §9), in step with
# `vale.ini`'s `BlockIgnores`: block quotations are the source's, and
# reference-list URLs come from the ledger. Reference headings are
# `references_section.REFERENCE_TITLE`'s (#951); "Further reading" is
# this check's own addition.
_BLOCKQUOTE_RE = re.compile(r"(?sm)^(> .*?)(?:\n\n+|\Z)")
_REFERENCES_RE = re.compile(
    rf"(?ism)^(#{{1,6}}[ \t]*(?:{references_section.REFERENCE_TITLE}|Further[ \t]+reading)"
    r"[ \t]*$.*?)(?:\n#+ |\Z)"
)

# Code bodies come from `_code_regions` (linear scans, #824), not
# `citation_gate._blank_code`, which includes the delimiter lines; an
# info string cannot overflow. Same verbatim environment list as the gate.


def _finding(rule: str, match: str, line: int, message: str, repair: str = "edit") -> dict:
    """One finding in `style_check.collapse()`'s shape, bound to `RULES`."""
    return style_elements.finding(RULES, rule, match, line, message, repair)


def _blank(pattern: "re.Pattern", text: str) -> str:
    """`pattern`'s matches blanked in place, so line numbers do not move.

    Not a second `_blank_code`, which blanks a fixed set and is called
    unchanged for it; widening it for this module's own regions would
    change a function four modules depend on.
    """
    return pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def _bare_urls(text: str) -> "list[dict]":
    """Every URL the reader would see as raw text rather than as a link."""
    scannable = _blank(_LINK_DEFINITION_RE, _blank(_LINK_TARGET_RE, text))
    scannable = _blank(_REFERENCES_RE, _blank(_BLOCKQUOTE_RE, scannable))
    found = []
    for match in _URL_RE.finditer(scannable):
        url = match.group(0)
        found.append(
            _finding(
                "bare-url",
                url,
                line_of(text, match.start()),
                f"`{url}` is shown as a bare URL. Write it as a "
                "`[descriptive text](url)` link instead, so the sentence reads "
                "and the PDF has something to click "
                "(docs/writing-standards/page.md §14).",
            )
        )
    return found


def _wide_code_lines(bodies: "list[tuple[int, str]]", why: str) -> "list[dict]":
    """Every code line in `bodies` -- `(first line number, body)` pairs,
    as `_code_regions` returns them -- too wide for the page."""
    found = []
    for first, body in bodies:
        for index, raw in enumerate(body.split("\n")[:-1]):
            if len(raw.rstrip()) <= MAX_CODE_COLUMNS:
                continue
            found.append(
                _finding(
                    "wide-code-line",
                    raw.strip()[:60],
                    first + index,
                    f"this code line is {len(raw.rstrip())} columns wide, over "
                    f"the {MAX_CODE_COLUMNS} a page fits. {why} "
                    "(docs/writing-standards/page.md §14).",
                    # A wide line may be deliberate -- a URL or literal in a
                    # block verified to run -- so a person decides (#836).
                    repair="review",
                )
            )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every typesetting finding for `draft`, ordered by where it is."""
    text = draft.read_text(encoding="utf-8")
    # A `.tex` fragment gets only the width check. Width, because its
    # preamble is the user's, so reporting is the only lever (§13).
    # Not bare URLs, because `\url{}` is LaTeX's correct idiom.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return sorted(
            _wide_code_lines(
                _code_regions.latex_verbatim_bodies(text),
                "A verbatim environment cannot wrap, and a fragment is `\\input` "
                "into a document whose preamble this pipeline may not change, so "
                "nothing downstream can repair it",
            ),
            key=lambda finding: (finding["line"], finding["rule"]),
        )
    # Width runs on the original text; the URL check on a blanked copy,
    # with URL-only spans' backticks spaced out first so they stay visible.
    prose = citation_gate._blank_code(_URL_ONLY_SPAN_RE.sub(r" \1 ", text))
    found = _bare_urls(prose) + _wide_code_lines(
        _code_regions.fenced_bodies(text),
        "A fenced block renders as LaTeX `verbatim`, which wraps only because "
        "the render loads `fvextra`; keeping the line short avoids the "
        "continuation marker a wrap leaves behind",
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
