"""The `file` field the way reference managers actually escape it (#964).

A `file` field holds `Desc:path:mimetype` triples separated by `;`, and
the exporters escape exactly the characters that would otherwise be read
as one of those two delimiters, plus the escape itself:

- Zotero and Better BibTeX write a Windows path as
  `C\\:\\\\Users\\\\me\\\\x.pdf`, the drive colon and every backslash
  escaped;
- a `;` that belongs to a file name is written `\\;`;
- JabRef writes the same triple with an empty description, `:path:PDF`.

Splitting on a bare `:` rebuilt `C\\:\\Users\\me\\x.pdf`, which exists
nowhere, so every attachment of a Windows library resolved to "no PDF"
and sync exited 3.

A module of its own, beside `bib_reader` rather than inside it, for two
reasons: `bib_reader` is close to the 250-line ceiling, and this half is
stdlib-only where `bib_reader` needs bibtexparser, so a bare-python
caller can read a stored field without the parser.
"""

import re

# Exactly the three escapes the exporters write. `\\n` or `\\x` in a path
# is a backslash followed by a letter, and stays one.
_ESCAPE = re.compile(r"\\([\\:;])")


def split_unescaped(value: str, sep: str) -> list[str]:
    """`value` split on every `sep` no backslash escapes, escapes kept.

    A character scan rather than `re.split(r"(?<!\\\\):")`: a lookbehind
    sees `\\\\:` -- an escaped backslash, then a real separator -- as an
    escaped separator, which is the drive-letter shape this exists for.
    """
    pieces, current = [], []
    chars = iter(value)
    for char in chars:
        if char == "\\":
            # The escape and the character it escapes travel together, so
            # neither half is mistaken for a separator or a new escape.
            current.append(char + next(chars, ""))
        elif char == sep:
            pieces.append("".join(current))
            current = []
        else:
            current.append(char)
    pieces.append("".join(current))
    return pieces


def unescape(value: str) -> str:
    """`value` with the exporters' `\\\\`, `\\:` and `\\;` undone."""
    return _ESCAPE.sub(r"\1", value)


def attachments(file_field: str) -> list[tuple[str, str] | None]:
    """Each `;`-separated attachment as `(path, mimetype)`, unescaped, or
    `None` for one that is not `Desc:path:mimetype` at all.

    The path is everything between the first and the last part, rejoined
    with `:`, so a drive colon a hand edit left unescaped still lands in
    the path rather than splitting it.
    """
    found: list[tuple[str, str] | None] = []
    for attachment in split_unescaped(file_field, ";"):
        parts = split_unescaped(attachment, ":")
        if len(parts) < 3:
            found.append(None)
            continue
        found.append((unescape(":".join(parts[1:-1])), unescape(parts[-1])))
    return found
