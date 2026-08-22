# DEVELOPER-AGENTS.md

Guidance for coding agents (and anyone else) **working on this repository
itself**, as opposed to using it to draft content. The user-facing half is
[AGENTS.md](AGENTS.md); the why behind both is [SOUL.md](SOUL.md).

[AGENTS.md](AGENTS.md)'s citekey invariant binds code here too: no module
may generate, guess or rewrite a citekey, and no new check may be promoted
into a gate beside `chitragupta/citation_gate.py`.

## Role

This assistant manages most of the day-to-day development here: implementing
features, writing tests first, running the full local check suite, opening
PRs, watching CI, merging, and cutting releases. Proceed autonomously through
that whole cycle for a routine code change rather than pausing to check in at
each step -- reserve pausing for decisions that are genuinely irreversible
(force-pushes, history rewrites, deleting something not obviously
regenerable) or genuinely ambiguous (a requirement with more than one
reasonable reading and no clear tie-breaker in this file or the code).

## Behavioural rules: think before coding

Four rules about *how to work*, as opposed to what the code should look
like ([docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md)). They prioritise
caution over speed; for a genuinely trivial change, use judgement.

1. **Think before coding.** State assumptions rather than making silent
   choices. Where a requirement has more than one reasonable reading,
   present the alternatives instead of picking one quietly -- this is the
   "genuinely ambiguous" case under "Role" above, and it is the one time
   pausing beats proceeding.
