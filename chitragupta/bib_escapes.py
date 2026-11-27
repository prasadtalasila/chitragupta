"""The `file` field the way reference managers actually escape it (#964).

Exporters escape `:`, `;` and `\\` in `Desc:path:mimetype` triples, so a
Windows path arrives as `C\\:\\\\Users...`; splitting on a bare `:` made
every Windows attachment "no PDF" and sync exited 3. Stdlib-only, so a
bare-python caller can read a stored field without bibtexparser.
"""

import re

# Exactly the three escapes exporters write; `\\n` stays a backslash and n.
_ESCAPE = re.compile(r"\\([\\:;])")


def split_unescaped(value: str, sep: str) -> list[str]:
    """`value` split on every `sep` no backslash escapes, escapes kept.

    A scan, not a lookbehind split: `(?<!\\\\):` misreads `\\\\:` (escaped
    backslash, then a separator), the drive-letter shape.
    """
    pieces, current = [], []
    chars = iter(value)
    for char in chars:
        if char == "\\":
            # The escape travels with its character, so neither half splits.
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
