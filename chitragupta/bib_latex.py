"""bibtexparser 1.x's LaTeX-to-Unicode decoding, kept when the parser
moved to bibtexparser 2.

Why vendored rather than v2's own `LatexDecodingMiddleware`: that one
decodes through pylatexenc, which disagreed with 1.x on 1,242 field
values of this project's real bibliographies -- every `105--107` page
range became `105–107`, and a macro pylatexenc knows but renders as
nothing (`\\textbar`) vanished from titles. Those values reach the
ledger and every rendered reference list, so the upgrade keeps 1.x's
output byte for byte instead of changing it as a side effect.
`tests/test_bib_latex.py` pins that against values 1.4.4 produced.

The logic below is 1.4.4's `latexenc.latex_to_unicode` and its two
helpers, unchanged in behaviour. The 2,547 replacement pairs it reads
live in `bib_latex_table.json` beside this file, in their original
order, which matters: the first replacement to match wins.

Copyright (c) 2012-2018, Francois Boulogne and the python-bibtexparser
contributors. Used under the BSD-3-Clause option of bibtexparser 1.x's
LGPLv3-or-BSD dual licence: redistributions of source code must retain
this copyright notice, and the name of the author may not be used to
endorse or promote products derived from this software without specific
prior written permission. THIS SOFTWARE IS PROVIDED BY THE AUTHOR "AS
IS" AND ANY EXPRESS OR IMPLIED WARRANTIES ARE DISCLAIMED.
"""

import functools
import itertools
import json
import re
import unicodedata
from pathlib import Path

TABLE_PATH = Path(__file__).with_name("bib_latex_table.json")


@functools.cache
def _tables() -> dict[str, list[tuple[str, str]]]:
    """The three replacement tables, read once. Lazily, so importing
    `bib_reader` for its dataclasses never pays for a 79 KB parse."""
    raw = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    return {name: [tuple(pair) for pair in pairs] for name, pairs in raw.items() if name[0] != "_"}


def _replace_latex(string: str, latex: str, unicod: str) -> str:
    """One replacement. A combining accent lands *after* the character
    that follows its LaTeX form, and is dropped at the very end of the
    string, where there is nothing for it to land on -- 1.x's rule."""
    if latex not in string:
        return string
    if not unicodedata.combining(unicod):
        return string.replace(latex, unicod)
    for match in re.finditer(re.escape(latex), string):
        i, j = match.span()
        if j < len(string):
            string = "".join([string[:i], string[j], unicod, string[(j + 1) :]])
        else:
            string = string[:i]
    return string


def _replace_all_latex(string: str, replacements) -> str:
    for unicod, latex in replacements:
        string = _replace_latex(string, latex.rstrip(), unicod)
    return string


def latex_to_unicode(string: str) -> str:
    """A LaTeX string as Unicode, NFC-normalised, with every brace
    removed -- 1.x's TODO about escaped braces included, since keeping
    its output is the point."""
    tables = _tables()
    if "\\" in string or "{" in string:
        string = _replace_all_latex(
            string,
            itertools.chain(tables["unicode_to_crappy_latex1"], tables["unicode_to_latex"]),
        )
    string = string.replace("{", "").replace("}", "")
    if "\\" in string or "{" in string:
        string = _replace_all_latex(string, tables["unicode_to_crappy_latex2"])
    return unicodedata.normalize("NFC", string)
