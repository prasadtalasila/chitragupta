"""A draft cut into the sections `draft diff` compares, each with its body.

The heading scan is `chitragupta.dossier._sections.sections()`, reused so
that fenced code and LaTeX verbatim are skipped by the one rule the
dossier already applies. What is narrowed here is which headings start a
section: in Markdown the `#` line is the document's title, not a
section, so it stays with the text above the first `##`; in LaTeX only
`\\chapter`, `\\section` and `\\subsection` cut, and anything finer stays
inside its parent. A diff reported per `\\paragraph` would scatter one
edit across headings no reader thinks of as sections.
"""

from dataclasses import dataclass, field

from chitragupta.dossier._sections import sections
from chitragupta.render_output._paths import _MARKDOWN_SUFFIXES

LEADING = "(before the first heading)"

# Every character `str.splitlines()` breaks on besides "\n". The gate
# numbers a citekey's line by counting "\n" alone, so the heading scan is
# handed a copy with these blanked to spaces: one character for one, so
# both count the same lines and a key is placed in the section it sits in.
OTHER_BREAKS = str.maketrans(dict.fromkeys("\r\v\f\x1c\x1d\x1e\x85\u2028\u2029", " "))

# `sections()` levels: `\chapter` 1, `\section` 2, `\subsection` 3.
_TEX_DEEPEST = 3


@dataclass(frozen=True)
class Section:
    """One section of a version, keyed by (title, occurrence)."""

    title: str
    occurrence: int  # 0 for the first section with this title
    body: str
    # 1-indexed lines the section covers, its heading included, so a
    # citekey's line can be placed. Not part of a section's identity.
    first_line: int = field(default=1, compare=False)
    last_line: int = field(default=1, compare=False)


def _cuts(text: str, suffix: str, lines: list[str]) -> list[tuple[str, int]]:
    """(title, heading line) for every heading that starts a section."""
    markdown = suffix in _MARKDOWN_SUFFIXES
    found = []
    for heading in sections(text):
        is_md = lines[heading.start - 1].lstrip().startswith("#")
        if markdown and is_md and heading.level >= 2:
            found.append((heading.title, heading.start))
        elif not markdown and not is_md and heading.level <= _TEX_DEEPEST:
            found.append((heading.title, heading.start))
    return found


def split(text: str, suffix: str) -> list[Section]:
    """`text` as its sections, in order, with the text above the first one
    as a section of its own when it holds anything but whitespace."""
    flat = text.translate(OTHER_BREAKS)
    lines = text.split("\n")
    cuts = _cuts(flat, suffix, flat.split("\n"))
    starts = [start for _, start in cuts]
    found = []
    first = starts[0] if starts else len(lines) + 1
    leading = "\n".join(lines[: first - 1]).strip()
    if leading:
        found.append(Section(LEADING, 0, leading, 1, first - 1))
    seen: dict[str, int] = {}
    for (title, start), end in zip(cuts, [*starts[1:], len(lines) + 1]):
        occurrence = seen.get(title, 0)
        seen[title] = occurrence + 1
        body = "\n".join(lines[start : end - 1]).strip("\n")
        found.append(Section(title, occurrence, body, start, end - 1))
    return found


def title_at(split_sections: list[Section], line: int) -> str:
    """The title of the section holding 1-indexed `line`.

    The only lines `split()` leaves out are blank ones above the first
    heading, which hold no citekey; should one be asked about anyway, it
    is above the first heading, and is named so.
    """
    held = (s.title for s in split_sections if s.first_line <= line <= s.last_line)
    return next(held, LEADING)
