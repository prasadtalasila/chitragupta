"""The `python -m chitragupta.draft style` findings about typesetting.

Beside `chitragupta/style_acronym_drift.py`, `style_tables.py`,
`style_figures.py` and `style_equations.py`, the fifth finding in that
command computed in plain Python rather than by Vale. Two checks, both
about whether a line will fit the page it is printed on
(docs/WRITING-STANDARDS.md §14):

- a **bare URL** shown as prose, where a `[descriptive text](url)` link
  reads better and gives the PDF something clickable,
- a **fenced code-block line wider than the page**, which is the one
  overflow class nothing downstream can fix.

**Why Vale cannot do either.** Vale matches patterns inside prose, and
its Markdown scoping deliberately excludes code spans and fenced blocks
(`assets/vale/vale.ini`'s own comment says so). The bare-URL check has to
look *past* that scoping to tell a link's visible text from its target,
and the width check has to look *inside* a fence at raw columns -- the
exact regions Vale hides. So neither is expressible as a Vale rule, the
same reason the table and figure checks are not.

**Why a wide code line is the one that cannot be fixed downstream.**
An over-long inline code span is repaired at render time by
`assets/pandoc/breakable_inline_code.lua`, which gives it `\\penalty0`
break points. A fenced block becomes a LaTeX `verbatim`, and a verbatim
line is one unbreakable box by construction -- no filter, package or
preamble can wrap it. The author has to shorten the line, which is why
this is a drafting-layer finding rather than a rendering one. Measured
against a real 428-page book: 58 of its 89 `Overfull \\hbox` warnings
were exactly this, the largest single class.

**Long prose words are deliberately not checked here**, though
docs/WRITING-STANDARDS.md §14 still asks for them. TeX hyphenates a
long English word in a roman font perfectly well -- `interoperability`
breaks as `in-teroperability` even in a 4cm column -- so the rule has no
overflow to prevent, and every candidate it would raise on this
project's own book (36 of them, `interoperability` and
`indistinguishable` among them) has no repair that is not a worse word.
§9's table records it as guidance with no mechanical proxy, the same
shape as its "should this equation have been numbered at all" row.
"""

import re
from pathlib import Path

from chitragupta import citation_gate, style_elements
from chitragupta.render_output import _paths
from chitragupta.render_output._tables import line_of

RULES = {
    "bare-url": "chitragupta.BareUrl",
    "wide-code-line": "chitragupta.WideCodeLine",
}

# The widest verbatim line that fits, measured rather than assumed --
# `pdflatex` reports an Overfull \hbox from the next column on. Two
# geometries matter and they disagree: this project's book style
# (11pt, 80pt margins) fits 79, and `render()`'s own defaults (12pt,
# 1in margins) fit 76. The tighter one is the limit, because a draft
# rendered either way has to fit; picking the book's 79 would pass
# lines that overflow under a plain `draft render`.
#
# **Measured through pandoc's own template, not a bare `\documentclass`.**
# That template loads `lmodern`, whose typewriter face is narrower than
# Computer Modern's, and measuring without it gave 76/73 -- three
# columns tight in both geometries, which reported real, fitting lines
# from this project's own book as too wide. Re-measure the same way if
# the template or the font ever changes.
MAX_CODE_COLUMNS = 76

# A URL as *displayed text*. The scheme is required: a bare `www.` or a
# domain on its own is a judgement about whether it is even a link,
# which is not this check's to make.
#
# The last character is constrained separately so the match stops before
# the sentence's own punctuation. A plain `\S+` swallows it -- `See
# <https://example.com/b>.` reported `https://example.com/b>.` -- and a
# finding that misquotes the URL it is about is one an author has to
# read twice to act on.
_URL_RE = re.compile(r"""https?://[^\s<>"']*[^\s<>"'.,;:!?)\]}]""")

# An inline code span holding a URL and nothing else. That is a URL
# being *shown* to the reader, and it wants a link for the same reason
# an unmarked one does -- the monospace font changes nothing about
# readability or whether the PDF has anything to click. A span with a
# URL among other tokens (`curl https://...`, `BASE_URL=https://...`)
# is genuinely code and is left alone: rewriting it as a link would
# corrupt the command it prints. Measured across `content/drafts/`
# before the distinction was drawn: 1 of the first kind, 0 of the
# second, so the narrow rule costs nothing and still catches the case
# this check exists for.
_URL_ONLY_SPAN_RE = re.compile(r"`(https?://[^`\s]+)`")

# An inline link's target, `](...)`, and a reference definition's,
# `[id]: ...`. Blanked before the scan so the URL a correct link points
# at is not itself reported -- what is looked for is a URL the reader
# sees, not one the markup resolves.
_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
_LINK_DEFINITION_RE = re.compile(r"^[ \t]*\[[^\]]+\]:[ \t]*\S+", re.MULTILINE)

# The quoted-span exemption docs/WRITING-STANDARDS.md §9 states, in the
# two shapes it takes here. Kept deliberately in step with
# `assets/vale/vale.ini`'s `BlockIgnores`, which excludes the same two
# regions from every Vale rule: a draft quotes its sources by
# construction, so a bare URL inside a block quotation is the source's
# and not this draft's to rewrite, and `chitragupta/references.py`
# splices bibliography URLs straight out of the ledger into the
# references section, where rewriting one as a link would misrepresent
# the entry.
_BLOCKQUOTE_RE = re.compile(r"(?sm)^(> .*?)(?:\n\n+|\Z)")
_REFERENCES_RE = re.compile(
    r"(?sm)^(#+ +(?:[\d.]+ +)?(?:References|Further reading|Bibliography|Works cited)\b.*?)"
    r"(?:\n#+ |\Z)"
)

