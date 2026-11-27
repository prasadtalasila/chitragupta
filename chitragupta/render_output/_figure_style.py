"""Whether each figure a draft names carries the current house block (#1013).

Reports; never writes: a render-time rewrite would make the rendered
source differ from the reviewed one. `figure sync` is the writer.
Only a `.tex` directly inside `figures/` is a figure (WRITING-STANDARDS §10).
An unreadable figure is skipped: an advisory must never stop a render.
"""

from pathlib import Path, PurePosixPath

from chitragupta.figure import finding, load_house
from chitragupta.render_output._figures import _figure_refs, _resolve_sibling


def _figure_sources(text: str) -> list[str]:
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
