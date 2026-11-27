r"""Which TikZ libraries a draft's figures ask for, as one preamble load (#781).

A figure is `\input` inside a float, a group: a library's macros are defined
locally but its loaded flag globally, so the second float finds no macros.
Reloading per figure is worse: `positioning` appends to `\tikz@node@reset@hook`
on each load, shifting every node N times with a clean exit. So the renderer
loads them once in the preamble; a figure's own load line becomes a no-op, so
the file still compiles alone or in a user's thesis.

Reads source only, so it and its tests work without TeX Live.
"""

import re
import sys
from pathlib import Path

# `strip_comments` lives in a leaf module so `chitragupta.figure` can use it
# without importing this package; older callers still import it from here.
from chitragupta._tex_comments import strip_comments
from chitragupta.render_output._figures import _TEX_FORMATS, _resolve_sibling

# Regex, as `_figures.py` reads these files. PGF has no optional-argument form,
# so only space sits between the name and its brace.
_USETIKZLIBRARY_RE = re.compile(r"\\usetikzlibrary\s*\{([^}]*)\}")


def libraries_in(source: str) -> list[str]:
    r"""Every library one figure file loads, in source order, deduped.

    An empty name is dropped: `\usetikzlibrary{}` is fatal in TeX, and one
    figure's typo would become every render's failure.
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

    Sorted, not set order: output must be byte-identical across processes
    (docs/CODE-STANDARDS.md, "Repeatable"). An unresolvable or unreadable
    reference contributes nothing silently: `_figure_warnings` reports it, and
    a decode failure must not stop a render.
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

    A `--fragment` has no preamble, so one `[prefix] text` stderr line tells
    the skill what the `\input`ing document must load (docs/WRITE-A-BOOK.md).
    Silent when there is nothing to say.
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

    One string, since `\usetikzlibrary` needs `tikz` loaded first and pandoc's
    order for repeated variables is no contract. Never `\usetikzlibrary{}`.
    """
    load = r"\usepackage{tikz}"
    if not libraries:
        return load
    return load + r"\usetikzlibrary{" + ",".join(libraries) + "}"
