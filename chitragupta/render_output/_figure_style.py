"""Whether each figure a draft names carries the current house block (#1013).

Reports; never writes. A renderer that rewrites its inputs at render
time is ruled out by #1013: the source a person reviewed would no longer
be the source that rendered. `python -m chitragupta figure sync` is the
writer, and every line here names it.

Only a `.tex` file directly inside a `figures/` directory is a figure,
the same rule `figure sync` walks by (docs/WRITING-STANDARDS.md §10): a
LaTeX draft may `\\input` its own sections too, and those carry no block.
A figure that cannot be resolved is `_figure_warnings`' to report, and
one that cannot be read is skipped -- an advisory must never be what
stops a render.
"""

from pathlib import Path, PurePosixPath

from chitragupta.figure import finding, load_house
from chitragupta.render_output._figures import _figure_refs, _resolve_sibling


def _figure_sources(text: str) -> list[str]:
    """Every figure file `text` references, once each, in order."""
    refs = dict.fromkeys(_figure_refs(text))
    return [ref for ref in refs if PurePosixPath(ref).parent.name == "figures"]


def warnings(text: str, input_path: Path) -> list[str]:
    """One `<ref>: <finding>` line per referenced figure that is not current."""
    refs = _figure_sources(text)
    if not refs:
        return []
    try:
        house = load_house()
    except (OSError, ValueError) as exc:
        return [f"house figure-style block unreadable ({exc}); figures not checked"]
    found = []
    for ref in refs:
        resolved = _resolve_sibling(input_path.parent, ref)
        if resolved is None:
            continue
        try:
            source = resolved.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        message = finding(source, house)
        if message:
            found.append(f"{ref}: {message}")
    return found
