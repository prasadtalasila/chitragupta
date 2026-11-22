# Collection scoping: draft from the shelf, not the library

Read this when `python -m chitragupta.corpus ledger --collections`
reports at least one collection. Paths here are from the project root.

A reference-manager library usually spans several topics, and its owner
has already sorted it -- "these are the modelling papers". chitragupta-importer
writes that sorting into the bib, `sync` carries it into the ledger, and
`search()` can honour it.

Use it. BM25 over a whole library and BM25 over one shelf do not return
the same papers, and the shelf is **not** a subset of the library's
ranking: measured over a 642-item corpus, a 19-item shelf surfaced ten
papers the whole-corpus search never returned at all, because a small
pool promotes what a large pool's competition buries
(`bench/RESULTS.md`, 2026-08-19).

`ledger --collections` prints one row per collection: its **slug path**
(`digital-twin.dt-platforms`), its **display path** (`Digital Twin / DT
Platforms`) and how many papers it holds.

**Offer the choice once, before any retrieval.** Match the user's words
against the display paths, show the likely rows, ask which one this draft
belongs to, and accept "none, search everything" as an answer. Record the
**slug path** in `scope.md`'s header, beside `language:`, with the display
path as a note for people:

```text
- collection: digital-twin.dt-platforms   # Digital Twin / DT Platforms
- collection: (whole corpus)      # user declined, or the library has none
```

The slug is what you pass. It survives the collection being renamed in
the reference manager; the display path does not.

**Then pass the slug on every retrieval call in the run:**

```bash
python -m chitragupta.draft retrieve search "<query>" --k 15 \
    --collection "<the recorded slug path>" --log <draft>
```

If `--collection` exits 2, the value names no collection, or names
several (two siblings can share a display path). Show the user the
command's message and the `ledger --collections` rows, and ask. Never
retry with a guessed slug.

Three rules, none of them negotiable:

- **Every call, or none.** One unflagged call silently widens the scope
  for that search: `retrieval.md`'s `collection` column will show
  it read as corpus-wide after the fact, but by then the run has already
  read outside the shelf -- the discipline has to hold while the run is
  happening, not just be checkable afterwards.
- **`retrieve evidence` takes no `--collection`.** The flag is on
  `search` only, and rightly: `evidence` zooms into one citekey you have
  already chosen, so there is nothing left for a collection to filter.
  Use it as normal.
- **Degrade silently.** Only a bib written by chitragupta-importer
  carries collections (`docs/ZOTERO.md`). If `ledger --collections`
  reports none, say nothing, ask nothing, record
  `- collection: (whole corpus)`, and behave exactly as this skill did
  before this section existed.

Scoping is a **narrowing**, and a narrowing cannot surface a paper the
shelf does not hold. If retrieval inside the shelf comes back thin for a
sub-theme, say so -- in the draft and in `rejected.md` -- rather than
quietly widening mid-run. The step that sent you here names the skill
that may widen.
