r"""The two pages a draft prints on, and which one a figure is checked on
(#1140, X-1 and X-5 reduced).

**Two pages, because this repository sets two.** `draft render` sets a
draft as a 12pt A4 `article` with 1in margins; `book-assembler` sets a
book as an 11pt A4 `book` with 80pt margins
(`.claude/skills/book-assembler/assets/book-skeleton.tex`). Before this
module the article's numbers were written out in six places that agreed
by convention, and the book's text block was written nowhere, so
`figure check` measured a book unit's figure against the article's 453pt
when the book's text block is 437.5pt. Choosing another paper size is
epic #1140's parked remainder, not this module's job.

**The text block is measured, not computed.** The class and the geometry
options decide `\textwidth` and `\textheight` together, so each page
records what LuaLaTeX reports for its `preamble`, and
`tests/test_page.py` compiles both preambles and holds the numbers to
them. Arithmetic over paper size and margin would not notice a class or
geometry change that moved the real text block.

**It imports `config` and nothing else of this package.** `spec` would
be the natural source of `SPEC_MD`, but importing it closes a cycle:
`spec` reaches `render_output` through the dossier, and `render_output`
takes its defaults from here. `tests/test_page.py` holds the two names
to one value instead.
"""

from dataclasses import dataclass
from pathlib import Path

from chitragupta import config

# `spec.SPEC_MD`, restated: see the module docstring.
SPEC_MD = "spec.md"


@dataclass(frozen=True)
class Page:
    """One page: what `draft render` passes pandoc for it, the two
    preamble lines that set it, and the text block they leave, in TeX
    points."""

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

    A figure under a book's drafts directory, one with a spec in the
    mirrored `content/specs/` directory, is on the book: a book's units
    are files in that directory and their figures sit in its `figures/`.
    That holds even when a unit is rendered on its own, since the book
    is the narrower page. Only the spec's existence is read, and a spec
    reached through a symlink out of `content/specs/` does not count, as
    `spec.spec_dir` refuses one.
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