2. **Simplicity first.** Write the minimum that solves the stated
   problem. No speculative abstraction for a single call site, no
   unrequested `config.toml` key, no defensive handling for a state that
   cannot occur. Ask whether a reviewer would call it over-engineered; if
   yes, cut it. Note the one deliberate exception: the *comments* are not
   subject to this -- see
   [docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md#the-comment-rules-and-the-misreading-to-avoid).
3. **Surgical changes.** Each changed line should trace to the requested
   task. Do not refactor unrelated code, and match the local style of
   whatever you are editing. Remove imports and helpers *your* change
   orphaned; report pre-existing dead code rather than deleting it in the
   same diff. A module already on the size register is a thing to mention
   in the PR, not a licence to rewrite it while passing through. This is
   where the Boy Scout Rule lands here: cleanup happens, in its own PR
   and against the register, rather than inside an unrelated diff --
   [why](docs/CODE-STANDARDS.md#the-boy-scout-rule-and-surgical-changes).
4. **Goal-driven execution.** Turn the task into a verifiable goal before
   starting: "fix the bug" becomes "write a test that reproduces it, then
   make it pass" -- which is the test-driven rule below, arrived at from
   the other direction. For a multi-step change, state the plan as steps
   with the check that verifies each.

## Code standards

[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) is the standard the code
itself is held to -- the code counterpart of `docs/WRITING-STANDARDS.md`.
Read it before a non-trivial change. In brief:

- **Two rules are machine-checked**, by `tests/test_code_standards_scan.py`
  as part of the ordinary `pytest` run: at most **25 statements** per
  function, at most **250 code lines** per module. Both are **ratchets** --
  today's offenders are frozen in a register that may only shrink, so a
  new offender fails and a fixed one must be delisted.
- **Statements, not physical lines**, because this repository *requires*
  rationale comments and a physical-line limit would reward deleting them.
- **Cognitive complexity is capped at 25, not SonarQube's default 15** --
  aligned with the 25-statement rule, for the same anti-over-splitting
  reason. Do not split a function merely to satisfy an S3776 finding of
  25 or below; mark it *Accepted* in SonarCloud instead --
  [why](docs/CODE-STANDARDS.md#cognitive-complexity-the-bar-is-25-not-sonarqubes-default-15).
- Everything else in that document -- naming, one-thing-per-function, the
  code-smell vocabulary -- is a review standard with no detector,
  deliberately. A quality score is not a thing to drive to zero;
  [docs/AUTO-IMPROVEMENT.md](docs/AUTO-IMPROVEMENT.md)'s R3 is the rule,
  and it applies to code as written.
- It is written against the clean-code checklist rather than invented
  here, and maps every rule in it to enforced / already-here /
  review / not-applicable. [docs/INSPIRATION.md](docs/INSPIRATION.md) has
  the provenance.

## Module boundaries

`chitragupta/references.py` formats an IEEE bibliography entry (authors, venue,
volume, pages) from the ledger's `bib_fields` column, which `sync`
populates via `bib_reader` -- it does not, and must not, parse
`bibliography.bib` itself. The one thing that legitimately reads the bib
file directly is pandoc's `--citeproc`, which is not this codebase. See
[AGENTS.md](AGENTS.md) for why `bib_reader` is the sole reader.

What a part *does* and what it *costs to install* are separate axes:
`chitragupta/render_output.py` is drafting-layer code that needs no package from
the `enrich` group, which is why it sits in `chitragupta/` rather than
`chitragupta/enrich/`. `chitragupta/review/verbatim_check.py` is the same axis
read the
other way: it sits beside the two aids it belongs with, not in
`scripts/`, which holds dev tooling and no layer entry point at all.

## Environment constraints on this host

`pip install` outside a venv is blocked (PEP 668) -- unconditionally, on
every host, regardless of root access. **This matters for the corpus
layer too**: `python -m chitragupta.corpus sync` needs `bibtexparser` (parsing
`bibliography.bib` correctly -- nested braces, LaTeX escapes -- isn't
worth hand-rolling), so it must be run via the installed venv, not the
bare system interpreter. `python -m chitragupta.draft gate` is the exception
(see [AGENTS.md](AGENTS.md)).

**Probe for a toolchain; never assume one, in either direction.** An
earlier revision of this file asserted that root, TeX Live and Pandoc were
unavailable here, and a later one asserted the opposite. Both were one
machine's facts written as project rules, and both went stale. The
durable rule is the probe:

- **When the enrichment layer's dependencies are present:** stages that need them
  (Docling parsing; Pandoc/TeX Live rendering) work directly on the host,
  not only inside `docker/` -- there is nothing docker-exclusive about
  any of them.
- **When they're absent:** don't hang, stack-trace, or silently skip
  without saying so. Every `chitragupta/enrich/*` stage already self-probes its
  own prerequisites and reports honestly (`ok`/`skipped`/`missing-binary`)
  via `chitragupta/enrich/__main__.py` rather than assuming the target implies
  availability -- keep any new stage consistent with that pattern instead
  of inventing a new fallback policy.

Install everything with:

```bash
bash scripts/install_full_pipeline.sh              # Python deps only (default) -- what every host needs regardless of OS packages
bash scripts/install_full_pipeline.sh os-deps      # apt-get: TeX Live, Pandoc, poppler-utils, OpenCV runtime, Poetry, zip/unzip -- needs root, opt-in
bash scripts/install_full_pipeline.sh dev-deps     # pytest/pytest-cov, to run the test suite -- opt-in
bash scripts/install_full_pipeline.sh all          # os-deps + python-deps
bash scripts/install_full_pipeline.sh cpu-torch    # swap torch to the cpu-only wheel index -- opt-in
```

This is **the single install script for both the host and Docker and CI**
-- `docker/Dockerfile` calls it once per stage as separate `RUN` lines, and
`.github/workflows/ci.yml` calls it directly too, rather than any of them
having their own separate apt-get/pip/poetry install logic. Python
dependencies are managed by Poetry as a lockfile/venv manager for a
checkout, Docker and CI ([docs/PACKAGING.md](docs/PACKAGING.md) records
the decision to also make this a published, pip-installable package, and
what had to land first). If you find a dependency-order issue, fix it
once in `pyproject.toml` (+ `poetry lock` to update `poetry.lock`) and
every target picks it up. Don't add a second install path.

Read that last sentence as the invariant it protects, not as the
mechanism: the goal is **one place a dependency fact can be written**, so
a fix lands once and every target picks it up. The single script is the
mechanism for a checkout, Docker and CI; **there are now two front
doors** onto it (#265) -- `install_full_pipeline.sh` for those three, and
`chitragupta install os-deps|gpu-torch` for someone who pip-installed,
reaching the *same script's* `os-deps` stage and the *same*
`ensure_gpu_torch` function rather than a reimplementation of either.
`chitragupta install python-deps|dev-deps|all` refuse by name instead,
each naming the `pip install chitragupta-cli[...]` extra that already
replaces it (below) -- accepting them would run something with a
different meaning than the argument implies, which is worse than
refusing. Two front doors, one source of truth, still no second place to
write a version down.

**Extras mirror the three optional Poetry groups below**, so `pip
install chitragupta-cli[enrich]` resolves the same versions `poetry
install --with enrich` does. The two declarations are unrelated Poetry
mechanisms that happen to need the same facts -- a group dependency never
reaches a built wheel's metadata, so an extra needs its own, duplicate
entry under `[tool.poetry.dependencies]` (`optional = true`) -- and
`tests/test_pyproject_extras.py` is what keeps the two from drifting
apart silently. The one thing pip cannot do that `poetry install
--with enrich` does: match torch to this host's GPU driver
(`ensure_gpu_torch`, above) -- `pip install chitragupta-cli[enrich]` on a
CUDA host still lands a CPU-only wheel, silently, exactly as a bare
`pip install torch` would. `chitragupta doctor` detects that mismatch and
names `chitragupta install gpu-torch` as the fix; nothing makes it
automatic, because pip has no post-install hook this project would be
willing to use.

`cpu-torch` is deliberately **not** part of `all`, and is not something
the script infers. It asserts that a GPU is absent *for good* -- true of
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
withheld). **It has still not been built or run in this environment** (no
Docker daemon here) -- treat it as a draft to validate, not a tested
artifact.

## The enrichment layer (`chitragupta/enrich/`, `chitragupta/enrich/__main__.py`)

Implements Docling -> sentence-transformers/Chroma ->
BERTopic -> Pandoc/LaTeX, one script for both host and Docker. Each stage
self-probes its own prerequisites (pandoc/pdflatex on PATH) and
reports honestly (`skipped`/`missing-binary`) rather than assuming the
target implies availability -- don't "fix" a skip by hardcoding
target-specific behavior; fix the probe if it's wrong. `--target
host|docker` is **informational only** for exactly that reason: the
probes decide, not the flag, so nothing branches on it.

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
corpus. `embed` and `bertopic` are refused rather than scoped, because
each writes one whole-corpus artefact with no partial form -- allowing
either needs the Chroma collection to record its own coverage first.
[docs/LADDERS.md](docs/LADDERS.md#scoping-a-run-to-one-draft) owns that
reasoning; keep it there rather than restating it.

No stage in this pipeline calls out to an LLM or needs an API key --
Docling, embeddings/Chroma, BERTopic, and the Pandoc/LaTeX render
step are all local/deterministic. Any LLM-backed synthesis happens only
via the `.claude/skills/` drafting layer, invoked through a Claude Code
session rather than a standalone API call.

`chitragupta/enrich/corpus.py` sources the enrichment corpus from the ledger and
nothing else, so every document it yields is citable and
keyed by its citekey alone. Keep it that way -- the enrichment layer must never
index a document a draft would not be allowed to cite. If a paper is
worth enriching, it belongs in the reference manager: catalogue it,
re-export, and re-run `python -m chitragupta.corpus sync`.

## Conventions a new stage has to follow

Three, each learned from a bug rather than chosen:

- **Anything holding the write lock reports per document.** DESIGN.md's
  concurrency policy requires a serial section to be observably making
  progress, and an unreported one is indistinguishable from a hang -- a
  correct run was read as stuck and killed at 399 of 501 documents
  (#50). `sync`, `docling_parse` and `embed_index` all emit
  `[done/total] <citekey>`, opened *before* the slow call so the reader
  sees the document currently under way rather than the last one that
  finished. Where it goes differs, and the split is deliberate.
  `sync`'s stdout is a documented contract -- bibliography order,
  diffable between runs, pinned by tests -- so its progress and warnings
  go through `logging` to `logs/pipeline.log` instead (3.4.0). The
  enrichment stages keep their stdout and *mirror* it into the same file
  via `logging_setup.say()`, which prints and logs one line with
  `extra={"file_only": True}` so the console handler doesn't echo it.
  Two kinds of message stay bare `print`s and must not be
  converted: anything built across several writes (`print(..., end="")`,
  where a log record's one-line-per-entry shape would withhold the
  citekey until the work finished) and anything running in a worker
  process or a signal handler. Flush anything printed: stdout is
  block-buffered when it isn't a terminal, and the tail of an
  interrupted run is the part worth keeping.
- **Classify a failure by cause on the exception, not by matching its
  message.** `pdf_text.py` sets `transient` and `timed_out` marks that
  survive the pool's pickling; `sync` reports each cause separately
  because they want opposite fixes (raise the timeout and `--reparse`
  versus fix or remove the PDF). Adding a cause means adding a mark, not
  a string match.
- **Report a partial result as a failure.** Docling's `PARTIAL_SUCCESS`
  returns a document that stops early; writing it would hand the citation
  gate a source that silently ends at page k of n. Check the status and
  raise *before* anything is written, so nothing enters the incremental
  cache.

## Development process: agile, test-driven

Work in small, independently-shippable increments -- prefer several small,
reviewable PRs over one large one, and prefer a working, tested slice of a
feature over a complete-but-untested one. Within each increment, follow
test-driven development:

1. Write a failing test that captures the behavior being added or the bug
   being fixed, and confirm it actually fails (a test that passes before
   the fix exists isn't testing anything).
2. Write the minimum implementation that makes it pass.
3. Refactor with the test suite green, if the result needs cleaning up.

This applies to bug fixes as much as features: "fix the bug" becomes
"write a test that reproduces it, then make it pass" -- don't fix
something you can't first demonstrate is broken. Exception: exploratory
spikes to understand a problem before committing to an approach don't
need up-front tests, but the resulting real change does.

### Recording a plan before you build

[docs/FEATURE-ROADMAP.md](docs/FEATURE-ROADMAP.md) holds what would be
built and in what order. For an item whose design is genuinely
underdetermined, write the plan down in `plans/` **before** the first
test, and link it from the PR.

Most items do not need one -- a roadmap entry already carries the files
touched, the size and the dependencies, and for a mechanical change that
is the whole plan. [plans/README.md](plans/README.md) has the three
tests for when a plan earns its place, the shape to follow, and the rule
that a merged plan records which PR closed it.

`plans/` does not ship: it is in `scripts/release.py`'s
`EXCLUDE_TOP_LEVEL`, like `tests/` and `bench/`. It is linted, though --
the markdownlint globs above include it.

## Before claiming a task complete: run all local checks

Never report a task as done on the strength of a plan or a code read alone.
Before saying so, actually run, in this repo:

- The full test suite with coverage: `.venv-full/bin/python -m pytest
  --cov --cov-report=term-missing`. Bare `--cov` deliberately: what is
  measured is declared once, by `[tool.coverage.run].source` in
  `pyproject.toml`, so a path added there cannot be missed by a command
  line that still names the old two. This repo maintains
  100% line and branch coverage -- a change that drops it needs a test
  added, not a lowered bar. `fail_under = 100` in `pyproject.toml`'s
  `[tool.coverage.report]` enforces that rather than leaving it asserted,
  so the run exits non-zero on a drop. It assumes the full toolchain:
  without pandoc/TeX Live/poppler the render tests self-skip and the
  total falls short for a missing binary rather than a missing test --
  pass `--cov-fail-under=0` on such a host. CI runs both legs against a
  floor rather than exempting either: Linux holds the full 100, and the
  Windows leg -- which installs no `os-deps` and so self-skips the render
  and pdf tests -- holds 95, low enough not to need re-tuning whenever
  toolchain-only code is added and high enough to catch a real collapse.
- **All three linters, at their full paths** (see "The linters, which
  are enforced" below). They are not optional and not CI's job alone --
  `markdownlint` in particular fails on prose that no test touches, so a
  green suite says nothing about it:

  ```bash
  pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks
  ruff check chitragupta scripts .claude/hooks
  markdownlint-cli2 "*.md" "docs/**/*.md" ".claude/**/*.md" "plans/**/*.md"
  ```

- `poetry check`.
- At least one real end-to-end smoke test that exercises the actual
  change against real dependencies, not only its mocked unit tests --
  e.g. if you touch a CLI script, run it for real; if you touch
  `chitragupta/enrich/*` and the `enrich` Poetry group is installed, run it against
  the real sentence-transformers/chromadb/bertopic stack, not just
  `sys.modules`-mocked fakes. Unit tests catch regressions in logic;
  smoke tests catch wrong assumptions about how the real library actually
  behaves (this project's test suite has caught real fake-vs-real
  behavior drift this way before -- see `tests/test_enrich_embed_index.py`
  and `tests/test_enrich_topic_model.py`'s own comments).

Only once all of the above are green does a task count as complete.

### Reading a red `codecov/project` on a branch you believe is 100%

Believe your local run first, and check the session count before you go
looking for the coverage you lost -- because twice now there was none to
find.

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
status was computed early, not that an upload was lost. Note what that
rules out: on #199 both legs logged `Upload queued for processing
complete` on the first attempt, so the upload step being green was
accurate and `fail_ci_if_error: true` would have changed nothing.
`codecov.yml`'s `after_n_builds` is the gate that holds the notification
until both uploads are in; that file carries the reasoning, and
`tests/test_codecov_upload_gate.py` keeps its number in step with the
matrix. **One session** is the different problem -- a leg that never
produced a `coverage.xml` -- and there the status will sit pending rather
than post a wrong number.

### The linters, which are enforced

`.pylintrc` and `.markdownlint.yaml` are in the tree, adopted from
[DTaaS](https://github.com/INTO-CPS-Association/DTaaS) -- the same source
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) takes its standards
from. `pyproject.toml`'s `[tool.ruff]` is not: DTaaS carries no ruff
config to inherit, so its `select` and `per-file-ignores` were decided
fresh, the way the paragraph below states. Run all three before you push;
`ci.yml`'s `lint` job runs exactly these, and the paths are part of the
command rather than a detail -- a narrower glob is how a tree stops being
checked without anyone deciding it should:

```bash
pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks
ruff check chitragupta scripts .claude/hooks   # config: pyproject.toml's [tool.ruff]
markdownlint-cli2 "*.md" "docs/**/*.md" ".claude/**/*.md" "plans/**/*.md"   # npm i -g markdownlint-cli2
```

**Read the linter's own exit code, not a pipeline's.** `pylint … | tail`
reports `tail`'s status, so a real finding passes for a clean run. That is
not hypothetical: it put a `line-too-long` through a local check and into
CI on 2026-08-15.

**All three are blocking, at a binary zero-messages bar** -- never a
`fail-under` score, because
[R3](docs/AUTO-IMPROVEMENT.md#the-requirements) rules out driving a
number, and a score can improve while the thing you cared about gets
worse. There is no backlog left to avoid: the pylint/markdownlint
adoption in 5.8.0 cleared both to zero first, and ruff's own adoption
did the same, which is this file's own rule that **a check that has not
been made to pass must not ship.**

What that adoption had to settle, since each is a decision a later reader
will otherwise have to re-derive:

- **The encoding sites went first.** Enabling pylint before fixing them
  would have closed the detector on the debt register's top item without
  closing the item. All of the locale-codec encoding item is fixed, not
  just the seven sites pylint could see.
- **Wrapping long lines grew ten registered files.** `line-too-long` and
  the C2 file-length ratchet pull against each other; C0301 won, and the
  counts in `tests/test_code_standards_scan.py` moved with it.
- **`MD060` is off.** Table cell padding, 839 of the 947-finding
  baseline, and the alternative was a diff touching every table in the
  documentation to move spaces around. Everything else is enforced.
- **The enrich group's imports are in `ignored-modules`** rather than
  installed in CI. They are lazy imports inside the functions that need
  them; pylint resolves imports statically wherever they sit, so without
  that list a lint job that does not download torch reports `import-error`
  against all of them.

**What ruff's adoption had to settle**, the same shape of decision, with
no DTaaS config to inherit it from:

- **`select` is `["E", "F", "BLE", "RUF100"]`, not ruff's own (much
  broader) default.** `BLE` is the rule the adoption exists for; `E`/`F`
  are pyflakes/pycodestyle's core correctness checks plus the "keep
  lines short" review rule [CODE-STANDARDS.md's build
  order](docs/CODE-STANDARDS.md#build-order) already named for ruff;
  `RUF100` is what turns a `# noqa: BLE001` into a checked claim instead
  of a comment nothing reads.
- **`per-file-ignores` covers `__init__.py`'s `F401`/`E402`** wholesale
  (`registry/`, `spec/`, `unit/`, `dossier/`, `render_output/`,
  `review/figure_layout/`) rather than 52 per-line `noqa`s: each
  re-exports a submodule's public name so `from chitragupta import x`
  reaches it, four of them via a deliberately late import to dodge a
  circular import at definition time, both already explained inline
  where the comment rules require it.
- **The measurement found two real gaps**, not just inert markers:
  `chitragupta/overlap_skipgram.py`'s `CorpusSkipgramIndex` annotated
  three fields `"array[int]"` with no `array` import in the module (F821
  -- fixed by adding it), and `style_check.language_of`/
  `style_acronym_drift.findings` each caught a blind `Exception` that
  `dossier.dossier_dir` only ever raises as `dossier.DossierError`
  (BLE001 -- fixed by narrowing, not suppressing).
- **One of the 12 existing `# noqa: BLE001` markers was already
  unneeded**, and `RUF100` is what proved it:
  `chitragupta/pdf_text.py`'s `_extract_docling` re-raises via `raise ...
  from exc`, which BLE001's own definition of "blind" exempts. `bench/`'s
  two markers were checked the same way and are genuine --
  [Tier 3.1](docs/TECHNICAL-DEBT.md#31-bench-is-outside-every-check-in-the-repository)
  leaves `bench/` outside every check including this one, unchanged, so
  they stay inert in practice but correct on the evidence.
- **`ruff`'s own version is pinned exactly**, not only for Sonar S8544:
  `RUF100`'s verdict on a given `except` block depends on carve-outs
  (like the re-raise one above) that are undocumented and narrower than
  `BLE001` looks, so an unpinned bump could move that verdict and redden
  the job on a rule this project never touched.

`.gitattributes` (`* text=auto eol=lf`) *is* in force now and needs no
runner: it normalises line endings so CI's Windows leg reads
byte-identical files to the Linux leg, which matters because four tests
here scan this repository's own source.

## Reviewing before you push: the OpenCodeReview plugin

**This is a step in the cycle, not an optional extra.** Step 3 of
[Shipping a code change](#shipping-a-code-change-the-full-cycle) is to run
it on the branch and act on what it finds, before the PR is opened -- the
same standing as the local check suite above it. It is the one review that
happens while the change is still cheap to alter, which is the whole
reason it goes before the PR rather than after.

[OpenCodeReview](https://github.com/alibaba/open-code-review) is a Claude
Code **plugin**, installed per-host from the `alibaba/open-code-review`
marketplace and enabled in the user's own `settings.json`. It is not a
dependency of this repository, is not in `pyproject.toml`, and is not part
of CI -- so it is the developing agent that has to invoke it. Nothing else
will. If the plugin is not available on this host, skip it and **say so in
the PR's test plan**, rather than installing it mid-task or letting its
absence pass unmentioned.

It provides two skills, both of them plugin skills; what differs is who
does the thinking.

| Skill | Who reviews | Needs an LLM endpoint |
|---|---|---|
| `/open-code-review:delegate-review` | **You do.** The skill has OCR select the files and resolve the rules, then hands you each diff to review yourself | **No** |
| `/open-code-review:review` | **A separate model call.** The skill drives `ocr review`, which sends each file to a configured endpoint and returns comments | **Yes** |

**Prefer `delegate-review` here, and not only as a fallback.** It is a
first-class mode -- "LLM-free on the OCR side", in the plugin's own words
-- and it is the better fit for this repository: the agent doing the
reviewing is already carrying
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md), the layer boundaries and
the citekey invariant, which is exactly the context a detached CLI call
does not have. `review` additionally needs `OCR_LLM_URL`/`OCR_LLM_TOKEN`/
`OCR_LLM_MODEL`, `~/.opencodereview/config.json`, or
`ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`; with none set it exits on
`resolve LLM endpoint` and nothing has been reviewed.

**Say how much of the branch it saw, not only which mode ran.** OCR
cannot review Markdown at all -- every `.md` file comes back excluded as
`unsupported_ext` -- so on a prose-heavy branch the review covers a
fraction of the diff. Measured on three consecutive PRs: 9 files of 25
(#199), 8 of 12 (#204), 10 of 21 (#209). "OCR reviewed the branch" is a
much weaker claim on the first kind of branch than the second, and the
test plan should carry the count so a reader can tell them apart.

**Two things about installing it**, neither guessable and both hit on
this host. `npm i -g @alibaba-group/open-code-review@1.9.9` puts the
binary at `$(npm root -g)/../bin/ocr`, which is not on `PATH` by default
-- pinned because the extension list and schema probed below are facts
about this exact release, not about OCR in general; and npm's
`allow-scripts` default blocks the package's postinstall, which is
survivable -- the shipped binary still runs -- but prints a warning that
reads like a failed install.

Whichever runs, **say which one did.** "OCR reviewed the branch" and "I
reviewed the branch against OCR's rules" are different claims, and only
one of them is usually true.

### What the plugin does and does not reach

`.opencodereview/rule.json` is what makes it worth running here. OCR's
built-in rule is generic Python review, and is wrong about this tree in
both directions -- it would flag the dense *why*-comments, the f-string
`PRAGMA` and the deliberately duplicated pool builders, and it does not
know the citekey invariant, the layer boundaries, C1/C2 counted in
statements, or the `encoding="utf-8"` rule. The project file replaces it
for `chitragupta/`, `tests/`, `scripts/`, `bench/` and `.github/`, and excludes
`content/` and `papers/` -- the user's drafts and their personal
bibliography, which are not this repository's code and have no business
being sent to a third-party endpoint.

**It cannot review Markdown, so it cannot review the documents that
govern this project.** OCR opens only extensions it recognises as code
and drops the rest *before* rules are consulted, reporting
`exclude_reason: unsupported_ext`. Probed against open-code-review
v1.9.9: `.py`, `.json`, `.yml`/`.yaml`, `.sh` and `.toml` are reviewed;
`.md`, `.txt`, `.rst` and `.cfg` are not. So `AGENTS.md`, this file,
`docs/CODE-STANDARDS.md` and every skill in `.claude/` are outside it
entirely -- a clean OCR run says nothing about them.

What *does* cover Markdown, so "OCR came back clean" is never read as
"the standing instructions were reviewed": `markdownlint-cli2 "*.md"
"docs/**/*.md" ".claude/**/*.md" "plans/**/*.md"` (see
["The linters, which are enforced"](#the-linters-which-are-enforced)) for
style and structure; `tests/test_technical_debt_scan.py`, the doc-drift
test, for the one class of factual claim that has a machine-readable
source of truth to check against; and a human reading the diff for
everything else -- content, argument, whether a stale sentence is still
true -- which is the one check with no detector and stays that way.

Two traps, both of which have already caught someone:

- **`ocr rules check <path>` is a rule *lookup*, not a coverage check.**
  It resolves a rule for a file OCR would never open, so it will
  cheerfully confirm a Markdown rule that can never fire. The command
  that answers "will this file actually be reviewed?" is
  `ocr delegate preview --format json`, whose `excluded_files` carries
  the reason. `tests/test_opencodereview_rules.py` pins both halves --
  that no glob is orphaned, and that no rule targets an extension OCR
  will not open -- because an orphaned glob fails *open*: OCR silently
  falls back to its built-in rule and still exits 0.
- **The `ocr` binary may not be on `PATH`.** A user-prefix npm install
  puts it in `~/.npm-global/bin`, which is not on the default path, so
  the plugin's own `which ocr` prerequisite check reports NOT INSTALLED
  on a host where it is installed. Check that before concluding the tool
  is absent.

### It is an aid, not a gate

Same standing as the review layer ([SOUL.md](SOUL.md)): nothing here
blocks on it, `python -m chitragupta.draft gate` remains the only gate, and a
finding is a claim to agree or disagree with. Judge each against
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) rather than adopting it
because a tool said so -- a change made only to silence a reviewer is the
failure mode that document's R3 is about. The plugin's `review` skill
offers to apply fixes autonomously; the surgical-changes rule above still
governs what may land in your diff.

The rules in `.opencodereview/rule.json` are themselves prose handed to a
model, and nothing checks that they are obeyed -- a run that reports
clean is not evidence of anything beyond what OCR could open in the
first place.

## Commit messages

Title line: imperative mood, concise, describes the change's effect (not
"updated files" or "misc fixes"). PRs are squash-merged (see "Pull
requests" below), and **the PR title is what lands** --
`squash_merge_commit_title` is `PR_TITLE`, so it is the PR title
unconditionally, whatever the branch's commits are called.

**Never add the PR number by hand**, anywhere: not in the PR title, not
in a branch commit, not in a merge subject. GitHub appends it when it
composes the title (e.g. `Fix reconcile drift detection (#42)`), and it
composes the title every time now. Writing it in as well is how you get
`(#42) (#42)`.

That rule used to carry an exception -- merging with an explicit
`--subject`, which GitHub takes verbatim and appends nothing to, so the
number had to be written in. That exception is **gone**, and so is the
older hazard beside it, that `COMMIT_OR_PR_TITLE` took a one-commit
branch's *commit* title rather than the PR's, so a drifted commit title
landed instead. Both were fixed by the settings in [Merging](#merging),
applied 2026-08-18.

Body: a blank line, then a bulleted list of the specific, concrete changes,
each bullet starting with a present-tense verb (Fix, Add, Remove, Migrate,
Upgrade) and naming what actually changed, not vague summaries. No
preamble paragraph before the bullets. For example (style, not this repo's
literal content):

```text
Fix reconcile drift detection, secret handling, and stale config warnings

- Fix reconcile to detect and reprovision users whose containers are gone,
  refuse `--fix` when Docker is unreachable or `--output-dir` differs
  from cwd.
- Restore secret-file exclusion in build.py, consolidate
  SECRET_FILENAMES, and chmod secret files 0600 unconditionally.
- Warn on stale root `.env` from install/update/generate paths; remove
  dead code no longer reachable after the above.
```

**This body shape is still not what lands by default, and you still have
to state it at merge time.** The title half of that problem is fixed; the
body half is not, and it is worth being exact about why, because the
obvious fix does not work and has already been tried.

Historically the repository ran GitHub's default,
`squash_merge_commit_message = COMMIT_MESSAGES`, which builds the body by
concatenating the branch's commit messages with `*` bullets. Measured over
the 30 commits before 2026-08-18: 14 carried a leading `* <branch commit
title>` line and 8 had a prose body rather than bullets, neither of them
an authoring mistake.

It is now `PR_BODY`, which lands **the pull request description, verbatim**
-- and that is not this shape either. `.github/pull_request_template.md`
is a *review* document: `## Type of Change`, `## Test plan`, `##
Checklist`, all of it with tick-boxes. Merged unedited it puts those
tick-boxes in `main`'s history. **No setting turns one into the other.**
`squash_merge_commit_message` takes exactly three values -- `PR_BODY`,
`COMMIT_MESSAGES`, `BLANK` -- and none of them transforms the text; there
is no templating step between a PR description and a commit body for a
setting to hook into.

So the body is supplied at merge time, by `--body-file` -- see
[Merging](#merging). Not a workaround for an unapplied setting any more;
the setting that would replace it does not exist.

## Merging

Squash -- not by convention, by configuration: `allow_merge_commit` and
`allow_rebase_merge` are both `false`, so it is the only method the
repository offers. Merge with:

```bash
gh pr merge <N> --squash --body-file <path to a body in the shape above>
```

**No `--subject`, and no `(#N)`.** `squash_merge_commit_title` is
`PR_TITLE`, so GitHub composes the title from the PR and appends the
number itself. Passing `--subject` takes your string verbatim instead,
which means re-solving a problem that is now solved and getting `(#42)
(#42)` if you also write the number in.

**`--body-file` is still needed, and is not a leftover.** The body
setting is `PR_BODY`, which lands the PR description verbatim -- review
tick-boxes and all -- so without this flag `main`'s history gets
`.github/pull_request_template.md` rather than a commit message. As
["Commit messages"](#commit-messages) sets out, no value of
`squash_merge_commit_message` produces the documented shape, because none
of them transforms the text. Write the file in the bulleted shape rather
than piping raw branch commits into it, which just reproduces the old
`*`-concatenated default by another route.

The point is not the exact incantation. It is that the format becomes
something a command produces, not something a person has to remember at
the end of a long session, in a browser, after CI has gone green. That is
this project's standing answer to guidance that does not stick: the
ratchet, the citation gate, and this are the same move
([docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md#why-a-ratchet-suits-this-project-specifically)).

### What the repository settings fixed, and what they could not

Applied 2026-08-18 (#238), after being recorded here undone for long
enough to be worth saying which half each one closed:

```bash
gh api -X PATCH repos/prasadtalasila/chitragupta \
  -f squash_merge_commit_title=PR_TITLE \
  -f squash_merge_commit_message=PR_BODY \
  -F allow_merge_commit=false -F allow_rebase_merge=false
```

- **`PR_TITLE` closed the title completely.** "GitHub uses the PR title"
  is now unconditional rather than true only on a multi-commit branch,
  and the `(#N)`-by-hand exception this file used to carry is gone with
  it. Nothing about a title has to be remembered at merge time.
- **`PR_BODY` did not close the body**, and the expectation that it would
  was a reasoning error worth leaving on the record rather than quietly
  correcting: #238 argued the squash body could be the PR description
  because the PR template "already shapes" it. It does shape it -- into a
  review document, which is a different artefact from a commit message.
  The improvement is real but narrower than claimed: the fallback when
  someone forgets `--body-file` is now a verbose template instead of
  `*`-concatenated commit titles. Both are wrong; the new one is wrong
  more legibly.
- **Disabling the other two methods** made "Merge method: squash" a fact
  about the repository rather than a sentence in this file, which is the
  one of the three that needed no follow-up.

The general lesson, since this file is where process claims live: a
setting closes a gap only where a machine can do the whole job. Titles
are mechanical, so a setting finished them. A commit body is a piece of
writing addressed to a different reader than a PR description, and no
enum value writes it for you.

## Issues and pull requests

Templates live in `.github/`, where GitHub picks them up automatically --
don't restate their section list here:

- `.github/pull_request_template.md` -- auto-populates every new PR.
- `.github/ISSUE_TEMPLATE/bug_report.md` and
  `.github/ISSUE_TEMPLATE/feature_request.md`.

A PR title is held to the same bar as a commit's title line: concise,
describes the effect -- and it is now held to it literally, since
`squash_merge_commit_title = PR_TITLE` makes the PR title the commit
title on `main` whatever the branch's commits are called. The template's
**Test plan** section is not a formality -- fill it from what you
actually ran (see "Before claiming a task complete" above), not from what
you intended to run.

The template stays a review document and is not written to double as a
commit message. That is a deliberate split, not an oversight: a reviewer
needs the test plan and the checklist, and `main`'s history does not.
[Merging](#merging)'s `--body-file` is what keeps them apart -- omit it
and the whole template, tick-boxes included, becomes the commit body.

Merge method: squash, enforced by the repository rather than by this
sentence -- see [Merging](#merging). Each PR becomes exactly one commit
on `main`.

## Versioning and releases

Semantic versioning (`pyproject.toml`'s `[tool.poetry].version`), bumped
according to the most significant change in the release, not the number
of commits:

- **PATCH** (x.y.Z): bug fixes, documentation-only changes, CI/workflow-only
  changes, test-only additions -- nothing that changes what the pipeline
  does or how it's invoked.
- **MINOR** (x.Y.0): new backward-compatible functionality -- a new
  script, a new `chitragupta/` module, a new optional config key, a performance
  improvement that doesn't change output shape.
- **MAJOR** (X.0.0): breaking changes -- anything that changes an
  existing citekey/output format, removes or renames a `config.toml` key
  without a fallback, changes a CLI's argument shape, or otherwise
  requires an existing user to change how they invoke or configure the
  pipeline.

Release notes go in the GitHub Release body, not the git tag message.
`.github/RELEASE_TEMPLATE.md` has the shape to follow -- GitHub does *not*
pick that file up automatically, so copy from it by hand when drafting a
release.

## Shipping a code change: the full cycle

Any change that touches code (not a docs-only change) goes through the
complete cycle, and isn't done until every step below has actually
succeeded -- not merely started:

1. Branch off `main`, commit (see "Commit messages" above), push.
2. Decide the version bump (see "Versioning and releases") and update
   `pyproject.toml` as part of the same branch -- `release.yml` verifies
   the pushed tag against `pyproject.toml`'s version on `main`, so the
   bump has to land *before* the tag exists, i.e. in this PR, not after.
3. Run the [OpenCodeReview plugin](#reviewing-before-you-push-the-opencodereview-plugin)
   over the branch and act on what it finds. Nothing invokes it for you --
   it is not in CI and not a dependency -- so if this step is skipped it
   simply does not happen. Record in the PR's test plan which skill ran,
   or that the plugin was unavailable.
4. Open a PR against `main` (see "Issues and pull requests" above).
5. Wait for `.github/workflows/ci.yml` to complete on the PR and confirm
   it's green -- if it fails, fix the actual cause (see "Before claiming a
   task complete") and push again; don't merge past a red check.
6. Request review from Copilot, resolve every issue it identifies, and
   mark each as resolved; consider all previous Copilot comments made in
   this PR while resolving the issues. Make a push after all issues are
   resolved, and then request re-review from Copilot. Iterate until all
   issues are resolved. Use judgement on a genuinely trivial finding
   rather than treating every comment as mandatory -- but "trivial" means
   actually inconsequential (a wording nit), not "inconvenient to fix."
7. **Check that `main` has not moved since CI last ran.** If it has,
   merge or rebase onto it and **do the whole cycle again from step 2** --
   re-decide the version bump, re-run every local check, and wait for CI
   on the new head. A branch that went green against an older `main` is
   not evidence about the merge commit, which is what actually lands.

   This is not bookkeeping. CI already builds the *merge* commit for a
   `pull_request` event, so a stale branch can go red for something it did
   not do -- and, worse, can go **green on a state that no longer
   exists**. Both were seen on 2026-08-15: #204's `lint` failed on
   over-length lines that arrived from `main` in #198, and #209 merged
   cleanly onto a version `main` had already taken, landing on `main`
   claiming a release it was not. The version is the usual casualty,
   because two branches picking the *same* number produce a
   byte-identical line that git merges without a conflict --
   `scripts/check_version_bump.py` now fails CI on that, but it can only
   fail on a run that actually happened.
8. Squash-merge the PR.
9. Tag `v<version>` (matching what's now in `main`'s `pyproject.toml`) and
   push the tag.
10. Confirm `.github/workflows/release.yml` completed and the resulting
   GitHub Release has its `chitragupta-<version>.zip` asset
   attached -- this is the actual deliverable, not the tag or the merge
   by itself.
