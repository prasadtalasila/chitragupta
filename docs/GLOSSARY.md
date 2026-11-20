# 📖 Glossary: the working vocabulary

Status: **reference.**

**Written for** you, the person writing a draft with this pipeline. Each
entry says what the term means *to you* and names the document that owns
the detail. Terms are grouped by when you first meet them.

## 📚 Your library, inside the pipeline

- **Citekey**: the identifier your reference manager assigns each entry
  (`sample_dt_sync_2023`), cited in a draft as `[@sample_dt_sync_2023]`.
  The one hard rule: a citekey may be used only if it came from your own
  `.bib` export and a real PDF was really parsed ([SOUL.md](../SOUL.md)).
- **Corpus**: the `.bib` export plus the attached PDFs, synced into the
  ledger.
- **Ledger**: the database (`content/ledger.sqlite`) recording each
  entry's citekey, title, whether its PDF parsed, and where the
  extracted text lives. Built by `chitragupta corpus sync`, inspected
  with `chitragupta corpus ledger` ([ZOTERO.md](ZOTERO.md)).
- **Sync**: the deterministic run that reads your `.bib`, updates the
  ledger, and extracts each PDF's text. No AI is involved, so the same
  bibliography always yields the same citekeys.
- **Parse**: turning one PDF into plain text the pipeline can search and
  quote ([PDF-PARSER.md](PDF-PARSER.md) compares the two backends).

## ✍ Writing

- **Genre skill**: one of the six drafting skills (survey, thesis
  chapter, textbook chapter, tutorial, deep research, verbatim digest).
  The other five skills work on their drafts: three revisers, the book
  assembler, and `figure-drawer`. You ask in ordinary words and the
  right one answers ([GENRE.md](GENRE.md)).
- **Draft**: the document being written, under `content/drafts/`.
- **Dossier**: the folder beside a draft holding the judgment that
  produced it: scope, reader, sources kept and turned down, and a
  revision log. It is why a draft can be changed months later without
  re-running anything ([DOSSIER.md](DOSSIER.md),
  [WRITING-PROCESS.md](WRITING-PROCESS.md)).
- **The gate**: `chitragupta draft gate`, which checks that every
  citekey in the draft is in the ledger. It is the only *blocking* check
  in the pipeline; a failure sends the draft back to be rewritten.
- **Render**: turning a finished draft into PDF/LaTeX/Word with its
  bibliography resolved. `chitragupta draft render` runs the gate again
  first.
- **Stamp** (the draft fingerprint): a digest of the draft's text that
  `chitragupta draft dossier stamp` records in `scope.md` once the gate
  passes. `dossier status` compares against it to tell you whether the
  draft changed since ([USER-EDITS.md](USER-EDITS.md)).
- **Evidence sidecar**: a document rendered beside a draft, listing each
  cited source and the spans its dossier marked quotable. Four of the six
  genres produce one
  ([DOSSIER.md](DOSSIER.md#-the-evidence-sidecar-decided-per-genre)).
- **Verbatim digest**: the sixth genre. Private study notes mostly in the
  papers' own words, each copied run closed by its citation. Never a
  deliverable and never a source for another draft
  ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)).
- **Spec, unit, registry**: the book track. The **spec** is the outline
  you sign off; a **unit** is one chapter, generated from its own
  contract and accepted on its own; the **registries** collect
  terminology, claims and cross-references across accepted units
  ([WRITE-A-BOOK.md](WRITE-A-BOOK.md)).

## 🔭 Exploring

- **Topic**: a group of papers about the same thing. **Seed topics** are
  phrases *you* wrote (`content/seed_topics.toml`), matched against your
  papers; **emergent topics** are groupings found by clustering
  ([TOPIC-MODELLING.md](https://github.com/prasadtalasila/chitragupta/blob/main/docs/TOPIC-MODELLING.md)).
- **Topic graph**: how topics relate, by sharing papers and by being
  about similar things. `chitragupta corpus discover` walks it
  ([TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md)).
- **Overview**: the Markdown file `corpus discover --out` writes for one
  topic: its papers, its neighbours, and sentences quoted verbatim from
  the papers. Raw material for a draft, never a generated summary.

## 🔍 Checking

- **Review aid**: one of the eleven read-only reports you can run over a
  finished draft. Every aid is **advisory**: it reports and never blocks
  ([REVIEW.md](REVIEW.md)).
- **Provenance**: the aid answering "does the cited paper actually say
  this?", worst matches first
  ([CITATION-PROVENANCE.md](CITATION-PROVENANCE.md)).
- **Verbatim scan**: the aid answering "how much of this wording came
  from my sources?" ([PLAGIARISM.md](PLAGIARISM.md)).
- **Agenda**: `chitragupta review agenda`, which merges the other aids'
  reports into one ranked, deduplicated worklist ([AGENDA.md](AGENDA.md)).
- **Unattended** and **surfaced**: the two kinds of agenda item. An
  unattended item is one `agenda-reviser` may repair without asking; a
  surfaced item waits for you to decide.

## ⚙ How the machinery talks about itself

You need these only when reading the deeper pages.

- **Layer**: one of the four parts of the pipeline, each with its own
  command: corpus (deterministic), drafting (generative, reviewed by
  you), enrichment (optional depth), review (advisory). `init`,
  `install`, `doctor` and `figure` sit outside the layers
  ([FEATURES.md](FEATURES.md#-the-four-layers)).
- **Stage**: one step of the enrichment layer (`docling`, `embed`,
  `bertopic`, `extract-keywords`, `seed-topics`, `converge`,
  `topic-graph`). Each reports `ok`, `partial`, `skipped` or `error`;
  [LADDERS.md](LADDERS.md) says which change the exit code.
- **Artefact**: a file a stage or a sync writes under `content/` for
  later commands to read. The layers never call each other, so you can
  run any piece alone.
- **Ladder** and **tier**: a *ladder* falls back automatically and tells
  you which rung it landed on; a *tier* is a menu you chose from, and
  stops rather than substituting when your choice is unavailable
  ([LADDERS.md](LADDERS.md)).
- **Enrichment / the enrich extra**: the optional heavy machinery
  (layout-aware parsing, semantic search, topic modelling), installed
  with `pip install 'chitragupta-cli[enrich]'`. Everything that can use
  it says so when it is absent instead of failing.
