"""What an assembled book pulls in, and where its own citekeys come from.

Split from `chitragupta/review/citekey_union.py` because resolving an
assembly's includes is a separate job from the set arithmetic over them,
and because getting it wrong is the difference between a useful report
and a wholly false one.

**A book is composed by reference, not by fusion**, and that is the fact
this module exists to handle. `.claude/skills/book-assembler` writes
`book.tex` as *structure only* -- "every word of prose lives in the units
this file \\inputs" -- and resolves each unit's citations per unit through
citeproc, so the numbered IEEE reference lists live in the unit renders
and **`book.tex` itself contains no citekey at all**. `book.md` is the
same shape in Markdown: a table of contents hyperlinking the chapter
files, never their prose.

So reading the assembly's own text for citekeys and subtracting finds
nothing and would report every unit's sources as lost. What actually
answers "did the citekeys come out?" is *which units the assembly
includes*: including a unit includes all of its prose, so omitting one
drops every source only it stood on. That is the same invariant, read
against the artefact this pipeline really produces.

The assembly does still have citekeys of its own, and they are the other
direction's whole subject: anything in a file it includes that is **not**
an acceptance unit -- a title page, a hand-written appendix, a preamble
definitions file. A citekey entering there entered outside any unit's
record, which is exactly what `appeared` reports.

**Deliberately not a second `\\input` parser**, the same call
`chitragupta/review/figure_layout/` already made across this same
boundary: `render_output/_figures.py` owns how a LaTeX include is spelled
and the rule that a draft's own text never resolves outside its own
directory, so both are imported rather than restated. Only the two things
that module has no reason to know are local -- a Markdown *link* (it
matches image syntax, and a book's table of contents is not images) and
the suffix a bare `\\input{foo}` leaves off.
"""

import re
from pathlib import Path

from chitragupta.render_output._assets import _URI_SCHEME_RE
from chitragupta.render_output._figures import _local_tex_include_refs, _resolve_sibling

# A Markdown link to a local file: `[Chapter 1](01-chapter.md)`. Not
# `_local_image_refs`, which matches `![alt](path)` -- an assembled
# `book.md` is a table of contents linking its chapters, and an image
# reference is not an include.
_MD_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")

# The suffixes a bare include may leave off. LaTeX's `\input{foo}` means
# `foo.tex`; `.def` is here because book-assembler's own preamble inputs
# `citeproc-defs.def`, and `.md` because a unit may be drafted as one.
_SUFFIXES = (".tex", ".md", ".def")


def references(text: str) -> list[str]:
    """Every local file the assembly names, in document order, deduplicated.

    Order is kept because the report walks the book's own structure, and
    an include repeated in a preamble should not be listed twice. A link
    with a URI scheme is dropped here rather than by `_resolve_sibling`,
    which would only report it as "not found on disk" -- a URL was never
    going to be a file, and naming it as a coverage gap would be noise.
    """
    found: list[str] = []
    for target in _local_tex_include_refs(text) + _MD_LINK.findall(text):
        if target and not _URI_SCHEME_RE.match(target) and target not in found:
            found.append(target)
    return found


def _resolve(book: Path, target: str) -> Path | None:
    """`target` as a file beside the assembly, or None if none exists.

    `_resolve_sibling` first and unmodified, so the absolute-path and
    `..`-escape refusals stay in one place. The suffix loop is the one
    thing it cannot do for us: `\\input{foo}` and `\\input{foo.tex}` are
    the same file to LaTeX, and the shipped book.tex uses both forms.
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

    An include is a unit when its **stem** is an acceptance unit id --
    matched by id rather than by filename, because a unit may be drafted
    as `.md` and rendered to `.tex` for assembly, and the two are the same
    unit. Everything else is the assembly's own material, and its text is
    returned for the caller to take citekeys from -- read here, once,
    rather than resolved here and opened again there.

    **Two ways an include goes unread, and both are returned rather than
    dropped.** It may resolve to no file at all; or it may resolve to
    something that is not text -- a `book.md` may link a cover image or a
    PDF, and `\\input` will happily name a file this cannot decode. Reading
    one raises `UnicodeDecodeError` mid-run, which would take the whole
    report out over a file that was never going to carry a citekey. A
    report that silently ignored either would be claiming coverage of
    material it never saw, so they are named instead.
    """
    included: set[str] = set()
    others: list[tuple[str, str]] = []
    unread: list[str] = []
    for target in references(text):
        stem = Path(target).stem
        if stem in unit_ids:
            included.add(stem)
            continue
        resolved = _resolve(book, target)
        if resolved is None:
            unread.append(target)
            continue
        try:
            others.append((resolved.name, resolved.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            unread.append(target)
    return included, others, unread
