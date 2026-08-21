#!/usr/bin/env python3
"""Populate a `groups` field in a plain Zotero BibTeX export, from
collection membership read out of `zotero.sqlite`.

    !!  WARNING: THIS SCRIPT VIOLATES THE SPIRIT OF THIS PROJECT.  !!

It reads Zotero's **internal SQLite database** directly. Nothing else in
this repository does that, and nothing else should. Two rules bend for
it: `chitragupta/bib_reader.py` is meant to be the only reader of bibliographic
data, and it reads an *export* rather than application internals; and the
pipeline's inputs are meant to be auditable by the person who produced
them, which a multi-megabyte application database is not. The tables this
queries carry no compatibility promise, so a Zotero release may
restructure them and leave this script **wrong rather than broken**.

**The sanctioned way to get this field is Better BibTeX** -- see
docs/ZOTERO.md. Use this only when that is impossible, and treat the
output as provisional. docs/EXPORT-ZOTERO-GROUPS.md carries the full
argument, the matching rules and the fragility list; this docstring
deliberately does not restate them.

It is careful about the two things that could do damage: the database is
opened **read-only**, so it is safe to run while Zotero has the library
open, and the input `.bib` is never modified -- output goes to a separate
file differing from the input only by inserted `groups` lines.

Usage:
    python3 scripts/populate_bib_groups.py <zotero.sqlite> <in.bib> <out.bib>
"""

import re
import sqlite3
import sys
from collections import defaultdict, namedtuple

import bibtexparser
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode

# The field Better BibTeX writes and chitragupta/bib_collections.py parses. Named
# rather than inlined because it appears in the "don't clobber" check and
# in the text this script emits, and those two must not drift apart.
GROUPS_FIELD = "groups"

# A DOI shaped like 10.NNNN/suffix, stopping at whitespace or punctuation
# that cannot appear in a DOI. This stays a regular expression where the
# rest of the parsing does not, because it is the one genuine regex
# problem here: pulling a DOI out of free-form prose in `extra`, which no
# BibTeX parser can help with.
DOI_RE = re.compile(r'10\.\d{4,9}/[^\s,;\'"<>]+')

# Trailing characters a DOI collects when it was scraped from a sentence.
_DOI_TRAILING = ').,]>'

Indexes = namedtuple("Indexes", "doi url title collections")


def open_library(sqlite_path):
    """The Zotero database, read-only.

    `mode=ro` is load-bearing, not a precaution: it is what makes this
    safe to run against a live library while Zotero is open, which is the
    promise docs/EXPORT-ZOTERO-GROUPS.md makes. A writable handle would
    put someone's entire reference library at the mercy of a bug here.
    """
    return sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)


def strip_doi(value: str) -> str:
    """A DOI reduced to the form both sides are compared in."""
    return value.strip().rstrip(_DOI_TRAILING).lower()


def normalise_title(value: str) -> str:
    """A title reduced to the form both sides are compared in.

    Applied to Zotero's plain-Unicode titles and to bib titles alike. By
    the time a bib title arrives here bibtexparser has already decoded the
    LaTeX and dropped brace protection, so this only has to handle what
    remains: any braces that survived, whitespace, and case.
    """
    return re.sub(r'\s+', ' ', value.replace('{', '').replace('}', '')).strip().lower()


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
    # convert_to_unicode is what performs that decoding. It is safe here
    # precisely because this parse is never written back out: the output
    # file is spliced from the original text, so no decoded value can
    # leak into it.
    parser = BibTexParser(common_strings=True)
    parser.customization = convert_to_unicode
    database = bibtexparser.loads(text, parser)
    return {entry["ID"]: entry for entry in database.entries}


def _matching_brace(text: str, open_pos: int) -> int:
    """The index of the `}` closing the `{` at `open_pos`."""
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced braces in the bib file")


