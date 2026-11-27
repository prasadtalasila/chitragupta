"""Private-use characters a report quotes from a source, written as a
marker the render can set (#1125).

PDF text layers carry private-use code points no render font has, and a
missing glyph is a build error. Right for a draft (#996), but in a
report the character came from the source, so it is written `[U+E230]`
in the `.md`/`.tex`/`.pdf`; the `.json` keeps the original. Stdlib-only.
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
