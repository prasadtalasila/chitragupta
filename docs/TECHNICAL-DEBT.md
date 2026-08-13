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
- [Tier 4: the test suite](#tier-4-the-test-suite)
- [Reviewing with OpenCodeReview](#reviewing-with-opencodereview)
- [The standing-instruction budget](#the-standing-instruction-budget)
- [Process debt: the formats that are not adhered to](#process-debt-the-formats-that-are-not-adhered-to)
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

### 3.1 Text I/O on the locale codec

32 of `src/`'s 67 text-I/O call sites call `read_text()` /
`write_text()` / `open()` with **no `encoding=`**, so they use the host's
locale codec:

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

**The two failure modes are not the same, and the difference decides
where this matters.** Both were reproduced against cp1252 rather than
reasoned about, because the intuitive answer is wrong:

- **Writing raises.** `"≥"`, a CJK name and a Cyrillic name each raise
  `UnicodeEncodeError` on a cp1252 host. This is a hard, loud crash,
  and it lands *after* the expensive work is done.
- **Reading almost never raises.** cp1252 leaves only five bytes
  undefined (`0x81`, `0x8D`, `0x8F`, `0x90`, `0x9D`), so a UTF-8 draft
  read back as cp1252 overwhelmingly **succeeds and returns mojibake**:
  `"Films at ≥ 5 nm ... 中文 ... café"` comes back as
  `"Films at â‰¥ 5 nm ... ä¸\xadæ–‡ ... cafÃ©"`. Silent corruption, not a
  traceback.

So the sites that matter are the **writes**, and the read sites matter
only where the text is used as text rather than scanned for ASCII:

- **`src/references.py:430,451`** and **`src/render_output.py:148,171,172`**
  -- write the rendered bibliography and the sanitised markdown/bib
  handed to pandoc. A Cyrillic or CJK author name is ordinary in a real
  reference export, and on a cp1252 host it crashes the render.
- **`src/render_output.py:141,151`** -- read the draft and
  `bibliography.bib` and pass them straight back out to pandoc, so a
  mojibake read becomes a mojibake PDF with no error anywhere.
- **`src/retrieval.py:168`** -- reads parsed text into the BM25 index
  under `errors="ignore"`. Corrupted tokens degrade ranking silently.

**What this is *not*.** `src/citation_gate.py:191` reads the draft the
same way, and it was worth checking whether the project's one gate could
be taken out this way. It cannot: citekeys are ASCII, so
`extract_citekeys()` returns identical results from the correctly-decoded
and the mojibake text (verified on the example above -- both yield
`[(1, 'zhang_2021')]`). The gate is unaffected, and the same reasoning
clears `src/review/citation_coverage.py:73`. Recorded here because the
opposite conclusion is the natural one to jump to.

Why it has not been caught: an encoding-less write followed by an
encoding-less read round-trips for anything the host codec can
represent, and cp1252 covers the em dash the four test comments name.
Linux CI is UTF-8 and cannot see any of it; the Windows leg would, but
only if a fixture fed it a character outside cp1252.

**Fix shape:** pass `encoding="utf-8"` at all 32 sites -- mechanical, one
PR, with a test that renders a bibliography containing a CJK author name.
Writes first if it is split.

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

CODE-STANDARDS.md states the C1/C2 exclusion and its reason -- one-shot
analysis code whose `main()` reads top to bottom on purpose -- and
explicitly prefers saying so to "the alternative reading, which is that
its 8 long functions were quietly not counted." That is the right call.

The **untested** half is the part no document addresses, and it is
narrower than it first looks. `bench/repro_check.py`, the largest of the
eight and the one that decides whether a parser change reproduces,
already handles it: `self_check()` runs from `main()` on every
invocation, and its docstring names this exact gap -- "`bench/` sits
outside CI's coverage targets, so nothing in the test suite will ever
catch a regression here. This runs on every invocation instead." Nine
assertions prove the detector can see a difference before a zero from it
is believed.

That leaves the debt as: **it is a pattern of one.** The other seven
scripts hold no assertion at all, and the guard is a convention in one
file's `main()` rather than anything a new script would inherit or a
reviewer would be reminded of. `bench_drift.py` (336 lines) and
`sweep_sync.py` (366) also publish numbers that decisions are made from.

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
with no `shellcheck`, and its most delicate part is unreached there.

`ensure_gpu_torch` reinstalls torch from a driver-matched wheel index
after Poetry has resolved a different one, walking `cu130 -> cu118` to
find the newest tag at or under the driver's CUDA ceiling. Its first
statement is `if ! command -v nvidia-smi; then return`, and no GitHub
runner has a GPU -- so **both CI legs execute exactly that one line and
stop.** Everything after it, including the `nvidia-smi` output parsing
and the tag walk, has only ever run by hand on one A40 host.

The consequence is the one its own comment describes: torch installs
clean, `torch.cuda.is_available()` returns `False`, and the enrichment
stack runs on CPU with no error anywhere. That is the failure this
function exists to prevent, and it is the failure a regression in it
would silently reintroduce.

### 3.6 The Windows coverage floor is a 5-point blind spot

`.github/workflows/ci.yml:110-111` holds Linux at `fail_under=100` and
Windows at 95. The reason given is good and specific: Windows gets
`python-deps` only, `os-deps` is apt-only, so ~30 render and pdf tests
self-skip.

The debt is that 95 is a *floor*, not a *target*: the 5 points are not
attributed to the skipped tests, so Windows-only code that no test
reaches is indistinguishable from a render test that self-skipped. This
matters precisely for [3.1](#31-text-io-on-the-locale-codec), whose
failure mode is Windows-specific. Attributing the gap -- via
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

## Tier 4: the test suite

21,780 lines across 40 modules, against `src/`'s 13,379 -- the suite is
1.6x the code it tests, holds 100% line and branch coverage, and is in
better shape than the code. A full review found no dead helper, no
order-dependent test, no network access, no `xfail`, no bare
`pytest.raises(Exception)`, and no test writing outside `tmp_path`. Most
of what a checklist would flag here is deliberate and stated: duplicated
setup (a test that reads top to bottom beats a DRY one), long modules
(C2 does not cover tests, for a stated reason), several asserts per test
(one *behaviour* per test), and five assertion-free tests that are each a
documented "does not raise".

Two real findings, both **fixed in the change that adds this section**
rather than left on the list, because both were making the suite fail on
a maintainer's machine while passing in CI -- the worst direction for a
test to be wrong in.

### 4.1 Tests that assert against un-versioned per-host data

`config.toml` and `papers/bibliography.bib` are gitignored, per-host, and
different on every machine. Two tests depended on them:

- **`tests/test_config.py::test_parser_ocr_defaults_off`** called
  `importlib.reload(config)` after deleting the `PARSER_OCR` environment
  variable. Every sibling test in that class *sets* its variable, which
  wins over the TOML, so none of them care which `config.toml` the reload
  picks up. Deleting it made this the only test in the class that fell
  through to the file -- so a developer with `ocr = true` in their own
  `config.toml` got a failure reading "PARSER_OCR is not False" and
  meaning "you enabled OCR". CI never saw it, because CI copies
  `config.toml.example`. Fixed by pointing `CONFIG_PATH` at an empty TOML,
  which is the only way to assert the *code's* default rather than the
  example's.
- **`tests/test_feature_workflows.py::TestRealBibliographySmoke`**
  asserted `len(refs) == 646` against the maintainer's real
  bibliography. The class self-skips wherever that file is absent, so
  this assertion could only ever run on a maintainer's machine, and could
  only ever fail there -- on the ordinary act of adding a paper. It was
  at 642 when this review ran.

The second was worse than brittle: it *competed with a real detector*.
`src/bib_reader.py` already warns when bibtexparser silently drops an
entry it cannot parse, and that gap -- not the total -- is the thing
worth failing on, because a dropped entry is a paper the user believes
is citable and is not. The fix derives the expectation from the file
itself, so it holds at any library size.

**The general rule, now in `.opencodereview/rule.json`'s `tests` entry:**
flag any assertion whose truth depends on a file the repository does not
track. It is invisible to CI by construction, so it can only be caught by
review.

### 4.2 `bib_reader`'s dropped-entry warning counts contentless stubs

Found while fixing 4.1, and not fixed here because it is a `src/` change
and this is a documentation PR.

`src/bib_reader.py:234` compares `len(bib_database.entries)` against
`_count_raw_entries(raw_text)`, which counts every `@` block. Zotero
exports a contentless `@misc{key,\n}` stub for an attachment with no
metadata, and bibtexparser correctly drops it -- there is no title,
author or year to lose. The maintainer's library has two, so the warning
fires on every `sync`, reporting "2 may have been silently dropped" on a
library that is entirely fine.

A guard that cries wolf on a healthy corpus is worse than none: the run
it needs to be believed on is the one where a real entry has unbalanced
braces, and by then the message is furniture. The fix is to count only
blocks carrying at least one field, which is what the repaired test in
4.1 now does -- so the test and the warning currently disagree, and the
test is the one that is right.

### 4.3 A git worktree under `.claude/` breaks two tree-walking scans

`.claude/` is a scanned root for the tests that police this repository's
own tree. Claude Code creates its worktrees at
`.claude/worktrees/<name>/`, which puts a **second complete copy of the
repository inside a scanned root**. Two scans then misfire, and the
mechanism is worth stating precisely, because the obvious reading --
"they are finding stale code from an old commit" -- is wrong in both
cases.

- **`test_removed_command_scan.py`** allowlists the three files that may
  legitimately name the command removed in 5.2.0 (the direct `src.sync`
  entry point, since replaced by `python -m src.corpus sync`) --
  spelled indirectly here, because that scan reads this file too and is
  right to: `src/sync.py` (the
  refusal), `tests/test_corpus_entrypoint.py` (which runs it), and
  itself. `_ALLOWED` holds **exact relative paths**, so the same file at
  `.claude/worktrees/<name>/src/sync.py` is a different path, misses the
  allowlist, and is reported. The copy is not stale; it is the same
  refusal machinery, at a path the allowlist cannot name.
- **`test_skill_retrieval_logging.py`** globs `.claude/**/*.md` and
  requires every `src.draft retrieve` invocation to carry `--log`. That
  rule is for *skill and agent protocol files*, where a missing flag
  means a drafting run's cost goes unmeasured. A worktree drags the whole
  repository under that glob, so `docs/RETRIEVAL.md` -- user
  documentation showing the command's general form, correctly outside the
  scan on `main`, and identical there today -- gets held to a rule that
  was never meant for it.

So neither is a finding about old code. Both are one defect: **a scan
scoped to `.claude/` cannot tell a skill file from a nested checkout of
everything.** On this review's host there were seven worktrees, all on
branches long since merged, and the suite was red for that reason alone
while CI stayed green -- CI's `actions/checkout` has no worktrees.

Two fixes, and the cheap one is not the repository's:

- **`git worktree prune`, plus removing the locked ones by hand.** If
  they are stale, this is the whole fix and costs nothing.
- **Exclude `.claude/worktrees/` from both scans' roots.** One line
  each, and the durable fix, since anyone using Claude Code worktrees on
  this repository will hit it again. Left out of this change because it
  is a behaviour change to two guard tests and belongs in its own diff
  against this entry, not inside a documentation PR -- the same Boy Scout
  reconciliation [CODE-STANDARDS.md](CODE-STANDARDS.md#the-boy-scout-rule-and-surgical-changes)
  makes for `src/`.

## Reviewing with OpenCodeReview

`.opencodereview/rule.json` now carries seven per-tree rules, so `ocr`
reviews this repository against its own standards rather than against
generic Python advice.
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md#reviewing-before-you-push-opencodereview-if-it-is-installed)
says when to run it. Two limits belong on this list rather than in that
document, because they are costs rather than instructions:

- **The rules are prose handed to a model, and nothing checks that they
  are obeyed.** They are an aid with the same standing as the review
  layer, not a gate, and a run that reports clean is not evidence of
  anything. `tests/test_opencodereview_rules.py` pins only that the file
  parses and that every glob still reaches the tree -- which matters
  because an orphaned glob fails *open*, silently returning that tree to
  OCR's built-in rule while every command still exits 0.
- **The schema is undocumented and was established by probing.** The
  published docs URL 404s, so the two fields OCR actually reads (`path`
  and `rule`) were found by feeding its unmarshaller wrong-typed values
  and reading the Go struct fields it named. Anything else in an entry is
  ignored without complaint. A future OCR release could rename either and
  the only symptom would be rules quietly ceasing to match; the pinned
  field names in that test are what turns it into a failure.

## The standing-instruction budget

An assessment, requested rather than found: **are the developer-facing
documents too long to be followed?**

### What a session actually carries

| Document | Words | ~Tokens | When loaded |
|---|---|---|---|
| `CLAUDE.md` | 533 | 710 | Always -- it is the router |
| `SOUL.md` | 613 | 820 | As the stated tie-breaker |
| `AGENTS.md` | 1,529 | 2,040 | Drafting sessions only |
| `DEVELOPER-AGENTS.md` | 3,772 | 5,030 | Code sessions only |
| `docs/CODE-STANDARDS.md` | 3,999 | 5,330 | "Before a non-trivial change" |

A code session that follows the router reads roughly **11,900 tokens**
before it reads a line of code. The whole prose corpus, if something
loaded all of it, is about 141,000 tokens -- which is why the router
exists.

### The answer is: not on the axis you would expect

**It is not a capacity problem.** 11,900 tokens is about 5% of a modern
context window. Nothing is being pushed out, and the split by task
already prevents the worst case -- a drafting session does not carry the
release process, and a refactoring session does not carry the dossier
format. That design is sound and should not be undone.

**It is a position problem, and the evidence is in the git log.** Rank
the sections of `DEVELOPER-AGENTS.md` by where they sit, then by whether
they are actually obeyed:

| Section | Depth into file | Adhered to |
|---|---|---|
| Behavioural rules, module boundaries, the probe pattern | 5-38% | Yes, visibly and consistently |
| Conventions a new stage follows, test-driven process | 50-65% | Yes |
| Commit messages | 73% | Body shape: 22 of 30 |
| Issues and pull requests | 81% | Mixed |
| Versioning | 86% | Yes |
| Shipping cycle | 92% | Partly -- 4 of 28 landed without a PR |

Everything in the first two-thirds holds. The wobble is concentrated in
the last quarter. That correlation is real and worth knowing.

**But it is not the cause of the symptom that prompted the question, and
saying so is more useful than agreeing.** The single worst-adhered rule
-- the commit body shape, missing from 14 of the last 30 -- is not
forgotten. It is *unreachable*: GitHub composes that body from the
repository's `squash_merge_commit_message` setting, and no amount of
reading a document changes what a server-side default produces. See
[Process debt](#process-debt-the-formats-that-are-not-adhered-to). A
shorter `DEVELOPER-AGENTS.md` would not have moved that number by one.

### What follows from that

1. **Do not shorten by deleting rationale.** It is the same trap
   [the comment rules](CODE-STANDARDS.md#the-comment-rules-and-the-misreading-to-avoid)
   describe: the *why* is the part that cannot be reconstructed, and an
   agent that "tightens" these files destroys the most valuable thing in
   them. Length is not the defect.
2. **Shorten by moving, where a rule fires late.** The commit, PR, merge
   and release rules are needed at the *end* of a session and stored at
   73-92% of a file read at the beginning. Turning each into a command
   the session runs -- rather than a paragraph it must still be holding
   -- is the change that would help, and is what the new `Merging`
   section does.
3. **Prefer a mechanism to a sentence.** This project's own position,
   stated twice already (the citation gate, the C1/C2 ratchet): "an agent
   cannot talk its way past a failing test, and a future session that has
   never read this document still cannot land a 40-statement function."
   Every rule that can become a setting or a check should, and the prose
   should then say less, not more.
4. **Watch the trend, not the total.** This PR grew
   `DEVELOPER-AGENTS.md` by 26% (2,983 to 3,772 words). That is a real
   cost, accepted here because it replaces guidance that demonstrably was
   not working with a command and a setting. It would not be worth paying
   twice.

**Not recommended:** a word budget. It is a continuous score, and
[R3](AUTO-IMPROVEMENT.md#the-requirements) rules those out for exactly
the reason that applies here -- it would be met by deleting the
explanations rather than by moving the rules.

## Process debt: the formats that are not adhered to

Measured over the **last 30 commits on `main`**:

| Rule | Violations | Cause |
|---|---|---|
| Body is a bulleted list, no preamble | 14 carry a leading `* <title>` | GitHub's `COMMIT_MESSAGES` squash default |
| Body is a bulleted list, no preamble | 8 are prose paragraphs | Authoring |
| Squash-merged through a PR | 4 of 28 have no `(#N)` | Pushed to `main` directly |
| PR number not added by hand | 1 reads `(#144) (#148)` | Authoring |
| Title in imperative mood | 1 noun phrase | Authoring |

**The dominant cause is a repository setting, not discipline.**
`squash_merge_commit_message` is `COMMIT_MESSAGES`, which builds the
squash body by concatenating the branch's commit messages with `*`
bullets. The documented shape therefore survives only if whoever merges
hand-edits the body in the web UI, every time. Restating the rule more
firmly cannot fix a default; that is why this is debt and not a lapse.

A second, quieter defect: `squash_merge_commit_title` is
`COMMIT_OR_PR_TITLE`, so GitHub uses the PR title on a multi-commit
branch and the *commit's* title on a single-commit one.
`DEVELOPER-AGENTS.md` asserted the PR title unconditionally, which was
simply wrong for the one-commit case -- corrected in this change.

**The fix is three settings**, recorded in
[DEVELOPER-AGENTS.md's Merging section](../DEVELOPER-AGENTS.md#merging)
with the exact command. They need admin rights, so they are the
maintainer's to apply:

- `squash_merge_commit_title=PR_TITLE`
- `squash_merge_commit_message=PR_BODY` -- and
  `.github/pull_request_template.md` already shapes that body
- `allow_merge_commit=false`, `allow_rebase_merge=false`, so "Merge
  method: squash" is a property of the repository rather than a sentence

That is roughly 15 of the ~20 violations above closed by configuration,
permanently, for every future contributor and every future session.

**What deliberately is not proposed:** a test over `git log`. It is the
obvious move in this repository's idiom, and it does not work here --
`actions/checkout` fetches depth 1, so CI has no history to walk, and a
scan that self-skipped when history is absent would be green on the one
host that never has it. The settings are strictly better: they prevent
rather than detect.

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
| Tests duplicating setup, several asserts in one test, 2,000-line test modules, five tests with no assert | All four are checked positions, not drift -- see [Tier 4](#tier-4-the-test-suite). The assert-free five are documented "does not raise" tests |
| `class TestRealConfigToml` in `tests/test_config.py` asserting against the real `config.toml` | Deliberate and named in its own docstring -- it is a sanity check on the constants as actually computed. Unlike [4.1](#41-tests-that-assert-against-un-versioned-per-host-data), it does not claim to be testing a *default* |
| `bench/repro_check.py` has no test module | It self-checks instead. `self_check()` runs from `main()` on every invocation, with nine assertions proving the detector can see a difference before a zero from it is believed -- a deliberate answer to `bench/` sitting outside coverage, stated in its own docstring |
| `src/citation_gate.py:191` reads the draft with no `encoding=` | Real, and on the list at [3.1](#31-text-io-on-the-locale-codec) -- but *not* a way to break the gate. Citekeys are ASCII, so extraction returns the same result from mojibake as from correct text. Verified, because the opposite conclusion is the natural one |

## What to take first

Ordered by what breaks if it is left, not by size:

0. **[Process] The three merge settings.** Not first because it is the
   most important, but because it is the only item here that costs one
   command, needs no review, and closes roughly 15 of the ~20 format
   violations permanently. It needs admin rights, which is the only
   reason it is not already done.
1. **[3.1] `encoding="utf-8"` at 32 call sites.** The only item in this
   document with a *demonstrated* crash on ordinary input -- a CJK or
   Cyrillic author name, rendered on a cp1252 host. Mechanical, testable,
   one PR. The reads are worth fixing in the same pass, but they corrupt
   rather than crash, so take the writes first if it is split.
2. **[Tier 1] `src/sync.py::run`.** 117 statements, separable at six
   named seams, and already the register's designated first job.
3. **[3.4] A `docker build` job in CI.** Cheapest real coverage gain in
   this list -- one workflow job against 56 lines currently verified by
   nothing.
4. **[Tier 2] Annotate `src/review/verbatim_check.py`.** 47 functions,
   no behaviour change, and it removes the tree's only zero.
5. **[Tier 1] Split `src/dossier.py`** along the four ranges above, and
   delist whatever comes back under C1 in the same PR.
6. **[4.2] Count only entries with fields** in `bib_reader`'s
   dropped-entry warning, so it stops firing on every healthy Zotero
   export. Small, and it restores a guard that currently reads as noise.

Everything below that is real but can wait. Each of the five is one PR:
"several small, reviewable PRs over one large one" applies to this
project's own housekeeping as much as to its features, which is the
reason the register froze today's code rather than fixing it.
