# 🤖 AGENTS.md

The contract for agents (and anyone else) **using this pipeline to
draft content**. A draft here is co-authored: the human curates the
corpus, sets the scope and steers; the agent retrieves, writes grounded
prose, and records the judgement behind it. This file is the agent's
half of that bargain.

> **Changing chitragupta's own code, rather than drafting with it? Read
> `DEVELOPER-AGENTS.md` first -- it governs.** (In a git checkout only --
> `chitragupta init` deliberately does not scaffold it; see `CLAUDE.md`'s
> routing table.) Test policy, the local check suite, environment
> constraints, code standards, and commit/PR/release conventions all
> live there.
>
> [CLAUDE.md](CLAUDE.md) is the one-screen router between the two, for an
> agent that has not yet worked out which task it is on.

[SOUL.md](SOUL.md) is the one-page why behind everything below. When this
file and that one seem to disagree, that one is the tie-breaker.

Every artefact shape this file names -- a dossier, a review report, a
gate-passed draft, a signed spec -- exists as a real, committed example
under `docs/examples/sample-project/`, produced by running the real
pipeline over five sample papers.
[docs/examples/README.md](docs/examples/README.md) is the map. When in doubt
about what a file should look like, look there before inventing a shape.

## 🔑 The hard invariant: never fabricate a citekey

Fabricated placeholder references have made it into real papers before --
that is the failure mode this pipeline is built to prevent, and it is why
this is the one rule that cannot bend. [SOUL.md](SOUL.md) states the
invariant itself. In a conventional retrieval pipeline the model is
*asked* not to invent a reference; here, nothing you generate can reach
a rendered document without passing a check you cannot talk your way
past.

Rule: a citekey may only be used if it appears in `papers/bibliography.bib`
(source of truth -- see below) and was picked up into `content/ledger.sqlite`
by `python -m chitragupta.corpus sync`.

All five genre skills (`survey-writer`, `thesis-chapter-writer`,
`textbook-chapter-writer`, `tutorial-writer`, `deep-research` in
`.claude/skills/`) must run `python -m chitragupta.draft gate <file>` on its
own output and only present the draft once it exits 0. So must
`book-assembler`, which writes no prose but does write a document: the
LaTeX book it composes is a new file, and this layer has one exit
whatever produced the file. This is a gate,
not a lint suggestion -- treat a `FAIL` the same way you'd treat a
failing test. It binds the two teaching genres too, where citations are
optional: a draft that cites nothing passes trivially, but a draft that
cites anything must pass on merit.

A PostToolUse hook (`.claude/hooks/citation_gate_hook.py`, wired up in
`.claude/settings.json`) also enforces this mechanically: any Write/Edit
under `content/drafts/*.md` or `*.tex` runs the gate automatically and
surfaces a blocking `FAIL` naming the offending citekey(s) if it doesn't
pass. **It is a PostToolUse hook, so it fires *after* the write lands** --
the file exists, with the bad citekey in it, until the `FAIL` is fixed.
The block is on the agent continuing as though the draft were sound, not
on the bytes reaching disk, and a draft abandoned at that point stays
wrong on disk. Treat the instruction above as belt-and-suspenders, not
the only line of defense -- and still run the gate by hand before calling
a draft done, since the hook only fires on the tool call that wrote the
file, not on demand.

The gate proves every citekey is *real*. Whether each cited paper
actually *supports* its sentence is a different question, answered by
the review layer below -- advisorily, never as a block.

## 🧼 Start each draft in a clean session

Begin a draft in a fresh session -- `/clear` in Claude Code, or a new
conversation in whatever agent you use. Not tidiness: it closes the one
failure the gate above cannot see.

The gate is mechanical and complete for what it measures. A citekey is
in the ledger or it is not, so a **fabricated** one is caught every
time. What it cannot catch is a **real** citekey -- present in
`content/ledger.sqlite`, correctly spelled, genuinely parsed from a
genuine PDF -- that an earlier task in the same session left sitting in
context, and that then gets cited for a claim it does not support.
Every deterministic check in this pipeline passes that draft. `python
-m chitragupta.draft gate` passes it, the PostToolUse hook passes it,
and `python -m chitragupta.review verbatim scan` is looking for
something else entirely. Nothing anywhere detects it, which is why the
remedy is procedural rather than another check.

