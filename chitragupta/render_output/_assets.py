"""Local files a draft references, copied beside the rendered output.

A `tex` output must compile on its own, and a draft's references are never
grounds to read or write outside its directory.
"""

import re
import shutil
from pathlib import Path
from urllib.parse import unquote

from chitragupta import config
from chitragupta.render_output._citeproc import aliased_bib_text
from chitragupta.render_output._figures import (
    _figure_refs,
    _local_tex_include_refs,
    _resolve_sibling,
)


# Markdown image syntax, including CommonMark's `![alt](<my figure.png>)` for a
# path with a space (m-58). The alt text admits one level of nested brackets for a
# digest caption's `[@key]` cite (#991).
_MD_IMAGE_RE = re.compile(
    r"!\[(?:[^\[\]]|\[[^\[\]]*\])*\]"
    r'\((?:<(?P<angled>[^>]*)>|(?P<bare>[^)\s]+))(?:\s+"[^"]*")?\)'
)
# A URI scheme prefix (http:, https:, data:, ...) -- pandoc fetches these
# itself; nothing local to copy.
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _local_image_refs(text: str) -> list[str]:
    """Every local (non-URL) image path a Markdown draft references.

    Percent-decoded, since a bare destination spells a space as `%20` (m-58).
    """
    return [
        unquote(ref)
        for ref in (m.group("angled") or m.group("bare") for m in _MD_IMAGE_RE.finditer(text))
        if not _URI_SCHEME_RE.match(ref)
    ]


def _copy_local_images(input_path: Path, dest_dir: Path) -> None:
    """Copies every local image `input_path` references beside the output.

    Without this a `tex` output's `\\includegraphics` is unresolved (the `pdf`
    format reads images via `--resource-path`). An unresolvable reference is
    skipped for pandoc to report; one `_resolve_sibling` refuses (absolute,
    `..`, or a symlink out of the directory, #823) is skipped too.
    """
    for ref in _local_image_refs(input_path.read_text(encoding="utf-8")):
        src = _resolve_sibling(input_path.parent, ref)
        if src is None:
            continue
        _copy_beside(src, dest_dir / ref)


def _escapes(draft_dir: Path, ref: str) -> bool:
    """Whether `ref` is spelled inside `draft_dir` but lands outside it.

    pandoc and TeX open the spelled name, and the TeX read fence (#823, #1037)
    judges the name, not where a symlink leads. Absolute and `..` spellings
    answer False: the fence refuses those itself.
    """
    ref_path = Path(ref)
    if ref_path.is_absolute() or ".." in ref_path.parts:
        return False
    candidate = draft_dir / ref_path
    return candidate.is_file() and not config.resolves_inside(candidate, draft_dir)


def _refuse_escaping_refs(input_path: Path, text: str) -> None:
    """Raises `OutsideContentDir` when the draft names a file that is a
    symlink out of its own directory, before pandoc or the TeX engine runs.

    Skipping is not enough: pandoc and TeX open the spelled name, so the
    target was compiled in anyway (#823). Refused, since leaving it out would
    be a quietly wrong render. An `\\input` is checked with and without `.tex`.
    """
    refs = [(ref, (ref, f"{ref}.tex")) for ref in _local_tex_include_refs(text)]
    refs += [(ref, (ref,)) for ref in _local_image_refs(text)]
    for ref, spellings in refs:
        if any(_escapes(input_path.parent, spelling) for spelling in spellings):
            raise config.OutsideContentDir(
                f"{input_path} references {ref}, which resolves outside "
                f"{input_path.parent} through a symlink. pandoc and the TeX engine "
                "would read it wherever it points; copy the file into the "
                "draft's directory instead."
            )


def _copy_beside(src: Path, dst: Path) -> None:
    """Copies `src` to `dst`, unless they are the same (resolved) file.

    Not dead code: `--output-dir` may name the draft's own directory, where
    `shutil.copy2` raises `SameFileError`; that once failed a whole book.
    """
    if src.resolve() == dst.resolve():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_local_tex_includes(input_path: Path, dest_dir: Path) -> None:
    """Copies every `\\input{...}`/`\\include{...}` file beside the output,
    with `_copy_local_images`' skip rules and reasons (#222).
    """
    for ref in _figure_refs(input_path.read_text(encoding="utf-8")):
        src = _resolve_sibling(input_path.parent, ref)
        if src is None:
            continue
        _copy_beside(src, dest_dir / ref)


def _copy_book_bibliography(dest_dir: Path) -> None:
    """Writes the corpus bibliography into `dest_dir`, aliased for bibtex.

    A fragment defers citations to the book's `\\bibliography{...}`, which
    bibtex resolves in `content/rendered/<book>/`. `config.BIB_FILE_PATH` is
    the user's own export and is **never modified**; this writes a copy with
    `aliased_bib_text` applied so keys match the fragments' `\\citep{...}`.
    Idempotent across units: the aliasing covers the whole file. No
    bibliography is not an error here: the render failed earlier.
    """
    if not config.BIB_FILE_PATH.is_file():
        return
    text = config.BIB_FILE_PATH.read_text(encoding="utf-8")
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / config.BIB_FILE_PATH.name).write_text(aliased_bib_text(text), encoding="utf-8")
