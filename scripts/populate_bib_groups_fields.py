"""Reading a plain Zotero BibTeX export for `scripts/populate_bib_groups.py`:
every entry's fields, keyed by citekey, as the values that script matches
on.

A sibling of that script rather than part of it only because moving to
bibtexparser 2 took the script past `docs/CODE-STANDARDS.md`'s 250-line
module limit; it has no other caller. `tests/test_populate_bib_groups.py`
reaches it through the script's `read_fields`.
"""

import bibtexparser
from bibtexparser.middlewares import LatexDecodingMiddleware, RemoveEnclosingMiddleware
from bibtexparser.model import DuplicateBlockKeyBlock, DuplicateFieldKeyBlock, Entry, Field


def read_fields(text: str) -> dict:
    """Every entry's fields, keyed by citekey."""
    # Parsing is delegated to bibtexparser -- the same library
    # chitragupta/bib_reader.py uses, and for the same reason it gives there:
    # nested braces, multi-line values and LaTeX escapes make a
    # hand-rolled BibTeX parser a worse bet than a maintained one. An
    # earlier version of this script hand-rolled it with regular
    # expressions and got accents wrong, decoding `Caf\'{e}` to `Cafe`,
    # which then failed to match the `Café` Zotero stores.
    #
    # Only the title is decoded, by bibtexparser 2's own decoder
    # (pylatexenc): this script runs from `scripts/` with no `chitragupta`
    # on its path, so chitragupta/bib_latex.py's copy of 1.x's decoder is
    # out of reach, and for a title match pylatexenc is if anything closer
    # to the text Zotero stores (`--` as an en dash, ``Q'' as curly
    # quotes). A DOI or URL is matched as written: pylatexenc reads `%` as
    # a comment and `&` as a column separator, and on this repository's
    # exports the raw values equal 1.x's decoded ones in every entry. All
    # of it is safe precisely because this parse is never written back
    # out: the output file is spliced from the original text.
    #
    # A block bibtexparser 2 refused only for a duplicate -- a repeated
    # field, or a repeated citekey -- is recovered, delimiters removed by
    # hand since 2.x runs no middleware on a refused block; 1.x returned
    # both kinds, the first of two same-named fields winning and the later
    # of two same-keyed entries. An entry with no fields is left out, as
    # 1.x left it out: Zotero's contentless `@misc{key,\n}` stub belongs in
    # populate_bib_groups.py's `no_fields` bucket, not among the entries to
    # match.
    library = bibtexparser.parse_string(text)
    unenclose, decode = RemoveEnclosingMiddleware(), LatexDecodingMiddleware()
    fields_by_key = {}
    for block in library.blocks:
        if isinstance(block, (DuplicateBlockKeyBlock, DuplicateFieldKeyBlock)):
            block = unenclose.transform_block(block.ignore_error_block, library)
        if not isinstance(block, Entry) or not block.fields:
            continue
        fields = dict(reversed([(field.key.lower(), field.value) for field in block.fields]))
        if "title" in fields:
            title = Entry("misc", "title", [Field("title", fields["title"])])
            fields["title"] = decode.transform_block(title, library)["title"]
        fields_by_key[block.key] = fields
    return fields_by_key