Framing travels the same way. A session that spent an hour on one topic
carries its vocabulary, its emphases and its sense of what matters, and
the next draft inherits all three without anyone having chosen them.

**Clearing is cheap here, and that is not a coincidence** -- it is what
`content/dossiers/` is for. The reader, the scope, the glossary, the
kept evidence, the rejected candidates and the steering already given
live on disk rather than in the conversation, so a fresh session picks
a draft back up by reading them. `docs/DRAFT-ITERATION.md` is that
design; this guidance and that architecture argue for each other.

One thing to do before clearing mid-work: **get this session's steering
into `steering.md` first.** `draft-reviser` reads chat steering from
the dossier, so steering that was only ever said dies with the session.

## 📚 The bib file is the source of truth (not this pipeline)

`papers/bibliography.bib` (path configurable via `config.toml`'s
`[bib].path` or the `BIB_FILE` env var; gitignored, per-host data -- see
docs/CONFIG.md) is a manual export from your reference manager's BibTeX
export feature -- no auto-sync plugin is installed, so it is not
continuously auto-synced. Whatever citekey BibTeX assigns there
(e.g. `talasila_composable_2025`, or `noauthor_digital_nodate` for an item
with no discoverable author) is the citekey everywhere downstream.
`chitragupta/bib_reader.py` parses it and is the only place that reads it; nothing
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
the reference manager, re-export, re-run `python -m chitragupta.corpus sync`.
There is no
watch/auto-export step. Removal is deliberately opt-in -- `sync` only
*reports* a citekey that has dropped out of the bib file until it is
re-run with `--remove-stale`, because a short export is more often a
botched one than an intentional deletion. README.md and docs/ZOTERO.md
have the full semantics.

## 🏗 The four layers

The numbers below are the order these are introduced, and the order you
meet them: you need a corpus before a draft, and there is nothing to
review until a draft exists. They are not a dependency rank -- the
enrichment layer is optional and nothing above it needs it.

- **Layer 1, the corpus layer -- deterministic** (`python -m chitragupta.corpus
  sync`):
  bib file
  read -> ledger update -> PDF text extraction -> duplicate-citekey check
  -> stale-citekey report. No LLM calls, no judgment calls, idempotent;
  safe to run unattended. docs/ARCHITECTURE.md has the stage detail.

  The same layer also *reads itself back*: `python -m chitragupta.corpus
  ledger` lists what is synced, and `python -m chitragupta.corpus discover`
  maps what the corpus is about -- a topic's papers, its neighbouring
  topics, and the bridges between them -- once the enrichment layer has
  built the topic graph. Both are read-only and lock-free, so either is
  a legitimate way for a drafting session to orient itself before any
  draft exists; `docs/TOPIC-DISCOVERY.md` has the workflow, and
  [`discover_digital_twin.txt`](docs/examples/sample-project/content/discover_digital_twin.txt)
  in the sample project is a real transcript of one.