# A fenced block, opening fence to closing fence, with the content
# captured. Deliberately not `citation_gate._blank_fenced`: that one
# blanks the whole fence including its delimiter lines, because it
# exists to blank the block out, and here the delimiter lines must be
# excluded -- an info string like ```python is not a content line and
# cannot overflow anything.
_FENCE_RE = re.compile(
    r"^([ \t]*)(`{3,}|~{3,})[^\n]*\n(.*?)^[ \t]*\2[^\n]*$", re.MULTILINE | re.DOTALL
)

# A `.tex` fragment's equivalent, for the same reason and with the same
# shape: the delimiter lines excluded, the content captured. The
# environment list matches `citation_gate._LATEX_VERBATIM_RE`'s -- that
# one blanks these regions and this one measures inside them, so they
# have to agree on what counts as verbatim.
_LATEX_VERBATIM_RE = re.compile(
    r"\\begin\{(verbatim|lstlisting|minted)\*?\}[^\n]*\n(.*?)^[ \t]*\\end\{\1\*?\}",
    re.MULTILINE | re.DOTALL,
)


def _finding(rule: str, match: str, line: int, message: str) -> dict:
    """One finding in the shape `style_check.collapse()` produces from
    Vale's own -- a thin `RULES`-bound wrapper over the shared
    `style_elements.finding`, matching how the sibling modules call it."""
    return style_elements.finding(RULES, rule, match, line, message)


def _blank(pattern: "re.Pattern", text: str) -> str:
    """`pattern`'s matches blanked in place, character for character.

    In place rather than removed, for the reason
    `citation_gate._blank_code` gives: every line number reported below
    is computed from a position in this string, so the blanking must not
    move anything.

    **Not a second way of doing what `_blank_code` does**, though it
    shares that one-line idiom. `_blank_code` blanks a *fixed* set of
    three patterns and is called here, unchanged, for exactly that set.
    This takes the pattern as an argument, because the regions below --
    a link target, a block quotation, a references section -- are this
    module's own and belong in no other caller's set. Parameterising
    `_blank_code` instead would widen a function four modules depend on
    to serve one of them.
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
                "(WRITING-STANDARDS.md §14).",
            )
        )
    return found


def _wide_code_lines(text: str, pattern: "re.Pattern", group: int, why: str) -> "list[dict]":
    """Every code line in `pattern`'s blocks too wide for the page."""
    found = []
    for block in pattern.finditer(text):
        offset = block.start(group)
        for index, raw in enumerate(block.group(group).split("\n")[:-1]):
            if len(raw.rstrip()) <= MAX_CODE_COLUMNS:
                continue
            found.append(
                _finding(
                    "wide-code-line",
                    raw.strip()[:60],
                    line_of(text, offset) + index,
                    f"this code line is {len(raw.rstrip())} columns wide, over "
                    f"the {MAX_CODE_COLUMNS} a page fits. {why} "
                    "(WRITING-STANDARDS.md §14).",
                )
            )
    return found


def findings(draft: Path) -> "list[dict]":
    """Every typesetting finding for `draft`, ordered by where it is."""
    text = draft.read_text(encoding="utf-8")
    # A `.tex` fragment gets the width check and nothing else, and the
    # asymmetry is the point rather than an omission.
    #
    # Width, because it is the one draft this pipeline cannot fix for
    # the author. A Markdown draft's fences are wrapped at render time
    # by the `fvextra` load `_pandoc.py` adds; a fragment is `\input`
    # into the user's own thesis, whose preamble is theirs -- §13's
    # carve-out and `style_tables.py`'s "nothing this pipeline does may
    # get between them". So reporting is the only lever there, which
    # makes this the *more* important surface for the check, not a
    # lesser one.
    #
    # Not the bare-URL rule, because `\url{}` is LaTeX's correct idiom
    # and flagging it would be wrong; telling a raw URL in `.tex` prose
    # from one already inside `\url{}`/`\href{}{}` is a different
    # parsing problem than the Markdown one, and is not attempted here.
    if draft.suffix.lower() not in _paths._MARKDOWN_SUFFIXES:
        return sorted(
            _wide_code_lines(
                text,
                _LATEX_VERBATIM_RE,
                2,
                "A verbatim environment cannot wrap, and a fragment is `\\input` "
                "into a document whose preamble this pipeline may not change, so "
                "nothing downstream can repair it",
            ),
            key=lambda finding: (finding["line"], finding["rule"]),
        )
    # The width check reads fences, so it runs on the original text; the
    # URL check must not see inside them, so it runs on a blanked copy.
    # The backticks around a URL-only span are dropped first (to spaces,
    # so nothing moves), which is what leaves that one visible to the
    # scan while every other span is still blanked out under it.
    prose = citation_gate._blank_code(_URL_ONLY_SPAN_RE.sub(r" \1 ", text))
    found = _bare_urls(prose) + _wide_code_lines(
        text,
        _FENCE_RE,
        3,
        "A fenced block renders as LaTeX `verbatim`, which wraps only because "
        "the render loads `fvextra`; keeping the line short avoids the "
        "continuation marker a wrap leaves behind",
    )
    return sorted(found, key=lambda finding: (finding["line"], finding["rule"]))
