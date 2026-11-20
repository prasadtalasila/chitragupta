# 📚 Populating `groups` in a plugin-free Zotero BibTeX export

Status: **how-to.**

**Written for** someone who wants Zotero collection labels in the ledger
but cannot get [Better BibTeX](https://retorque.re/zotero-better-bibtex/)
to produce them. **Assumed:** a Zotero library and a BibTeX export of it.
**Not covered here:** the supported way to get this field, which is
[ZOTERO.md](ZOTERO.md#-keeping-your-collections-optional), and what the
pipeline does with collections once it has them, which is
[CLI.md](CLI.md).

## ⚠ Read this before using it

> **⚠️ WARNING: this script and this document violate the spirit of this
> project.**
>
> `scripts/populate_bib_groups.py` reads Zotero's **internal SQLite
> database** directly. Nothing else in this repository does that, and
> nothing else should. It is documented here because it exists and
> undocumented tools are worse; being documented does not make it
> recommended.

Two of this project's rules bend for it:

- **`chitragupta/bib_reader.py` is the only sanctioned reader of
  bibliographic data**, and it reads an *export* the user deliberately
  produced and can inspect. This script reaches into Zotero application
  tables (`itemData`, `collectionItems`, `collections` and others) with
  no compatibility promise. A Zotero release may restructure them and
  leave this script **wrong rather than broken**, which is the dangerous
  direction, because wrong output looks like output.
- **The pipeline's inputs are meant to be auditable by their owner.** A
  `.bib` file can be read and diffed; a multi-megabyte application
  database cannot ([SOUL.md](../SOUL.md)).

It never touches citekeys. It only ever *adds* a `groups` field to an
entry that already exists.

**Use [Better BibTeX](ZOTERO.md#-keeping-your-collections-optional)
instead** wherever you can. Reach for this only when Better BibTeX cannot
be installed or is misbehaving, and treat the result as provisional.

## 💡 Background

Zotero's built-in BibTeX export does not write the `groups` field that
Better BibTeX writes with JabRef-specific fields on. This script fills
the same field from collection membership in `zotero.sqlite`, for
`chitragupta/bib_collections.py` to parse after a sync.

It writes the **leaf collection name only**, comma-separated when an item
is filed under several, deliberately matching what Better BibTeX emits so
the two producers stay comparable. The database records the parent, so a
`Parent > Child` path could be produced; it is not, because it would
disagree with the field's other producer.

## ⌨ Usage

```sh
python3 scripts/populate_bib_groups.py <path-to-zotero.sqlite> <input.bib> <output.bib>
```

- `zotero.sqlite`: Zotero's local database. The script opens it with
  `mode=ro`, so it is safe to run while Zotero itself is open.
- `input.bib`: a BibTeX file exported from Zotero's built-in "BibTeX"
  translator (File -> Export Library / Collection).
- `output.bib`: written fresh; **the input is never modified.**

The output differs from the input only by inserted `groups` lines: the
script splices text into the original instead of re-serialising a parsed
model, so `diff input output` shows exactly what it decided. Re-running
is safe, as an entry that already has a `groups` field is left
untouched.

## 🔎 How matching works

Bib entries carry no Zotero item ID, so each entry is matched back to a
row in `zotero.sqlite` using, in order, first hit wins:

1. **DOI**, scanned out of *any* field value on the Zotero item, because
   some older `conferencePaper` records store `DOI: 10.xxx/yyy` inside
   `extra`.
2. **URL**, an exact match against the item's `url` field.
3. **Title**, an exact match after normalisation.

A DOI names a work, a URL names a copy of one, and a title merely
describes one. The `.bib` file is read with `bibtexparser`, not regular
expressions, so titles arrive already decoded: `Caf\'{e}` compares equal
to the `Café` Zotero stores, and `{OMG}` to `OMG`. An item's collections
come from a join of `collectionItems` and `collections`.

## 🚫 Fragility / known limitations

- **Duplicate library items.** If a match key hits several items (the
  same work added more than once), their collections are **unioned**
  onto the one bib entry: over-inclusive, though not wrong.
- **Title matching is the weakest link.** It is an exact
  normalised-string match, so a retitled or typo'd duplicate will not
  match, and two different works sharing a title would collide.
- **Items filed in no collection** correctly get no `groups` field.
- **Blocks carrying no fields** (Zotero's contentless `@misc{key,}`
  stubs for an attachment with no metadata) are counted as `no_fields`
  and left alone, named for what they are rather than as "dropped", so a
  healthy library raises no false alarm.
- **Asking for a parent collection does not select its
  subcollections.** `chitragupta/bib_collections.py` matches a parent
  against `Parent > Child` paths, but this script writes leaf names only,
  so `--collection "Digital twins"` finds only the papers filed directly
  under `Digital twins`, not those in `Modelling` beneath it. Ask for
  each subcollection by name.
- **A comma inside a collection name** is replaced by `;` before
  joining, so it cannot corrupt the list. Untested against real data,
  because Zotero's UI does not allow one.
- **The inserted line is tab-indented**, matching Zotero's translator.

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

The buckets sum to 644 (`403 + 191 + 43` written, `1 + 4` filed
nowhere, `2` with no fields); `matched_multiple_items` is a note on the
637, not a bucket.