def scan_entries(text: str) -> list:
    """`(citekey, close_position)` per `@type{key, ...}` block, in file order."""
    # The parser above cannot supply this: it returns values, not
    # offsets, and the offsets are what let the output be a splice of the
    # input rather than a re-serialisation. This deliberately interprets
    # nothing inside the entry -- it finds one delimiter.
    #
    # An unbalanced entry raises rather than returning what it managed to
    # find. Silently truncating a bibliography is the one failure mode
    # this script must not have.
    found = []
    for match in re.finditer(r'@(\w+)\s*\{', text):
        open_pos = match.end() - 1
        close_pos = _matching_brace(text, open_pos)
        header = text[match.end():close_pos]
        found.append((header.split(',', 1)[0].strip(), close_pos))
    return found


def _index_field(cur, field_name: str, transform) -> dict:
    """`transform(value) -> set(itemID)` over one named Zotero field.

    `fieldsCombined` rather than `fields` because it also covers fields
    belonging to item types that Zotero has since retired, which older
    entries in a long-lived library still use.
    """
    index = defaultdict(set)
    cur.execute("""
        select d.itemID, v.value
        from itemData d
        join fieldsCombined f on d.fieldID = f.fieldID
        join itemDataValues v on d.valueID = v.valueID
        where f.fieldName = ?
    """, (field_name,))
    for item_id, value in cur.fetchall():
        index[transform(value)].add(item_id)
    return index


def _index_dois(cur) -> dict:
    """Every DOI-shaped substring in *any* field value.

    Scanning all fields rather than the DOI field is what finds the DOIs
    buried in `extra`; see the module docstring.
    """
    index = defaultdict(set)
    cur.execute("""
        select d.itemID, v.value
        from itemData d join itemDataValues v on d.valueID = v.valueID
    """)
    for item_id, value in cur.fetchall():
        # itemDataValues.value is untyped in Zotero's schema, so a year
        # arrives as an int and the regex cannot run on it.
        if isinstance(value, str):
            for found in DOI_RE.findall(value):
                index[strip_doi(found)].add(item_id)
    return index


def _index_collections(cur) -> dict:
    """itemID -> the collection names it is *directly* filed under."""
    # The leaf name only, with no parent path, because that is what
    # Better BibTeX writes and this script exists to imitate it. Zotero
    # does nest collections and this database records the parent, so a
    # full `Parent > Child` path could be produced here -- but it would
    # disagree with the field's other producer and make the two exports
    # incomparable.
    index = defaultdict(set)
    cur.execute("""
        select ci.itemID, c.collectionName
        from collectionItems ci
        join collections c on ci.collectionID = c.collectionID
    """)
    for item_id, name in cur.fetchall():
        index[item_id].add(name)
    return index


def build_indexes(con) -> Indexes:
    """The four lookups every entry is matched against."""
    cur = con.cursor()
    return Indexes(
        doi=_index_dois(cur),
        url=_index_field(cur, 'url', lambda value: value.strip()),
        title=_index_field(cur, 'title', normalise_title),
        collections=_index_collections(cur),
    )


def match_item_ids(fields: dict, indexes: Indexes):
    """`(item_ids, method)` for one entry, or `(None, None)`.

    Ordered strongest identifier first. A DOI names a work; a URL names a
    copy of one; a title merely describes one, and two different works can
    share a title -- so title is a last resort, not a peer.
    """
    for name, index, normalise in (
        ('doi', indexes.doi, strip_doi),
        ('url', indexes.url, str.strip),
        ('title', indexes.title, normalise_title),
    ):
        value = fields.get(name)
        if value:
            hit = index.get(normalise(value))
            if hit:
                return hit, name
    return None, None


def escape_group_name(name: str) -> str:
    """One collection name, safe to join with commas.

    Better BibTeX joins names with a bare comma inside one `{...}` and
    escapes nothing, so the comma is the field's only separator. Replacing
    it keeps a name that contains one from being read back as two groups.
    Zotero's UI does not allow a comma in a collection name, which makes
    this a defensive fallback rather than a live case.
    """
    return name.replace(',', ';')


