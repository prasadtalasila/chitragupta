# DEVELOPER-AGENTS.md

Guidance for coding agents (and anyone else) **working on this repository
itself**, as opposed to using it to draft content. The user-facing half is
[AGENTS.md](AGENTS.md); the why behind both is [SOUL.md](SOUL.md).

[AGENTS.md](AGENTS.md)'s citekey invariant binds code here too: no module
may generate, guess or rewrite a citekey, and no new check may be promoted
into a gate beside `src/citation_gate.py`.

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

`src/references.py` formats an IEEE bibliography entry (authors, venue,
volume, pages) from the ledger's `bib_fields` column, which `sync`
populates via `bib_reader` -- it does not, and must not, parse
`bibliography.bib` itself. The one thing that legitimately reads the bib
file directly is pandoc's `--citeproc`, which is not this codebase. See
[AGENTS.md](AGENTS.md) for why `bib_reader` is the sole reader.

What a part *does* and what it *costs to install* are separate axes:
`src/render_output.py` is drafting-layer code that needs no package from
the `enrich` group, which is why it sits in `src/` rather than
`src/enrich/`. `src/review/verbatim_check.py` is the same axis read the
other way: it sits beside the two aids it belongs with, not in
`scripts/`, which holds dev tooling and no layer entry point at all.

## Environment constraints on this host

`pip install` outside a venv is blocked (PEP 668) -- unconditionally, on
every host, regardless of root access. **This matters for the corpus
layer too**: `python -m src.corpus sync` needs `bibtexparser` (parsing
`bibliography.bib` correctly -- nested braces, LaTeX escapes -- isn't
worth hand-rolling), so it must be run via the installed venv, not the
bare system interpreter. `python -m src.draft gate` is the exception
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
  without saying so. Every `src/enrich/*` stage already self-probes its
  own prerequisites and reports honestly (`ok`/`skipped`/`missing-binary`)
  via `src/enrich/__main__.py` rather than assuming the target implies
  availability -- keep any new stage consistent with that pattern instead
  of inventing a new fallback policy.

Install everything with:
```
bash scripts/install_full_pipeline.sh              # Python deps only (default) -- what every host needs regardless of OS packages
bash scripts/install_full_pipeline.sh os-deps      # apt-get: TeX Live, Pandoc, poppler-utils, OpenCV runtime, Poetry, zip/unzip -- needs root, opt-in
bash scripts/install_full_pipeline.sh dev-deps     # pytest/pytest-cov, to run the test suite -- opt-in
bash scripts/install_full_pipeline.sh all          # os-deps + python-deps
```
This is **the single install script for both the host and Docker and CI**
-- `docker/Dockerfile` calls it once per stage as separate `RUN` lines, and
`.github/workflows/ci.yml` calls it directly too, rather than any of them
having their own separate apt-get/pip/poetry install logic. Python
dependencies are managed by Poetry as a lockfile/venv manager only
(`package-mode = false` in `pyproject.toml` -- nothing here is published
or pip-installable). If you find a dependency-order issue, fix it once in
`pyproject.toml` (+ `poetry lock` to update `poetry.lock`) and every
target picks it up. Don't add a second install path.

`docker/` (Dockerfile) builds the same TeX Live/Pandoc stack inside a
container instead, for hosts where the
`os-deps` assumption above doesn't hold (no root, or root deliberately
withheld). **It has still not been built or run in this environment** (no
Docker daemon here) -- treat it as a draft to validate, not a tested
artifact.

## The enrichment layer (`src/enrich/`, `src/enrich/__main__.py`)

