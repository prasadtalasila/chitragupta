# Exporting your library from Zotero

Status: **how-to.** Written 2026-08-03.

**Written for** anyone getting their own library into this pipeline for
the first time. **Assumed:** nothing. **Not covered here:** what the
pipeline then does with it -- [CLI.md](CLI.md) has the commands.

How to get a `.bib` file and its PDFs into the shape this pipeline
expects. See [../README.md](../README.md) for the Quickstart that
refers here.

Step 1 above, in detail, for [Zotero](https://www.zotero.org/) (see its own
[export documentation](https://www.zotero.org/support/kb/exporting) for the
general feature):

1. Right-click the collection you want (or use **File -> Export Library**
   for everything) -> **Export Collection...** / **Export Library...**.
2. Format: **BibTeX**. Check **Export Files** -- without it you get
   metadata only and `pdf_text.py` will have nothing to extract.
3. Save it as `bibliography` directly inside this repo's `papers/`
   directory. Zotero writes `papers/bibliography.bib` plus a **companion
   folder** (`papers/bibliography/`, `files/<id>/<name>.pdf` inside) for
   every attachment -- the exported `.bib`'s `file` field encodes that
   folder's name as a literal relative path, tied to whatever name you
   gave the export at save time.
4. **Don't rename that companion folder afterward.** `src/bib_reader.py`'s
   `_resolve_pdf_path` resolves each entry's `file` field relative to
   wherever `bibliography.bib` itself lives (`papers/`) -- if you rename
   or move the attachments folder, that relative path breaks silently
   (entries just show up as "without a PDF attachment" after `sync`, not
   as an error).
5. Re-run `python -m src.corpus sync`.

## Keeping your collections (optional)

Zotero organises a library into collections and subcollections, and that
tree is a judgement you have already made -- *these are the modelling
papers*. This pipeline can use it to scope a draft's retrieval to the
subset you curated for it, rather than to the whole library (#195):

```bash
python -m src.corpus ledger --collections               # what exists
python -m src.corpus ledger --collection "Digital twins"
python -m src.draft retrieve search "surrogate models" --collection "Digital twins"
```

The genre skills use this too, and ask about it once. Each of them
offers the list above at scope time, records the answer as a
`collection:` line in the draft's `scope.md`, and passes
`--collection` on every retrieval call for the rest of the run;
`draft-reviser` and `corpus-reviser` then read that line back rather than
asking again. Decline the offer and everything searches the whole
library, exactly as it did before.

It is worth knowing what the narrowing buys and what it costs, because
neither is obvious. Measured over a 642-item corpus (`bench/RESULTS.md`,
2026-08-19): scoping to a 19-item shelf raised the share of surfaced
papers that were actually cited from 0.31 to 0.89, and it cost nothing
in index terms -- the retrieval cache is shared, and scoring is
corpus-wide with only the ranking filtered. It did **not** reduce the
size of the retrieval payload, because a fixed `--k` still returns `k`
results. And a shelf is not a subset of the library's ranking: that same
19-item shelf surfaced ten papers the whole-corpus search never returned,
because a small pool promotes what a large pool's competition buries.

**Zotero's own BibTeX exporter drops collection membership entirely**, so
none of that works on a plain export -- the commands run, and nothing is
in any collection. Keeping it needs
[Better BibTeX](https://retorque.re/zotero-better-bibtex/):

1. Install Better BibTeX and restart Zotero.
2. **Edit -> Settings -> Better BibTeX -> Export -> Fields**, and turn on
   **Export JabRef-specific fields**. That writes JabRef's `groups` field
   into every entry, naming each collection the item belongs to.
3. Export as **Better BibTeX** rather than the built-in BibTeX, with
   **Export Files** checked as in step 2 above.
4. Re-run `python -m src.corpus sync`.

**The stated cost, and why it is probably not a cost for you.** Better
BibTeX warns that this option "will disable caching in exports", and its
[performance notes](https://retorque.re/zotero-better-bibtex/support/performance/)
put the difference at roughly 9 seconds against 3-4 on an 86-item library.
But those same notes say the cache "will not be active" when **Export
Files** is enabled -- and step 2 above requires Export Files, because
without the attachments there is nothing for this pipeline to parse. So an
export done the way this page describes never had the cache to lose.
Turning JabRef fields on costs you nothing further.

Two things follow. If you also keep a *separate* Better BibTeX export for
something else -- a `.bib` for a LaTeX document, an auto-export on a timer
-- that one does lose its cache, since the preference is global rather than
per-export. And if you do not want collections, leave the option off:
nothing else in this pipeline reads the field.

**If Better BibTeX is not an option at all**, there is a discouraged
fallback that reads collection membership out of `zotero.sqlite` directly
-- [EXPORT-ZOTERO-GROUPS.md](EXPORT-ZOTERO-GROUPS.md). It bends two of
this project's rules and says so at length. Prefer the option above.

Two conventions come with `groups`, and both are JabRef's rather than
ours. Several collections are comma-separated, and a subcollection
arrives as its path from the root (`Digital twins > Modelling`). Asking
for a parent selects everything beneath it, so `--collection "Digital
twins"` also returns the modelling papers. Matching ignores case, and it
is per-segment rather than by substring: `Modelling` will not match a
different collection called `Modelling notes`.

If your exporter writes them somewhere else, point `[bib].collections_field`
in `config.toml` at that field instead ([CONFIG.md](CONFIG.md)).

A Zotero export is the **only** way to get a paper into this pipeline.
There is no directory you can drop a raw PDF into to have it indexed:
the enrichment layer's corpus is the bibliography, so anything it can
retrieve is something a draft may cite -- see
[`src/enrich/corpus.py`](https://github.com/prasadtalasila/chitragupta/blob/main/src/enrich/corpus.py)
and AGENTS.md's citekey
invariant. (Earlier versions did have such a directory, `papers/pdfs/`;
it is gone. A PDF there is now ignored.)

To add more papers later: add the entry in Zotero, re-export the same way
(re-check **Export Files** so new attachments are included), then re-run
`python -m src.corpus sync`.

Removing a paper: delete the entry in Zotero, re-export, re-run `sync`.
By default `sync` only *reports* citekeys that dropped out of the bib file
(`stale   <citekey> (no longer in bibliography.bib)`, one line per
citekey, plus a single summary note pointing at `--remove-stale`) -- it
doesn't delete their `content/ledger.sqlite` row until you re-run with
`--remove-stale`. This is deliberate. A bib export that comes back short
a citekey is far more often a botched re-export, or `BIB_FILE` pointing
at the wrong path, than an intentional deletion -- so the default keeps
the ledger untouched until a human confirms.

`--remove-stale` still refuses, raising, if the bib file comes back
completely empty against a non-empty ledger. Same reason: fix the export
or the path rather than deleting everything in one run.

## Citekeys have to work as filenames

A citekey is not only an identifier here -- it is the stem of every file
the pipeline writes for that paper (`content/parsed/<citekey>.txt`, and
the enrichment layer's `content/docling/<citekey>.md`). So a citekey
containing `/` or `\`, one of `: * ? " < > |`, or a name Windows reserves
(`CON`, `NUL`, `COM1`...) is **skipped**, with a warning naming it:

```text
  WARNING skipping citekey 'smith/2024': it contains '/', which cannot
  appear in a filename. ...  Rename it in your reference manager,
  re-export, and re-run sync.
```

Zotero's own key generator won't produce one of those, so you are most
likely to hit this with Better BibTeX and a custom key pattern. This
project never rewrites a citekey -- the bib file is the source of truth --
so the fix is always to rename it in the reference manager and re-export.
Ordinary accented characters (`naïve_2024`) are fine; they are legal in a
filename.

All paths are configurable in `config.toml` (repo root), overridable
per-run with an env var of the same name, e.g. `BIB_FILE=/path/to/other.bib
python -m src.corpus sync`. See [CONFIG.md](CONFIG.md) for the
full settings reference.
