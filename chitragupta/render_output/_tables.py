"""Tables: a caption in the draft, a number in every rendered format.

`docs/WRITING-STANDARDS.md` §13 has a Markdown draft write a table, a
native pandoc caption line, and an id marker under it:

    | Starting point | Core idea |
    |---|---|
    | DTaaS | One tenant-facing platform |

    : Where to start when building a first twin.
    <!-- table: start-here -->

and refer to it with an inline `<!-- tableref: start-here -->`, which
expands to the whole reference phrase. The author writes no number,
because there is no number a draft can carry that is right in every
format it renders to -- see the three cases below.

**Why the caption is text and only the id is a marker.** A caption may
cite, and `chitragupta/citation_gate.py` is this project's one gate; a
caption is also prose a reader of the draft is meant to see. The id is
neither, so the id is what hides in a comment.

**Three cases, not `_math.py`'s one predicate.** Each was measured
against pandoc 3.1.11.1 rather than assumed:

- **LaTeX-bound** (`tex`/`latex`/`pdf`): the caption keeps its pandoc
  spelling and gains a raw `\\label{}`, which survives the Markdown
  reader into `\\caption{...\\label{...}}` -- so LaTeX numbers the table
  itself, and a reference becomes `Table~\\ref{}`. That is what makes the
  same unit read "Table 3" in an `article` and "Table 2.1" inside an
  assembled `book` that numbers its chapters -- or "Table 5" in one that
  does not, since `book-assembler` suppresses chapter numbering
  (`\\setcounter{secnumdepth}{-2}`) for units that number their own
  headings, and a table then counts flat across the whole book. Both
  measured; the point is that the *consuming* document decides, which is
  why no number belongs in a draft.
- **`md`**: this format never reaches pandoc at all
  (docs/RENDERING-FLOW.md), so a caption line would land in
  `content/rendered/` as a stray colon and nothing would number it. The
  caption becomes a bold paragraph carrying a number counted here.
- **Everything else** (`docx`, `html`, ...): pandoc's own writers number
  nothing -- a captioned table round-trips through the docx writer as a
  bare caption paragraph -- so the caption stays a caption and the number
  is written into it.

Pandoc-crossref's `@tbl:id` spelling is not available here, and not for
reasons of taste: `citation_gate.py`'s `_PANDOC_CITE_RE` matches a bare
`@key`, so `@tbl:start-here` reads as the citekey `tbl` and fails the
gate as a fabricated reference.

Nothing here touches a `.tex` fragment. `thesis-chapter-writer` writes a
real `\\begin{table}` with its own `\\caption` and `\\label`, numbered by
the thesis that `\\input`s it -- §13's carve-out, the same shape as §10's
inline TikZ -- and pandoc's LaTeX reader already numbers `\\ref` for the
`.md` preview.
"""

import re
from typing import NamedTuple


# The caption line, in pandoc's own spelling, and the id marker directly
# under it. Adjacency is the contract: it is what lets one regex tell a
# caption from an ordinary paragraph that happens to start with a colon,
# and it mirrors §11's `<!-- single-source: -->`, which sits against its
# own paragraph the same way.
_TABLE_RE = re.compile(
    r"^[ \t]*:[ \t]*(?P<caption>\S.*?)[ \t]*\n"
    r"[ \t]*<!--[ \t]*table:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*$",
    re.MULTILINE,
)

# A marker with no caption line above it. Matched separately so "you
# wrote a marker and no caption" is reported as itself rather than as a
# table nobody refers to -- the same split `_math._LONE_MARKER_RE` makes.
_MARKER_RE = re.compile(r"^[ \t]*<!--[ \t]*table:[ \t]*(?P<id>\S+)[ \t]*-->[ \t]*$", re.MULTILINE)

# The reference. Inline rather than on a line of its own, because it
# stands in for a noun phrase inside a sentence.
_REF_RE = re.compile(r"<!--[ \t]*tableref:[ \t]*(?P<id>\S+?)[ \t]*-->")