Implements Docling -> sentence-transformers/Chroma ->
BERTopic -> Pandoc/LaTeX, one script for both host and Docker. Each stage
self-probes its own prerequisites (pandoc/pdflatex on PATH) and
reports honestly (`skipped`/`missing-binary`) rather than assuming the
target implies availability -- don't "fix" a skip by hardcoding
target-specific behavior; fix the probe if it's wrong. `--target
host|docker` is **informational only** for exactly that reason: the
probes decide, not the flag, so nothing branches on it.

`src/enrich/embed_index.py`, `src/enrich/topic_model.py`, and
`src/enrich/docling_parse.py` are all incremental, mirroring
`src/ledger.py`'s own skip-what-hasn't-changed logic for the corpus
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

`src/enrich/corpus.py` sources the enrichment corpus from the ledger and
nothing else, so every document it yields is citable and
keyed by its citekey alone. Keep it that way -- the enrichment layer must never
index a document a draft would not be allowed to cite. If a paper is
worth enriching, it belongs in the reference manager: catalogue it,
re-export, and re-run `python -m src.corpus sync`.

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

## Before claiming a task complete: run all local checks

Never report a task as done on the strength of a plan or a code read alone.
Before saying so, actually run, in this repo:

- The full test suite with coverage: `.venv-full/bin/python -m pytest
  --cov=src --cov=scripts --cov-report=term-missing`. This repo maintains
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
- `poetry check`.
- At least one real end-to-end smoke test that exercises the actual
  change against real dependencies, not only its mocked unit tests --
  e.g. if you touch a CLI script, run it for real; if you touch
  `src/enrich/*` and the `enrich` Poetry group is installed, run it against
  the real sentence-transformers/chromadb/bertopic stack, not just
  `sys.modules`-mocked fakes. Unit tests catch regressions in logic;
  smoke tests catch wrong assumptions about how the real library actually
  behaves (this project's test suite has caught real fake-vs-real
  behavior drift this way before -- see `tests/test_enrich_embed_index.py`
  and `tests/test_enrich_topic_model.py`'s own comments).

Only once all of the above are green does a task count as complete.

### The linters, which are configured but not yet enforced

`.pylintrc` and `.markdownlint.yaml` are in the tree, adopted from
[DTaaS](https://github.com/INTO-CPS-Association/DTaaS) -- the same source
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) takes its standards
from -- so a baseline is reproducible on any host:

```bash
pylint --rcfile=.pylintrc src scripts        # needs the project's deps importable
markdownlint-cli2 "*.md" "docs/**/*.md"      # npm i -g markdownlint-cli2
```

**Neither is in CI, and neither is a check you have to pass yet.** Run
them on code you touched and fix what is clearly yours; do not go fixing
the backlog in an unrelated diff. Both baselines are measured in
[docs/TECHNICAL-DEBT.md's Tier 5](docs/TECHNICAL-DEBT.md#tier-5-continuous-integration-and-the-linters)
-- 44 real pylint findings after the deliberate categories are disabled,
and 100 markdownlint findings once the cosmetic `MD060` is set aside --
along with the disable list and the order the two should be adopted in.

They are deliberately not wired into `ci.yml` yet, and the reason is a
rule from this file rather than a preference: **a check that has not been
made to pass must not ship.** Enabling pylint today would mean either a
red build or suppressing `unspecified-encoding`, which is the top item on
the debt register -- closing the detector without closing the defect. The
order is: fix the encoding sites, fix the long lines, then enable, at a
binary zero-messages bar rather than a `fail-under` score.

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
for `src/`, `tests/`, `scripts/`, `bench/` and `.github/`, and excludes
`content/` and `papers/` -- the user's drafts and their personal
bibliography, which are not this repository's code and have no business
being sent to a third-party endpoint.

**It cannot review Markdown, so it cannot review the documents that
govern this project.** OCR opens only extensions it recognises as code
and drops the rest *before* rules are consulted, reporting
`exclude_reason: unsupported_ext`. Probed against the installed binary:
`.py`, `.json`, `.yml`/`.yaml`, `.sh` and `.toml` are reviewed; `.md`,
`.txt`, `.rst` and `.cfg` are not. So `AGENTS.md`, this file,
`docs/CODE-STANDARDS.md` and every skill in `.claude/` are outside it
entirely -- a clean run says nothing about them, and doc drift stays a
human's job.

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
blocks on it, `python -m src.draft gate` remains the only gate, and a
finding is a claim to agree or disagree with. Judge each against
[docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md) rather than adopting it
because a tool said so -- a change made only to silence a reviewer is the
failure mode that document's R3 is about. The plugin's `review` skill
offers to apply fixes autonomously; the surgical-changes rule above still
governs what may land in your diff.

## Commit messages

Title line: imperative mood, concise, describes the change's effect (not
"updated files" or "misc fixes"). PRs are squash-merged (see "Pull
requests" below), so write commits and PR titles as if either one could
become the commit title on `main`, and don't add the PR number by hand --
GitHub appends it (e.g. `Fix reconcile drift detection (#42)`).

**Which of the two GitHub actually uses is a repository setting, and this
repository's setting means it depends on your branch.**
`squash_merge_commit_title` is `COMMIT_OR_PR_TITLE`: with two or more
commits on the branch GitHub takes the PR title, with exactly one it takes
that commit's title. So a one-commit branch whose commit title has drifted
from the PR title lands the commit's, not the PR's. Keep them the same, or
merge with an explicit subject -- see [Merging](#merging).

Body: a blank line, then a bulleted list of the specific, concrete changes,
each bullet starting with a present-tense verb (Fix, Add, Remove, Migrate,
Upgrade) and naming what actually changed, not vague summaries. No
preamble paragraph before the bullets. For example (style, not this repo's
literal content):

```
Fix reconcile drift detection, secret handling, and stale config warnings

- Fix reconcile to detect and reprovision users whose containers are gone,
  refuse `--fix` when Docker is unreachable or `--output-dir` differs
  from cwd.
- Restore secret-file exclusion in build.py, consolidate
  SECRET_FILENAMES, and chmod secret files 0600 unconditionally.
- Warn on stale root `.env` from install/update/generate paths; remove
  dead code no longer reachable after the above.
```

**This body shape is not what lands on `main` by default, and that is the
single biggest reason it is not adhered to.** Measured over the last 30
commits: 14 carry a leading `* <branch commit title>` line, and 8 have a
prose body rather than bullets. Neither is an authoring mistake. The
repository's `squash_merge_commit_message` is GitHub's default,
`COMMIT_MESSAGES`, which builds the squash body by concatenating the
branch's commit messages with `*` bullets -- so the shape above survives
only if whoever merges hand-edits the body in the web UI, every time,
forever. Writing the rule down more emphatically cannot fix a default.
[Merging](#merging) is where it is fixed.

## Merging

Squash, always. Do it with a command that *states* the title and body
rather than accepting what GitHub composes:

```bash
gh pr merge <N> --squash \
  --subject "$(gh pr view <N> --json title --jq .title)" \
  --body-file <(git log origin/main..HEAD --reverse --pretty=format:%b)
```

The point is not the exact incantation -- edit the body to the bulleted
shape above before passing it. The point is that the format becomes
something a command produces, not something a person has to remember at
the end of a long session, in a browser, after CI has gone green. That is
this project's standing answer to guidance that does not stick: the
ratchet, the citation gate, and this are the same move
([docs/CODE-STANDARDS.md](docs/CODE-STANDARDS.md#why-a-ratchet-suits-this-project-specifically)).

**Three repository settings would make it structural instead**, and are
the actual fix -- they need a maintainer with admin rights, so they are
recorded here rather than done:

```bash
gh api -X PATCH repos/prasadtalasila/chitragupta \
  -f squash_merge_commit_title=PR_TITLE \
  -f squash_merge_commit_message=PR_BODY \
  -F allow_merge_commit=false -F allow_rebase_merge=false
```

- `PR_TITLE` makes "GitHub uses the PR title" true unconditionally,
  rather than only on a multi-commit branch.
- `PR_BODY` makes the squash body the PR description -- which
  `.github/pull_request_template.md` already shapes -- and retires the
  `*`-concatenated default that produced 14 of the last 30 bodies.
- Disabling the other two merge methods makes "Merge method: squash" a
  fact about the repository rather than a sentence in this file.

Until they are set, the `gh pr merge` form above is the workaround, and
the rule genuinely is harder to follow than it reads.

## Issues and pull requests

Templates live in `.github/`, where GitHub picks them up automatically --
don't restate their section list here:

- `.github/pull_request_template.md` -- auto-populates every new PR.
- `.github/ISSUE_TEMPLATE/bug_report.md` and
  `.github/ISSUE_TEMPLATE/feature_request.md`.

A PR title is held to the same bar as a commit's title line: concise,
describes the effect. The template's **Test plan** section is not a
formality -- fill it from what you actually ran (see "Before claiming a
task complete" above), not from what you intended to run.

Merge method: squash -- see [Merging](#merging) for the command and for
why the default does not produce the documented shape. Each PR becomes
exactly one commit on `main`, so keep the PR title accurate even when the
branch itself carries several intermediate commits.

## Versioning and releases

Semantic versioning (`pyproject.toml`'s `[tool.poetry].version`), bumped
according to the most significant change in the release, not the number
of commits:

- **PATCH** (x.y.Z): bug fixes, documentation-only changes, CI/workflow-only
  changes, test-only additions -- nothing that changes what the pipeline
  does or how it's invoked.
- **MINOR** (x.Y.0): new backward-compatible functionality -- a new
  script, a new `src/` module, a new optional config key, a performance
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
7. Squash-merge the PR.
8. Tag `v<version>` (matching what's now in `main`'s `pyproject.toml`) and
   push the tag.
9. Confirm `.github/workflows/release.yml` completed and the resulting
   GitHub Release has its `chitragupta-<version>.zip` asset
   attached -- this is the actual deliverable, not the tag or the merge
   by itself.
