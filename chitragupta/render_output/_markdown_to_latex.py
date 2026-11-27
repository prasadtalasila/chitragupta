"""`markdown_to_latex`: Markdown snippets to LaTeX in one pandoc process.

For text not read from a draft: glossary, list of symbols (#1138), index
entries (#1168).
"""

import subprocess

from chitragupta import config, programs
from chitragupta.render_output._errors import ConversionError, _require

# A raw LaTeX block, not a paragraph: a text starting `: ` would turn a separator
# paragraph into a definition-list term, while pandoc copies a raw block verbatim.
_SEPARATOR = "CHITRAGUPTATEXTSEPARATOR"
_SEPARATOR_BLOCK = f"\n\n```{{=latex}}\n%{_SEPARATOR}\n```\n\n"


def markdown_to_latex(texts: "list[str]") -> "list[str]":
    """Each of `texts`, Markdown, as a LaTeX fragment, in order.

    One process for the whole list: a book has hundreds of definitions and a
    process each would dominate the run. Uses the draft render's inline-code
    filter so code spans break the same way.
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
