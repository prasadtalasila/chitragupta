r"""Which TikZ libraries a draft's figures ask for, as one preamble load.

#781. `\usetikzlibrary` is legal in the document body, and figure files
have always carried their own -- but a figure file is `\input` inside a
`figure` float, and a float is a group. The library's macros are defined
*locally* there while `\tikz@library@<name>@loaded` is set *globally*, so
the second float skips the load and finds none of the macros. Every
per-figure workaround for that is worse, because
`tikzlibrarypositioning.code.tex` appends to `\tikz@node@reset@hook`
globally on each load, so N loads shift every node N times. Measured on a
`book`-class document inputting one `positioning` figure into three
floats with the loaded flag cleared between them: the node sat at
71.26pt, then 128.17pt, then 185.07pt, with `pdflatex` exiting 0 and
nothing in the log. That is the reported symptom -- figures spilling off
the page of an assembled book that built cleanly.

So the renderer loads them once, ungrouped, in the preamble. A figure
file keeps its own plain load line and is then a no-op that appends
nothing, which is what lets the same file still compile in the two
documents this pipeline does not write: `thesis-chapter-writer`'s
fragment inside a user's own thesis, and the minimal probe document
`chitragupta.review figure` and docs/WRITING-STANDARDS.md §10 build
around one figure.

This module reads figure *source* and never compiles anything, which is
what keeps it -- and its tests -- working on a host with no TeX Live.
"""

import re
import sys
from pathlib import Path

from chitragupta.render_output._figures import _TEX_FORMATS, _resolve_sibling

# A TeX comment: `%` to the end of the line. Stripped before any pattern
# here runs, and before `review/figure_layout`'s own source checks run --
# #404, where every symptom was a *wrong* answer rather than a missing
# one. A commented-out `\draw` was reported as an edge the figure claims;
# a commented-out `\node`'s label was measured for length; and worst, a
# comment merely *mentioning* a node declaration made the probe ask
# pdflatex for a shape nothing had drawn, so the aid reported a figure
# that compiles fine as one that does not. For this module the same rule
# has a second edge: a commented-out `\usetikzlibrary` would otherwise
# put a library in the preamble no figure uses, and a misspelled name
# inside a comment would fail the whole render (docs/TIKZ-STYLE.md -- a
# missing name takes the whole call down).
#
# `\%` is a literal percent sign and does not start a comment, hence the
# lookbehind. `\\%` -- an escaped backslash followed by a real comment --
# is read the wrong way by that lookbehind and is left alone: it needs a
# character-by-character scan rather than a regex, and no figure this
# pipeline draws has produced one.
#
# This is the canonical definition. `review/figure_layout/_source.py`
# imports it from here rather than keeping its own, because the
# dependency runs review -> render_output and never back.
_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")

# The load itself. Deliberately regex over TikZ rather than a LaTeX
# parser, matching how `_figures.py` already reads these same files. PGF
# has no optional-argument form of this macro, so there is nothing
# between the name and its brace but space.
_USETIKZLIBRARY_RE = re.compile(r"\\usetikzlibrary\s*\{([^}]*)\}")


def strip_comments(source: str) -> str:
    """`source` with every TeX comment removed.

    The first thing every reader of a figure's source here does. See
    `_COMMENT_RE` for what that fixes and what it deliberately does not.
    """
    return _COMMENT_RE.sub("", source)


def libraries_in(source: str) -> list[str]:
    r"""Every library one figure file loads, in source order, deduped.

    An empty name is dropped rather than carried: `\usetikzlibrary{}`
    fails fatally in TeX on the comma list rather than skipping, so
    re-emitting one into the preamble would turn one figure's typo into
    every render's failure.
    """
    names: list[str] = []
    for group in _USETIKZLIBRARY_RE.findall(strip_comments(source)):
        for raw in group.split(","):
            name = raw.strip()
            if name and name not in names:
                names.append(name)
    return names


def library_union(figure_refs: list[str], draft_dir: Path) -> list[str]:
    """Every library the draft's figures ask for, sorted.

    Sorted rather than first-seen: this string lands in the preamble of
    every render, a `set` iterates in hash order, Python randomises
    string hashing per process, and byte-identical output over unchanged
    input is a product rule here (docs/CODE-STANDARDS.md, "Repeatable").

    A reference that does not resolve to a readable file under the
    draft's own directory contributes nothing and says nothing --
    `_figure_warnings` is what reports a missing figure, and a second
    report of the same fact from the preamble builder would be noise.
    `errors="replace"` for the reason `_figure_has_citekey` uses it: a
    figure file that is not valid UTF-8 is its own problem, and raising
    here would make the preamble builder the thing that stops a render.
    """
    found: set[str] = set()
    for ref in figure_refs:
        resolved = _resolve_sibling(draft_dir, ref)
        if resolved is not None:
            found.update(libraries_in(resolved.read_text(encoding="utf-8", errors="replace")))
    return sorted(found)


def preamble_libraries(
    figure_refs: list[str], draft_dir: Path, fragment: bool, output_format: str
) -> list[str]:
    r"""The union for this render, reporting it when nothing can load it.

    A `--fragment` render emits no preamble, so the load this module
    exists to produce reaches nothing there and the document that
    `\input`s the unit has to carry it -- the same structural reason
    `fvextra` and `\LTcapwidth` are in `book-assembler`'s own preamble
    (docs/WRITE-A-BOOK.md). One stderr line says which, in the `[prefix] text`
    shape `render()` already prints every figure, table and equation
    warning in, because the consumer is a skill reading the render's
    output rather than a caller reading a return value.

    Printed only when there is something to say: a standalone render has
    it in its own preamble, and a fragment whose figures load nothing
    would otherwise get a line naming no library.
    """
    libraries = library_union(figure_refs, draft_dir)
    if fragment and libraries and output_format in _TEX_FORMATS:
        print(
            f"[tikz-libraries] {','.join(libraries)} -- a fragment has no preamble; "
            "load these in the assembling document",
            file=sys.stderr,
        )
    return libraries


def header_include(libraries: list[str]) -> str:
    r"""The `header-includes` value for a draft that has a figure.

    One string rather than two `--variable` arguments, because
    `\usetikzlibrary` needs `tikz` already loaded and pandoc's
    concatenation order for repeated variables is not a contract worth
    leaning on. An empty union emits the package alone -- never
    `\usetikzlibrary{}`, which is fatal.
    """
    load = r"\usepackage{tikz}"
    if not libraries:
        return load
    return load + r"\usetikzlibrary{" + ",".join(libraries) + "}"
