# AGENTS.md

Guidance for coding agents (and anyone else) **using this pipeline to
draft content**.

> **Changing chitragupta's own code, rather than drafting with it? Read
> [DEVELOPER-AGENTS.md](DEVELOPER-AGENTS.md) first -- it governs.** Test
> policy, the local check suite, environment constraints, code standards,
> and commit/PR/release conventions all live there.
>
> [CLAUDE.md](CLAUDE.md) is the one-screen router between the two, for an
> agent that has not yet worked out which task it is on.

[SOUL.md](SOUL.md) is the one-page why behind everything below. When this
file and that one seem to disagree, that one is the tie-breaker.

## The hard invariant: never fabricate a citekey

Fabricated placeholder references have made it into real papers before --
that is the failure mode this pipeline is built to prevent, and it is why
this is the one rule that cannot bend. [SOUL.md](SOUL.md) states the
invariant itself.

Rule: a citekey may only be used if it appears in `papers/bibliography.bib`
(source of truth -- see below) and was picked up into `content/ledger.sqlite`
by `python -m src.corpus sync`.

All five genre skills (`survey-writer`, `thesis-chapter-writer`,
`textbook-chapter-writer`, `tutorial-writer`, `deep-research` in
`.claude/skills/`) must run `python -m src.draft gate <file>` on its
own output and only present the draft once it exits 0. This is a gate,
not a lint suggestion -- treat a `FAIL` the same way you'd treat a
failing test. It binds the two teaching genres too, where citations are
optional: a draft that cites nothing passes trivially, but a draft that
cites anything must pass on merit.

A PostToolUse hook (`.claude/hooks/citation_gate_hook.py`, wired up in
`.claude/settings.json`) also enforces this mechanically: any Write/Edit
under `content/drafts/*.md` or `*.tex` runs the gate automatically and blocks
the write with a `FAIL` reason on the offending citekey(s) if it doesn't
pass. Treat the instruction above as belt-and-suspenders, not the only line
of defense -- but still run the gate by hand before calling a draft done,
since the hook only fires on the tool call that wrote the file, not on
demand.

## The bib file is the source of truth (not this pipeline)

`papers/bibliography.bib` (path configurable via `config.toml`'s
`[bib].path` or the `BIB_FILE` env var; gitignored, per-host data -- see
docs/CONFIG.md) is a manual export from your reference manager's BibTeX
export feature -- no auto-sync plugin is installed, so it is not
continuously auto-synced. Whatever citekey BibTeX assigns there
(e.g. `talasila_composable_2025`, or `noauthor_digital_nodate` for an item
with no discoverable author) is the citekey everywhere downstream.
`src/bib_reader.py` parses it and is the only place that reads it; nothing
else should ever generate or guess a citekey.

