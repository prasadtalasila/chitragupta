# 📚 Getting your library in from Zotero

Status: **how-to.**

**Written for** anyone getting their own library into this pipeline for
the first time. **Assumed:** nothing. **Not covered here:** what the
pipeline then does with it; [CLI.md](CLI.md) has the commands.

This is the [README](../README.md) Quickstart's first step, in detail,
for [Zotero](https://www.zotero.org/). There are two ways in:

| Route | Collections | Renamed citekeys recognised by | Citekeys |
| --- | --- | --- | --- |
| **[chitragupta-importer](https://github.com/prasadtalasila/chitragupta-importer)** (recommended) | yes, as slug paths | the importer's `cg-renames` block, and a matching PDF | frozen by the importer: a written key never changes |
| A plain Zotero **BibTeX export** | none | a matching PDF only | Zotero's, rebuilt on every export |

Either way the pipeline reads only `papers/bibliography.bib` and the PDFs
it points at. It never reads Zotero, and never learns which route wrote
the file.

## 📥 With chitragupta-importer

The importer reads Zotero's own storage, read-only, and writes the whole
`papers/` directory. Its first run freezes the citekeys an existing
bibliography already uses, so drafts that cite them keep working:

```bash
chitragupta-importer zotero --data-dir ~/Zotero --out papers \
    --bootstrap old.bib --merge-duplicates --dry-run    # check first
chitragupta-importer zotero --data-dir ~/Zotero --out papers \
    --bootstrap old.bib --merge-duplicates              # first run, for real
chitragupta-importer zotero --data-dir ~/Zotero --out papers \
    --merge-duplicates                                  # every later run
chitragupta corpus sync
```

What chitragupta gets from it is the bib file and the PDFs:

```text
papers/
├── bibliography.bib      the tables, then one entry per item that has a PDF
└── files/
    └── <citekey>.pdf     each item's main PDF
```

### 📄 What `bibliography.bib` looks like

A complete example, with three collections nested two deep and two
sibling collections that share the name `Medical`. In the tables,
`<TAB>` stands for **one real tab character**; the importer writes tabs,
and a row separated by spaces is skipped.

```bibtex
@comment{cg-collections v1
digital-twin<TAB>Digital Twin
digital-twin.dt-platforms<TAB>DT Platforms
digital-twin.use-cases<TAB>Use Cases
digital-twin.use-cases.medical<TAB>Medical
digital-twin.use-cases.medical-1<TAB>Medical
}

@comment{cg-renames v1
lehner_pattern_2023-1<TAB>lehner_pattern_2023
}

@incollection{haselbach_dtus_2020,
    title = {Digital Twins in Use},
    booktitle = {Proceedings of the Digital Twin Workshop},
    author = {Haselbach, Peter and Ortiz, Ana},
    year = {2020},
    file = {Full Text PDF:files/haselbach_dtus_2020.pdf:application/pdf},
    cg-collections = {digital-twin.dt-platforms, digital-twin.use-cases.medical},
}

@article{lehner_pattern_2023,
    title = {A Pattern Language for Digital Twins},
    journal = {Software and Systems Modeling},
    author = {Lehner, Daniel},
    year = {2023},
    file = {Full Text PDF:files/lehner_pattern_2023.pdf:application/pdf},
    cg-collections = {digital-twin},
}
```

BibTeX and biber ignore both `@comment` blocks, and JabRef and BibDesk
keep them, so the file stays an ordinary bibliography for every other
tool. The `cg-renames` block is optional. The importer will write it
once
[chitragupta-importer#7](https://github.com/prasadtalasila/chitragupta-importer/issues/7)
lands; chitragupta already reads it.

### 📐 The format, part by part

**`cg-collections` (an entry field).** The slug path of every collection
the item is directly in, separated by commas. Being in `a.b.c` means being
in `a` and `a.b` too, so list only the deepest. A malformed path is
dropped.

**A slug path.** Lower-case segments of `[a-z0-9]`, with single `-`
inside a segment, joined by `.`: `digital-twin.use-cases.medical-1`. The
importer makes each segment from the collection's name (`Industry 5.0`
becomes `industry-5-0`) and freezes it per collection, so renaming a
collection keeps its slug and moving one keeps its segment. Two siblings
with the same name get `medical` and `medical-1`.

**Both tables.** One `@comment{...}` block each:

| Part | Rule |
| --- | --- |
| First line | `cg-collections v1` or `cg-renames v1`: the name in lower case, a space, the version |
| Version | `v1` is the one this release knows. Another version, or none, is still read, but sync prints a `WARNING` and exits **3** |
| Rows | One per line: key `<TAB>` value. Further tab-separated fields are ignored; blank lines are skipped; each field is trimmed |
| Skipped rows | A row with no tab, or a key that is not valid for the table, is skipped, and sync warns once with the count |
| Braces | The block ends at its matching `}`. Write a brace inside a value as `\{` or `\}` |
| Repeats | Two blocks of one name are merged; for a repeated key the first row wins |
| Place | Anywhere in the file; the importer puts them first |

| Table | Key | Value |
| --- | --- | --- |
| `cg-collections` | a slug path | the collection's **own** name (`Medical`), never its path; the display path `Digital Twin / Use Cases / Medical` is rebuilt from the parent rows |
| `cg-renames` | the retired citekey | the citekey that replaced it. Both must work as filenames ([below](#-citekeys-have-to-work-as-filenames)) |

A `cg-renames` row matters only when its old key has left the bib and its
new key is in it; [CLI.md](CLI.md#-when-a-citekey-is-renamed) has what
`sync` then reports and records.

## 📤 With a plain Zotero BibTeX export

Zotero's own exporter still works, with no collections and no
`cg-renames` block (its
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
5. Re-run `chitragupta corpus sync`.

An entry needs nothing specific to chitragupta, only a `file` field whose
path is relative to the bib file. The sample project's first entry:

```bibtex
@article{sample_dt_overview_2024,
  title   = {Digital Twins: Definitions, Distinctions, and a Short Taxonomy},
  author  = {Author, A. and Builder, B.},
  journal = {Synthetic Sample Papers},
  year    = {2024},
  volume  = {1},
  pages   = {1--5},
  file    = {Full Text PDF:files/sample_dt_overview_2024.pdf:application/pdf}
}
```

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
already made (*these are the modelling papers*). With an importer-written
bib, this pipeline can use them to scope a draft's retrieval to that
subset rather than the whole library:

```bash
chitragupta corpus ledger --collections              # every collection
chitragupta corpus ledger --collection digital-twin  # a slug path
chitragupta draft retrieve search "surrogate models" \
    --collection "Digital Twin/Use Cases"            # or a display path
```

`ledger --collections` prints each collection's slug path, display path
and paper count, counting the papers beneath it; a collection the table
names but no paper is in shows `0`:

```text
  digital-twin                      Digital Twin                        2
  digital-twin.dt-platforms         Digital Twin / DT Platforms         1
  digital-twin.use-cases            Digital Twin / Use Cases            1
  digital-twin.use-cases.medical    Digital Twin / Use Cases / Medical  1
  digital-twin.use-cases.medical-1  Digital Twin / Use Cases / Medical  0

  5 collection(s).
```

`--collection` takes either form. A slug path is read only in lower case,
as slugs are written; anything else is compared, whole and ignoring case
and the spacing around `/`, with every display path, so a name holding
`/` still matches. A parent selects everything beneath it. A value that
names no collection, or names two (the two `Medical`s above), **exits 2**
with the choices rather than returning nothing:

```text
'Digital Twin/Use Cases/Medical' names 2 collections; pass one slug path:
  digital-twin.use-cases.medical
  digital-twin.use-cases.medical-1
```

Each genre skill runs `ledger --collections` at scope time. If your
library has none, it says nothing and records `collection: (whole
corpus)`. Otherwise it offers the list once and records the chosen slug
path in the draft's `scope.md`, with the display path as a note:

```text
- collection: digital-twin.dt-platforms   # Digital Twin / DT Platforms
```

It passes that slug on every retrieval call; `draft-reviser` and
`corpus-reviser` read the line back and do not ask again. Decline and
everything searches the whole library.

On a 642-item corpus, scoping to a 19-item shelf raised the share of
surfaced papers that were cited from 0.31 to 0.89, at no index cost. It
did **not** shrink the retrieval payload (a fixed `--k` still returns `k`
results), and the shelf surfaced ten papers the whole-corpus search never
returned, because a small pool promotes what a large pool's competition
buries.

Since 7.0.0 the `groups` field Better BibTeX's *Export JabRef-specific
fields* wrote is no longer read; sync says so once if your bib still has
it, and once if `config.toml` still sets `[bib] collections_field`. A
draft whose `scope.md` recorded a `groups` path (`Digital twins >
Modelling`) is listed by `dossier status` under `unresolved_collections`
until its scope is re-chosen.

## ⬆ Upgrading from 6.x to 7.0.0

7.0.0 changes how collections reach the pipeline, so a 6.x project needs
four things, once:

1. **Re-import with chitragupta-importer**
   ([above](#-with-chitragupta-importer)), then run
   `chitragupta corpus sync`. That sync migrates the ledger to its new
   schema. Until it has run, the read-only commands (`ledger`, `retrieve`)
   refuse: the ledger "predates this version's schema", run sync to
   migrate it.
2. **Remove `[bib] collections_field`** from `config.toml`. It is no
   longer read, and sync says so once while it is there.
3. **Port every draft scoped by a `groups` path** (`- collection: Digital
   twins > Modelling` in its `scope.md`). Its next `--collection` exits 2,
   and `dossier status` lists it under `unresolved_collections`.
   [chitragupta#1252](https://github.com/prasadtalasila/chitragupta/issues/1252)
   has an agent prompt that ports them; draft-reviser does the same for
   one draft when it re-grounds.
4. **Stop using `scripts/populate_bib_groups.py`.** It is gone, with the
   `groups` field it wrote; the importer replaces both.

## 🚪 Where papers come from

A `bibliography.bib`, written by the importer or exported, is the
**only** way to get a paper into this pipeline.
There is no directory you can drop a raw PDF into: the enrichment layer's
corpus is the bibliography, so anything it can retrieve is something a
draft may cite (see
[`chitragupta/enrich/corpus.py`](https://github.com/prasadtalasila/chitragupta/blob/main/chitragupta/enrich/corpus.py)
and AGENTS.md's citekey invariant). A PDF without a `.bib` entry pointing
at it is ignored.

To add papers later, add the entry in Zotero, re-run the importer (or
re-export the same way, with **Export Files** ticked), and re-run `sync`.

To remove a paper, delete the entry in Zotero, re-import or re-export,
and re-run `sync`. By default `sync` only *reports* citekeys that dropped
out of the bib file (`stale   <citekey> (no longer in bibliography.bib)`,
plus one summary note pointing at `--remove-stale`); it deletes their
`content/ledger.sqlite` row only when you re-run with `--remove-stale`.
This is deliberate: a short export is far more often a botched re-export,
or `BIB_FILE` pointing at the wrong path, than an intentional deletion.
A key that left because the paper now has another key is reported as
`renamed to <new key>`; drafts citing it are swapped with
`chitragupta draft dossier apply-renames`
([DRAFT-ITERATION.md](DRAFT-ITERATION.md#-swapping-a-renamed-citekey)).

Before either run acts, it names **what else on disk still references
that citekey** (the overlap index, the topic graph, the chunk vectors),
so you see the residue before you confirm, and points you at
`chitragupta draft dossier status --all` for the drafts and dossiers
that cite it. It repairs nothing: only the ledger row is ever
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

Neither the importer nor Zotero's own key generator produces one, so you
are most likely to hit this with a custom Better BibTeX key pattern. This
project never rewrites a citekey (the bib file is the source of truth),
so the fix is always to rename it in the reference manager and
re-export. Accented characters (`naïve_2024`) are fine.

All paths are set in `config.toml` and overridable per run with an env
var of the same name, e.g. `BIB_FILE=/path/to/other.bib python -m
chitragupta.corpus sync` ([CONFIG.md](CONFIG.md)).
