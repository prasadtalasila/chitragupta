"""bibtexparser 2's splitter, read into the entry dicts bibtexparser 1.x
returned.

`bib_reader` and everything downstream of it -- the ledger's stored
fields, the reference renderers, `bib_integrity`'s counts -- were built
against 1.x's entries: one dict per entry, lowercase field names,
`ENTRYTYPE` and `ID`, values with their delimiters gone and LaTeX
decoded. The move to 2.x keeps that shape and those values exactly,
checked against 1.4.4's own output on 2,365 references from three
real reference-manager exports. So 2.x is used for what it does well --
splitting a file into blocks, including the ones it cannot parse -- and
every rule 1.x applied after that is restated here, each with the
input that showed it:

- Tabs are expanded to 8-column stops across the whole file first
  (pyparsing, under 1.x, did this before parsing anything).
- A value is its `#`-joined parts, each a `{braced}` or `"quoted"`
  string with the delimiters gone, a number, or a `@string` macro.
  The twelve month macros are predefined (1.x's `common_strings`) and
  a file's own `@string` overrides one. An undefined macro is kept as
  written: 1.x raised on it and ended the whole read, which is the one
  place this does not copy 1.x.
- Inside a string, one trailing newline is dropped and the whitespace after
  every other newline (non-breaking spaces included) is removed.
- Field names and the entry type are lowercased; the first of two
  same-named fields wins; the fields come out in reverse file order,
  then `ENTRYTYPE`, `ID`, and `file` last.
- An entry of a type outside `STANDARD_TYPES`, or with no fields at all,
  is skipped (issue 888 and `bib_integrity.block_has_fields`).
- Two entries under one citekey both come back, so
  `bib_integrity.duplicated_citekeys` can refuse both.
- Every value but `file` is LaTeX-decoded by `bib_latex`, the citekey
  included; `file` is decoded only where it is LaTeX (#964).
"""

import logging
import re
from dataclasses import dataclass

from bibtexparser.model import (
    Block,
    DuplicateBlockKeyBlock,
    DuplicateFieldKeyBlock,
    Entry,
    String,
)
from bibtexparser.splitter import Splitter

from chitragupta import bib_latex

logger = logging.getLogger(__name__)

# bibtexparser 1.x's `bibdatabase.STANDARD_TYPES`, which 2.x dropped.
STANDARD_TYPES = frozenset(
    {
        "article",
        "book",
        "booklet",
        "conference",
        "inbook",
        "incollection",
        "inproceedings",
        "manual",
        "mastersthesis",
        "misc",
        "phdthesis",
        "proceedings",
        "techreport",
        "unpublished",
    }
)

# bibtexparser 1.x's `COMMON_STRINGS`, which `common_strings=True` loaded.
MONTHS = {
    "jan": "January",
    "feb": "February",
    "mar": "March",
    "apr": "April",
    "may": "May",
    "jun": "June",
    "jul": "July",
    "aug": "August",
    "sep": "September",
    "oct": "October",
    "nov": "November",
    "dec": "December",
}

_SPACES_AFTER_NEWLINE = re.compile(r"\n[^\S\n]+")

_BLOCK_START = re.compile(r"^[ \t]*@\w+\s*[{(]", re.MULTILINE)
_LINE_START_AT = re.compile(r"^[ \t]*@", re.MULTILINE)
_BACKSLASH_BEFORE_BRACE = re.compile(r"\\(?=[{}])")


@dataclass(frozen=True)
class _Masks:
    """Two private-use code points the file does not hold, standing in
    while 2.x splits it -- see `_masked`."""

    at: str
    backslash: str


def parse_entries(raw_text: str) -> list[dict]:
    """Every entry `raw_text` holds, as bibtexparser 1.x returned it."""
    text = raw_text.expandtabs()
    free = (chr(code) for code in range(0xE000, 0xF900) if chr(code) not in text)
    mask = _Masks(at=next(free), backslash=next(free))
    library = Splitter(_masked(text, mask)).split()
    strings = dict(MONTHS)
    entries = []
    for block in library.blocks:
        block = _recovered(block)
        if isinstance(block, String):
            strings[block.key.lower()] = _value(block.value, strings, mask)
        elif isinstance(block, Entry):
            record = _record(block, strings, mask)
            if record is not None:
                entries.append(record)
    return entries


