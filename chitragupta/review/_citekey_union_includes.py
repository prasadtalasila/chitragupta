"""What an assembled book pulls in, and where its own citekeys come from.

A book is composed by reference: `book.tex` is structure only and holds no
citekey (units keep `\\citep{key}` until the book's one bibtex pass), and
`book.md` is a table of contents. So the answer to "did the citekeys come
out?" is which units the assembly includes; omitting one drops every
source only it stood on. Citekeys in included non-unit files (title page,
appendix, preamble) entered outside any record, which `appeared` reports.

Not a second `\\input` parser: `render_output/_figures.py` owns include
spelling and the no-escape rule. Only Markdown links and the suffix a bare
`\\input{foo}` leaves off are local.
"""

import re
from pathlib import Path

from chitragupta.render_output._assets import _URI_SCHEME_RE
from chitragupta.render_output._figures import _local_tex_include_refs, _resolve_sibling

# A link, not `_local_image_refs`: `book.md` links its chapters.
_MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")

# Suffixes a bare include may leave off; `.def` for books assembled before
# citations were deferred (`citeproc-defs.def`), `.md` for a unit drafted so.
_SUFFIXES = (".tex", ".md", ".def")


def references(text: str) -> list[str]:
    """Every local file the assembly names, in document order, deduplicated.
    URI-scheme links are dropped here: a URL reported "not found on disk"
    would be noise.
    """
    found: list[str] = []
    for target in _local_tex_include_refs(text) + _MD_LINK.findall(text):
        if target and not _URI_SCHEME_RE.match(target) and target not in found:
            found.append(target)
    return found


def _resolve(book: Path, target: str) -> Path | None:
    """`target` as a file beside the assembly, or None if none exists.
    `_resolve_sibling` keeps the absolute and `..`-escape refusals; the
    suffix loop is because `\\input{foo}` and `{foo.tex}` are one file.
    """
    direct = _resolve_sibling(book, target)
    if direct is not None:
        return direct
    for suffix in _SUFFIXES:
        with_suffix = _resolve_sibling(book, f"{target}{suffix}")
        if with_suffix is not None:
            return with_suffix
    return None


def split(
    book: Path, text: str, unit_ids: set[str]
) -> tuple[set[str], list[tuple[str, str]], list[str]]:
    """`(unit ids included, (name, text) per non-unit file read, names not read)`.

    An include is a unit when its stem is an acceptance unit id (a unit may
    be `.md` or `.tex`), but it must still resolve: an id match alone
    reported a deleted chapter as included (#496). An include that resolves
    to no file, or to an undecodable one (a cover image), is returned as
    unread, never dropped, so the report claims no coverage it lacks.
    """
    included: set[str] = set()
    others: list[tuple[str, str]] = []
    unread: list[str] = []
    for target in references(text):
        stem = Path(target).stem
        resolved = _resolve(book, target)
        if resolved is None:
            unread.append(target)
            continue
        if stem in unit_ids:
            included.add(stem)
            continue
        try:
            others.append((resolved.name, resolved.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            unread.append(target)
    return included, others, unread
