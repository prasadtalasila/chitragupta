# 📚 Exporting your library from Zotero

Status: **how-to.**

**Written for** anyone getting their own library into this pipeline for
the first time. **Assumed:** nothing. **Not covered here:** what the
pipeline then does with it; [CLI.md](CLI.md) has the commands.

This is the [README](../README.md) Quickstart's first step, in detail,
for [Zotero](https://www.zotero.org/) (its own
[export documentation](https://www.zotero.org/support/kb/exporting)
covers the general feature):

1. Right-click the collection you want (or use **File -> Export Library**
   for everything) -> **Export Collection...** / **Export Library...**.
2. Format: **BibTeX**. Check **Export Files**; without it you get
   metadata only and `pdf_text/` will have nothing to extract.
3. Save it as `bibliography` directly inside this repo's `papers/`
   directory. Zotero writes `papers/bibliography.bib` plus a **companion
   folder** (`papers/bibliography/`, `files/<id>/<name>.pdf` inside) for
   every attachment. Each entry's `file` field encodes that folder's name
   as a literal relative path.
4. **Don't rename that companion folder afterward.** `bib_reader`
   resolves each `file` field relative to wherever `bibliography.bib`
   lives (`papers/`). If you rename or move the attachments folder, that
   path breaks silently: after `sync` the entries show up as "without a
   PDF attachment", and no error is raised.
5. Re-run `python -m chitragupta.corpus sync`.

On Windows, Zotero and Better BibTeX escape the drive colon, every
backslash (`C\:\\Users\\...`) and a `;` in a file name (`\;`).
`bib_reader` undoes exactly those escapes, so there is nothing to convert
by hand.

The sample project's
[`bibliography.bib`](examples/sample-project/papers/bibliography.bib) is
a five-entry export of this shape, with its `files/` folder beside it. If
your entries come up "without a PDF attachment", compare against it.

## 🗂 Keeping your collections (optional)

Your Zotero collections and subcollections are a judgement you have
already made (*these are the modelling papers*). This pipeline can use
them to scope a draft's retrieval to that subset rather than the whole
library:

```bash
python -m chitragupta.corpus ledger --collections               # what exists
python -m chitragupta.corpus ledger --collection "Digital twins"
python -m chitragupta.draft retrieve search "surrogate models" --collection "Digital twins"
```

Each genre skill runs `ledger --collections` at scope time. If your
library has none, it says nothing and records `collection: (whole
corpus)`. Otherwise it offers the list once, records the answer as a
`collection:` line in the draft's `scope.md`, and passes `--collection`
on every retrieval call; `draft-reviser` and `corpus-reviser` read that
line back and do not ask again. Decline and everything searches the
whole library.

On a 642-item corpus, scoping to a 19-item shelf raised the share of
surfaced papers that were cited from 0.31 to 0.89, at no index cost. It
did **not** shrink the retrieval payload (a fixed `--k` still returns `k`
results), and the shelf surfaced ten papers the whole-corpus search never
returned, because a small pool promotes what a large pool's competition
buries.

**Zotero's own BibTeX exporter drops collection membership entirely**, so
on a plain export the commands run and nothing is in any collection.
Keeping it needs [Better BibTeX](https://retorque.re/zotero-better-bibtex/):

1. Install Better BibTeX and restart Zotero.
2. **Edit -> Settings -> Better BibTeX -> Export -> Fields**, and turn on
   **Export JabRef-specific fields**. That writes JabRef's `groups` field
   into every entry, naming each collection the item belongs to.
3. Export as **Better BibTeX** rather than the built-in BibTeX, with
   **Export Files** checked as in step 2 above.
4. Re-run `python -m chitragupta.corpus sync`.

Better BibTeX warns that this option "will disable caching in exports",
but its
[performance notes](https://retorque.re/zotero-better-bibtex/support/performance/)
say the cache "will not be active" when **Export Files** is enabled
anyway, so an export done this way loses nothing. A *separate* Better
BibTeX export you keep for something else does lose its cache, since the
preference is global. If you do not want collections, leave the option
off: nothing else reads the field.

If Better BibTeX is not an option at all, a discouraged fallback reads
collection membership out of `zotero.sqlite` directly:
[EXPORT-ZOTERO-GROUPS.md](EXPORT-ZOTERO-GROUPS.md). It bends two of this
project's rules. Prefer the option above.

`groups` follows JabRef's conventions. Several collections are
comma-separated, and a subcollection arrives as its path from the root
(`Digital twins > Modelling`). Asking for a parent selects everything
beneath it. Matching ignores case and is per-segment, not by substring:
`Modelling` will not match a collection called `Modelling notes`. If your
exporter writes membership to another field, point
`[bib].collections_field` in `config.toml` at it ([CONFIG.md](CONFIG.md)).

A Zotero export is the **only** way to get a paper into this pipeline.
There is no directory you can drop a raw PDF into: the enrichment layer's
corpus is the bibliography, so anything it can retrieve is something a
draft may cite (see
[`chitragupta/enrich/corpus.py`](https://github.com/prasadtalasila/chitragupta/blob/main/chitragupta/enrich/corpus.py)
and AGENTS.md's citekey invariant). A PDF without a `.bib` entry pointing
at it is ignored.

To add papers later, add the entry in Zotero, re-export the same way
(with **Export Files** ticked), and re-run `sync`.

To remove a paper, delete the entry in Zotero, re-export and re-run
`sync`. By default `sync` only *reports* citekeys that dropped out of the
bib file (`stale   <citekey> (no longer in bibliography.bib)`, plus one
summary note pointing at `--remove-stale`); it deletes their
`content/ledger.sqlite` row only when you re-run with `--remove-stale`.
This is deliberate: a short export is far more often a botched re-export,
or `BIB_FILE` pointing at the wrong path, than an intentional deletion.

Before either run acts, it names **what else on disk still references
that citekey** (the overlap index, the topic graph, any dossier's
`evidence.md`/`sections.md`, the chunk vectors), so you see the residue
before you confirm. It repairs nothing: only the ledger row is ever
removed.
[CLI.md](CLI.md#-what-else-still-references-a-citekey-you-are-about-to-remove)
has the format.

`--remove-stale` still refuses, raising, if the bib file comes back
completely empty against a non-empty ledger. It also deletes nothing when
the read itself came back short: an entry the BibTeX parser dropped
(usually unbalanced braces), or a citekey skipped because it cannot be a
filename (below). The stale list is then printed as a report, the
summary line names what was lost, and the run exits **3**. Fix the entry
named in the `WARNING`, re-export, and re-run.

A non-standard entry type such as `@software` or `@online` is ignored by
design, silently: it is never synced and does not count as dropped. Export
such an item under a standard type (`@misc`, say) if you want it.

## 🏷 Citekeys have to work as filenames

A citekey is also the stem of every file the pipeline writes for that
paper (`content/parsed/<citekey>.txt`, `content/docling/<citekey>.md`).
So a citekey containing `/` or `\`, one of `: * ? " < > |`, or a name
Windows reserves (`CON`, `NUL`, `COM1`...) is **skipped**, with a
warning naming it:

```text
  WARNING skipping citekey 'smith/2024': it contains '/', which cannot
  appear in a filename. ...  Rename it in your reference manager,
  re-export, and re-run sync.
```

Zotero's own key generator won't produce one, so you are most likely to
hit this with a custom Better BibTeX key pattern. This project never
rewrites a citekey (the bib file is the source of truth), so the fix is
always to rename it in the reference manager and re-export. Accented
characters (`naïve_2024`) are fine.

All paths are set in `config.toml` and overridable per run with an env
var of the same name, e.g. `BIB_FILE=/path/to/other.bib python -m
chitragupta.corpus sync` ([CONFIG.md](CONFIG.md)).