One constraint follows from that, enforced in `bib_reader.citekey_problem()`:
a citekey is also a **filename stem** (`content/parsed/<citekey>.txt`, its
`.passages.json` sidecar, the enrichment layer's `content/docling/<citekey>.md`),
so it has to be usable as one. A citekey containing a path separator, a
character Windows forbids, or a reserved device name is **skipped with a
warning naming it**, rather than sanitised -- this project never rewrites a
citekey, so the only fix is to rename it in the reference manager and
re-export. Skipping loses one paper and says so; letting it through would
write outside `content/`.

That rule is why a module needing bibliographic detail reads it back out
of the ledger rather than re-opening the bib file.

Adding or removing a paper is the user's job, not a skill's: change it in
the reference manager, re-export, re-run `python -m src.corpus sync`. There is no
watch/auto-export step. Removal is deliberately opt-in -- `sync` only
*reports* a citekey that has dropped out of the bib file until it is
re-run with `--remove-stale`, because a short export is more often a
botched one than an intentional deletion. README.md and docs/ZOTERO.md
have the full semantics.

## The four layers

The numbers below are the order these are introduced, and the order you
meet them: you need a corpus before a draft, and there is nothing to
review until a draft exists. They are not a dependency rank -- the
enrichment layer is optional and nothing above it needs it.

- **Layer 1, the corpus layer -- deterministic** (`python -m src.corpus sync`):
  bib file
  read -> ledger update -> PDF text extraction -> duplicate-citekey check
  -> stale-citekey report. No LLM calls, no judgment calls, idempotent;
  safe to run unattended. docs/ARCHITECTURE.md has the stage detail.
- **Layer 2, the drafting layer -- generative** (the `.claude/skills/`): invoked
  on
  demand, reviewed by the user. **Read-only over the corpus layer**: they
  never write to `content/ledger.sqlite`, and they never run `python -m
  src.corpus sync` or the enrichment layer on the user's behalf. On an empty
  ledger a skill says so and stops rather than regenerating anything --
  except the two teaching genres, where citations are optional:
  `textbook-chapter-writer` and `tutorial-writer` instead ask the user
  whether to proceed uncited, and wait. Each run writes a **dossier**
  beside its draft
  (`content/dossiers/<the draft's path minus its suffix>/`, Markdown,
  owned by `src/dossier.py`) holding the reader, scope, glossary, kept
  evidence, **rejected candidates and why**, and the steering the user
  gave in chat. That is what makes a draft revisable weeks later:
  `draft-reviser` reads the dossier and edits the affected sections
  instead of re-running the genre skill over the whole topic -- including
  when the change comes from the corpus rather than from you, re-grounding
  a draft whose cited papers a `sync` removed. If you do want the whole
  corpus re-searched, ask for it and you get `corpus-reviser`, which is
  the same edit discipline over a full retrieval pass -- it still keeps
  the dossier. And if what you want repaired is the verbatim overlap a
  scan reported, that is `overlap-reviser`: it works the findings one at
  a time, reasks you before deciding paraphrase-or-quote on a long run,
  and keeps no repair that `python -m src.draft gate` and `python -m
  src.review verbatim recheck` do not both accept. Never re-run a genre
  skill to change an existing draft -- see docs/DRAFT-ITERATION.md.
- **Layer 3, the enrichment layer -- optional** (`python -m src.enrich`):
  Docling, embeddings and topic modelling over the same corpus. It extends
  the *corpus* layer rather than the drafting one -- nothing in it is
  generative, everything it writes is a corpus artefact, and it takes the
  same write lock as `sync` for that reason. Run by a human, never by a
  skill. It imports nothing from the drafting or review layers, which is
  what keeps this picture free of a cycle -- a per-draft stage wrapping
  either one would reintroduce it.
- **Layer 4, the review layer -- advisory** (`src/review/citation_provenance.py`,
  `src/review/verbatim_check.py`, `src/review/citation_coverage.py`): run by
  hand on
  a finished draft, never invoked automatically. Each reads a draft plus
  the corpus and produces **evidence for a human judgement, never a
  verdict** -- every one exits 0 whether it finds something or not, and
  none may block a draft. Don't promote one to a gate --
  [SOUL.md](SOUL.md) has why. It **takes no lock**: read-only over the
  corpus, so it keeps working during a `sync`, like `python -m
  src.corpus ledger` and retrieval. Input is a draft under `content/`; output is
  `content/review/`, mirroring the draft's path under `content/drafts/`
  the way `content/rendered/` and `content/dossiers/` do, with
  `src/review/__init__.py` owning that contract.

  *Review*, not *verification*: `src.draft gate` is verification, it lives
  in the drafting layer, and it is that layer's only exit. The gate
  answers a question with one correct answer and may block; these three
  answer questions of judgement and may not.

  `verbatim_check`'s `scan` mode is the whole-draft × whole-corpus one,
  and the complement of the citation gate: the gate proves every citekey
  is real, the scan reports what wording came along with them. It is the
  exact detection tier, and the paraphrase tiers beside it are unbuilt,
  so a clean run is not a clean bill of health --
  [docs/PLAGIARISM.md](docs/PLAGIARISM.md). Its `recheck` mode compares a
  re-scan against a payload `scan --write` filed earlier, so "is this
  finding gone, and did fixing it break anything else" is arithmetic
  rather than two reports read side by side. Advisory like the rest: it
  exits 0 on a draft that got worse.

## Retrieval

`src/retrieval.py` (BM25 over a cached term-frequency index, stdlib-only,
no venv or model download needed) is what the genre skills use by
default. `src/enrich/embed_index.py` (sentence-transformers + Chroma) is
a working upgrade path with a matching `search(query, k)` shape, to swap
in when BM25 stops being enough -- a judgement call, not a corpus-size
threshold. docs/RETRIEVAL.md has the caching mechanics and the
choose-between-them guidance.

Retrieval finds a *document*; `src/passages.py` decides which part of it
may be shown. Anything that needs to point at a span of a source rather
than the whole of it -- `citation_provenance`, `verbatim_check`, the
enrichment layer -- goes through that one ladder rather than re-deriving
passages, so a caller cannot accidentally quote from a rung that isn't
quotable. See docs/LADDERS.md.

## Config lives in `config.toml`

Every setting lives in `config.toml` at the repo root, and every one is
overridable by an env var of the same name (e.g.
`BIB_FILE=/other/path.bib python -m src.corpus sync`). docs/CONFIG.md is the
reference.

`python -m src.draft gate` needs no venv -- it only reads
`content/ledger.sqlite` through stdlib `sqlite3` and runs with bare
`python`. `python -m src.corpus sync` does need the venv, and must be run
through the installed one rather than the bare system interpreter.
