# 📚 Populating `groups` in a plugin-free Zotero BibTeX export

Status: **how-to.** Written 2026-08-17.

**Written for** someone who wants Zotero collection labels in the ledger
but cannot get [Better BibTeX](https://retorque.re/zotero-better-bibtex/)
to produce them. **Assumed:** a Zotero library and a BibTeX export of it.
**Not covered here:** the supported way to get this field, which is
[ZOTERO.md](ZOTERO.md#-keeping-your-collections-optional), and what the
pipeline does with collections once it has them, which is
[CLI.md](CLI.md).

## ⚠ Read this before using it

> **⚠️ WARNING — this script and this document violate the spirit of this
> project.**
>
> `scripts/populate_bib_groups.py` reads Zotero's **internal SQLite
> database** directly. Nothing else in this repository does that, and
> nothing else should. It is documented here because it exists and
> undocumented tools are worse, not because it is recommended.

Two of this project's rules bend for it:

- **`chitragupta/bib_reader.py` is the only sanctioned reader of bibliographic
  data** (`DEVELOPER-AGENTS.md`'s module boundaries). It reads an
  *export* -- a file the user deliberately
  produced and can inspect. This script reaches behind the export into
  `itemData`, `itemDataValues`, `fieldsCombined`, `collectionItems` and
  `collections`: Zotero application internals with no compatibility
  promise. A Zotero release may restructure any of them without notice,
  and this script would then be **wrong rather than broken** -- the
  dangerous direction, because wrong output looks like output.
- **The pipeline's inputs are meant to be auditable by their owner.** A
  `.bib` file can be read and diffed by the person who exported it; a
  multi-megabyte application database cannot. Deriving
  citation-adjacent metadata from something the user cannot check is
  exactly the opacity this project exists to argue against
  ([SOUL.md](../SOUL.md)).

It does not touch citekeys, which is the one line that cannot be crossed
at all -- it only ever *adds* a `groups` field to an entry that already
exists.

**Use [Better BibTeX](ZOTERO.md#-keeping-your-collections-optional)
instead** wherever you can. Reach for this only when Better BibTeX cannot
be installed or is misbehaving, and treat the result as provisional.

## 💡 Background

Zotero's built-in BibTeX export does not write a `groups` field -- that is
a Better BibTeX extension, which writes JabRef's `groups` field when
*Export -> Fields -> Export JabRef-specific fields* is on. Better BibTeX
turned out to be flaky for this library, so this script fills the same
field by reading collection membership out of `zotero.sqlite`.

`groups` here means "which Zotero collection(s) is this reference filed
under", and it is what `chitragupta/bib_collections.py` parses after a sync. The
script writes the **leaf collection name only**,
comma-separated when an item is filed under several -- deliberately
matching what Better BibTeX emits, so the two producers of this field
stay comparable. Zotero does nest collections and the database does record
the parent, so a full `Parent > Child` path could be produced here; it is
not, because it would disagree with the field's other producer.

## ⌨ Usage

```sh
python3 scripts/populate_bib_groups.py <path-to-zotero.sqlite> <input.bib> <output.bib>
```

Example, as run for this repository:

```sh
python3 scripts/populate_bib_groups.py papers/zotero.sqlite \
  papers/bibliography.bib papers/bibliography-groups.bib
```

- `zotero.sqlite` -- Zotero's local database. The script opens it with
  `mode=ro`, so it is safe to run while Zotero itself is open.
- `input.bib` -- a BibTeX file exported from Zotero's built-in "BibTeX"
  translator (File -> Export Library / Collection).
- `output.bib` -- written fresh; **the input is never modified.**

The output differs from the input only by inserted `groups` lines. That is
a deliberate design property, not an accident: the file is produced by
splicing text into the original rather than by re-serialising a parsed
model, so `diff input output` shows exactly what the script decided and
nothing else. It needs `bibtexparser`, the same dependency
`chitragupta/bib_reader.py` uses.

Re-running is safe: an entry that already has a `groups` field is left
untouched, so a second pass over the same output adds nothing.

## 🔎 How matching works

Bib entries carry no Zotero item ID, so each entry is matched back to a
row in `zotero.sqlite` using, in order, first hit wins:

1. **DOI** -- scanned out of *any* field value on the Zotero item, not
   just the dedicated `DOI` field, because some item types (older
   `conferencePaper` records) store `DOI: 10.xxx/yyy` inside `extra`
   instead.
2. **URL** -- exact match against the item's `url` field.
3. **Title** -- exact match after normalisation.

The order is strongest identifier first: a DOI names a work, a URL names a
copy of one, and a title merely describes one.

Reading the `.bib` file is delegated to `bibtexparser` rather than done
with regular expressions, for the reason `chitragupta/bib_reader.py` gives: nested
braces, multi-line values and LaTeX escapes make a hand-rolled BibTeX
parser a worse bet than a maintained one. Titles therefore arrive already
decoded, so `Caf\'{e}` compares equal to the `Café` Zotero stores, and
`{OMG}` to `OMG`.

Once an item is found, its collections come from a straight join:
`collectionItems` -> `collections`, taking `collectionName`.

## 🚫 Fragility / known limitations

- **Duplicate library items.** This Zotero library has items added more
  than once (identical DOI/title, different `dateAdded`), each possibly
  filed into a different collection. If a match key hits several items,
  their collections are **unioned** onto the one bib entry -- 241 of 644
  entries in the last run. Usually what you want, but it means an entry
  can list a collection only one of its duplicate records was filed
  under: over-inclusive rather than wrong.
- **Title matching is the weakest link** (43 of 644 in the last run). It
  is an exact normalised-string match, so a retitled or typo'd duplicate
  will not match, and two different works sharing a title would collide.
- **Items filed in no collection** correctly get no `groups` field -- not
  a bug, just nothing to report (5 of 644).
- **Blocks carrying no fields** are counted as `no_fields` and left alone
  (2 of 644). These are Zotero's contentless `@misc{key,}` stubs for an
  attachment with no metadata, which `bibtexparser` is right to drop --
  #235 documents the same two
  blocks in this library. The bucket is named for what they are rather
  than for a failure, because reporting them as "dropped" on a healthy
  library is exactly the crying-wolf problem 4.2 is about. They are
  still counted, so the buckets sum to the total.
- **A collection name containing a literal comma** would corrupt the
  `{a,b}` list; the script substitutes `;` inside an individual name
  before joining. Untested against real data, because Zotero's UI does not
  allow a comma in a collection name.
- **The inserted line is tab-indented**, matching Zotero's translator. The
  parser reads any layout, but a file indented differently gains one line
  that does not match its neighbours.

## 📊 Last run stats (this repository)

```text
entries total:            644
matched_multiple_items       241
matched_no_collection_via_doi 1
matched_no_collection_via_url 4
matched_via_doi              403
matched_via_title            43
matched_via_url              191
no_fields                    2
groups field added to:    637 / 644 entries
```

Every block lands in exactly one bucket, so those sum to 644:
`403 + 191 + 43` written, `1 + 4` matched but filed nowhere, `2`
carrying no fields. `matched_multiple_items` is a note on the 637, not a
bucket of its own.
