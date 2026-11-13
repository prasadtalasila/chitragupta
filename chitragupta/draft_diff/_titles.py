"""Heading titles in one plain form, from LaTeX or from Markdown.

The redline places a margin note at a heading only where the change
report's title for a section and the heading's argument in latexdiff's
output read the same. They start far apart: pandoc wraps a heading that
holds code or emphasis in `\\texorpdfstring`, spells dashes out and
moves an `{#id}` attribute into a label, while the report keys a
Markdown section by its raw title. Both are reduced here to the same
plain text (#1194).
"""

import re

from chitragupta.render_output._paths import _MARKDOWN_SUFFIXES


def group_end(text: str, opened: int) -> int:
    """The offset just past the `}` closing the group whose `{` is at `opened`."""
    depth, at = 0, opened
    while at < len(text):
        char = text[at]
        if char == "\\":
            at += 2
            continue
        depth += char == "{"
        depth -= char == "}"
        at += 1
        if depth == 0:
            return at
    return len(text)


def _without_groups(text: str, command: re.Pattern) -> str:
    """`text` with every `command{...}`, argument and all, taken out."""
    while match := command.search(text):
        text = text[: match.start()] + text[group_end(text, match.end() - 1) :]
    return text


_DELETED = re.compile(r"\\(?:DIFdel|DIFdelFL|label)\{")
_COMMENT = re.compile(r"(?<!\\)%.*")
_ESCAPED = re.compile(r"\\([^A-Za-z])")
_CONTROL_WORD = re.compile(r"\\[A-Za-z@]+\*?")
_TEXORPDFSTRING = re.compile(r"\\texorpdfstring\s*\{")

# A Markdown heading's markup, which pandoc turns into LaTeX the plain
# title no longer shows: code backticks, `*`/`_` emphasis (an `_` inside
# a word is a character, as in `my_var`), and a trailing `{#id}`,
# `{.class}` or `{-}` attribute.
_MD_ATTRIBUTES = re.compile(r"\s*\{[#.-][^{}]*\}\s*$")
_MD_MARKUP = re.compile(r"`+|\*+|(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])")


def _first_arguments(text: str) -> str:
    """`text` with each `\\texorpdfstring{tex}{plain}` reduced to `tex`.

    pandoc wraps a heading holding markup in one, and the PDF string
    repeats its words: kept whole, the title reads twice over.
    """
    while match := _TEXORPDFSTRING.search(text):
        first_end = group_end(text, match.end() - 1)
        rest = first_end
        if text[first_end : first_end + 1] == "{":
            rest = group_end(text, first_end)
        text = text[: match.start()] + text[match.end() : first_end - 1] + text[rest:]
    return text


def _plain(text: str) -> str:
    """Dashes as one character each, whitespace normalised: the form both
    sides of a title comparison end in. pandoc spells `—` as `---`."""
    return " ".join(text.replace("---", "—").replace("--", "–").split())


def plain_title(argument: str) -> str:
    """A heading's argument as the change report titles it: deleted text,
    labels, comments and markup gone, whitespace normalised."""
    text = _COMMENT.sub("", _without_groups(argument, _DELETED))
    text = _CONTROL_WORD.sub("", _first_arguments(text))
    text = _ESCAPED.sub(r"\1", text).replace("~", " ")
    return _plain(text.replace("{", "").replace("}", ""))


def report_title(title: str, suffix: str) -> str:
    """A change report's section title in `plain_title`'s form.

    A `.tex` draft's title is LaTeX, read as a heading's argument is; a
    Markdown one loses its markup and attribute, as pandoc's output does.
    """
    if suffix not in _MARKDOWN_SUFFIXES:
        return plain_title(title)
    return _plain(_MD_MARKUP.sub("", _MD_ATTRIBUTES.sub("", title)))
