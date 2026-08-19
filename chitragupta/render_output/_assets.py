"""Local files a draft references, copied beside the rendered output.

Images and TikZ figures, on the same rule and for the same reason: a
`tex` output has to be compilable on its own, and a draft's own
references are never grounds to read or write outside its directory.
"""

import re
import shutil
from pathlib import Path

from src.render_output._figures import _figure_refs, _resolve_sibling


# Matches Markdown image syntax: ![alt](path) or ![alt](path "title").
_MD_IMAGE_RE = re.compile(r'!\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
# A URI scheme prefix (http:, https:, data:, ...) -- pandoc fetches these
# itself; nothing local to copy.
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _local_image_refs(text: str) -> list[str]:
    """Every local (non-URL) image path a Markdown draft references."""
    return [
        ref for ref in (m.group(1) for m in _MD_IMAGE_RE.finditer(text))
        if not _URI_SCHEME_RE.match(ref)
    ]


def _copy_local_images(input_path: Path, dest_dir: Path) -> None:
    """Copies every local image `input_path` references alongside the
    rendered output in `dest_dir`, so a `tex` output is actually
    self-contained and compilable on its own (`cd` to the directory the
    render landed in -- see `_output_dir` -- and `pdflatex *.tex`).

    Without this, pandoc's LaTeX writer emits `\\includegraphics{path}`
    verbatim, unresolved and uncopied -- the `pdf` format only looks fine
    because pandoc's own internal pdflatex pass reads the image directly
    via `--resource-path` below, in a temp dir this function never touches.
    A relative `path` an image reference doesn't resolve to a real file
    under `input_path`'s own directory is silently skipped here (letting
    pandoc's own missing-resource handling surface it, same as today), as
    is any reference that would resolve outside `input_path`'s directory
    (absolute, or `..`-escaping) -- a draft's image references are never a
    reason to write outside `dest_dir`.
    """
    for ref in _local_image_refs(input_path.read_text(encoding="utf-8")):
        ref_path = Path(ref)
        if ref_path.is_absolute() or ".." in ref_path.parts:
            continue
        src = input_path.parent / ref_path
        if not src.is_file():
            continue
        _copy_beside(src, dest_dir / ref_path)


def _copy_beside(src: Path, dst: Path) -> None:
    """Copies `src` to `dst`, unless they are the same file.

    Rendering *into the draft's own directory* is a real case, not a
    degenerate one: `--output-dir` exists so a book's fragments land
    beside the `book.tex` that \\input-s them, which is the directory the
    chapters already live in. There the source and the destination of
    every figure and image are the same path, and `shutil.copy2` raises
    `SameFileError` rather than doing nothing -- which failed all fifteen
    fragment conversions of a real book at once (2026-08-19). Compared by
    resolved path, so a symlinked output directory is caught too.
    """
    if src.resolve() == dst.resolve():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_local_tex_includes(input_path: Path, dest_dir: Path) -> None:
    """Copies every `\\input{...}`/`\\include{...}` file `input_path`
    references alongside the rendered output in `dest_dir`, mirroring
    `_copy_local_images` exactly -- same skip rules (absolute, or
    `..`-escaping, or not a real file under `input_path`'s own
    directory), for the same reason: a `tex` output must be
    self-contained and compilable on its own, and a draft's own
    references are never a reason to write outside `dest_dir` (#222).
    """
    for ref in _figure_refs(input_path.read_text(encoding="utf-8")):
        src = _resolve_sibling(input_path.parent, ref)
        if src is None:
            continue
        _copy_beside(src, dest_dir / ref)
