"""bibtexparser 2's splitter, read into the entry dicts bibtexparser 1.x
returned.

Everything downstream was built on 1.x's entries, so 2.x only splits
blocks and 1.x's rules are restated here, checked against 1.4.4 on 2,365
real references: tabs expanded first; `#`-joined values with month
macros predefined (an undefined macro is kept as written, where 1.x
raised); string whitespace trimmed after newlines; lowercased names,
first duplicate field wins, reverse file order then `ENTRYTYPE`, `ID`,
`file`; nonstandard or fieldless entries skipped (issue 888); duplicate
citekeys both returned for `bib_integrity`; LaTeX decoded except `file`
(#964).
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

    A backslash before a brace is masked: BibTeX and 1.x count `\\}` as
    closing, 2.x does not, and a value ending in a raw-URL backslash never
    closed. A line-start `@` inside a balanced block is masked, since 2.x
    starts a new block there and drops the entry (decorators in Zotero
    text). Unbalanced blocks are left for 2.x to recover from, as 1.x did.
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
    """The `file` field is decoded only where it is LaTeX (#964): Zotero
    writes it raw (`bib_escapes` undoes it), Mendeley as LaTeX (`{\\_}`)."""
    if "{\\" not in file_field:
        return file_field
    return _decoded(file_field)


def _decoded(value: str) -> str:
    """`value` LaTeX-decoded, or as written when 1.x's decoder raises.

    It raises `TypeError` on `\\;` (#964); one value kept as written beats
    a sync that stops.
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
