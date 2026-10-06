"""Pandoc's Markdown citation grammar, for `chitragupta/citation_gate.py`.

Split out of `citation_gate` for size (#1021). Every module that finds a
Pandoc citation -- the gate, `references_renumber`, the dossier's key
scan and the render's figure and citeproc checks -- takes it from here,
so what one of them reads as a citation the others read too. Standard
library only, like the gate.
"""

import bisect
import re

from chitragupta._braced_keys import braced_keys

# Pandoc's own citekey grammar, and the one definition of it in this
# package: a letter, digit, `_` or `*` start, then letters, digits and
# `_`, with `:.#$%&-+?<>~/` allowed only *between* them. The lookahead is
# what stops a sentence-final `.` or a closing `>` being eaten -- pandoc
# resolves `key` in "shown by @key.", not `key.`. Restricting the body to
# `[A-Za-z0-9_-]` truncated the key at the first of those characters, so
# the gate verified a *prefix* of what pandoc would look up: a draft
# citing `[@smith:2020]` passed on a ledger holding `smith`, and pandoc
# then rendered `[?]` -- the one thing this gate exists to catch. In the
# other direction a legitimate Better-BibTeX key (`doe.2020`) was refused
# as unknown, pushing an author to "fix" a correct citation.
#
# "Letter" and "digit" are Unicode's, as they are pandoc's (#1021): with
# ASCII classes `[@müller_2020]` was checked as the key `m` and
# `@日本_2021` was not seen at all, and the ledger admits such keys from
# a Better BibTeX export with key folding off. Python's `\w` is pandoc's
# `isAlphaNum` plus `_` on every character the differential test draws,
# a combining mark included: it ends the key in both. A digit may start
# a key (`[@3dprinting_2020]`), and so may `*`: `@*` is pandoc's
# cite-everything wildcard, which would put every entry in the bib file
# into the reference list, so it is reported as the key `*` and fails.
#
# A `:` or `/` may also stand before a `/`, as in pandoc's grammar, so a
# URL-shaped key reads whole: `[@a:/b]` cites `a:/b`, and `@c//d` cites
# `c//d`. Without it the gate checked the prefix `a` (#1021).
#
# A hyphen *run* is matched whole, deliberately unlike pandoc, which
# stops at `--` (verified against `pandoc -t json` on this host). Keys
# with a doubled hyphen are real here -- bibtexparser collapses
# "as-a-service" into `zech_digital-twins-as--service_2024` -- and
# render_output/_citeproc.py already repairs that for pandoc by aliasing
# the run away in a temp copy. That repair is driven by this pattern, so
# matching pandoc's truncation here would both refuse the key at the gate
# and leave the alias unbuilt, silently dropping the citation instead.
PANDOC_KEY = r"[\w*](?:\w|-+(?=\w)|[:.#$%&+?<>~/](?=\w)|[:/](?=/))*"

# Every `@` that could open a citation, with the `-` of a suppressed
# author if one comes first: a bare key, or the `{` of a braced one.
# Whether it does open one depends on what stands before it, which a
# lookbehind cannot express (`_opens`).
_AT_RE = re.compile(rf"(-?)@(?:({PANDOC_KEY})|\{{)")
# A bracket opens or closes a bracketed citation unless escaped, and a
# blank line ends the paragraph, closing any left open -- a line of only
# `>` included, which is a blockquote's blank line. Blank in the
# *original* text: a line blanking emptied (inline code, a comment) is
# still inside its paragraph, and reading it as a break closed the
# bracket early and dropped the citation in it.
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

    Pandoc 3.6's Markdown reader hands such a command to TeX, so the `@`
    after it is the first thing in a new inline, and opens a citation:
    `\\x@k` cites `k`. Pandoc 3.1 does so only after a name ending in
    digits (`\\xa12@k`), and a command either knows to take an argument
    (`\\emph@k`) swallows the `@`. Reading all of them as citations
    covers whichever pandoc renders, and can only over-report.
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

    Anything but a letter, a digit or a `.` may, which is pandoc's rule.
    That is what keeps an email address (`name@example.com`) from
    reading as a citation, and nothing more is needed for that: an
    address has a letter or digit before its `@`. The rule used to
    exclude `_%+-` as well, "for email addresses", and that hid `pre-@k`,
    `x_@k`, `x%@k` and `x+@k` from the gate while pandoc cited every one
    of them (#1021).

    A backslash before the `@` escapes it only when it is not itself
    escaped, so the run is counted: `\\@k` is no citation, `\\\\@k` is.
    Nor does a `.` block it when escaped (`\\.@k`), or when it ends a run
    of three that pandoc's smart punctuation reads as an ellipsis
    (`x...@k`; `x....@k` is an ellipsis and a full stop).
    The odd case is what keeps LaTeX's @-as-letter idiom (`\\makeatletter
    ... \\@ifundefined`) out, which matters because a thesis chapter's
    `.tex` is gated too. For the same reason a raw TeX command before the
    `@` (`_after_tex_command`) counts only in Markdown: in a `.tex` file
    `\\c@page` is LaTeX's own counter, not a citation.
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

    Depth counts nested brackets and never goes below zero, so a stray
    `]` cannot close a group still open. Erring towards "inside" is the
    safe direction for `citations` below: inside, a label is a citation.
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

    `text` has had its code and other non-prose blanked already, from
    `source` (`text` itself when not given), and `latex` says it is a
    `.tex` file's (`_opens`). `labels` are the
    example-list labels it defines (`_markdown_inert`): pandoc reads
    `@label`, `(@label)` and `@{label}` as a reference to that example,
    not a citation, everywhere except inside a bracketed citation
    (`[@label]`, `[see @label, p. 3]`), where it still cites.
    """
    found = []
    braced = []
    for match in _AT_RE.finditer(text):
        at = match.start() + len(match.group(1))
        # The `@` after a `-` may always open one; the `-` itself, which
        # marks the author suppressed, only by the same rule as an `@`.
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
