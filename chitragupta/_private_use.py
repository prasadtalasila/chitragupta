"""Private-use characters a report quotes from a source, written as a
marker the render can set (#1125).

A PDF's text layer carries Unicode private-use code points for glyphs a
font defines for itself, so they reach `content/parsed/` and from there
every review report and evidence sidecar that quotes a source. No font
in the render chain has them, and `assets/latex/chitragupta-lualatex.tex`
makes a missing glyph a build error, so a report holding one had no PDF.

That error stays right for a *draft* (#996): the author wrote the
character and can fix it. In a report the character came from the
source, there is nothing to fix, and a `content/unicode-extra.tex` entry
per code point does not scale. So a report writes each one as a visible
`[U+E230]`, in its `.md` and therefore its `.tex` and `.pdf`; its `.json`
keeps the original.

Stdlib-only.
"""

import re

# The BMP's Private Use Area and the two supplementary private-use planes,
# 15 and 16 (Unicode chapter 23.5).
_PRIVATE_USE = re.compile("[\ue000-\uf8ff\U000f0000-\U000ffffd\U00100000-\U0010fffd]")


def _marker(char: str) -> str:
    return f"[U+{ord(char):04X}]"


def mark(text: str) -> tuple[str, list[str]]:
    """`text` with each private-use character replaced by its marker, and
    the markers used, once each, in code-point order."""
    found = sorted(set(_PRIVATE_USE.findall(text)))
    return _PRIVATE_USE.sub(lambda m: _marker(m.group(0)), text), [_marker(c) for c in found]


def note(markers: list[str]) -> str:
    """The stderr line telling a reader the markers stand in for
    characters, so none is mistaken for the quoted text's own."""
    count = len(markers)
    noun = "character" if count == 1 else "characters"
    return f"  note: {count} private-use {noun} no font can set shown as {', '.join(markers)}"
