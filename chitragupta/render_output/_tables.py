"""Tables: a caption in the draft, a number in every rendered format.

§13 has a Markdown draft write a table, a pandoc caption line, and an id marker:

    | Starting point | Core idea |
    |---|---|
    | DTaaS | One tenant-facing platform |

    : Where to start when building a first twin.
    <!-- table: start-here -->

referred to by `<!-- tableref: start-here -->`. The caption is text (it may
cite, and the gate must see it); only the id hides in a comment. The author
writes no number, since none is right in every format (pandoc 3.1.11.1):

- **LaTeX-bound**: a raw `\\label{}` survives into `\\caption{}`, so the
  consuming document decides ("Table 3" in an article, "Table 2.1" or flat
  numbering in a book, depending on its `secnumdepth`).
- **`md`**: never reaches pandoc, so the caption becomes a bold paragraph
  with a number counted here.
- **Everything else**: pandoc's writers number nothing, so the number is
  written into the caption.

Not pandoc-crossref's `@tbl:id`: the gate would read it as a fabricated
citekey. `.tex` fragments are untouched: their `\\begin{table}` is numbered
by the thesis (§13's carve-out).
"""

import re
from typing import NamedTuple


# Caption line and id marker directly under it. Adjacency is the contract that
# tells a caption from a paragraph starting with a colon (as §11's markers do).
_TABLE_RE = re.compile(
    r"^[ \t]*:[ \t]*(?P<caption>\S.*?)[ \t]*\n"
    r"[ \t]*<!--[ \t]*table:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*$",
    re.MULTILINE,
)

# A marker with no caption line above it, matched separately so it is reported
# as itself -- the same split `_math._LONE_MARKER_RE` makes.
_MARKER_RE = re.compile(r"^[ \t]*<!--[ \t]*table:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*$", re.MULTILINE)

# Inline, because it stands in for a noun phrase inside a sentence.
_REF_RE = re.compile(r"<!--[ \t]*tableref:[ \t]*(?P<id>\S+?)[ \t]*-->")

# Formats with a LaTeX counter. Same set as `_figures._TEX_FORMATS`, kept separate:
# figures care because TikZ draws nowhere else, a different reason that may change.
_LATEX_BOUND = {"tex", "latex", "pdf"}


class Table(NamedTuple):
    """One declared table. `line` is for `chitragupta/style_tables.py`'s
    reports; nothing in this module reads it.
    """

    id: str
    caption: str
    number: int
    line: int


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def tables(text: str) -> "list[Table]":
    """Every captioned, marked table in `text`, numbered in document order,
    which is LaTeX's counting order, so md/docx and pdf numbers agree.
    """
    return [
        Table(m.group("id"), m.group("caption"), number, line_of(text, m.start()))
        for number, m in enumerate(_TABLE_RE.finditer(text), start=1)
    ]


def references(text: str) -> "list[tuple[str, int]]":
    """Every `tableref` marker in `text`, as (id, 1-based line), for
    `style_tables.py`'s section checks.
    """
    return [(m.group("id"), line_of(text, m.start())) for m in _REF_RE.finditer(text)]


def _caption_for(table: Table, output_format: str) -> str:
    if output_format in _LATEX_BOUND:
        return f": {table.caption}\\label{{tab:{table.id}}}"
    if output_format == "md":
        return f"**Table {table.number}:** {table.caption}"
    return f": Table {table.number}: {table.caption}"


def _reference_for(table: Table, output_format: str) -> str:
    """The phrase a `tableref` marker expands to in `output_format`.

    The LaTeX form is wrapped in a raw-attribute span: pandoc's reader owns `~`
    (subscript) and would emit `Table\\textasciitilde{}\\ref{...}`. The
    `\\label` survives bare.
    """
    if output_format in _LATEX_BOUND:
        return f"`Table~\\ref{{tab:{table.id}}}`{{=latex}}"
    return f"Table {table.number}"


def substitute(text: str, output_format: str) -> str:
    """`text` with every caption numbered and every reference resolved.

    A reference to a missing table is left as is (deleting it would cut a noun
    phrase from a sentence); `warnings` reports it. Captions are numbered by
    position, so a reused id still numbers both; a reference to it takes the
    last, and `warnings` reports the collision.
    """
    declared = tables(text)
    by_id = {table.id: table for table in declared}
    in_order = iter(declared)

    def _caption(_match: "re.Match[str]") -> str:
        return _caption_for(next(in_order), output_format)

    text = _TABLE_RE.sub(_caption, text)

    def _reference(match: "re.Match[str]") -> str:
        table = by_id.get(match.group("id"))
        return match.group(0) if table is None else _reference_for(table, output_format)

    return _REF_RE.sub(_reference, text)


def warnings(text: str) -> "list[str]":
    """Every marker and reference in `text` that cannot resolve.

    Printed, never fatal: an unnumbered table is a smaller defect than a
    refused render.
    """
    ids = [table.id for table in tables(text)]
    # Both patterns end at the same marker line's end, so the end offset (not
    # the id) tells a captioned marker from an uncaptioned one reusing its id.
    captioned = {m.end() for m in _TABLE_RE.finditer(text)}
    found = [
        f"`{marker.group('id')}` has no caption line above its marker, so nothing numbers it"
        for marker in _MARKER_RE.finditer(text)
        if marker.end() not in captioned
    ]
    found += [
        f"`{table_id}` is declared by more than one table"
        for table_id in sorted(set(ids))
        if ids.count(table_id) > 1
    ]
    found += [
        f"`{ref}` is referred to but no table declares it"
        for ref in sorted({m.group("id") for m in _REF_RE.finditer(text)} - set(ids))
    ]
    return found