# The formats pandoc hands to LaTeX, and so the only ones where a counter
# exists to defer numbering to. Same set as `_figures._TEX_FORMATS`, kept
# separate rather than imported: a figure's reason for caring is that
# TikZ cannot draw anywhere else, which is not this reason, and one of
# the two could legitimately change.
_LATEX_BOUND = {"tex", "latex", "pdf"}


class Table(NamedTuple):
    """One declared table: what refers to it, what it says, which number
    it takes in a format that has to be told, and where its caption is.

    `line` is here for `chitragupta/style_tables.py`, which reports a
    table nobody explains and has to say where. Nothing in this module
    reads it: a render either resolves a marker or warns about it by
    name, and neither needs a position.
    """

    id: str
    caption: str
    number: int
    line: int


def line_of(text: str, offset: int) -> int:
    """The 1-based line `offset` falls on."""
    return text.count("\n", 0, offset) + 1


def tables(text: str) -> "list[Table]":
    """Every captioned, marked table in `text`, numbered in document order.

    Document order is LaTeX's own counting order, which is what keeps the
    number this module writes for `md`/`docx` and the number LaTeX writes
    for `pdf` pointing at the same table.
    """
    return [
        Table(m.group("id"), m.group("caption"), number, line_of(text, m.start()))
        for number, m in enumerate(_TABLE_RE.finditer(text), start=1)
    ]


def references(text: str) -> "list[tuple[str, int]]":
    """Every `tableref` marker in `text`, as (id, 1-based line).

    Also for `style_tables.py`: which *section* a reference sits in is
    what tells a table the prose reads from one it merely stands beside,
    and that is a line-number question.
    """
    return [(m.group("id"), line_of(text, m.start())) for m in _REF_RE.finditer(text)]


def _caption_for(table: Table, output_format: str) -> str:
    """The caption line `table` gets in `output_format`."""
    if output_format in _LATEX_BOUND:
        return f": {table.caption}\\label{{tab:{table.id}}}"
    if output_format == "md":
        return f"**Table {table.number}:** {table.caption}"
    return f": Table {table.number}: {table.caption}"


def _reference_for(table: Table, output_format: str) -> str:
    """The phrase a `tableref` marker expands to in `output_format`.

    The LaTeX-bound form is wrapped in pandoc's raw-attribute span rather
    than written bare, because of the tie: a bare `Table~\\ref{...}` in
    Markdown reaches the LaTeX writer as
    `Table\\textasciitilde{}\\ref{...}` -- pandoc's Markdown reader owns
    `~` (its subscript syntax) and escapes it, so the reference sets with
    a literal tilde in the middle. Measured on this pipeline's own render,
    not on pandoc in the abstract. The `\\label` beside it needs no such
    wrapper, and does survive bare.
    """
    if output_format in _LATEX_BOUND:
        return f"`Table~\\ref{{tab:{table.id}}}`{{=latex}}"
    return f"Table {table.number}"


def substitute(text: str, output_format: str) -> str:
    """`text` with every caption numbered and every reference resolved.

    A reference naming a table that does not exist is left exactly as it
    was: substituting nothing for it would delete a noun phrase from the
    middle of a sentence, leaving prose that reads as though a word were
    missing. `warnings` reports it instead.

    Captions are numbered by **position**, not by id, so a draft that
    reuses an id still numbers both of its captions correctly -- `sub`
    visits matches in document order, which is the order `tables` counts
    in. A *reference* to a reused id cannot be resolved that way and
    takes the last table claiming it; that ambiguity is inherent, and
    `warnings` is what reports the collision behind it.
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

    Lines a caller prints, like `_figure_warnings` -- none of these stops
    a render. A table that renders without a number is a defect a reader
    sees; a render that refuses because of one is a defect the whole
    document pays for.
    """
    ids = [table.id for table in tables(text)]
    # Both patterns end at the end of the same marker line, so the end
    # offset is what tells a marker that has a caption above it from one
    # that does not -- rather than the id, which would miss a second,
    # uncaptioned marker reusing an id that is captioned elsewhere.
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
