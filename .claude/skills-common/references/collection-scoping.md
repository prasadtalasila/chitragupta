# Collection scoping: draft from the shelf, not the library

Read this when `python -m chitragupta.corpus ledger --collections`
reports at least one collection. Paths here are from the project root.

A Zotero library usually spans several topics, and its owner has already
sorted it -- "these are the modelling papers". `chitragupta/bib_collections.py`
carries that judgement into the ledger and `search()` can honour it.

Use it. BM25 over a whole library and BM25 over one shelf do not return
the same papers, and the shelf is **not** a subset of the library's
ranking: measured over a 642-item corpus, a 19-item shelf surfaced ten
papers the whole-corpus search never returned at all, because a small
pool promotes what a large pool's competition buries
(`bench/RESULTS.md`, 2026-08-19).

**Offer the choice once, before any retrieval.** Show what
`ledger --collections` listed, ask which one this draft belongs to, and
accept "none, search everything" as an answer. Record the result in
`scope.md`'s header, beside `language:`:

```text
- collection: Digital twins > Modelling
- collection: (whole corpus)      # user declined, or the library has none
```

**Then pass it on every retrieval call in the run:**

```bash
python -m chitragupta.draft retrieve search "<query>" --k 15 \
    --collection "<the recorded name>" --log <draft>
```

Three rules, none of them negotiable:

- **Every call, or none.** One unflagged call silently widens the scope
  for that search: `retrieval.md`'s `collection` column (#254) will show
  it read as corpus-wide after the fact, but by then the run has already
  read outside the shelf -- the discipline has to hold while the run is
  happening, not just be checkable afterwards.
- **`retrieve evidence` takes no `--collection`.** The flag is on
  `search` only, and rightly: `evidence` zooms into one citekey you have
  already chosen, so there is nothing left for a collection to filter.
  Use it as normal.
- **Degrade silently.** Most exports carry no collections at all --
  plain Zotero's BibTeX exporter drops them, and only Better BibTeX's
  JabRef-fields option keeps them (`docs/ZOTERO.md`). If
  `ledger --collections` reports none, say nothing, ask nothing, record
  `- collection: (whole corpus)`, and behave exactly as this skill did
  before this section existed.

Scoping is a **narrowing**, and a narrowing cannot surface a paper the
shelf does not hold. If retrieval inside the shelf comes back thin for a
sub-theme, say so -- in the draft and in `rejected.md` -- rather than
quietly widening mid-run. The step that sent you here names the skill
that may widen.
