"""Pandoc's Markdown citation grammar, for `chitragupta/citation_gate.py`.

The one definition every module that finds a Pandoc citation uses
(#1021), so they all agree. Standard library only, like the gate.
"""

import bisect
import re

from chitragupta._braced_keys import braced_keys

# Pandoc's citekey grammar: `:.#$%&-+?<>~/` only *between* key characters,
# so a sentence-final `.` is not eaten. A narrower body made the gate check
# a prefix (`[@smith:2020]` passed on `smith`, pandoc rendered `[?]`) and
# refused real Better-BibTeX keys.
# Letters and digits are Unicode's, as pandoc's (#1021). `*` may start a
# key: `@*` cites everything, so it is reported as key `*` and fails. A
# `:` or `/` may precede `/`, so URL-shaped keys read whole.
# A hyphen *run* is matched whole, unlike pandoc: bibtexparser produces
# `--` keys, and render_output/_citeproc.py aliases them for pandoc using
# this pattern. Matching pandoc here would refuse the key and drop it.
PANDOC_KEY = r"[\w*](?:\w|-+(?=\w)|[:.#$%&+?<>~/](?=\w)|[:/](?=/))*"

# Every `@` that could open a citation, with a suppressed-author `-`.
# What stands before decides, which a lookbehind cannot express (`_opens`).
_AT_RE = re.compile(rf"(-?)@(?:({PANDOC_KEY})|\{{)")
# Brackets unless escaped; a blank line (or a lone `>`) closes them. Blank
# in the *original* text: a blanked code line is still in its paragraph.
_BRACKET_RE = re.compile(r"\\[\s\S]|[\[\]]|\n[ \t>]*(?=\n)")


def _unescaped(text: str, slash: int) -> bool:
    """Whether the backslash at `slash` is itself unescaped: the run of
    backslashes ending there has odd length."""
    run = slash
    while run and text[run - 1] == "\\":
        run -= 1
    return (slash - run) % 2 == 0


def _escaped_char(text: str, at: int) -> bool:
    """Whether the character at `at` follows an unescaped backslash."""
    return at > 0 and text[at - 1] == "\\" and _unescaped(text, at - 1)


def _dot_run(text: str, pos: int) -> int:
    """How many unescaped `.` stand directly before `pos`."""
    start = pos
    while start and text[start - 1] == "." and not _escaped_char(text, start - 1):
        start -= 1
    return pos - start


def _after_tex_command(text: str, pos: int) -> bool:
    """Whether `pos` follows a raw TeX command, `\\name` or `\\name12`.

    Pandoc versions disagree on whether `@` after one opens a citation;
    reading all as citations covers both and can only over-report.
    """
    end = pos
    while end and text[end - 1] in "0123456789":
        end -= 1
    name = end
    while name and text[name - 1].isalpha():
        name -= 1
    return 0 < name < end and text[name - 1] == "\\" and _unescaped(text, name - 1)


def _opens(text: str, pos: int, latex: bool) -> bool:
    """Whether a citation may start at `pos`, by what stands before it.

    Anything but a letter, digit or `.` may (pandoc's rule); that alone
    keeps email addresses out. Excluding `_%+-` too hid real citations
    (#1021). An odd backslash run escapes the `@`, which keeps LaTeX's
    `\\@ifundefined` out of a gated `.tex`; an escaped `.` or one ending a
    three-dot ellipsis does not block. A raw TeX command before `@` counts
    only in Markdown: in `.tex`, `\\c@page` is a counter.
    """
    if pos == 0:
        return True
    before = text[pos - 1]
    if before == "\\":
        return not _unescaped(text, pos - 1)
    if before == ".":
        return _escaped_char(text, pos - 1) or _dot_run(text, pos) % 3 == 0
    if not before.isalnum():
        return True
    return not latex and _after_tex_command(text, pos)


def _inside_brackets(text: str, source: str) -> tuple[list[int], list[bool]]:
    """Each offset where bracket depth turns zero or non-zero, and which.

    Depth never goes below zero, erring towards "inside", where a label
    is a citation: the safe direction.
    """
    changes, inside = [0], [False]
    depth = 0
    for match in _BRACKET_RE.finditer(text):
        token = match.group()
        if token == "[":
            depth += 1
        elif token == "]":
            depth = max(depth - 1, 0)
        elif token.startswith("\n") and not source[match.start() : match.end()].strip(" \t>\n"):
            depth = 0
        if (depth > 0) != inside[-1]:
            changes.append(match.end())
            inside.append(depth > 0)
    return changes, inside


def citations(
    text: str,
    labels: "set[str] | frozenset" = frozenset(),
    *,
    latex: bool = False,
    source: "str | None" = None,
) -> list:
    """(start, end, key) of every citation pandoc reads in `text`, in order.

    `text` is already blanked from `source`; `latex` marks a `.tex` file.
    `labels` (example-list labels) are references, not citations, except
    inside a bracketed citation, where they still cite.
    """
    found = []
    braced = []
    for match in _AT_RE.finditer(text):
        at = match.start() + len(match.group(1))
        # A `-` marks the author suppressed, and opens only by `@`'s rule.
        if match.group(1) and _opens(text, match.start(), latex):
            start = match.start()
        elif match.group(1) or _opens(text, at, latex):
            start = at
        else:
            continue
        if match.group(2) is None:
            braced.append((start, match.end()))
        else:
            found.append((start, match.end(), match.group(2)))
    found.extend(braced_keys(text, braced))
    if any(key in labels for _, _, key in found):
        changes, inside = _inside_brackets(text, text if source is None else source)
        found = [
            cite
            for cite in found
            if cite[2] not in labels or inside[bisect.bisect_right(changes, cite[0]) - 1]
        ]
    return sorted(found)
