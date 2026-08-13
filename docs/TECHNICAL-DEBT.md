# Technical debt: what is owed, and what only looks like it

Status: **register, not a standard.** Written 2026-08-13, from a
full-tree review of `src/`, `scripts/`, `bench/`, `docker/` and
`.github/`. Nothing here is enforced. The one part of this project's debt
that *is* enforced -- the C1/C2 ratchet -- lives in
`tests/test_code_standards_scan.py` and is
[pointed at](#tier-1-the-debt-the-ratchet-already-holds), never restated.

[CODE-STANDARDS.md](CODE-STANDARDS.md) says what the code must look like.
This document says where it currently doesn't, and -- just as important --
where it looks like it doesn't but is right.

**Written for** someone deciding what to take next, and for the agent that
picks this repository up cold and needs to know which surprising thing is
a bug and which is a decision. It assumes
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md) for the process around a
change and [CODE-STANDARDS.md](CODE-STANDARDS.md) for the standard itself.

**Not covered here:** anything about drafts ([AGENTS.md](../AGENTS.md)),
prose standards ([WRITING-STANDARDS.md](WRITING-STANDARDS.md)), or
features not yet built --
[AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md) owns the roadmap and this
document owns the arrears. A thing that was never built is not a debt.

## Table of contents

- [How something gets on this list](#how-something-gets-on-this-list)
- [Tier 1: the debt the ratchet already holds](#tier-1-the-debt-the-ratchet-already-holds)
- [Tier 2: the debt CODE-STANDARDS.md already named](#tier-2-the-debt-code-standardsmd-already-named)
- [Tier 3: found by review, tracked nowhere](#tier-3-found-by-review-tracked-nowhere)
- [What is not debt](#what-is-not-debt)
- [What to take first](#what-to-take-first)

## How something gets on this list

Three conditions, all of them:

1. **It is a cost already incurred**, not a feature not yet written.
   "`src/dossier.py` is 1605 code lines" qualifies. "There is no citation
   graph" does not -- that is [AUTO-IMPROVEMENT.md](AUTO-IMPROVEMENT.md)'s
   agenda, and confusing the two turns a debt register into a wish list,
   which is how registers stop being read.
2. **It names a file, a count, or a call site.** "The code could be
   cleaner" is a score, and
   [R3](AUTO-IMPROVEMENT.md#the-requirements) -- the rule
   CODE-STANDARDS.md is built on -- rules out driving a score to zero.
   Every entry below carries a number or a path someone can open.
3. **Someone would be worse off if it were left.** A stylistic
   disagreement is not debt.

It comes **off** the list the way it went on: in its own pull request,
against this file. That is the same discipline
[the ratchet](CODE-STANDARDS.md#what-a-ratchet-is-and-the-debt-register)
imposes on C1/C2, applied by hand to the items no detector covers.

This file is **not** a gate and gains no test. `python -m src.draft gate`
remains the only gate in the project ([SOUL.md](../SOUL.md)), and a debt
list that could fail a build would be a threshold tuned to today's worst
code -- exactly what the ratchet exists to avoid.

## Tier 1: the debt the ratchet already holds

`tests/test_code_standards_scan.py` freezes **28 functions** over C1 (25
statements) and **12 modules** over C2 (250 code lines), each with its
current size in a trailing comment that
`test_every_registered_offender_records_its_current_count` keeps honest.

**That register is the authority. This section does not copy it** -- a
debt stated in two places is a debt that will eventually be stated two
different ways, and only one of the two is checked on every run. What
follows is the thing the register cannot carry: where the two largest
entries would actually split.

### `src/sync.py::run` -- 117 statements, 4.7x the next worst

The register names it and CODE-STANDARDS.md calls it the first to take.
Reading it, the seams are visible and are not arbitrary: the function
runs **probe -> resolve -> dispatch -> drain -> reconcile -> summarise**,
and only the middle two are about parsing at all. The drain loop
(`src/sync.py:398-448`) is a self-contained "apply results in bib order"
with four exclusive branches -- parsed, backend-vanished, timed-out,
failed -- each already carrying its own rationale comment. The reconcile
step after it (`stale`/`prune_missing`) shares no state with the parse
except `seen_citekeys`.

The reason to say this here rather than in the register: the register's
trailing `# 117` says how big the debt is, not that it is *separable*. A
117-statement function that genuinely could not split would be a
different problem.

### `src/dossier.py` -- 1605 code lines, and four responsibilities

The largest module in the tree, and the one whose split is least
ambiguous. By line range it is already four modules stacked:

| Lines | Responsibility |
|---|---|
| 112-1050 | The dossier data model -- paths, sections, citekeys, evidence blocks, retrieval log |
| 1052-1500 | Status, brief and drift reporting over that model |
| 1505-1670 | Archive bundle / export / restore (`tarfile`, member checking) |
| 1670-2149 | The `argparse` CLI: eleven `_cmd_*` functions plus `main` |

Four of the register's 28 C1 offenders (`_cmd_status`, `main`,
`_cmd_brief`, `_cmd_status_all`, `_print_drift`) sit in that last block,
which is the shape CODE-STANDARDS.md predicts: "a `main()` that parses
arguments, does the work, and formats the output -- most of the C1
register has that shape."

Note what splitting it would *not* fix. C2 permits a registered module to
grow ([deliberately](CODE-STANDARDS.md#what-a-ratchet-is-and-the-debt-register)),
so nothing fails today; this is debt because a reader looking for the
export format has to know it is not in the first 1500 lines.

## Tier 2: the debt CODE-STANDARDS.md already named

[Build order](CODE-STANDARDS.md#build-order) lists four things that would
extend the enforced half, none of them built. They are debt rather than
roadmap because each has a **cost already being paid**, measured below.
The build order owns the sequencing; this section only supplies the
numbers it was written without.

### The 11 inert `# noqa: BLE001` markers

`src/` and `scripts/` carry 11 `# noqa: BLE001` suppressions
(`runlock.py`, `pdf_text.py` x5, `enrich/__main__.py`,
`enrich/docling_parse.py` x3) and **no linter is configured** --
`pyproject.toml` has no `ruff`, `flake8`, `pylint` or `mypy` section, and
no workflow invokes one. BLE001 is a ruff rule code.

The markers are not harmful; each sits beside a real *why*-comment
explaining the broad catch, which is what CODE-STANDARDS.md's comment
rules actually require. But they are a suppression list for a tool that
cannot read them, which means it has never been checked that the
suppressed set is the *right* set. Build-order item 2 anticipates exactly
this ("the register above and ruff's ignore list are two debt lists; they
should be one") -- it just assumes ruff arrives first. It has not.

### Type annotations: 288 of 383, and one module at zero

Build-order item 3 says "`src/` is partly annotated." It is 75%
(288 of 383 `def`s carry a return annotation), and the distribution is
the finding rather than the total:

| Module | Annotated |
|---|---|
| `src/review/verbatim_check.py` | **0 / 47** |
| `src/review/citation_provenance.py` | 16 / 17 |
| `src/review/citation_coverage.py` | 11 / 12 |
| `src/review/__init__.py` | 10 / 10 |
| `src/runlock.py` | 3 / 7 |
| `src/sync.py` | 4 / 8 |
| `src/dossier.py` | 62 / 65 |

`verbatim_check.py` is the second-largest module in the repository and
the only one in the tree with no annotations at all, sitting beside three
siblings that are effectively complete. That is the
[Be consistent](CODE-STANDARDS.md#understandability) rule -- which that
document calls "the highest-value one in this list" -- and it is a
review finding today, independent of whether a checker is ever adopted.

## Tier 3: found by review, tracked nowhere

New in this review. Each names a call site.

### 3.1 Text I/O on the locale codec, including the gate itself

**The most severe item in this document.** 32 of `src/`'s 67 text-I/O
call sites call `read_text()` / `write_text()` / `open()` with **no
`encoding=`**, so they use the host's locale codec:

| Module | Sites without `encoding=` |
|---|---|
| `src/render_output.py` | 8 / 8 |
| `src/enrich/docling_parse.py` | 7 / 11 |
| `src/references.py` | 4 / 4 |
| `src/enrich/embed_index.py`, `src/enrich/topic_model.py` | 3 / 3 each |
| `src/runlock.py` | 2 / 2 |
| `src/citation_gate.py`, `src/review/citation_coverage.py`, `src/pdf_text.py`, `src/retrieval.py` | 1 / 1 each |
| `src/dossier.py` | 1 / 12 |

This project already knows the rule. Four test modules --
`test_code_standards_scan.py:194`, `test_command_depth_scan.py:39`,
`test_removed_command_scan.py:102`, `test_review_entrypoint.py:45` --
each carry a comment saying `encoding="utf-8"` is passed because
"`read_text()` uses the locale codec, which is cp1252 on the Windows CI
leg, and these files are full of em dashes." CI sets no `PYTHONUTF8`.
The rule is understood, written down four times, and applied to fewer
than half of `src/`'s own call sites.

Three sites make this more than tidiness:

- **`src/citation_gate.py:191`** -- `check_document` reads the draft with
  the locale codec. A draft containing any character outside the host's
  codec raises `UnicodeDecodeError` and the gate exits on a traceback
  instead of a verdict. This is the one gate in the project
  ([CLAUDE.md](../CLAUDE.md)); a gate that crashes is a gate that did not
  run, which is the failure mode the whole design exists to prevent.
- **`src/render_output.py:151`** -- reads `bibliography.bib`. Author
  names with diacritics are the norm, not the exception, in a real
  reference export.
- **`src/references.py:430,451`** -- *writes* the rendered bibliography.
  The failure here is `UnicodeEncodeError` on output, after the work is
  done.

Why it has not been caught: an encoding-less write followed by an
encoding-less read round-trips correctly for any character the host codec
can represent, and cp1252 covers the em dash the test comments name. The
break needs a character outside it -- a Greek letter in a title, a CJK
author name, a `≥` in a quoted excerpt -- on a non-UTF-8 host. Linux CI
is UTF-8 and cannot see it.

**Fix shape:** pass `encoding="utf-8"` at all 32 sites. Mechanical, but
it is a code change and belongs in its own PR with a test that reads a
draft containing a non-cp1252 character.

### 3.2 `_executor_for` duplicated across a module boundary

`src/sync.py:66` and `src/enrich/docling_parse.py:430` both build the
docling process pool -- same `process_pool_context()`, same
`usable_devices()`, same `initargs` shape. The duplication is
**deliberate and documented**: `docling_parse`'s docstring says it is
kept local "so that `src/enrich/` doesn't depend on the core entrypoint
-- the dependency runs the other way everywhere else in this repo," and
that reasoning is sound.

It is still debt, of the **fragility** kind
([the review vocabulary](CODE-STANDARDS.md#code-smells-the-review-vocabulary)):
the two builders must agree about what `init_worker` is handed, the
docstring says so explicitly, and nothing checks it. A third argument
added to `init_worker` has to be added twice or the enrichment pool
starts workers the core pipeline would not. The resolution is a shared
helper in `src/pdf_text.py` -- which both already import, so it costs no
new dependency edge in either direction -- not a change to the layering.

### 3.3 `bench/` is outside every check in the repository

2021 lines of Python across 8 files, and it is excluded from all four
things that hold the rest of the tree:

- C1 and C2 (`STATEMENT_ROOTS`/`CODE_LINE_ROOTS` in the scan test)
- coverage (`source = ["src", "scripts"]` in `pyproject.toml`)
- the release archive (`scripts/release.py`)
- any linter, since there is none

Measured against the ratchet it does not face, `bench/` holds **8
functions over C1** and **2 modules over C2** (`repro_check.py` at 530
code lines, `sweep_sync.py` at 282).

CODE-STANDARDS.md states the exclusion and its reason -- one-shot
analysis code whose `main()` reads top to bottom on purpose -- and
explicitly prefers saying so to "the alternative reading, which is that
its 8 long functions were quietly not counted." That is the right call
for C1/C2. The debt is the **untested** half, which no document
addresses: `bench/repro_check.py` at 700 physical lines is the tool that
decides whether a parser change reproduces, and nothing verifies it
still works. A wrong answer from it is a wrong answer about the parser.

### 3.4 `docker/Dockerfile` has never been built

DEVELOPER-AGENTS.md is explicit -- "It has still not been built or run in
this environment (no Docker daemon here) -- treat it as a draft to
validate, not a tested artifact." No workflow under `.github/` builds it
either: `grep -r docker .github/workflows/` returns nothing.

So the documented answer for "hosts where the `os-deps` assumption
doesn't hold (no root, or root deliberately withheld)" is 56 lines that
have never executed anywhere, and [DOCKER.md](../DOCKER.md) is published
documentation for it. Honest labelling is not the same as working code.
The cheap fix is a `docker build` job in CI; it needs no daemon-in-daemon
tricks and no registry push to be worth having.

### 3.5 `scripts/install_full_pipeline.sh` -- 333 lines, no static check

The single install path for host, Docker and CI, called by
`docker/Dockerfile` (three times) and `.github/workflows/ci.yml`
directly. CI does exercise it on both legs, which is real verification of
the happy path -- this is not untested code. But it is 333 lines of shell
with no `shellcheck`, and its most delicate part
(`ensure_gpu_torch`, which reinstalls torch from a driver-matched wheel
index after Poetry resolves a different one) runs on neither CI leg,
since no runner has a GPU. That function's failure mode is a silently
wrong torch build.

### 3.6 The Windows coverage floor is a 5-point blind spot

`.github/workflows/ci.yml:110-111` holds Linux at `fail_under=100` and
Windows at 95. The reason given is good and specific: Windows gets
`python-deps` only, `os-deps` is apt-only, so ~30 render and pdf tests
self-skip.

The debt is that 95 is a *floor*, not a *target*: the 5 points are not
attributed to the skipped tests, so Windows-only code that no test
reaches is indistinguishable from a render test that self-skipped. This
matters precisely for [3.1](#31-text-io-on-the-locale-codec-including-the-gate-itself),
whose failure mode is Windows-specific. Attributing the gap -- via
`# pragma: no cover` on the toolchain-dependent branches, or a second
`.coveragerc` for the Windows leg -- would turn a floor into the same
100 the Linux leg holds.

### 3.7 `connect()` / `try` / `finally: close()` repeated at eight sites

`src/citation_gate.py:199`, `src/references.py:422,441`,
`src/retrieval.py:292,369`, `src/sync.py:339`,
`src/review/citation_provenance.py:313`, `src/enrich/corpus.py:48` all
open a ledger connection and close it in a `finally`. Every one is
correct -- this is not a leak -- but CODE-STANDARDS.md's threshold for
extraction ("two similar blocks are a coincidence; three are a pattern")
is passed twice over. A `ledger.connection()` context manager would make
the eight call sites two lines shorter each and make a future ninth
impossible to get wrong.

Lowest-value item here, listed because leaving it out would mean the next
reviewer finds it again.

## What is not debt

The other half of this document's job. Every item below looks like a
finding to a reviewer applying a checklist, and every one is a decision
with its reasoning attached. Changing any of them makes the codebase
worse.

| Looks like | Actually |
|---|---|
| Very long comments; `.github/workflows/ci.yml` roughly half prose | Required. [The comment rules](CODE-STANDARDS.md#the-comment-rules-and-the-misreading-to-avoid) -- *why*-comments are mandatory here, and the size rules count statements precisely so that explaining yourself is free |
| `con.execute(f"PRAGMA user_version = {target}")` (`src/ledger.py:128`) | Not SQL injection. `PRAGMA` does not accept `?` binding, and `target` is `len(_MIGRATIONS)` -- this module's own constant. The comment above it says exactly that |
| `_load_cache`/`_save_cache` duplicated in `retrieval.py` and `enrich/docling_parse.py` | Different requirements, and each docstring names the difference: retrieval needs a per-writer-unique temp name for concurrent subagents, docling does not and says why |
| 11 broad `except Exception` handlers | Each has a stated cause and a `# noqa` marker. See [Tier 2](#the-11-inert--noqa-ble001-markers) -- the debt is the absent linter, not the handlers |
| `--target host\|docker` accepted but never branched on | Deliberate: the probes decide, the flag is informational. Removing it is a CLI break for no gain |
| C2 permits a registered module to grow | [Deliberate](CODE-STANDARDS.md#what-a-ratchet-is-and-the-debt-register). Pinning each to today's size fails on every ordinary edit and gets the rule turned off |
| No timestamp in any review report | A product rule: two runs over unchanged input produce byte-identical output, so reports diff across revisions |
| Tests duplicate setup instead of DRYing it | [Adopted position](CODE-STANDARDS.md#tests): a test that reads top to bottom is worth more than a DRY one |
| `tests/test_pdf_text.py` at 1806 code lines | C2 does not cover tests, for a stated reason: a test module's length tracks the surface of the module under test |

## What to take first

Ordered by what breaks if it is left, not by size:

1. **[3.1] `encoding="utf-8"` at 32 call sites.** The only item whose
   failure mode is the citation gate crashing. Mechanical, testable, one
   PR.
2. **[Tier 1] `src/sync.py::run`.** 117 statements, separable at six
   named seams, and already the register's designated first job.
3. **[3.4] A `docker build` job in CI.** Cheapest real coverage gain in
   this list -- one workflow job against 56 lines currently verified by
   nothing.
4. **[Tier 2] Annotate `src/review/verbatim_check.py`.** 47 functions,
   no behaviour change, and it removes the tree's only zero.
5. **[Tier 1] Split `src/dossier.py`** along the four ranges above, and
   delist whatever comes back under C1 in the same PR.

Everything below that is real but can wait. Each of the five is one PR:
"several small, reviewable PRs over one large one" applies to this
project's own housekeeping as much as to its features, which is the
reason the register froze today's code rather than fixing it.