def _masked(text: str, mask: _Masks) -> str:
    """`text` as 2.x has to see it to split where 1.x did; `_value` swaps
    both masks back.

    Every backslash right before a brace becomes `mask.backslash`.
    BibTeX counts every brace, and so did 1.x, so `\\}` still closes a
    value; 2.x reads it as an escaped brace and does not count it, so a
    value ending in a backslash -- a URL chitragupta-importer wrote raw
    -- never closed, and its entry was dropped.

    And the `@` of every line that begins inside a balanced block becomes
    `mask.at`. 2.x's splitter starts a new block at any line beginning `@word(` or
    `@word{`, even inside a value, and drops the entry it was in; 1.x kept
    it. chitragupta-importer escapes braces but not parentheses, so Zotero
    text quoting a decorator or an annotation at the start of a line
    reaches the bib raw. Only a block whose delimiters balance is masked:
    an unbalanced one is left for 2.x to recover from by its next
    line-start `@`, which is what 1.x did.
    """
    text = _BACKSLASH_BEFORE_BRACE.sub(mask.backslash, text)
    chars, resume = list(text), 0
    for start in _BLOCK_START.finditer(text):
        if start.start() < resume:
            continue
        end = _closing(text, start.end() - 1)
        if end is None:
            continue
        for inner in _LINE_START_AT.finditer(text, start.end(), end):
            chars[inner.end() - 1] = mask.at
        resume = end + 1
    return "".join(chars)


def _closing(text: str, opener: int) -> int | None:
    """Where the block whose `{` or `(` is at `opener` closes, or None
    when its braces never balance."""
    depth = 0
    for index in range(opener + 1, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                return index if text[opener] == "{" else None
            depth -= 1
        elif char == ")" and depth == 0 and text[opener] == "(":
            return index
    return None


def _recovered(block: Block) -> Block:
    """The entry or string inside a block 2.x refused only for a
    duplicate -- a repeated citekey, or a repeated field. 1.x returned
    both, and `bib_integrity` relies on seeing them."""
    if isinstance(block, (DuplicateBlockKeyBlock, DuplicateFieldKeyBlock)):
        return block.ignore_error_block
    return block


def _record(entry: Entry, strings: dict[str, str], mask: _Masks) -> dict | None:
    entry_type = entry.entry_type.lower()
    if entry_type not in STANDARD_TYPES:
        logger.warning("Entry type %s not standard. Not considered.", entry_type)
        return None
    if not entry.fields:
        return None
    first = {}
    for field in entry.fields:
        first.setdefault(field.key.lower(), field.value)
    order = dict.fromkeys(field.key.lower() for field in reversed(entry.fields))
    order.pop("file", None)
    record = {key: _decoded(_value(first[key], strings, mask)) for key in order}
    record["ENTRYTYPE"] = entry_type
    record["ID"] = _decoded(entry.key)
    if "file" in first:
        record["file"] = _decoded_file(_value(first["file"], strings, mask))
    return record


def _decoded_file(file_field: str) -> str:
    """The `file` field is decoded only where it is LaTeX (#964). Zotero
    and Better BibTeX write it raw, escaping only `\\:`, `\\;` and `\\\\`,
    which are `bib_escapes`'s to undo. Mendeley writes it as LaTeX
    (`{\\_}` for an underscore), and decoding is what made those paths
    resolve, so a field holding `{\\` still is."""
    if "{\\" not in file_field:
        return file_field
    return _decoded(file_field)


def _decoded(value: str) -> str:
    """`value` LaTeX-decoded, or as written when 1.x's decoder raises.

    It raises `TypeError` on `\\;`, which its table maps to a
    multi-character string, and that took the whole read with it: first
    from a Zotero `file` field (#964), then from a URL, which
    chitragupta-importer writes raw. 1.x crashed here, so there is no
    output of its to keep; one value as written beats a sync that stops.
    """
    try:
        return bib_latex.latex_to_unicode(value)
    except TypeError:
        return value


def _value(raw: str, strings: dict[str, str], mask: _Masks) -> str:
    """A raw field or `@string` value, its `#`-joined parts resolved and
    whatever `_masked` hid put back."""
    value = "".join(_part(part, strings) for part in _parts(raw))
    return value.replace(mask.backslash, "\\").replace(mask.at, "@")


def _part(part: str, strings: dict[str, str]) -> str:
    if part[:1] in ("{", '"') and len(part) > 1:
        return _cleaned(part[1:-1])
    return strings.get(part.lower(), part)


def _cleaned(text: str) -> str:
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    return _SPACES_AFTER_NEWLINE.sub("\n", text)


def _parts(raw: str) -> list[str]:
    """`raw` split at every `#` outside braces and quotes, each part
    stripped. A quote inside braces does not open a quoted string, and a
    brace inside quotes still nests -- BibTeX's own rules."""
    parts, depth, quoted, start = [], 0, False, 0
    for i, char in enumerate(raw):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == '"' and depth == 0:
            quoted = not quoted
        elif char == "#" and depth == 0 and not quoted:
            parts.append(raw[start:i])
            start = i + 1
    parts.append(raw[start:])
    return [part.strip() for part in parts if part.strip()]
