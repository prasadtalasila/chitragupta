r"""The two pages a draft prints on, and which one a figure is checked on
(#1140, X-1 and X-5 reduced).

`draft render` sets a 12pt A4 `article` with 1in margins; `book-assembler`
sets an 11pt A4 `book` with 80pt margins, so a book figure must be
measured against 437.5pt, not 453pt. The text blocks are what LuaLaTeX
reports, not arithmetic, and `tests/test_page.py` compiles both
preambles to hold them. Imports only `config`: importing `spec` for
`SPEC_MD` would close a cycle through `render_output`.
"""

from dataclasses import dataclass
from pathlib import Path

from chitragupta import config

# `spec.SPEC_MD`, restated: see the module docstring.
SPEC_MD = "spec.md"


@dataclass(frozen=True)
class Page:
    """One page: what `draft render` passes pandoc, the two preamble lines
    that set it, and the text block they leave, in TeX points."""

    name: str
    documentclass: str
    fontsize: str
    papersize: str
    margin: str
    preamble: str
    text_width_pt: float
    text_height_pt: float


ARTICLE = Page(
    "article",
    "article",
    "12pt",
    "a4",
    "1in",
    "\\documentclass[12pt,a4paper]{article}\n\\usepackage[margin=1in]{geometry}\n",
    452.97,
    700.51,
)
# The book skeleton's two lines, verbatim; `latex-conventions.md`'s
# "Margins" says why 80pt.
BOOK = Page(
    "book",
    "book",
    "11pt",
    "a4",
    "80pt",
    "\\documentclass[11pt,a4paper]{book}\n\\usepackage[a4paper,margin=80pt]{geometry}\n",
    437.51,
    685.05,
)
PAGES = {each.name: each for each in (ARTICLE, BOOK)}


def page_for(figure: Path) -> tuple[Page, str]:
    """The page `figure` prints on, and why, in words a report prints.

    A figure in a drafts directory mirrored by a spec in `content/specs/`
    is on the book, even when a unit renders alone, since the book is the
    narrower page. A spec reached through a symlink out of
    `content/specs/` does not count, as `spec.spec_dir` refuses one.
    """
    try:
        relative = Path(figure).resolve().relative_to(config.DRAFTS_DIR.resolve())
    except ValueError:
        return ARTICLE, f"not under {config.DRAFTS_DIR}"
    for directory in list(relative.parents)[:-1]:
        spec_md = config.SPECS_DIR / directory / SPEC_MD
        if spec_md.is_file() and config.resolves_inside(spec_md, config.SPECS_DIR):
            return BOOK, f"from {spec_md}"
    return ARTICLE, "no book spec above it"