- **Layer 2, the drafting layer -- generative** (the `.claude/skills/`): invoked
  on
  demand, reviewed by the user. **Read-only over the corpus layer**: they
  never write to `content/ledger.sqlite`, and they never run `python -m
  chitragupta.corpus sync` or the enrichment layer on the user's behalf. On an empty
  ledger a skill says so and stops rather than regenerating anything --
  except the two teaching genres, where citations are optional:
  `textbook-chapter-writer` and `tutorial-writer` instead ask the user
  whether to proceed uncited, and wait. Each run writes a **dossier**
  beside its draft
  (`content/dossiers/<the draft's path minus its suffix>/`, Markdown,
  owned by `chitragupta/dossier/`) holding the reader, scope, glossary, kept
  evidence, **rejected candidates and why**, and the steering the user
  gave in chat -- `docs/examples/sample-project/content/dossiers/dt-overview/`
  holds four real ones, exactly as drafting filled them. That is what
  makes a draft revisable weeks later:
  `draft-reviser` reads the dossier and edits the affected sections
  instead of re-running the genre skill over the whole topic -- including
  when the change comes from the corpus rather than from you, re-grounding
  a draft whose cited papers a `sync` removed. If you do want the whole
  corpus re-searched, ask for it and you get `corpus-reviser`, which is
  the same edit discipline over a full retrieval pass -- it still keeps
  the dossier. And if what you want repaired is the verbatim overlap a
  scan reported, that is `agenda-reviser`: it works the findings one at
  a time, reasks you before deciding paraphrase-or-quote on a long run,
  and keeps no repair that `python -m chitragupta.draft gate` and `python -m
  chitragupta.review verbatim recheck` do not both accept. Never re-run a genre
  skill to change an existing draft -- see docs/DRAFT-ITERATION.md.

  **The human's own prose is a first-class input, not an obstacle.** An
  `outline.md` in the dossier can declare, per section, a brief the
  draft must obey but never show, the human's own claims to be grounded,
  and the exact retrieval queries to run verbatim; a hand-written
  section is grounded against the corpus, and any sentence the corpus
  cannot warrant is dropped *and named back to the user*, never silently
  kept. Steering respects the same boundary in reverse: obey it in
  emphasis and selection, but never let it manufacture support the
  corpus does not offer -- "the corpus does not contain this" is a
  correct and expected answer, not a failure to route around.

  **Verbatim source wording has one legitimate home, and it is not the
  draft.** The dossier's `evidence.md` records it in a `quote:` field --
  optional, captured only when a quotation is actually intended, and
  never the residue of retrieval. `python -m chitragupta.draft evidence`
  then renders those spans into an **evidence sidecar** beside the draft's
  render (`content/rendered/<topic>/<name>.evidence.pdf`), attributed and
  in quotation marks. Four of the five genres emit one;
  `tutorial-writer` does not, and docs/GENRE.md records why for each. A
  sidecar is never committed and never shipped -- `.gitignore` excludes
  it, and `scripts/release.py` archives only git-tracked paths -- because
  it carries wording from copyrighted sources. Never add a `quote:` after
  the fact to make one appear, and never copy a span out of one back into
  body prose.

  **A per-citekey TL;DR is a separate, smaller feature: browsing, not
  drafting.** `python -m chitragupta.draft tldr write <citekey>` (summary
  on stdin) caches a one-paragraph summary under `content/tldr/`, keyed
  to a fingerprint of that citekey's parsed text; `tldr show <citekey>`
  reads it back and reports it stale rather than silently describing a
  paper that has since been re-parsed. The tool never generates the
  summary itself -- a person or a skill composes it -- and
  `python -m chitragupta.corpus ledger` is untouched.
- **Layer 3, the enrichment layer -- optional** (`python -m chitragupta.enrich`):
  Docling, embeddings and topic modelling over the same corpus, ending
  in the topic graph that `corpus discover` reads. It extends
  the *corpus* layer rather than the drafting one -- nothing in it is
  generative, everything it writes is a corpus artefact, and it takes the
  same write lock as `sync` for that reason. Run by a human, never by a
  skill. It imports nothing from the drafting or review layers, which is
  what keeps this picture free of a cycle -- a per-draft stage wrapping
  either one would reintroduce it.
