"""`markdown_to_latex`: Markdown snippets to LaTeX in one pandoc process.

For text this package did not read from a draft: the book's Glossary and
List of Symbols (#1138) and the index's printed entries (#1168). Split
from `chitragupta/render_output/_pandoc.py`, which holds the draft's own
render, to keep that module under docs/CODE-STANDARDS.md's C2 limit.
"""

import subprocess

from chitragupta import config, programs
from chitragupta.render_output._errors import ConversionError, _require

# What `markdown_to_latex` joins its texts with and splits the output on.
# A raw LaTeX block rather than a paragraph: a text starting `: ` turns
# the paragraph before it into a definition-list term, which a bare
# separator paragraph would be, and pandoc copies a raw block verbatim.
_SEPARATOR = "CHITRAGUPTATEXTSEPARATOR"
_SEPARATOR_BLOCK = f"\n\n```{{=latex}}\n%{_SEPARATOR}\n```\n\n"


def markdown_to_latex(texts: "list[str]") -> "list[str]":
    """Each of `texts`, Markdown, as a LaTeX fragment, in order.

    For text this package did not read from a draft: the book's glossary
    and list of symbols (chitragupta/registry/_pages.py, #1138), whose
    definitions are Markdown in each unit's `scope.md`, and the index's
    entries (chitragupta/registry/_index_finish.py, #1168). One process for
    the whole list, joined on `_SEPARATOR`, because a book has a few
    hundred definitions and a process each would be most of the run.
    The same inline-code filter as a draft's own render, so a code span
    breaks the same way in the glossary as in the chapter.
    """
    if any(_SEPARATOR in text for text in texts):
        raise ConversionError(f"a text holds the separator {_SEPARATOR!r}")
    if not texts:
        return []
    _require("pandoc")
    joined = _SEPARATOR_BLOCK.join(texts)
    argv = [  # pragma: no cover-windows
        programs.require_program("pandoc"),
        "--from=markdown",
        "--to=latex",
        "--wrap=none",
        "--no-highlight",
        "--lua-filter",
        str(config.shipped("assets", "pandoc", "breakable_inline_code.lua")),
    ]
    result = subprocess.run(  # pragma: no cover-windows
        argv, input=joined, check=True, capture_output=True, text=True
    )
    parts = [part.strip() for part in result.stdout.split(f"%{_SEPARATOR}")]
    if len(parts) != len(texts):
        raise ConversionError(f"pandoc returned {len(parts)} parts for {len(texts)} texts")
    return parts
