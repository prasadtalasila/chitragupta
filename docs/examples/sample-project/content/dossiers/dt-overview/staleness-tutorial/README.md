# Dossier: dt-overview/staleness-tutorial

The working state that produced `content/drafts/dt-overview/staleness-tutorial.md` -- what a later
session needs in order to revise it without re-running the drafting
pipeline. Genre: tutorial.

| File | What it holds |
|---|---|
| `scope.md` | reader, dialect, what the draft covers/excludes, glossary, corpus/draft digests |
| `evidence.md` | each citekey kept, why, and the supporting quote or paraphrase |
| `rejected.md` | candidates retrieved and turned down, with the reason |
| `sections.md` | section heading -> the citekeys cited under it |
| `steering.md` | what the user asked for in chat that the draft doesn't show |
| `revisions.md` | append-only log of what changed and why |
| `retrieval.md` | every retrieval call, its result size, and a `mark-revision` boundary per pass |

This directory is gitignored, like the draft it describes. Back it up and
restore it with:

    python -m chitragupta.draft dossier export dt-overview/staleness-tutorial
    python -m chitragupta.draft dossier restore <archive.tar.gz> --force

A bundle carries drafts and dossiers, not the corpus: `content/ledger.sqlite`
is regenerable with `python -m chitragupta.corpus sync`, and `papers/bibliography.bib` is
your reference manager's export, which belongs in that tool's backup rather
than in a copy this pipeline keeps.

See `docs/DRAFT-ITERATION.md`.