- **Layer 4, the review layer -- advisory** (`python -m chitragupta.review`,
  owned by `chitragupta/review/`): ten aids that read over a finished
  draft -- by you, or by a skill that runs one on your behalf. Never a
  gate. By subcommand: `provenance` (does the cited paper say this),
  `verbatim` (how much wording came along from the sources), `coverage`
  (what retrieval surfaced that was never cited), `synthesis` (which
  sections lean on one source), `figure` (do the referenced figures fit
  their boxes), `uncited` (which sentences carry no citation at all),
  `quotation` (is each recorded quote really in its source), `support`
  (does the source entail the claim, by a real NLI model), `union` (does
  an assembled book still carry every citekey its accepted units stand
  on), and `agenda` -- which runs nothing itself, but merges the other
  eight draft-reading aids' reports, the drafting layer's prose check
  and the dossier's drift report into one ranked, deduplicated worklist.
  Each produces **evidence for a human judgement, never a verdict** --
  every one exits 0 whether it finds something or not, and
  none may block a draft. Don't promote one to a gate --
  [SOUL.md](SOUL.md) has why. The layer **takes no lock**: read-only over
  the corpus, so it keeps working during a `sync`, like `python -m
  chitragupta.corpus ledger` and retrieval. Input is a draft under `content/`;
  output is
  `content/review/`, mirroring the draft's path under `content/drafts/`
  the way `content/rendered/` and `content/dossiers/` do, with
  `chitragupta/review/__init__.py` owning that contract --
  `docs/examples/sample-project/content/review/dt-overview/` shows the full
  set for real drafts.

  *Review*, not *verification*: `chitragupta.draft gate` is verification, it lives
  in the drafting layer, and it is that layer's only exit. The gate
  answers a question with one correct answer and may block; these ten
  answer questions of judgement and may not.

  **One correct answer is what a gate needs, not what earns it.** The
  deciding question is what the check is measured against. The gate is
  measured against the ledger, which is ground truth -- the human's own
  `.bib` export plus a real parse of a real PDF -- and no state of the
  world makes a citekey absent from it legitimately present. A check
  measured against a *recorded preference* -- a target someone typed,
  which can be wrong, stale, or deliberately overridden -- reports and
  never blocks however mechanical its answer, because blocking on it
  would refuse a correct draft on a bad target. That holds whichever
  layer the check lives in, and it is why DEVELOPER-AGENTS.md bars
  promoting any new check into a gate beside `chitragupta/citation_gate.py`.
  docs/ARCHITECTURE.md's "Layer 4" has the argument.

  `verbatim`'s `scan` mode is the whole-draft × whole-corpus one,
  and the complement of the citation gate: the gate proves every citekey
  is real, the scan reports what wording came along with them. It runs
  three detection tiers, and the one that sees a genuine restatement
  needs an optional stack a checkout may not have -- so a clean run is
  not a clean bill of health, and the scan names any tier that did not
  run. [docs/PLAGIARISM.md](docs/PLAGIARISM.md). Its `recheck` mode compares a
  re-scan against a payload `scan --write` filed earlier, so "is this
  finding gone, and did fixing it break anything else" is arithmetic
  rather than two reports read side by side. Advisory like the rest: it
  exits 0 on a draft that got worse.

## 🔎 Retrieval

`chitragupta/retrieval.py` (BM25 over a cached term-frequency index, stdlib-only,
no venv or model download needed) is what the genre skills use by
default. `chitragupta/enrich/embed_index.py` (sentence-transformers + Chroma) is
a working upgrade path with a matching `search(query, k)` shape, to swap
in when BM25 stops being enough -- a judgement call, not a corpus-size
threshold. docs/RETRIEVAL.md has the caching mechanics and the
choose-between-them guidance.

Retrieval finds a *document*; `chitragupta/passages.py` decides which part of it
may be shown. Anything that needs to point at a span of a source rather
than the whole of it -- `citation_provenance`, `verbatim_check`, the
enrichment layer -- goes through that one ladder rather than re-deriving
passages, so a caller cannot accidentally quote from a rung that isn't
quotable. See docs/LADDERS.md.

Log what you retrieve: `python -m chitragupta.draft retrieve search
"<query>" --log <draft>` appends the call to the dossier's
`retrieval.md`, and that log is what makes the dossier's drift report
able to say, months later, which *new* papers the draft's own queries
would surface today.

## ⚙ Config lives in `config.toml`

Every setting lives in `config.toml` at the repo root, and every one is
overridable by an env var of the same name (e.g.
`BIB_FILE=/other/path.bib python -m chitragupta.corpus sync`). docs/CONFIG.md is
the
reference.

`python -m chitragupta.draft gate` needs no venv -- it only reads
`content/ledger.sqlite` through stdlib `sqlite3` and runs with bare
`python`. `python -m chitragupta.corpus sync` does need the venv, and must be run
through the installed one rather than the bare system interpreter.
