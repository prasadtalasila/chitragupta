# 🤖 DEVELOPER-AGENTS.md

The contract for coding agents (and anyone else) **working on this
repository itself**, as opposed to using it to draft content. The
drafting half is [AGENTS.md](AGENTS.md); the why behind both is
[SOUL.md](SOUL.md).

[AGENTS.md](AGENTS.md)'s citekey invariant binds code here too: no module
may generate, guess or rewrite a citekey, and no new check may be promoted
into a gate beside `chitragupta/citation_gate.py`. That includes test
fixtures, doc examples and the committed sample project, because a
fabricated citekey in an example teaches the fabrication this project
exists to prevent.

**Where to look for what**, since this file is long and a session rarely
needs all of it:

- Every change: [Role](#-role), [Behavioural
  rules](#-behavioural-rules-think-before-coding),
  [Code standards](#-code-standards), and the
  [full shipping cycle](#-shipping-a-code-change-the-full-cycle), which
  is the checklist the rest of the file explains.
- Before writing code: [Module boundaries](#-module-boundaries),
  [Environment constraints](#-environment-constraints-on-this-host), and,
  for anything under `chitragupta/enrich/`,
  [the enrichment layer](#-the-enrichment-layer-chitraguptaenrich-chitraguptaenrich__main__py)
  and [the stage conventions](#-conventions-a-new-stage-has-to-follow).
- Before claiming done: [the local
  checks](#-before-claiming-a-task-complete-run-all-local-checks),
  [the linters](#-the-linters-which-are-enforced), and
  [the OpenCodeReview step](#-reviewing-before-you-push-the-opencodereview-plugin).
- Landing it: [Commit messages](#-commit-messages),
  [Merging](#-merging), [Issues and pull
  requests](#-issues-and-pull-requests), and
  [Versioning and releases](#-versioning-and-releases).

## 🎭 Role

This assistant manages most of the day-to-day development here: implementing
features, writing tests first, running the full local check suite, opening
PRs, watching CI, merging, and cutting releases. Proceed autonomously through
that whole cycle for a routine code change rather than pausing to check in at
each step. Reserve pausing for decisions that are genuinely irreversible
(force-pushes, history rewrites, deleting something not obviously
regenerable) or genuinely ambiguous (a requirement with more than one
reasonable reading and no clear tie-breaker in this file or the code).

## 🤔 Behavioural rules: think before coding

Four rules about *how to work*, as opposed to what the code should look
like ([docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md)). They prioritise
caution over speed; for a genuinely trivial change, use judgement.

1. **Think before coding.** State assumptions rather than making silent
   choices. Where a requirement has more than one reasonable reading,
   present the alternatives instead of picking one silently. This is the
   "genuinely ambiguous" case under "Role" above, and it is the one time
   pausing beats proceeding.
2. **Simplicity first.** Write the minimum that solves the stated
   problem. No speculative abstraction for a single call site, no
   unrequested `config.toml` key, no defensive handling for a state that
   cannot occur. Ask whether a reviewer would call it over-engineered; if
   yes, cut it. Note the one deliberate exception: the *comments* are not
   subject to this; see
   [docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md#-the-comment-rules-and-the-misreading-to-avoid).
3. **Surgical changes.** Each changed line should trace to the requested
   task. Do not refactor unrelated code, and match the local style of
   whatever you are editing. Remove imports and helpers *your* change
   orphaned; report pre-existing dead code rather than deleting it in the
   same diff. A module already on the size register is a thing to mention
   in the PR, not a licence to rewrite it while passing through. This is
   where the Boy Scout Rule lands here: cleanup happens, in its own PR
   and against the register, rather than inside an unrelated diff
   ([why](docs/CODE-STANDARDS.md#-the-boy-scout-rule-and-surgical-changes)).
4. **Goal-driven execution.** Turn the task into a verifiable goal before
   starting: "fix the bug" becomes "write a test that reproduces it, then
   make it pass", which is the test-driven rule below, arrived at from
   the other direction. For a multi-step change, state the plan as steps
   with the check that verifies each.

## 📏 Code standards

[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) is the standard the code
itself is held to: the code counterpart of `docs/WRITING-STANDARDS.md`.
Read it before a non-trivial change. In brief:

- **Workflows are linted at the commit.** `bash
  scripts/install_full_pipeline.sh dev-deps` installs `actionlint` and
  points `core.hooksPath` at `git-hooks/`, so a commit touching
  `.github/workflows/` is checked before it lands rather than in CI ten
  minutes later. `ci.yml`'s lint job runs the same check, so the hook
  changes when you find out, not whether. `git commit --no-verify`
  bypasses it.
- **Two rules are machine-checked**, by `tests/test_code_standards_scan.py`
  as part of the ordinary `pytest` run: at most **25 statements** per
  function, at most **250 code lines** per module. Both are **ratchets**:
  today's offenders are frozen in a register that may only shrink, so a
  new offender fails and a fixed one must be delisted.
- **The same two rules bind `assets/webapp/`**, checked separately by
  `tests/webapp/code_standards.test.js` under `node --test` rather than
  `pytest` (JS has no `ast`). Offenders live in the same
  `code-standards-register.toml`, in its `c1js`/`c2js` tables, and it is
  the same ratchet: a new offender fails, a fixed one must be delisted.
  See [docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md#-the-binary-rules)
  for the two ways the JS scan's counting deliberately differs from the
  Python one.
- **Statements, not physical lines**, because this repository *requires*
  rationale comments and a physical-line limit would reward deleting them.
- **Cognitive complexity is capped at 25, not SonarQube's default 15**,
  aligned with the 25-statement rule for the same anti-over-splitting
  reason. Do not split a function merely to satisfy an S3776 finding of
  25 or below; mark it *Accepted* in SonarCloud instead
  ([why](docs/CODE-STANDARDS.md#-cognitive-complexity-the-bar-is-25-not-sonarqubes-default-15)).
- Everything else in that document (naming, one-thing-per-function, the
  code-smell vocabulary) is a review standard and deliberately has no
  detector. A quality score is not a thing to drive to zero;
  [docs/AUTO-IMPROVEMENT.md](docs/AUTO-IMPROVEMENT.md)'s R3 is the rule,
  and it applies to code as written.
- It is written against the clean-code checklist rather than invented
  here, and maps every rule in it to enforced / already-here /
  review / not-applicable. [docs/INSPIRATION.md](docs/INSPIRATION.md) has
  the provenance.

**Measure the headroom before you choose the fix's shape, not after.**
The 250-line ceiling is a ratchet, so a module already at 244, 248, 249
or 250 code lines constrains what may be added to it, and all four of
those were hit in one release run. Writing the obvious fix first and
discovering it lands at 267 costs the fix twice: once written, once
rewritten. Two consequences are worth knowing before you start:

- **A split the fix *forces* belongs in the same PR; a split you
  *chose* does not.** This is not an exception to the surgical-changes
  rule but its other half: the changed lines still trace to the task,
  because without them the task cannot land. Split at a boundary the
  module already had (a section comment, a docstring that names two
  jobs), say in the PR body which of the two kinds it was, and delist
  the module if the split takes it off the register.
- **Rationale can move from a docstring into a `#` comment**, since
  docstrings count toward the ceiling and comments do not. That is the
  standard's own sanction rather than a loophole, and the same move
  four times in one run is a pattern to state once in a PR body, not a
  thing to re-argue per commit.

## 🧩 Module boundaries

`chitragupta/references.py` formats an IEEE bibliography entry (authors, venue,
volume, pages) from the ledger's `bib_fields` column, which `sync`
populates via `bib_reader`. It does not, and must not, parse
`bibliography.bib` itself. The one thing that legitimately reads the bib
file directly is pandoc's `--citeproc`, which is not this codebase. See
[AGENTS.md](AGENTS.md) for why `bib_reader` is the sole reader.

What a part *does* and what it *costs to install* are separate axes:
`chitragupta/render_output/` is drafting-layer code that needs no package from
the `enrich` group, which is why it sits in `chitragupta/` rather than
`chitragupta/enrich/`. `chitragupta/review/verbatim_check/` is the same
axis read the other way: it sits beside the two aids it belongs with, not in
`scripts/`, which holds dev tooling and no layer entry point at all.

## 📂 The committed sample project is pipeline output, not prose

`docs/examples/sample-project/` is the worked example the user documentation
quotes: five synthetic sample papers and every artefact the pipeline
derives from them (drafts, dossiers, review reports, renders, a signed
spec, the topic artefacts). Two rules follow from what it is:

- **Regenerate, never hand-edit.** Every committed artefact there was
  produced by actually running the pipeline (`docs/examples/README.md` has
  the map; `docs/examples/sample-project/regenerate.sh` rebuilds the
  uncommitted substrate). A change that alters an artefact's format
  (the dossier grammar, a review report's shape, the topic graph's
  schema) makes the committed samples stale, and the fix is to re-run the
  affected command in that directory and commit its real output.
  Hand-editing a sample to match a format change produces exactly the
  fabricated-example problem the directory exists to avoid, and the
  documentation snippets quoting the artefact must move in the same PR
  (the docs sweep in
  [the shipping cycle](#-shipping-a-code-change-the-full-cycle)'s step 4
  covers those).
- **The citekey invariant holds even here.** The sample citekeys
  (`sample_*`) exist in `docs/examples/sample-project/papers/bibliography.bib`
  and were synced from real (if synthetic) PDFs; a new sample citation
  goes through the same bib-export-then-sync path, never a typed-in key.

Living under `docs/`, the sample project is part of the mkdocs site and
of what `chitragupta init` scaffolds, deliberately: documentation links
to its artefacts (small snippets are quoted inline; anything larger is a
hyperlink), and a fresh project gets the worked example as a safe
playground. The one carve-out is markdownlint; see the negated glob in
["The linters, which are enforced"](#-the-linters-which-are-enforced):
pipeline output is not lint-shaped and may not be hand-edited to become
so.

The harness examples beside it, `docs/examples/codex/` and
`docs/examples/opencode/`, follow the same two rules, with one
difference: their `content/` is what one harness and one local model
did, so it is replaced only by re-running that example's `run.sh`. It
is never edited, and never "corrected" where the model left the
skill's path, because recording what the model did is why the example
exists ([LOCAL-MODELS.md](docs/LOCAL-MODELS.md)).

## 🖥 Environment constraints on this host

`pip install` outside a venv is blocked (PEP 668), unconditionally, on
every host, regardless of root access. **This matters for the corpus
layer too**: `python -m chitragupta.corpus sync` needs `bibtexparser`
(parsing `bibliography.bib` correctly, with nested braces and LaTeX
escapes, isn't worth hand-rolling), so it must be run via the installed venv,
not the bare system interpreter. `python -m chitragupta.draft gate` is the
exception (see [AGENTS.md](AGENTS.md)).

**Probe for a toolchain; never assume one, in either direction.**
Whether a host has root, TeX Live or Pandoc is one machine's fact, not a
project rule, and writing it down as one goes stale. The durable rule is
the probe:

- **When the enrichment layer's dependencies are present:** stages that need them
  (Docling parsing; Pandoc/TeX Live rendering) work directly on the host,
  not only inside `docker/`; there is nothing docker-exclusive about
  any of them.
- **When they're absent:** don't hang, stack-trace, or silently skip
  without saying so. Every `chitragupta/enrich/*` stage already self-probes its
  own prerequisites and reports honestly (`ok`/`partial`/`skipped`/`error`)
  via `chitragupta/enrich/__main__.py` rather than assuming the target
  implies availability. Keep any new stage consistent with that pattern
  instead of inventing a new fallback policy.

Install everything with:

```bash
bash scripts/install_full_pipeline.sh              # Python deps only (default) -- what every host needs regardless of OS packages
bash scripts/install_full_pipeline.sh os-deps      # apt-get: TeX Live, Pandoc, poppler-utils, OpenCV runtime, Poetry, zip/unzip -- needs root, opt-in
bash scripts/install_full_pipeline.sh dev-deps     # pytest/pytest-cov, to run the test suite -- opt-in
bash scripts/install_full_pipeline.sh all          # os-deps + python-deps
bash scripts/install_full_pipeline.sh cpu-torch    # swap torch to the cpu-only wheel index -- opt-in
bash scripts/install_full_pipeline.sh gpu-torch    # match torch to this host's GPU driver (needs CHITRAGUPTA_PYTHON) -- opt-in
bash scripts/install_full_pipeline.sh vale         # the Vale prose linter alone -- opt-in
bash scripts/install_full_pipeline.sh actionlint   # the workflow linter alone -- opt-in
bash scripts/install_full_pipeline.sh stix-two     # the STIX Two font alone -- opt-in
```

This is **the single install script for both the host and Docker and CI**:
`docker/Dockerfile` calls it once per stage as separate `RUN` lines, and
`.github/workflows/ci.yml` calls it directly too, rather than any of them
having their own separate apt-get/pip/poetry install logic. Python
dependencies are managed by Poetry as a lockfile/venv manager for a
checkout, Docker and CI ([docs/PACKAGING.md](docs/PACKAGING.md) records
the decision to also make this a published, pip-installable package, and
what had to land first). If you find a dependency-order issue, fix it
once in `pyproject.toml` (+ `poetry lock` to update `poetry.lock`, or
`python3 scripts/relock.py` to regenerate it from nothing; see
[docs/UV-MIGRATION.md](docs/UV-MIGRATION.md)) and every target picks it
up. Don't add a second install path.

Read that last sentence as the invariant it protects, not as the
mechanism: the goal is **one place a dependency fact can be written**, so
a fix lands once and every target picks it up. The single script is the
mechanism for a checkout, Docker and CI; **there are two front
doors** onto it: `install_full_pipeline.sh` for those three, and
`chitragupta install os-deps|gpu-torch` for someone who pip-installed,
reaching the *same script's* `os-deps` stage and the *same*
`ensure_gpu_torch` function rather than a reimplementation of either.
`chitragupta install python-deps|dev-deps|all` refuse by name instead,
each naming the `pip install 'chitragupta-cli[...]'` extra that already
replaces it (below). Accepting them would run something with a
different meaning than the argument implies, which is worse than
refusing. Two front doors, one source of truth, still no second place to
write a version down.

**Extras mirror the three optional Poetry groups below**, so `pip
install 'chitragupta-cli[enrich]'` resolves the same versions `poetry
install --with enrich` does. The two declarations are unrelated Poetry
mechanisms that happen to need the same facts. A group dependency never
reaches a built wheel's metadata, so an extra needs its own, duplicate
entry under `[tool.poetry.dependencies]` (`optional = true`), and
`tests/test_pyproject_extras.py` is what keeps the two from drifting
apart silently. The one thing pip cannot do that `poetry install
--with enrich` does is match torch to this host's GPU driver
(`ensure_gpu_torch`, above): `pip install 'chitragupta-cli[enrich]'` on
a CUDA host still lands a CPU-only wheel, silently, exactly as a bare
`pip install torch` would. `chitragupta doctor` detects that mismatch and
names `chitragupta install gpu-torch` as the fix; nothing makes it
automatic, because pip has no post-install hook this project would be
willing to use.

`cpu-torch` is deliberately **not** part of `all`, and is not something
the script infers. It asserts that a GPU is absent *for good*: true of
a hosted CI runner and of a cpu-only container image, not true of a
laptop that might be a workstation next month. `ensure_gpu_torch` is the
probe; this is the assertion, and only a caller knows which it is
entitled to make. It is worth about 4GB: `docker/Dockerfile` measures a
6.2GB GPU-capable venv against 2.0GB cpu-only. `docker/Dockerfile`'s
`TORCH_VARIANT=cpu` and CI's Linux leg both call this one stage rather
than carrying their own copy of the swap.

`docker/` (Dockerfile) builds the same TeX Live/Pandoc stack inside a
container instead, for hosts where the
`os-deps` assumption above doesn't hold (no root, or root deliberately
withheld). CI builds its `cpu` variant on every push and PR but never
runs it; [DOCKER-DEVELOPER.md](DOCKER-DEVELOPER.md) has what is verified
by hand.

**Install this checkout editable, or not at all.** `.claude/hooks/`'s
launchers decide which `chitragupta` a hook's child imports by where the
package resolves *without* the working tree on `sys.path`
(`.claude/hooks/safe_path.py`, docs/HOOKS.md). A checkout whose venv also
carries a non-editable `chitragupta-cli` (`pip install chitragupta-cli`
run inside this same checkout's venv, instead of `poetry install` or
`pip install -e .`) reads exactly like an installed project to that
check, so its hooks run the installed copy rather than the working tree,
and a change here silently stops being what the citation gate enforces.
`scripts/install_full_pipeline.sh` (above) and `poetry install` give you
the editable shape; running `pip install chitragupta-cli` into the same
venv afterwards is the mistake this warns against, not a supported
combination to debug around.

## 🧠 The enrichment layer (`chitragupta/enrich/`, `chitragupta/enrich/__main__.py`)

The layer implements seven stages (Docling -> sentence-transformers/Chroma
-> BERTopic -> declared keywords -> seeded topics -> converged topic set
-> topic graph) in one script for both host and Docker. Each stage
self-probes its own prerequisites (docling importable, an upstream
artefact present) and reports honestly
(`ok`/`partial`/`skipped`/`error`) rather than assuming the target
implies availability. Don't "fix" a skip by hardcoding target-specific
behavior; fix the probe if it's wrong. Which of the four
words changes the run's exit code is
[docs/LADDERS.md](docs/LADDERS.md)'s to state, not this file's.
`--target host|docker` is **informational only** for exactly that reason:
the probes decide, not the flag, so nothing branches on it.

`chitragupta/enrich/embed_index.py`, `chitragupta/enrich/topic_model.py`, and
`chitragupta/enrich/docling_parse.py` are all incremental, mirroring
`chitragupta/ledger.py`'s own skip-what-hasn't-changed logic for the corpus
layer: a doc whose text hasn't changed since the last run isn't
re-embedded, and a PDF whose `(size, mtime_ns)` hasn't changed since the
last run (`config.DOCLING_CACHE_PATH`) isn't re-parsed by Docling.

That per-document incrementality is what `--for-draft` rests on, so
don't trade it away. The flag narrows the corpus to the citekeys one
draft cites, and the reason a narrow run and a full run can be mixed in
either order without repeating work is that the caches are keyed by
document and merged, never rewritten to match the run's own view of the
corpus. `embed`, `bertopic` and the three topic stages after them are
refused rather than scoped, because each writes one whole-corpus
artefact with no partial form; allowing any of them needs the Chroma
collection to record its own coverage first.
[docs/LADDERS.md](docs/LADDERS.md#-scoping-a-run-to-one-draft) owns that
reasoning; keep it there rather than restating it.

No stage in this pipeline calls out to an LLM or needs an API key:
Docling, embeddings/Chroma, BERTopic, and the Pandoc/LaTeX render
step are all local/deterministic. Any LLM-backed synthesis happens only
via the `.claude/skills/` drafting layer, invoked through a Claude Code
session rather than a standalone API call.

`chitragupta/enrich/corpus.py` sources the enrichment corpus from the ledger and
nothing else, so every document it yields is citable and keyed by its
citekey alone. Keep it that way: the enrichment layer must never index a
document a draft would not be allowed to cite. If a paper is
worth enriching, it belongs in the reference manager: catalogue it,
re-export, and re-run `python -m chitragupta.corpus sync`.

## 🤝 Conventions a new stage has to follow

There are three, each one the fix for a failure that is easy to repeat:

- **Anything holding the write lock reports per document.** DESIGN.md's
  concurrency policy requires a serial section to be observably making
  progress, and an unreported one is indistinguishable from a hang: a
  correct run gets read as stuck and killed. `sync`, `docling_parse`
  and `embed_index` all emit
  `[done/total] <citekey>`, opened *before* the slow call so the reader
  sees the document currently under way rather than the last one that
  finished. Where it goes differs, and the split is deliberate.
  `sync`'s stdout is a documented contract (bibliography order,
  diffable between runs, pinned by tests), so its progress and warnings
  go through `logging` to `logs/pipeline.log` instead. The
  enrichment stages keep their stdout and *mirror* it into the same file
  via `logging_setup.say()`, which prints and logs one line with
  `extra={"file_only": True}` so the console handler doesn't echo it.
  Two kinds of message stay bare `print`s and must not be converted:
  anything built across several writes (`print(..., end="")`,
  where a log record's one-line-per-entry shape would withhold the
  citekey until the work finished) and anything running in a worker
  process or a signal handler. Flush anything printed: stdout is
  block-buffered when it isn't a terminal, and the tail of an
  interrupted run is the part worth keeping.
- **Classify a failure by cause on the exception, not by matching its
  message.** `pdf_text/` sets `transient` and `timed_out` marks that
  survive the pool's pickling; `sync` reports each cause separately
  because they want opposite fixes (raise the timeout and `--reparse`
  versus fix or remove the PDF). Adding a cause means adding a mark, not
  a string match.
- **Report a partial result as a failure.** Docling's `PARTIAL_SUCCESS`
  returns a document that stops early; writing it would hand the citation
  gate a source that silently ends at page k of n. Check the status and
  raise *before* anything is written, so nothing enters the incremental
  cache.

## 🧪 Development process: agile, test-driven

Work in small, independently-shippable increments. Prefer several small,
reviewable PRs over one large one, and prefer a working, tested slice of a
feature over a complete-but-untested one. Within each increment, follow
test-driven development:

1. Write a failing test that captures the behavior being added or the bug
   being fixed, and confirm it fails (a test that passes before
   the fix exists isn't testing anything).
2. Write the minimum implementation that makes it pass.
3. Refactor with the test suite green, if the result needs cleaning up.

This applies to bug fixes as much as features: "fix the bug" becomes
"write a test that reproduces it, then make it pass". Don't fix
something you can't first demonstrate is broken. Exception: exploratory
spikes to understand a problem before committing to an approach don't
need up-front tests, but the resulting real change does.

**A reported prescription is a hypothesis, not a specification.** An
issue, a review comment or a code report usually names both a symptom
and the fix it thinks closes it, and the two are checked separately: the
failing test reproduces the *symptom*, and only then does the prescribed
fix get to prove it turns that test green. A prescribed fix can fail to
close its own symptom (accepting a citekey "exactly equal to a known
ledger citekey" cannot close a report about citekeys that have *left*
the ledger), and only the test shows that; re-reading the issue does
not.

**A guard is tested against the exact shape it was blind to.** For a
check that reports "clean" the failure is silent, so a test asserting it
passes on good input proves nothing. Feed it the real pre-fix artefact
(the actual `docs.yml` block, the actual malformed row) and confirm the
test is red before the fix, or the guard's whole value is untested.

### 🧷 Finish the checkout, then baseline the suite

**A `git worktree` is a fresh checkout, and needs the same one-line
setup a fresh clone does:**

```bash
cp config.toml.example config.toml   # gitignored per-host data; a
                                     # checkout of any kind never has it
```

`config.toml` is deliberately not in git, and `chitragupta/config.py`
refuses to import without it rather than falling back silently, so its
absence fails tests that have nothing to do with configuration:
`.claude/hooks/`'s launchers, the CSL resolver, the citation-gate hook.
`.github/workflows/ci.yml` runs exactly this `cp` in both the `test` and
the `lint` job for that reason, and the session-start hook tells a new
clone to. A worktree needs it just the same.

**A finished checkout on a complete toolchain has no known failures at
all.** That is the number worth having, because it makes any red yours.
Without `config.toml`, tests fail across the suite; without `os-deps`,
the tests that shell out to `pdftotext`, `pandoc` or `lualatex` fail or
self-skip. With both, the only skips are the cases that want a
`papers/bibliography.bib` (gitignored per-host data, absent on any fresh
checkout and in CI) and one that only has something to skip off Linux.

**So baseline, and expect zero.** Write the counts down before touching
anything, then answer "did I break something?" by diffing pass and fail
counts against that record, and by name where they moved. What a
baseline is *for* on a complete host is the residue you cannot remove:
an already-released version moves the count, and a partial toolchain
turns real coverage into a self-skip, which is why such a host wants
`--cov-fail-under=0` (see the coverage note below). It is not a licence
to carry red that the two setup commands above would have removed. The
same holds for a lint finding your commit did not make true: name it in
the PR rather than fixing it here (the surgical-changes rule above, and
step 4 of the shipping cycle).

Run it from the venv whose pin matches `pyproject.toml`: the
`.venv-full/bin/python` the command below already names. A second venv
built against a different pin will disagree with CI in both directions,
which makes its red *and* its green worthless as evidence.

### 🗺 Recording a plan before you build

[docs/FEATURE-ROADMAP.md](docs/FEATURE-ROADMAP.md) holds what would be
built and in what order. For an item whose design is underdetermined,
write the plan down in `plans/` **before** the first
test, and link it from the PR.

Most items do not need one: a roadmap entry already carries the files
touched, the size and the dependencies, and for a mechanical change that
is the whole plan. [plans/README.md](plans/README.md) has the three
tests for when a plan earns its place, the shape to follow, and the rule
that a merged plan records which PR closed it.

`plans/` does not ship: it is in `scripts/release.py`'s
`EXCLUDE_TOP_LEVEL`, like `tests/` and `bench/`. It is linted, though;
the markdownlint globs above include it.

## ✅ Before claiming a task complete: run all local checks

Never report a task as done on the strength of a plan or a code read alone.
Before saying so, run, in this repo:

- The full test suite with coverage: `.venv-full/bin/python -m pytest
  -n auto --cov --cov-report=term-missing`. `-n auto` (pytest-xdist,
  in the dev group) spreads it over every core: 15 minutes serial
  became 5 on a 32-core host. Bare `--cov` deliberately: what is
  measured is declared once, by `[tool.coverage.run].source` in
  `pyproject.toml`, so a path added there cannot be missed by a command
  line that still names the old two. This repo maintains
  100% line and branch coverage; a change that drops it needs a test
  added, not a lowered bar. `fail_under = 100` in `pyproject.toml`'s
  `[tool.coverage.report]` enforces that rather than leaving it asserted,
  so the run exits non-zero on a drop. It assumes the full toolchain:
  without pandoc/TeX Live/poppler the render tests self-skip and the
  total falls short for a missing binary rather than a missing test, so
  pass `--cov-fail-under=0` on such a host. CI exempts neither leg, and
  both legs hold 100. The Windows leg installs no `os-deps`, so its
  render and pdf tests self-skip; rather than budget for that under a
  lower number, it reads `coveragerc-windows.toml`, which excludes
  exactly the lines that leg cannot reach (`pragma: no cover-windows`),
  so a self-skipped render test and Windows code nothing reaches stay
  distinguishable. `tests/test_coverage_configs_agree.py` pins
  the two configs to one floor, and this sentence to it.

  **This local run is the only one that compiles TeX.** CI's Linux leg
  runs `-m "not slow"`, leaving out every test marked
  `@pytest.mark.slow` (a real `lualatex`/`pdflatex` compile, 85% of the
  suite's time), and reads `coveragerc-windows.toml` as well, since the
  lines only those tests reach are the ones Windows cannot reach either.
  So a green CI says nothing about the figure checks or the PDF render;
  your local run does. Mark a new test `slow` only if it compiles: a
  mark that leaves any other line uncovered fails CI's coverage step.
- **CI's whole `lint` job, in one command**, with your dev venv active
  so `python`, `pylint` and `ruff` resolve to the pinned ones:

  ```bash
  bash scripts/check_local.sh
  ```

  It runs every step of `ci.yml`'s `lint` job in CI's order and stops
  at the first failure: the version-bump check (off `main` only, as in
  CI), pylint, `ruff check`, `ruff format --check`, shellcheck,
  actionlint, markdownlint, `npm ci` and the webapp and OpenCode node
  tests, and the Vale exemptions check. CI's install steps become
  checks that the tool is installed, with a warning when a pip or npm
  tool's version is not CI's pin (actionlint and Vale are pinned inside
  `install_full_pipeline.sh` instead). `npm ci` is the exception and
  runs as in CI: it writes only this checkout's `node_modules/`.
  `tests/test_check_local.py` reads both files and fails
  when they part, so a step added to the job reaches the script in the
  same change. None of it is optional or CI's job alone:
  `markdownlint` in particular fails on prose that no test touches, so
  a green suite says nothing about it. "The linters, which are
  enforced" below explains the four linters' roots.

- **The webapp's own tests**, which the script above already runs; to
  run them alone after touching `assets/webapp/`:

  ```bash
  npm ci --ignore-scripts   # once per checkout: acorn, behind the C1/C2 scan below
  node --test tests/webapp/*.test.js
  ```

  Without `npm ci` the C1/C2 scan's tests skip, with that command as
  the reason, rather than fail, so a missing install cannot be
  mistaken for a ratchet breach. On CI they fail, since the install
  step ran there.

  `pytest` reaches none of that directory, which is JavaScript, so it
  holds its own coverage bar, at the same 100% of lines. CI's form of
  the command, which `check_local.sh` runs too and which needs node
  22.8 or later:

  ```bash
  node --test --experimental-test-coverage --test-coverage-include="assets/webapp/*.js" --test-coverage-lines=100 tests/webapp/*.test.js
  ```

  Node's report lists only files a test loaded, so
  `tests/webapp/browser_load.test.js` loads every script `index.html`
  names except the DOM wiring, the way the page does; a new module is
  in the report, and held to the bar, from the commit that adds it to
  the page. `tests/test_discover_app.py` can only pin source-level
  tripwires over the shipped text.
  Every module in that directory except `search.js`, `pickers.js`,
  `canvas.js`, `sidepanel.js` and `app.js` is written to run without a
  DOM and without cytoscape so that this command can exercise the real
  functions; those five are the DOM wiring left over, split out of
  `app.js` so each piece stays under the C2 limit, and the only five
  outside the coverage bar, because node never loads them.
  `tests/webapp/browser_smoke.test.js` is what tests them, and
  is their whole bar: it exports `fixture.js` through the real exporter
  (`python3` from the repository root, so it needs `config.toml` like
  the rest of the suite), opens it from `file://` in headless Chrome
  over the DevTools protocol, clicks through it, and fails on any
  console error, CSP refusal or element cytoscape dropped. With no
  Chrome or Chromium on `PATH` and `CHROME_PATH` unset, it skips with
  that instruction. **It does not run in GitHub Actions**: it skips
  there whenever `GITHUB_ACTIONS` is set, because the runner's Chrome
  timing out at startup failed the `lint` job on PRs that touched no
  webapp code. So the wiring's bar is a local run, by
  `bash scripts/check_local.sh` with a browser installed; a change to
  those five files needs one, named in the PR's test plan. The command
  rides in the `lint` job, where node is already installed for
  `markdownlint`. Node's runner takes files rather than a directory, so
  the glob is not decoration. `tests/webapp/code_standards.test.js` rides
  the same command: it is `assets/webapp/`'s C1/C2 ratchet (see "Code
  standards" above), not a behavioural test, but there is no separate
  webapp check suite for it to live in instead.

- `poetry check`.
- At least one real end-to-end smoke test that exercises the actual
  change against real dependencies, not only its mocked unit tests:
  e.g. if you touch a CLI script, run it for real. Unit tests catch
  regressions in logic; smoke tests catch wrong assumptions about how the
  real library behaves (this project's test suite has caught real
  fake-vs-real behaviour drift this way before; see
  `tests/test_enrich_embed_index.py` and `tests/test_enrich_topic_model.py`'s
  own comments).

  **For `chitragupta/enrich/*` this is partly automated, and it
  matters which part.** `tests/test_enrich_real_libraries.py` runs
  on every leg that has the `enrich` group installed, which is both of
  CI's: it drives the real `chromadb` through `build_index()`/`search()`,
  and asks the real `sentence_transformers`/`bertopic` classes whether
  they still accept what the fakes accept. What it deliberately does
  **not** do is construct an embedding model or fit a real BERTopic,
  because that would make every CI run depend on a ~420 MB HuggingFace
  fetch. So
  the hand-run smoke test still stands for anything touching
  `model.encode()` or the clustering itself; the chromadb persistence
  paths are covered by the suite, better than a hand run would.

Only once all of the above are green does a task count as complete.

### 🐛 Reading a red `codecov/project` on a branch you believe is 100%

Believe your local run first, and check the session count before you go
looking for the coverage you lost: usually there is none to find.

Each matrix leg uploads its own report, and the two are only correct
merged: score the Windows one alone and a 100% branch reads ~99%. Codecov
computes a status from whatever sessions it has finished processing at
that moment, so a status computed before the second upload lands blames
the branch for a difference the matrix creates by design. The tell is the
session count, from Codecov's own API rather than the PR page:

```bash
curl -s https://api.codecov.io/api/v2/github/prasadtalasila/repos/chitragupta/commits/<head-sha> \
  | python3 -c 'import json,sys; t=json.load(sys.stdin)["totals"]; print(t["sessions"], t["coverage"])'
```

Two sessions and 100.0 against a status that reported ~99% means the
status was computed early, not that an upload was lost. A green upload
step is accurate in that case, and `fail_ci_if_error: true` would change
nothing.
`codecov.yml`'s `after_n_builds` is the gate that holds the notification
until both uploads are in; that file carries the reasoning, and
`tests/test_codecov_upload_gate.py` keeps its number in step with the
matrix. **One session** is a different problem (a leg that never
produced a `coverage.xml`), and there the status will sit pending rather
than post a wrong number.

### 🧹 The linters, which are enforced

`.pylintrc` and `.markdownlint.yaml` are in the tree, adopted from
[DTaaS](https://github.com/INTO-CPS-Association/DTaaS), the same source
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) takes its standards
from. `pyproject.toml`'s `[tool.ruff]` is not: DTaaS carries no ruff
config to inherit, so its `select` and `per-file-ignores` were decided
fresh, the way the paragraph below states. Run all four before you push
(`scripts/check_local.sh` runs them with the rest of the lint job);
`ci.yml`'s `lint` job runs exactly these, and the paths are part of the
command rather than a detail: a narrower glob is how a tree stops being
checked without anyone deciding it should. `ruff format --check`'s roots
are wider than the other three's, deliberately: `tests/` and `bench/`
are formatted though neither is linted, see
[docs/TECHNICAL-DEBT.md](docs/TECHNICAL-DEBT.md)'s 5.5 for why narrowing
to match would only relocate the gap:

```bash
pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks
ruff check chitragupta scripts .claude/hooks   # config: pyproject.toml's [tool.ruff]
ruff format --check chitragupta scripts tests bench .claude/hooks
markdownlint-cli2 "*.md" "docs/**/*.md" ".claude/**/*.md" ".agents/**/*.md" ".opencode/**/*.md" "plans/**/*.md" "!docs/examples/sample-project" "!docs/examples/*/content" "!.claude/worktrees"   # npm i -g markdownlint-cli2
```

All three negations are stated in the command for the same
narrower-glob-is-a-decision reason. `docs/examples/sample-project/` is
pipeline *output* (drafts, dossiers, review reports), which is never
lint-shaped and may not be hand-edited to become so (see "The committed
sample project is pipeline output"). `docs/examples/*/content` is the
same kind of output from the harness examples beside it
(`docs/examples/codex/`, `docs/examples/opencode/`), whose `README.md`
files are hand-written and stay inside the glob, as does
`docs/examples/README.md`.

`.claude/worktrees/` is the third, and it is a *local*-only problem
that CI structurally cannot see. It holds throwaway checkouts of this
same repository, so `.claude/**/*.md` reaches entire nested copies of
the tree, copies of `docs/examples/sample-project/` among them, which
the first two negations do **not** exclude, because those patterns are
anchored at the repo root and the nested copy sits several directories
down. Without it a local run reports tens of thousands of findings, all
inside worktrees, and noise on that scale is indistinguishable from a
check nobody runs. The negation is in `ci.yml` too, where it is inert,
rather than only here: one command that a contributor and CI both run
is the property the glob comment upstream of it is protecting.

**Read the linter's own exit code, not a pipeline's.** `pylint … | tail`
reports `tail`'s status, so a real finding passes for a clean run.

**All four are blocking, at a binary zero-messages bar**, never a
`fail-under` score, because
[R3](docs/AUTO-IMPROVEMENT.md#-the-requirements) rules out driving a
number, and a score can improve while the thing you cared about gets
worse. The tree is at zero for all four, which is this file's own rule
that **a check that has not been made to pass must not ship.**
[docs/TECHNICAL-DEBT.md](docs/TECHNICAL-DEBT.md)'s 5.2 and 5.5 record
how each adoption got there.

The configuration decisions that still bind, so a later reader does not
have to re-derive them:

- **The enrich group's imports are in `.pylintrc`'s `ignored-modules`**
  rather than installed in CI. They are lazy imports inside the
  functions that need them; pylint resolves imports statically wherever
  they sit, so without that list a lint job that does not download torch
  reports `import-error` against all of them.
- **`line-too-long` (C0301) is on**, and wins over the C2 file-length
  ratchet where the two pull against each other.
- **`MD060` (table cell padding) is on**; `markdownlint-cli2 --fix`
  does that pass, not a person.
- **ruff's `select` is `["E", "F", "BLE", "RUF100"]`, not ruff's own
  (much broader) default.** `BLE` (blind `except`) is the rule ruff is
  here for; `E`/`F` are pyflakes/pycodestyle's core correctness checks
  plus the "keep lines short" rule
  [CODE-STANDARDS.md's build order](docs/CODE-STANDARDS.md#-build-order)
  names; `RUF100` turns a `# noqa: BLE001` into a checked claim instead
  of a comment nothing reads.
- **`per-file-ignores` covers `__init__.py`'s `F401`/`E402`** wholesale
  rather than per-line `noqa`s: each re-exports a submodule's public
  name so `from chitragupta import x` reaches it, some via a deliberately
  late import to dodge a circular import, already explained inline where
  the comment rules require it.
- **ruff's own version is pinned exactly**, not only for Sonar S8544:
  `RUF100`'s verdict on a given `except` block depends on carve-outs
  (a `raise ... from exc` re-raise is not "blind") that are undocumented
  and narrower than `BLE001` looks, so an unpinned bump could move that
  verdict and redden the job on a rule this project never touched.
- **`ruff format`'s roots are `chitragupta scripts tests bench
  .claude/hooks`**, wider than either linter's: `tests/` and `bench/`
  are formatted though neither is linted. Style and per-site suppression
  are different axes. Its hanging-indent style is accepted as is; there
  is no config knob that reproduces paren-aligned wrapping.
- **`.git-blame-ignore-revs` lists whole-tree reformat commits.** This
  repository squash-merges, so a reformat's SHA on `main` exists only
  after the merge, and its entry lands in a follow-up PR. The file's
  header states the mechanism.

`.gitattributes` (`* text=auto eol=lf`) normalises line endings so CI's
Windows leg reads byte-identical files to the Linux leg, which matters
because over a dozen tests here scan this repository's own source.

## 🔍 Reviewing before you push: the OpenCodeReview plugin

**This is a required step in the cycle.** Step 3 of
[Shipping a code change](#-shipping-a-code-change-the-full-cycle) is to run
it on the branch and act on what it finds, before the PR is opened, with
the same standing as the local check suite above it. It is the one review
that happens while the change is still cheap to alter, which is why it
goes before the PR rather than after.

[OpenCodeReview](https://github.com/alibaba/open-code-review) is a Claude
Code **plugin**, installed per-host from the `alibaba/open-code-review`
marketplace and enabled in the user's own `settings.json`. It is not a
dependency of this repository, is not in `pyproject.toml`, and is not part
of CI, so it is the developing agent that has to invoke it. Nothing else
will. If the plugin is not available on this host, skip it and **say so in
the PR's test plan**, rather than installing it mid-task or letting its
absence pass unmentioned.

It provides two skills, both of them plugin skills; what differs is who
does the thinking.

| Skill | Who reviews | Needs an LLM endpoint |
| --- | --- | --- |
| `/open-code-review:delegate-review` | **You do.** The skill has OCR select the files and resolve the rules, then hands you each diff to review yourself | **No** |
| `/open-code-review:review` | **A separate model call.** The skill drives `ocr review`, which sends each file to a configured endpoint and returns comments | **Yes** |

**Prefer `delegate-review` here, and not only as a fallback.** It is a
first-class mode ("LLM-free on the OCR side", in the plugin's own words),
and it is the better fit for this repository: the agent doing the
reviewing is already carrying
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md), the layer boundaries and
the citekey invariant, which is the context a detached CLI call does not
have. `review` additionally needs `OCR_LLM_URL`/`OCR_LLM_TOKEN`/
`OCR_LLM_MODEL`, `~/.opencodereview/config.json`, or
`ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`; with none set it exits on
`resolve LLM endpoint` and nothing has been reviewed.

**Say how much of the branch it saw, not only which mode ran.** OCR
cannot review Markdown at all (every `.md` file comes back excluded as
`unsupported_ext`), so on a prose-heavy branch the review covers a
fraction of the diff, often under half its files. "OCR reviewed the
branch" is a much weaker claim on a prose-heavy branch than on a code
one, and the test plan should carry the count so a reader can tell them
apart.

**Two things about installing it**, neither guessable. `npm i -g
@alibaba-group/open-code-review@1.9.9` puts the
binary at `$(npm root -g)/../bin/ocr`, which is not on `PATH` by
default. It is pinned because the extension list and schema probed below
are facts about this exact release, not about OCR in general. And npm's
`allow-scripts` default blocks the package's postinstall, which is
survivable (the shipped binary still runs) but prints a warning that
reads like a failed install.

Whichever runs, **say which one did.** "OCR reviewed the branch" and "I
reviewed the branch against OCR's rules" are different claims, and only
one of them is usually true.

### 🚫 What the plugin does and does not reach

`.opencodereview/rule.json` is what makes it worth running here. OCR's
built-in rule is generic Python review, and is wrong about this tree in
both directions: it would flag the dense *why*-comments, the f-string
`PRAGMA` and the deliberately duplicated pool builders, and it does not
know the citekey invariant, the layer boundaries, C1/C2 counted in
statements, or the `encoding="utf-8"` rule. The project file replaces it
for `chitragupta/`, `tests/`, `scripts/`, `bench/` and `.github/`, and excludes
`content/` and `papers/`: the user's drafts and their personal
bibliography, which are not this repository's code and have no business
being sent to a third-party endpoint.

**It cannot review Markdown, so it cannot review the documents that
govern this project.** OCR opens only extensions it recognises as code
and drops the rest *before* rules are consulted, reporting
`exclude_reason: unsupported_ext`. Probed against open-code-review
v1.9.9: `.py`, `.json`, `.yml`/`.yaml`, `.sh` and `.toml` are reviewed;
`.md`, `.txt`, `.rst` and `.cfg` are not. So `AGENTS.md`, this file,
`docs/CODE-STANDARDS.md` and every skill in `.claude/` are outside it
entirely, and a clean OCR run says nothing about them.

What *does* cover Markdown, so "OCR came back clean" is never read as
"the standing instructions were reviewed": markdownlint, at the globs
`ci.yml`'s lint job and `scripts/check_local.sh` run it with (see
["The linters, which are enforced"](#-the-linters-which-are-enforced)), for
style and structure; `tests/test_technical_debt_scan.py` and
`tests/test_docs_pins.py`, the doc-drift tests, for the factual claims
that have a machine-readable source of truth to check against; and a
human reading the diff for everything else (content, argument,
whether a stale sentence is still true), which is the one check with no
detector and stays that way.

Two traps:

- **`ocr rules check <path>` is a rule *lookup*, not a coverage check.**
  It resolves a rule for a file OCR would never open, so it will
  cheerfully confirm a Markdown rule that can never fire. The command
  that answers "will this file actually be reviewed?" is
  `ocr delegate preview --format json`, whose `excluded_files` carries
  the reason. `tests/test_opencodereview_rules.py` pins both halves
  (that no glob is orphaned, and that no rule targets an extension OCR
  will not open), because an orphaned glob fails *open*: OCR silently
  falls back to its built-in rule and still exits 0.
- **The `ocr` binary may not be on `PATH`.** A user-prefix npm install
  puts it in `~/.npm-global/bin`, which is not on the default path, so
  the plugin's own `which ocr` prerequisite check reports NOT INSTALLED
  on a host where it is installed. Check that before concluding the tool
  is absent.

### ⚠ It is an aid, not a gate

Same standing as the review layer ([SOUL.md](SOUL.md)): nothing here
blocks on it, `python -m chitragupta.draft gate` remains the only gate, and a
finding is a claim to agree or disagree with. Judge each against
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) rather than adopting it
because a tool said so. A change made only to silence a reviewer is the
failure mode that document's R3 is about. The plugin's `review` skill
offers to apply fixes autonomously; the surgical-changes rule above still
governs what may land in your diff.

The rules in `.opencodereview/rule.json` are themselves prose handed to a
model, and nothing checks that they are obeyed. A run that reports
clean is not evidence of anything beyond what OCR could open in the
first place.

## 💬 Commit messages

Title line: imperative mood, concise, describes the change's effect (not
"updated files" or "misc fixes"). PRs are squash-merged (see "Pull
requests" below), and **the PR title is what lands**:
`squash_merge_commit_title` is `PR_TITLE`, so it is the PR title
unconditionally, whatever the branch's commits are called.

**Never add the PR number by hand**, anywhere: not in the PR title, not
in a branch commit, not in a merge subject. GitHub appends it when it
composes the title (e.g. `Fix reconcile drift detection (#42)`), and it
composes the title every time. Writing it in as well is how you get
`(#42) (#42)`.

Body: a blank line, then a bulleted list of the specific, concrete changes,
each bullet starting with a present-tense verb (Fix, Add, Remove, Migrate,
Upgrade) and naming what actually changed, not vague summaries. No
preamble paragraph before the bullets. Lines wrap at 72 characters, with
continuation lines indented two spaces. No closing keyword (`Closes #N`):
it closes whichever issue it names when the commit lands, so it belongs
in the PR description. For example (style, not this repo's literal
content):

```text
Fix reconcile drift detection, secret handling, and stale config warnings

- Fix reconcile to detect and reprovision users whose containers are
  gone, refuse `--fix` when Docker is unreachable or `--output-dir`
  differs from cwd.
- Restore secret-file exclusion in build.py, consolidate
  SECRET_FILENAMES, and chmod secret files 0600 unconditionally.
- Warn on stale root `.env` from install/update/generate paths; remove
  dead code no longer reachable after the above.
```

**You write the body, in the PR description's `## Commit message`
section**, as one ```` ```text ```` fence holding exactly the text above
minus the title; the template carries the empty fence. That text lands
on `main` byte for byte, or the merge is refused. It is checked twice,
by the same code (`CommitBody` in `scripts/merge_pr.py`, whose docstring
is the grammar):

- **While the PR is open**, by `.github/workflows/commit-message.yml`,
  which re-runs whenever the description is edited. It is meant to be a
  required check (see [the settings](#-what-the-repository-settings-fixed-and-what-they-could-not)
  for its status), so a malformed body is red before review rather than
  at merge.
- **At merge**, by `python scripts/merge_pr.py <N>`; see
  [Merging](#-merging).

Nothing else in the description reaches the commit. The body is
written, not extracted: scraping bullets out of the description carries
every change twice and drags reviewer notes onto `main`. The template is a
*review* document (`## Type of Change`, `## Test plan`,
`## Checklist`), and a commit body is a piece of writing for a different
reader, so it is written, not extracted.

No repository setting could do this instead.
`squash_merge_commit_message` takes exactly three values (`PR_BODY`,
`COMMIT_MESSAGES`, `BLANK`), and none of them transforms the text.
`BLANK` (see [the settings](#-what-the-repository-settings-fixed-and-what-they-could-not))
only decides what a merge that bypasses the script lands: a title and
no body, rather than the raw description.

## 🔀 Merging

Squash, enforced by configuration rather than by convention:
`allow_merge_commit` and `allow_rebase_merge` are both `false`, so it is
the only method the repository offers. Merge with:

```bash
python scripts/merge_pr.py <N>
```

It reads the body from the PR description's `## Commit message` fence,
checks it against the format in ["Commit messages"](#-commit-messages),
prints it, and calls `gh pr merge <N> --squash --body-file -` for you.
A body that breaks the format is refused with the line number, the rule
and the offending line (shown escaped, so an invisible character is
visible); a description with no such section is refused with the empty
section to paste in. Nothing is stripped, joined or rewritten, and there
is no fallback to the branch's commit subjects. `--dry-run` does
everything but merge; `--check` reads a description on stdin and only
checks it, which is what CI runs.

### 🚦 It refuses a merge that would lose the version bump

Immediately before calling `gh pr merge`, and after composing the body,
it runs `git fetch origin --tags` and then
`scripts/check_version_bump.py --offline`, **the same script `ci.yml`
runs, unchanged**. If that exits 1, it prints why and **exits 1 without
merging**. `--dry-run` reports the same verdict, since that is where a
person looks first.

**The `git fetch` is what makes it work.** That
script reads `origin/main` and the tag list out of local git, so without
a fetch it compares against whatever this checkout last saw, and the
merge or tag that causes a collision lands *inside* the window being
checked. No new rules are written here; reusing that script is what keeps
the merge-time check from drifting away from the pull-request-time one.

**This is not a duplicate of the CI check, and step 8 above cannot
replace it.** `ci.yml` runs that check against the merge commit GitHub
built at `pull_request` time; another PR can merge, or push a tag,
between that run and your merge. Two branches picking the same version
produce a *byte-identical* `version =` line, so git merges it with no
conflict and `mergeable_state` stays `clean`; nothing else looks. And
step 8's "has `main` moved?" is a check a person performs *before*
merging, so the gap is between that check and the merge call itself.
Another PR can merge and tag the same version seconds after your check
passes, leaving `main` on a version already released against different
content.

Three consequences follow:

- **There is no `--force`.** A refusal's remedy is to bump the version,
  which you have to do regardless, so an override would only let you
  merge a branch you would then have to fix on `main`.
- **Exit 1 blocks whatever caused it**, a base ref that cannot be read
  included, since that script exits 1 for that too. This is deliberate,
  and it is the *opposite* of the caution `check_version_bump.on_pypi`
  needs: a merge is itself a network operation, so a state where this
  cannot tell is one where `gh pr merge` was not going to work either,
  and stopping costs nothing.
- **It reads this worktree's `pyproject.toml`**, so run the command from
  the branch being merged. That is how the cycle above already has you
  running it, and reading the PR head's file through the API instead
  would be a second way to ask what that script already answers.

**It still does not remove the habit of checking after the merge.** The
refusal closes the window before `gh pr merge` returns; nothing can close
the one *after* it, so re-read `main`'s version before pushing a tag:

```bash
git fetch origin -q --tags
git show origin/main:pyproject.toml | grep -m1 '^version'   # must be yours
```

**No `--subject`, and no `(#N)`.** `squash_merge_commit_title` is
`PR_TITLE`, so GitHub composes the title from the PR and appends the
number itself. Passing `--subject` takes your string verbatim instead,
which bypasses that and gives `(#42) (#42)` if you also write the
number in. The script does not offer the
flag, so this cannot happen by way of it.

**A body on stdin is still needed.** With the
body setting at `BLANK`, a squash commit without `--body-file` has a
title and no body. As ["Commit messages"](#-commit-messages) sets out, no
value of `squash_merge_commit_message` produces the documented shape,
because none of them transforms the text.
`plans/827-commit-message-format.md` has why the body is checked rather
than assembled, and why the merge side is enforced by being the one
documented command (producer-is-enforcement, the same standing the
OpenCodeReview step above already has) while the pull-request side is a
required check.

The format is something a check holds you to while the PR is open,
instead of something a person has to remember at the end of a long
session, in a browser, after CI has gone green. The ratchet, the
citation gate and this check are the same response to guidance that
does not stick
([docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md#-why-a-ratchet-suits-this-project-specifically)).

### ⚙ What the repository settings fixed, and what they could not

The repository is configured with:

```bash
gh api -X PATCH repos/prasadtalasila/chitragupta \
  -f squash_merge_commit_title=PR_TITLE \
  -F allow_merge_commit=false -F allow_rebase_merge=false
```

- **`PR_TITLE` closes the title completely.** "GitHub uses the PR title"
  is unconditional, so nothing about a title has to be remembered at
  merge time.
- **Disabling the other two methods** makes "Merge method: squash" a
  fact about the repository rather than a sentence in this file.
- **No body setting closes the body.** The PR template shapes the
  description into a review document, which is a different artefact
  from a commit message. That is why the author writes the body
  (["Commit messages"](#-commit-messages)).

Two settings complete that, and both need the repository owner. They
are an open action until the owner applies them; until then the body
setting is `PR_BODY` and the `commit-message` check is advisory:

```bash
gh api -X PATCH repos/prasadtalasila/chitragupta \
  -f squash_merge_commit_message=BLANK
```

- **`BLANK` replaces `PR_BODY`.** A merge that bypasses `merge_pr.py`
  (the web UI's button) then lands a title and no body, instead of the
  raw description with its tick-boxes and anything a bullet smuggled in
  (a `Co-authored-by:` trailer, a live `Closes #N`, an escape sequence).
  Still wrong, but empty rather than wrong in ways that cannot be
  rewritten out of history.
- **`commit-message` becomes a required status check** on `main`, in
  the repository's `main` ruleset or in branch protection. A required
  check can be selected only once it has reported at least once.

When the owner applies them, replace this paragraph with the fact.

The general lesson, since this file is where process claims live: a
setting closes a gap only where a machine can do the whole job. Titles
are mechanical, so a setting finished them. A commit body is a piece of
writing addressed to a different reader than a PR description, and no
enum value writes it for you.

## 🎫 Issues and pull requests

Templates live in `.github/`, where GitHub picks them up automatically;
don't restate their section list here:

- `.github/pull_request_template.md`: auto-populates every new PR.
- `.github/ISSUE_TEMPLATE/bug_report.md` and
  `.github/ISSUE_TEMPLATE/feature_request.md`.

A PR title is held to the same bar as a commit's title line: concise,
describes the effect. It is held to it literally, since
`squash_merge_commit_title = PR_TITLE` makes the PR title the commit
title on `main` whatever the branch's commits are called. The template's
**Test plan** section is not a formality: fill it from what you
actually ran (see "Before claiming a task complete" above), not from what
you intended to run.

The template is a review document with one exception: its `## Commit
message` section, whose fence is the commit body and is the only part of
the description that reaches `main`. That is a deliberate split: a
reviewer needs the test plan and the checklist, and `main`'s history
does not. [Merging](#-merging)'s `--body-file` is what carries the fence
across; a merge without it lands a title and no body.

Merge method: squash, enforced by the repository rather than by this
sentence; see [Merging](#-merging). Each PR becomes exactly one commit
on `main`.

**Dependabot PRs.** `.github/dependabot.yml` opens one grouped PR a
week that bumps the workflows' pinned action SHAs. It arrives
red, as expected: Dependabot neither raises
`pyproject.toml`'s version nor writes a `## Commit message` section,
so `lint`'s version-bump check and the `commit-message` check both fail
on it. Finish it like any other PR. Check out its branch, push a PATCH
bump ("Versioning and releases" below: CI/workflow-only), add the
commit-message fence to the description, and merge it with
`scripts/merge_pr.py`. Dependabot-triggered runs do not get the
repository's Actions secrets, so the Codecov and SonarQube steps may
fail on its first run too. Your push re-runs CI as you, with the
secrets, and that run is the one to read. Check the new `# vX.Y.Z`
comments against the action's release notes before merging. Moving a
pin is the point of the PR, and a major-version jump can change
behaviour.

## 📦 Versioning and releases

Semantic versioning (`pyproject.toml`'s `[tool.poetry].version`), bumped
according to the most significant change in the release, not the number
of commits:

- **PATCH** (x.y.Z): bug fixes, documentation-only changes, CI/workflow-only
  changes, test-only additions: nothing that changes what the pipeline
  does or how it's invoked.
- **MINOR** (x.Y.0): new backward-compatible functionality: a new
  script, a new `chitragupta/` module, a new optional config key, a performance
  improvement that doesn't change output shape.
- **MAJOR** (X.0.0): breaking changes: anything that changes an
  existing citekey/output format, removes or renames a `config.toml` key
  without a fallback, changes a CLI's argument shape, or otherwise
  requires an existing user to change how they invoke or configure the
  pipeline.

Every tag gets a GitHub Release with the wheel/sdist attached, but only
a **PATCH-free** tag (X.0.0 or X.Y.0) also publishes to PyPI.
`.github/workflows/release.yml`'s `publish-pypi` job skips a tag ending
anything other than `.0`, since a published version can never be
reused and a PATCH release doesn't need `pip install chitragupta-cli`
to see it immediately. `docs/PACKAGING.md` has the reasoning.

Release notes go in the GitHub Release body, not the git tag message.
`.github/RELEASE_TEMPLATE.md` has the shape to follow. GitHub does *not*
pick that file up automatically, so copy from it by hand when drafting a
release.

## 🚢 Shipping a code change: the full cycle

Any change that touches code (not a docs-only change) goes through the
complete cycle, and isn't done until every step below has succeeded,
not merely started:

1. Branch off `main`, commit (see "Commit messages" above), push.
2. Decide the version bump (see "Versioning and releases") and update
   `pyproject.toml` as part of the same branch. `release.yml` verifies
   the pushed tag against `pyproject.toml`'s version on `main`, so the
   bump has to land *before* the tag exists, i.e. in this PR, not after.
3. Run the [OpenCodeReview plugin](#-reviewing-before-you-push-the-opencodereview-plugin)
   over the branch and act on what it finds. Nothing invokes it for you
   (it is not in CI and not a dependency), so if this step is skipped it
   does not happen. Record in the PR's test plan which skill ran,
   or that the plugin was unavailable.
4. **Read the documentation the change touches or makes stale, and fix
   what you find.** OCR does not reach Markdown (["What the plugin does
   and does not reach"](#-what-the-plugin-does-and-does-not-reach)
   above), so for docs this step *is* the review, not an optional extra
   on top of it. Run three different searches, not one:
   - **The docs your diff already edited.** Read them for internal
     consistency: a table whose row count no longer matches its own
     prose, a diagram whose exported `.mmd`/`.svg` drifted from the
     fenced block it was rendered from, a cross-reference to a section
     you renamed.
   - **Everywhere else your change made something else false.** A new
     item added to an existing set is the usual trigger: it moves a
     count, a "the other N", an enumerated list, or an ordinal ("the
     Nth aid") in every place that already stated the old total:
     files nowhere in your diff, found only by grepping the repository
     for the specific number or name your change moved, not by
     rereading the files you happened to touch. A new review aid, for
     example, moves "the other N" in code docstrings, `docs/CLI.md`,
     `docs/ARCHITECTURE.md`, `docs/FEATURES.md`, `docs/DIAGRAMS.md` and
     its rendered exports, none of them in the PR's file list. Watch for
     the opposite mistake too: do not bump a count on the assumption that
     a new item changed what *existing* code reads. If the code was not
     touched, revert the doc rather than changing the code to match a claim
     nobody verified.
   - **What the documentation already decided, which your change may
     have just contradicted.** The first two searches look for prose
     your change falsified; this one looks for prose that falsifies
     *your change*. A rationale for **rejecting** a design is the
     dangerous shape, because it reads as history and is in fact a
     constraint: `docs/DESIGN.md` turns down locking the ledger on the
     ground that it "would force a run into one transaction, discarding
     the incremental commit points on a crash"; a fix that batches `sync`'s
     commits contradicts that, and only this sweep catches it, since no test
     would. Grep the documentation for the **claim** your change touches,
     not for the files in your diff.

   Search for the claim, not the file. A six-line code change that adds
   an item to an enumerated set can move a dozen prose sites, and a
   sentence fixed in four places can have three more verbatim copies. The
   size of a diff predicts nothing about the size of its sweep.

   A doc that was already stale *before* your change touched
   anything (traceable with `git log -1 -L<line>,<line>:<path>` to a
   commit that predates yours) is a real problem worth naming in the
   PR description, but fixing it is not this step's job: bundling an
   unrelated cleanup into a feature PR is what the
   surgical-changes rule above exists to prevent. The line is whether
   *your* commit is what made the sentence false.
5. Open a PR against `main` (see "Issues and pull requests" above).
6. Wait for `.github/workflows/ci.yml` to complete on the PR and confirm
   it's green. If it fails, fix the actual cause (see "Before claiming a
   task complete") and push again; don't merge past a red check.
7. Request review from Copilot, resolve every issue it identifies, and
   mark each as resolved; consider all previous Copilot comments made in
   this PR while resolving the issues. Make a push after all issues are
   resolved, and then request re-review from Copilot. Iterate until all
   issues are resolved. Use judgement on a genuinely trivial finding
   rather than treating every comment as mandatory, but "trivial" means
   inconsequential (a wording nit), not "inconvenient to fix."
8. **Check that `main` has not moved since CI last ran.** If it has,
   merge or rebase onto it and **do the whole cycle again from step 2**:
   re-decide the version bump, re-run every local check, and wait for CI
   on the new head. A branch that went green against an older `main` is
   not evidence about the merge commit, which is what lands.

   CI builds the *merge* commit for a
   `pull_request` event, so a stale branch can go red for something it
   did not do and, worse, can go **green on a state that no longer
   exists**. The version is the usual casualty, because two branches
   picking the *same* number produce a byte-identical line that git
   merges without a conflict. `scripts/check_version_bump.py` fails CI on
   that, but it can only fail on a run that actually happened.
9. Squash-merge the PR: `python scripts/merge_pr.py <N>` (see "Merging"
   above). It re-checks the version against `main` and the tags at the
   last possible moment and refuses rather than merging a collision,
   which catches the case step 8 structurally cannot: a PR that merges in
   the seconds after your check.
10. Tag `v<version>`, and **read `main`'s `pyproject.toml` again first**
   rather than trusting the number you bumped to. The merge closes the
   window before it; nothing closes the one after it, and a tag pushed
   on a collided version names somebody else's content.
11. Confirm `.github/workflows/release.yml` completed and the resulting
   GitHub Release has its assets attached: `chitragupta-<version>.zip`,
   `chitragupta-docker-<version>.zip`, and the wheel and sdist. This is
   the deliverable, not the tag or the merge by
   itself.