def _groups_for(fields: dict, indexes: Indexes, stats: dict) -> tuple:
    """The collection names one entry should be labelled with, and why.

    Returns `()` for every outcome that writes nothing, having recorded
    which outcome it was -- the three no-op cases mean different things
    (no such item, item filed nowhere) and the summary keeps them apart.
    """
    item_ids, method = match_item_ids(fields, indexes)
    if not item_ids:
        stats['unmatched'] += 1
        return ()
    groups = set()
    for item_id in item_ids:
        groups |= indexes.collections.get(item_id, set())
    if not groups:
        stats[f'matched_no_collection_via_{method}'] += 1
        return ()
    stats[f'matched_via_{method}'] += 1
    if len(item_ids) > 1:
        stats['matched_multiple_items'] += 1
    return tuple(sorted(groups))


def populate(text: str, indexes: Indexes):
    """`(output_text, stats)` -- the input with `groups` lines spliced in.

    Driven by the positional scan rather than by the parsed entries, so
    that anything the parser does not return as an entry (a `@comment`
    block, say) is stepped over without shifting the offsets of everything
    after it.
    """
    fields_by_key = read_fields(text)
    scanned = scan_entries(text)
    stats = defaultdict(int)
    # The total is the scan's count, not the parser's, so it agrees with
    # the number of `@` blocks in the file. The two differ -- 644 against
    # 642 on this repository's library -- and counting the parser's would
    # make that difference invisible, which is what `no_fields` prevents.
    stats['entries_total'] = len(scanned)
    pieces, cursor = [], 0
    for key, close_pos in scanned:
        fields = fields_by_key.get(key)
        if fields is None:
            # A block the parser did not return. Overwhelmingly this is
            # Zotero's contentless `@misc{key,\n}` stub for an attachment
            # with no metadata, which bibtexparser is right to drop --
            # #235 documents the same two blocks
            # in this library. A `@comment`/`@string` block lands here
            # too, being no entry at all.
            #
            # Named for what it is rather than for a failure: calling
            # these "dropped" or "unparsed" would report a problem on a
            # healthy library, which is the crying-wolf failure 4.2 is
            # about. They are still counted, so the buckets sum to the
            # total rather than leaving two blocks unaccounted for.
            stats['no_fields'] += 1
            continue
        if fields.get(GROUPS_FIELD):
            # Don't clobber a field that is already there: re-running this
            # on its own output must be a no-op, not a duplication.
            stats['already_had_groups'] += 1
            continue
        groups = _groups_for(fields, indexes, stats)
        if not groups:
            continue
        names = ','.join(escape_group_name(name) for name in groups)
        pieces.append(text[cursor:close_pos])
        pieces.append(f"\t{GROUPS_FIELD} = {{{names}}},\n")
        cursor = close_pos
    pieces.append(text[cursor:])
    return ''.join(pieces), stats


def format_stats(stats: dict) -> list:
    """The run summary, as printable lines.

    Only `matched_via_*` counts toward the total written: the similarly
    named `matched_no_collection_via_*` found an item but had nothing to
    write, so a prefix test on `matched` would overstate the result.
    """
    total = stats['entries_total']
    lines = [f"entries total:            {total}"]
    buckets = {key: value for key, value in stats.items() if key != 'entries_total'}
    lines += [f"{key:28s} {buckets[key]}" for key in sorted(buckets)]
    added = sum(value for key, value in buckets.items() if key.startswith('matched_via_'))
    lines.append(f"groups field added to:    {added} / {total} entries")
    return lines


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 3:
        print("usage: populate_bib_groups.py <zotero.sqlite> <in.bib> <out.bib>",
              file=sys.stderr)
        return 2

    sqlite_path, in_path, out_path = argv
    con = open_library(sqlite_path)
    try:
        indexes = build_indexes(con)
    finally:
        con.close()

    with open(in_path, encoding='utf-8') as handle:
        text = handle.read()
    out_text, stats = populate(text, indexes)
    with open(out_path, 'w', encoding='utf-8') as handle:
        handle.write(out_text)

    print('\n'.join(format_stats(stats)))
    print(f"wrote {out_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
