# 🛠 Developer guide

Material for working on this repository itself, as opposed to using it to
draft content: test running, the full source layout, and known gaps.
See [README.md](README.md) for the user-facing Quickstart/Configuration/
Architecture docs and [DOCKER.md](DOCKER.md) for running a container;
[DOCKER-DEVELOPER.md](DOCKER-DEVELOPER.md) here is this repo's own
record of how the two images are built and verified.

## 🧭 Table of contents

- [Running tests](#-running-tests)
- [Benchmarking the parser](#-benchmarking-the-parser)
- [Writing a script that drives the enrichment layer](#-writing-a-script-that-drives-the-enrichment-layer)
- [Repository layout](#-repository-layout)
- [Figures and copyright](#-figures-and-copyright)
- [Citation provenance](#-citation-provenance)
- [Open questions and unbuilt features](#-open-questions-and-unbuilt-features)

## 🧪 Running tests

```bash
# Install pytest/pytest-cov into the same venv (run python-deps first)
bash scripts/install_full_pipeline.sh dev-deps

# Run the full suite with coverage, over every core (pytest-xdist)
.venv-full/bin/python -m pytest -n auto --cov --cov-report=term-missing

# Same, on a host without pandoc/TeX Live/poppler: the render tests skip,
# so opt out of the 100% bar (pyproject's fail_under) rather than lower it
.venv-full/bin/python -m pytest -n auto --cov --cov-report=term-missing \
    --cov-fail-under=0
```

`tests/` covers both the corpus layer and `chitragupta/enrich/*`. The
enrich group's dependencies (docling, chromadb, bertopic,
sentence-transformers) are mocked via `sys.modules` for fast,
deterministic unit tests, so the `dev-deps` group alone is *not*
enough: the `enrich` group
(`bash scripts/install_full_pipeline.sh python-deps`) must already be
installed too, since
`tests/test_bib_reader.py` needs `bibtexparser` and the `chitragupta/enrich/` test
modules need docling/chromadb/bertopic/sentence-transformers.

One module is the deliberate exception.
`tests/test_enrich_real_libraries.py` drives the *real* `chromadb` through
`build_index()`/`search()`, and asks the real
`sentence_transformers`/`bertopic` classes whether they still accept the
keywords the fakes accept. The fakes are faithful enough that the
expensive failure is the day they quietly stop being; that module is what
notices. It does not download an embedding model (its own docstring says
why), so it stays as fast and as offline as the rest.

A handful of tests run real dependencies end to end rather than mocking
them, and skip automatically when the dependency is absent:
`tests/test_feature_workflows.py` and the `TestRenderReal`/
`TestExtractTextReal` classes elsewhere probe for the
`pdftotext`, `pandoc` and `lualatex` binaries on `PATH` (and
`test_feature_workflows.py` for `pdflatex`, to build a fixture PDF);
`tests/test_enrich_real_libraries.py` probes for an importable library
instead, which is the same idiom against a different kind of absence.

## ⚡ Benchmarking the parser

`bench/` measures what a full `docling` parse of the bib corpus costs on
a given machine, and is deliberately kept out of `tests/`: it takes a couple of
hours, needs real PDFs and a GPU, and answers a "how long / what's the
bottleneck" question rather than a pass/fail one. It is excluded from the
release zip for the same reason `tests/` is.

- [docs/PERFORMANCE.md](docs/PERFORMANCE.md): what each setting costs,
  organised by setting. Ships in the release archive, unlike `bench/`
- [docs/PARALLELISM.md](docs/PARALLELISM.md): parallel parse design
  (architecture, components, and the roadmap)
- [bench/README.md](https://github.com/prasadtalasila/chitragupta/blob/main/bench/README.md)
  covers how to run it, and what each switch measures
- [bench/RESULTS.md](https://github.com/prasadtalasila/chitragupta/blob/main/bench/RESULTS.md)
  is the dated measurement record, newest last, with raw per-run data
  in `bench/results/`. Read its "Which sections are current" table
  first: several early conclusions were overturned by later runs and
  are kept, marked, rather than deleted
- [bench/PARALLELISM-PLAN.md](https://github.com/prasadtalasila/chitragupta/blob/main/bench/PARALLELISM-PLAN.md)
  records what is still unknown, and what to measure before changing it

What the measurements established, and what the code relies on:

1. A `docling` parse is CPU-bound. A GPU alone buys little; turning OCR
   off (`[parser].ocr = false`, the default) buys more, because OCR
   competes for the same CPU the worker pool needs.
2. The pool gives each worker its own GPU rather than letting every
   worker resolve to `cuda:0`.
3. `worker_ceiling()` clamps the pool size; `bench/RESULTS.md` records
   what that clamp costs on the multi-GPU machine.
4. About 1% of documents come back with a different quotable passage on
   a re-parse, even with the same configuration. The
   artifact-by-artifact contract is in
   [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#-what-is-reproducible-and-what-is-not).

Read `bench/RESULTS.md`'s "Which sections are current" table before
quoting a number from it: several early conclusions were overturned by
later runs and are kept, marked, rather than deleted. `bench/` exists so
that the next conclusion is measured too.

## 🧠 Writing a script that drives the enrichment layer

`chitragupta.enrich.docling_parse.parse_corpus` and `python -m
chitragupta.corpus sync` both use
a worker pool when `[parser].workers` is above 1, and every start method
they can pick (`forkserver` or `spawn`; see `[parser].start_method`)
re-imports the calling program's `__main__` in each worker. Any script of
your own that calls them must guard its top level:

```python
if __name__ == "__main__":
    main()
```

Without it, every worker re-runs the script on startup and the pool dies
with `BrokenProcessPool`. `chitragupta/enrich/__main__.py` and `chitragupta/sync.py`
are both guarded already; this only bites ad-hoc scripts, and it bites
immediately rather than subtly.

## 📁 Repository layout

```text
README.md                 the user-facing overview: what this is, the Quickstart, hardware sizing
bench/                    parser measurement (dev-only, not shipped) -- see "Benchmarking the parser"
                          above; corpus.json/sample*.json are generated and gitignored, results/ is
                          committed evidence
  bench_docling.py          backend extraction timings, one process
  sweep_sync.py             the real `python -m chitragupta.corpus sync` swept over worker/GPU counts -- the harness
                            every pool-level figure must come from
  run_parallel.py           independent-process baseline; answers a different question to sweep_sync.py
  make_corpus.py            builds the gitignored work lists from your own bib file
  repro_check.py            compares two parses at three levels (bytes, passage spans, passage texts)
                            and self-checks its own detector on every run
SOUL.md                   one page: why this exists, the one invariant, what it refuses to become
AGENTS.md                 instructions for agents drafting *with* the pipeline -- the citekey
                          invariant, the four layers, retrieval
DEVELOPER-AGENTS.md       instructions for agents changing *this repo* -- install notes, dev
                          process, commit/PR/release conventions
DEVELOPER.md              this file -- test running, repo layout, open questions
DOCKER.md                 how do I run this in a container -- the toolchain image and the agent image
DOCKER-DEVELOPER.md       how the toolchain and agent images are built and verified before a release
.github/                  CI/release workflows, plus the issue and PR templates GitHub picks up
                          automatically and RELEASE_TEMPLATE.md (copied by hand)
docs/                     reference docs that ship in the release zip -- everything except the
                          root-level ones above, which stay put because they're what a reader looks
                          for first. README.md's Documentation tables and mkdocs.yml's nav index
                          them. Every file here carries a status line on its third line,
                          `Status: **<kind>.**`, so a reader can tell what they are holding before
                          reading it -- one of:
                            tutorial.                a lesson a reader follows start to finish
                            how-to.                  a procedure for a task the reader already has
                            reference.               what exists and how to look it up
                            implemented.             a built subsystem, described as built
                            reasoning document.      why a decision went the way it did, kept
                                                     because the reasoning outlives the decision
                            measurements.            numbers from a real run on a named machine
                            proposal.                nothing here is built; the decision is open
                          A new document picks one of those rather than inventing an eighth. The
                          line carries no date: git records when a file was written and revised
  DIAGRAMS.md               the workflow drawn thirteen ways; the fenced mermaid blocks are the source
  diagrams/                 the same thirteen as standalone files, for use outside this repo
    *.mmd                     mermaid sources with a title line
    svg/*.svg                 rendered exports, by scripts/render_diagrams.py. Exports only -- edit the
                              fenced block in DIAGRAMS.md, run --sync (house theme + .mmd copy), re-render
    svg/sources.json          which .mmd fingerprint each export was rendered from; pinned by a test
  examples/                 the committed sample project and harness examples (examples/README.md)
  logo.svg, logo-dark.svg   the README banner, light and dark
LICENSE                   MIT
assets/                   data files the pipeline reads at runtime, tracked and shipped
  csl/ieee.csl              the CSL style pandoc formats citations with ([render].csl default).
                          Vendored byte-identical to the CSL project's own release (CC BY-SA 3.0)
                          so it can be re-fetched and diffed -- do not edit it in place; the one
                          attribute this project needs is injected into a temp copy at render
                          time (see assets/csl/README.md and render_output._collapsed_csl)
  csl/README.md             the vendoring policy, upstream URL and sha256
.github/workflows/        ci.yml (on push/PR: test suite + coverage + poetry check on Linux and
                          Windows, the hook launchers, the lint job, a Docker build and
                          SonarQube), commit-message.yml (checks a PR's squash-commit fence),
                          docs.yml (builds the documentation site) and release.yml
                          (on a v* tag: verifies tag matches pyproject.toml's version, builds
                          scripts/release.py's zip, publishes it to a GitHub Release)
config.toml.example       tracked template for the central config -- paths, parser backend, worker
                          count, embedding model. Copy to config.toml (gitignored, per-host) before
                          anything imports chitragupta.config; see docs/CONFIG.md
papers/                   gitignored, per-host data -- not shipped in the repo
  bibliography.bib          BibTeX export -- source of truth for citekeys/metadata (config.toml's [bib].path default)
  bibliography/             the export's companion attachment folder, referenced by each entry's file field
pyproject.toml            Poetry config -- a real, publishable package (name chitragupta-cli, import
                          package chitragupta, [build-system] = poetry-core; docs/PACKAGING.md has
                          the decision and the naming) + pytest/coverage tool config
poetry.toml               project-local Poetry config: virtualenvs.create = false (installs into
                          whatever venv VIRTUAL_ENV points at, e.g. .venv-full/, instead of Poetry's own)
poetry.lock               resolved dependency versions -- `poetry lock` after editing one constraint;
                          `python3 scripts/relock.py` to regenerate it from nothing (docs/UV-MIGRATION.md)
mkdocs.yml                the documentation site published at prasad.talasila.in/chitragupta. `docs_dir: .`
                          on purpose: the site is this repository as it stands, so every cross-document
                          link works unchanged and there is no staging step to keep in sync. Built by
                          .github/workflows/docs.yml from pyproject.toml's optional `docs` group
                          (`poetry install --only docs`). Read its header before editing
chitragupta/                      the corpus and drafting layers (sync needs bibtexparser;
                          citation_gate/references need nothing)
  __main__.py               the `chitragupta`/`cg` console script: dispatches corpus, draft, review,
                          enrich, init, doctor, install and figure
  init.py, doctor.py, install.py  the package-level commands (docs/PACKAGING.md)
  figure/                   `chitragupta figure sync|check|new|look`, the figure-drawer toolkit
                          (docs/figure-checks/README.md)
  discover/                 `corpus discover`: the topic-graph walks, the HTML page and the offline app
  config.py                 every setting, as config.NAME; env var overrides
  config_load.py            the config.toml load and the typed getters config.py reads each setting through
  config_enrich.py          the [enrich]/[discover] knobs, re-exported by config.py as config.NAME
  runlock.py                one-writer-at-a-time lock over content/, held by `chitragupta.corpus sync` and
                          `chitragupta.enrich` -- the only two commands that write to it;
                          a dedicated sqlite file, so a killed holder releases it with no
                          staleness check and readers are never blocked
  bib_reader.py             parses bibliography.bib -- the only citekey source
  ledger.py                 per-citekey status tracking (content/ledger.sqlite); find_stale/prune_missing
                          detect/remove rows for citekeys no longer in the bib file. Also persists each
                          entry's formatting-relevant BibTeX fields (bib_fields, JSON), so references.py
                          can build a full bibliography entry without reading the bib file itself
  pdf_text/                 PDF text extraction, dispatched to pdftotext/docling by config.PARSER; also the parse-quality guard
  sync.py                   orchestrates the above -- the corpus layer's `sync` verb; --remove-stale opts into
                          deleting stale ledger rows (default: report only, see docs/ZOTERO.md)
  corpus.py                 the corpus layer's single entry point, `python -m chitragupta.corpus sync|ledger|topics|discover`.
                          sync.py and ledger.py carry no __main__ block of their own. Imports the verb
                          it was given rather than both, so asking for `ledger` never pays for sync's
                          bibtexparser -- see docs/ARCHITECTURE.md on why that one is not like the
                          other dispatchers
  draft.py                  the drafting layer's single entry point, `python -m chitragupta.draft
                          gate|dossier|retrieve|references|render|...`, twelve verbs (see --help);
                          same rule, same reasons
  dedup.py                  advisory near-duplicate citekey detection (shared DOI/title), called from sync
  reranker.py               the cross-encoder loader, cached per model id; shared by enrich's search rerank
                          and discover's ladder, so neither imports the other's privates
  retrieval.py              BM25 search over the corpus layer, backed by a cached term-frequency index.
                          `search` ranks and returns a snippet -- the best-covering passage for the
                          query, and the same one every run; `evidence` reads more of one document
                          when a snippet is not enough to judge it. A lookup, not a stage: see
                          docs/REJECTION.md for the two-stage read that was built and withdrawn.
                          `--log` records each call's payload in the dossier
  passages.py               where a citekey's supporting text comes from (docling sidecar -> form-feed
                          pages -> pdftotext) and whether it may be quoted -- shared by the consumers
                          that need to point at part of a source rather than all of it
  overlap_index.py          disk-cached word n-gram fingerprint index (content/overlap/) for
                          chitragupta/review/verbatim_check/'s overlap and scan modes -- one .fpr file per citekey plus
                          a merged, binary-searchable corpus-wide index.bin, both keyed by
                          (pdf_hash, parsed-file stat) so a re-run over an unchanged corpus costs no
                          re-fingerprinting. Read-only over the corpus layer, no writer lock
  citation_gate.py          hard citation-verification gate -- the drafting layer must pass this
  dossier/                  the working state behind a draft (reader, scope, kept evidence, rejected
                          candidates, steering, revision log) as Markdown under content/dossiers/,
                          mirroring the draft's path; plus tar.gz backup/restore. Read-only over the
                          corpus layer, never a gate -- see docs/DRAFT-ITERATION.md
  reference_entries.py      citekey -> formatted IEEE entry from the ledger, and the refusal of a key it lacks;
                          shared by references.py, evidence_appendix.py and discover
  references.py             auto-generates a draft's "## References" section from its own cited citekeys,
                          as numbered IEEE entries ordered by first appearance -- the same order (and
                          so the same numbers) pandoc's citeproc assigns when the draft is rendered
  render_output/            Pandoc/TeX Live rendering + standalone CLI -- stdlib-only, no enrich group
                          needed, which is why it sits here and not in chitragupta/enrich/. `--format md` on a
                          Markdown draft skips pandoc entirely and emits references.numbered_markdown's
                          plain numbered copy instead
chitragupta/review/                the review layer -- one command, `python -m chitragupta.review <aid>`, eleven aids
  __init__.py               the layer's shared output contract -- report path (content/review/,
                          mirroring the draft), the "not a gate" banner, the header, and the
                          write-md-then-render routine all eleven aids use. No timestamp, so a
                          report diffs across revisions
  __main__.py               the layer's single entry point: one parser, eleven subcommands, each
                          wired to its aid's own build_parser()/run(). The aids below carry no
                          __main__ block of their own -- see docs/ARCHITECTURE.md on why a layer's
                          command surface stays one level deep
  citation_coverage.py      `coverage` -- retrieval-candidates-vs-actually-cited report, not a gate
  citation_provenance.py    `provenance` -- what in each cited source supports the claim citing it,
                          not a gate (scores claims against passages.py's ladder; see
                          docs/CITATION-PROVENANCE.md)
  synthesis.py              `synthesis` -- how many sources each unit of the draft rests on, at the
                          unit its genre binds at (docs/WRITING-STANDARDS.md §11), not a gate
  uncited_prose.py          `uncited` -- which sentences carry no citation at all, the prose-side
                          question `coverage` does not answer. The one aid that reads no corpus
  verbatim_check/           `verbatim` -- per-citekey overlap, whole-draft x whole-corpus scan, and
                          page-locating checks against sources
  figure_layout/            `figure` -- a TikZ figure's own pre-flight defects (occlusion, chaotic
                          routing, illegible type, ...), not a gate -- see docs/TIKZ-STYLE.md
  _blocks.py                what a *block* is -- a table row, a list item, a heading -- in both
                          markups. Shared by provenance and uncited_prose; neither owns it
  _emit.py                  how an aid prints and files its report under --json/--write, shared by every aid
  _registry.py              which module runs each aid -- the one name->module map, keyed by review.AIDS
  _claims.py                which sentences of a draft carry a claim, and which are scaffolding.
                          Split from uncited_prose so the roadmap's C2 can share it
  _units.py                 what a "unit" is per genre, and how each genre treats uncited prose --
                          the two per-genre policy tables, pinned against dossier.GENRES
  _synthesis_render.py      how a synthesis report reads; _uncited_render.py is the same for uncited
chitragupta/enrich/                the enrichment layer (pyproject.toml's "enrich" Poetry group), optional
  __main__.py               the layer's entry point, `python -m chitragupta.enrich --stages …`; orchestrates
                          the stages below, which carry no __main__ block of their own
  corpus.py                 the enrichment layer's view of the ledger -- one CorpusDoc per bib item,
                          so every enriched document is citable, keyed by its citekey
  docling_parse.py, embed_index.py, topic_model.py, topic_seeding.py, topic_converge.py
scripts/                   dev tooling only -- no layer entry point lives here
  install_full_pipeline.sh  single staged install path for host, Docker and CI: os-deps, python-deps,
                          dev-deps, all, plus the opt-in cpu-torch, gpu-torch, vale, actionlint, stix-two
  relock.py                 regenerates poetry.lock through uv's resolver (docs/UV-MIGRATION.md)
  release.py                 bundles a distributable release/chitragupta-<version>.zip, dev files excluded
tests/                    pytest suite -- unit tests per module + end-to-end feature tests (see "Running tests")
content/                  generated, gitignored (regenerate with sync)
  ledger.sqlite, parsed/<citekey>.txt, drafts/, dossiers/, rendered/, review/,
  retrieval_index.json, overlap/,
  docling/, chroma/, topics.json, topic_seeds.json, topic_set.json,
  topic_embed_cache.json  (chitragupta/enrich/ outputs)
logs/                     gitignored -- pipeline.log, rotated at 5MB x 5 backups. Level from
                          config.toml's [logging]; relocate with the LOGS_DIR env var
.claude/skills/           drafting layer: six that write a draft (survey-writer,
                          thesis-chapter-writer, textbook-chapter-writer, tutorial-writer,
                          deep-research, review-digest), three that revise one that already exists
                          (draft-reviser, corpus-reviser, agenda-reviser), one that
                          assembles accepted units into a book (book-assembler), and one
                          that draws a figure for the others (figure-drawer). Each has a
                          SKILL.md and, where it needs one, a references/ folder read on
                          demand. Plus demo-recorder, which records the feature demo:
                          developer-only, so no distribution ships it (docs/HARNESS.md)
.claude/skills-common/    references/ shared by several skills (critique, prose check,
                          verbatim scan, collection scoping), kept once for all harnesses
.claude/agents/           deep-research's subagents: deep-research-interviewer, deep-research-writer, peer-reviewer
.claude/hooks/            citation_gate_hook.py and style_check_hook.py -- PostToolUse hooks,
                          mechanically enforcing the citation gate and the prose style check on
                          every Write/Edit under content/drafts/*.md and *.tex (see AGENTS.md);
                          code_standards_hook.py reports C1/C2 on a .py write in a checkout;
                          session_start_hook.py checks the project can draft at all; draft_target.py
                          is the shared "which file did this tool call touch" helper both PostToolUse
                          hooks use; safe_path.py decides whether their children may import
                          chitragupta from the project root (checkout) or not (installed project);
                          patch_paths.py reads the drafts an apply_patch payload touches (Codex, OpenCode)
.claude/settings.json     wires the four hooks above into PostToolUse/SessionStart
.agents/skills/           Codex's copy of each skill's SKILL.md (references stay in .claude/);
                          .codex/hooks.json runs the same hooks on apply_patch
.opencode/                OpenCode's copy of each SKILL.md (-opencode suffix), its gate plugin, and
                          opencode.json's deny list for the unsuffixed names (docs/HARNESS.md)
docker/                   Dockerfile (TeX Live/Pandoc/Poetry), Dockerfile.claude + docker-compose.yml +
                          entrypoint.sh + rc-daemon.sh/.env + .env.example (the Claude Code agent container, cpu/gpu profiles)
                          -- CI builds docker/Dockerfile (cpu variant) but never runs it, and does not
                          build Dockerfile.claude; see DOCKER-DEVELOPER.md
```

## 📐 Figures and copyright

A source paper's figures are a reading aid, never draft content.
[AGENTS.md](AGENTS.md) states the rule and the one exception (the
verbatim digest); `python -m chitragupta.draft figures <citekey>` is the
supported way to look at them. Code here must not insert a source
image into `content/drafts/`.

## 📖 Citation provenance

`python -m chitragupta.review provenance content/drafts/<slug>.md` reports, for
every citation in a draft, what in the cited source supports it and
where, ordered worst match first. It writes
`content/review/<the draft's path minus its suffix>.provenance.md` plus
`.tex`/`.pdf` renders beside it. The report mirrors the draft's own place
under `content/drafts/`, the same rule `rendered/` and `dossiers/` follow
(`config.mirrored_dir`), and `chitragupta/review/__init__.py` owns that
contract for every review-layer command.

Run it directly rather than wrapping it in an enrichment stage: that
would have the enrichment layer importing the review layer, and would
make an advisory report wait on `sync`'s write lock.

**Advisory, not a gate**, deliberately: matching is lexical, so it
cannot tell "the source doesn't say this" from "the source says it in
words I didn't recognise". `citation_gate` blocks because it checks
something exact (ledger membership); this reports because it doesn't.

Passage quality depends on what has been parsed. With the Docling stage
run, `content/docling/<citekey>.passages.json` supplies reading-ordered
paragraphs and the report quotes them. Without it, `pdftotext` output is
used and the report gives a page number **without quoting**: on a
two-column paper that text splices two columns onto every line, so any
excerpt would be a collage of two arguments.

Full design rationale, including the measurements behind those choices:
[docs/CITATION-PROVENANCE.md](docs/CITATION-PROVENANCE.md).

## ❓ Open questions and unbuilt features

Running this pipeline on a schedule is supported: a rotating
`logs/pipeline.log`, shared by the
corpus and enrichment layers (see `chitragupta/logging_setup.py`), a pages/s
throughput figure, exit codes an unattended caller can branch
on, and worked cron and systemd units in
[docs/CLI.md](docs/CLI.md#-running-sync-on-a-schedule), including the
absolute-interpreter-path detail that cron's minimal environment
requires.

One blocker is left, and it is not a coding task. With no continuous
auto-export, `bibliography.bib` is a manual, point-in-time snapshot: a
scheduled `sync` re-reads whatever was last exported, so it keeps the
corpus consistent with the bib file but cannot keep the bib file
consistent with your reference manager. A schedule watching only its
mtime does nothing until a human re-exports. Closing that properly means
either a Zotero auto-export plugin (outside this repo) or accepting that
the export stays a deliberate human step.

### 🚫 `content/topics.json` has no drafting consumer

`chitragupta/enrich/topic_model.py` writes it. Only `corpus discover`
(`chitragupta/discover/_data.py`, for its c-TF-IDF terms) and sync's residue
report read it; no genre skill does. `survey-writer` groups themes by
judgement and says so explicitly ("With a small corpus there's no BERTopic
step"). That is defensible today: clustering is whole-corpus, so assignments
are not stable between runs, and on a small corpus every document legitimately
lands in the outlier topic. If it is ever wired in, `survey-writer`'s "Cluster
by judgment" step is the seam, gated on the file existing and on there being
non-`-1` assignments, the same shape the existing skills use to gate on
`content/chroma/`.
