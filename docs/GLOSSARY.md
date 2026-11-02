# 📖 Glossary: the working vocabulary

Status: **reference.**

**Written for** you, the person writing a draft with this pipeline.
Every term below appears throughout the documentation. Each entry says
what the thing is *to you* and names the one document that owns the
detail. Terms are grouped by when you first meet them, not
alphabetically; read top to bottom once and the rest of the
documentation gets easier.

## 📚 Your library, inside the pipeline

- **Citekey**: the identifier your reference manager assigns each
  entry (`sample_dt_sync_2023`), which a draft cites as
  `[@sample_dt_sync_2023]`. The one hard rule of this project: a
  citekey may be used only if it came from your own `.bib` export and
  a real PDF was really parsed ([SOUL.md](../SOUL.md)).
- **Corpus**: your papers as the pipeline sees them, meaning the `.bib`
  export plus the attached PDFs, synced into the ledger.
- **Ledger**: the small database (`content/ledger.sqlite`) recording
  every entry: its citekey, title, whether its PDF parsed, and where
  the extracted text lives. Built and updated by `chitragupta corpus
  sync`; inspected with `chitragupta corpus ledger`
  ([ZOTERO.md](ZOTERO.md) gets you here).
- **Sync**: the deterministic run that reads your `.bib`, updates the
  ledger, and extracts each PDF's text. No AI is involved, so the same
  bibliography always yields the same citekeys.
- **Parse**: turning one PDF into plain text the pipeline can search
  and quote. Which of the two parser backends to use is
  [PDF-PARSER.md](PDF-PARSER.md)'s question.

## ✍ Writing

- **Genre skill**: one of the six drafting skills (survey, thesis
  chapter, textbook chapter, tutorial, deep research, verbatim digest).
  The other five
  work on drafts those produce: three revisers, the book assembler, and
  `figure-drawer`, which draws a figure for whichever skill hands it
  one. You never invoke one by name; you ask in ordinary words and the
  right one answers ([GENRE.md](GENRE.md)).
- **Draft**: the document being written, under `content/drafts/`.
- **Dossier**: the folder written *alongside* a draft holding the
  judgment that produced it: the scope, who the reader is, which
  sources were kept and which were turned down, and a revision log. It
  is why a draft can be changed months later without re-running
  anything ([DOSSIER.md](DOSSIER.md); the walkthrough is
  [WRITING-PROCESS.md](WRITING-PROCESS.md)).
- **The gate**: `chitragupta draft gate`, the single check standing
  between a draft and a rendered document. It asks whether every
  citekey in the draft is really in the ledger. It is the only
  *blocking* check in the pipeline, and a failure sends the draft back
  to be rewritten, so you normally never see one.
- **Render**: turning a finished draft into PDF/LaTeX/Word with its
  bibliography resolved. `chitragupta draft render` runs the gate again
  on the text it is about to render.
- **Stamp** (the draft fingerprint): a digest of the draft's text that
  `chitragupta draft dossier stamp` records in the dossier's `scope.md`
  once the gate passes. `dossier status` compares against it to tell you
  whether the draft changed since, for example after a hand edit
  ([USER-EDITS.md](USER-EDITS.md)).
- **Evidence sidecar**: a separate document rendered beside a draft,
  listing each cited source and the exact spans its dossier marked
  quotable. Four of the six genres produce one
  ([DOSSIER.md](DOSSIER.md#-the-evidence-sidecar-decided-per-genre)).
- **Verbatim digest**: the sixth genre. Private study notes written
  mostly in the papers' own words, each copied run closed by its
  citation. Never a deliverable and never a source for another draft
  ([VERBATIM-DIGEST.md](VERBATIM-DIGEST.md)).
- **Spec, unit, registry**: the book track. The **spec** is the book's
  outline, which you sign off; a **unit** is one chapter, generated
  from its own contract and accepted on its own; the **registries**
  collect terminology, claims and cross-references across accepted
  units ([WRITE-A-BOOK.md](WRITE-A-BOOK.md)).

## 🔭 Exploring

- **Topic**: a group of papers about the same thing. Two kinds exist
  side by side: **seed topics** are phrases *you* wrote
  (`content/seed_topics.toml`), matched against your papers; **emergent
  topics** are groupings the corpus itself turned out to have,
  discovered by clustering ([TOPIC-MODELLING.md](TOPIC-MODELLING.md)).
- **Topic graph**: how the topics relate to each other, by sharing
  papers and by being about similar things. `chitragupta corpus
  discover` is how you walk it
  ([TOPIC-DISCOVERY.md](TOPIC-DISCOVERY.md)).
- **Overview**: the Markdown file `corpus discover --out` writes for
  one topic. It lists the topic's papers with references, its
  neighbours, and real sentences quoted verbatim from the papers. It is
  raw material for a new draft and is never a generated summary.

## 🔍 Checking

- **Review aid**: one of the eleven read-only reports you can run over a
  finished draft (provenance, verbatim overlap, coverage, and so on).
  Every aid is **advisory**: it reports for you to judge and never
  blocks anything ([REVIEW.md](REVIEW.md)).
- **Provenance**: the aid answering "does the cited paper actually
  say this?", worst matches first
  ([CITATION-PROVENANCE.md](CITATION-PROVENANCE.md)).
- **Verbatim scan**: the aid answering "how much of this wording came
  from my sources?" ([PLAGIARISM.md](PLAGIARISM.md)).
- **Agenda**: `chitragupta review agenda`, which merges the other aids'
  reports into one ranked, deduplicated worklist
  ([AGENDA.md](AGENDA.md)).
- **Unattended** and **surfaced**: the two kinds of agenda item. An
  unattended item is one `agenda-reviser` may repair without asking (a
  short verbatim run, a prose finding, a citation to a paper the corpus
  no longer has). A surfaced item waits for you to decide.

## ⚙ How the machinery talks about itself

Five structural words the other documents lean on. You can write a whole
book without needing them; they matter when you read the deeper pages.

- **Layer**: one of the four parts of the pipeline, each with its own
  command: corpus (deterministic), drafting (generative, reviewed by
  you), enrichment (optional depth), review (advisory reports). The
  remaining commands (`init`, `install`, `doctor`, `figure`) set up a
  project or work on one figure, and sit outside the layers. [FEATURES.md](FEATURES.md#-the-four-layers)
  draws them.
- **Stage**: one step of the enrichment layer (`docling`, `embed`,
  `bertopic`, `extract-keywords`, `seed-topics`, `converge`,
  `topic-graph`). Each reports its own honest status: `ok`, `partial`,
  `skipped` or `error`. [LADDERS.md](LADDERS.md) states which of the
  four changes the run's exit code.
- **Artefact**: a file a stage or a sync writes under `content/`,
  which later commands read. The layers never call each other. They
  leave files for each other, which is why you can run any piece alone.
- **Ladder** and **tier**: the two ways the pipeline handles having
  more than one way to do a job. A *ladder* falls back automatically
  and tells you which rung it landed on; a *tier* is a menu you chose
  from, and stops rather than substituting when your choice is
  unavailable ([LADDERS.md](LADDERS.md)).
- **Enrichment / the enrich extra**: the optional heavy machinery
  (layout-aware parsing, semantic search, topic modelling), installed
  with `pip install 'chitragupta-cli[enrich]'`. Nothing else needs it.
  Everything that can use it says so when it is absent instead of
  failing.
