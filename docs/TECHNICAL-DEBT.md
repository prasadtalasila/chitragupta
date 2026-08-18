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
- [Tier 5: continuous integration and the linters](#tier-5-continuous-integration-and-the-linters)
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

`tests/test_code_standards_scan.py` freezes **10 functions** over C1 (25
statements) and **11 modules** over C2 (250 code lines), each with its
current size in a trailing comment that
`test_every_registered_offender_records_its_current_count` keeps honest.

Those two counts had drifted badly -- this section claimed 26 and 13
until #228 -- which is [build order](CODE-STANDARDS.md#build-order) item
4, the doc-drift detector, demonstrating the exact failure it was
proposed for. CODE-STANDARDS.md's copy of the same pair stayed correct
throughout, because a test pins it and nothing pins this one.

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

**Resolved in #219.** Kept below as the historical record of what the
split was measured against -- the actual result was `src/dossier/`, 12
modules along finer seams than the four below (the CLI block alone
needed splitting again once its formatting helpers moved with their
`_cmd_*` handlers into the modules whose state they print, or it would
have landed over the 250-code-line cap on its own).

The largest module in the tree, and the one whose split was least
ambiguous. By line range it was already four modules stacked:

| Lines | Responsibility |
|---|---|
| 112-1050 | The dossier data model -- paths, sections, citekeys, evidence blocks, retrieval log |
| 1052-1500 | Status, brief and drift reporting over that model |
| 1505-1670 | Archive bundle / export / restore (`tarfile`, member checking) |
| 1670-2149 | The `argparse` CLI: eleven `_cmd_*` functions plus `main` |

Four of the register's 26 C1 offenders (`_cmd_status`, `main`,
`_cmd_brief`, `_cmd_status_all`, `_print_drift`) sit in that last block,
which is the shape CODE-STANDARDS.md predicts: "a `main()` that parses
arguments, does the work, and formats the output -- most of the C1
register has that shape."

Note what splitting it would *not* have fixed on its own -- C2 permits a
registered module to grow
([deliberately](CODE-STANDARDS.md#what-a-ratchet-is-and-the-debt-register)),
so nothing failed before this; it was debt because a reader looking for
the export format had to know it was not in the first 1500 lines.

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
should be one") -- it assumes ruff arrives first. It has not.

### Type annotations: 394 of 433

Build-order item 3 says "`src/` is partly annotated." It is 91%
(394 of 433 `def`s carry a return annotation), and the distribution is
the finding rather than the total:

| Module | Annotated |
|---|---|
| `src/review/verbatim_check.py` | **60 / 60** -- resolved #133 |
| `src/review/citation_provenance.py` | 16 / 17 |
| `src/review/citation_coverage.py` | 11 / 12 |
| `src/review/__init__.py` | 10 / 10 |
| `src/runlock.py` | 3 / 7 |
| `src/sync.py` | 4 / 8 |
| `src/dossier.py` | 64 / 65 as one file; split into `src/dossier/` by #219, not re-measured per module since |

**`verbatim_check.py` no longer holds the tree's only zero.** It was
the second-largest module in the repository with no annotations at all,
against three siblings that were effectively complete. That breaks the
[Be consistent](CODE-STANDARDS.md#understandability) rule, which that
document calls "the highest-value one in this list."

It was annotated in full while #133, the skip-gram detection tier, was
already touching every function in the file. No behaviour changed, per
[What to take first](#what-to-take-first) item 4 below. `runlock.py` and `sync.py`
remain the two real partial modules; nothing here claims those are
resolved.

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
| `src/dossier.py` | 1 / 12 as one file; split into `src/dossier/` by #219, not re-measured per module since |

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

- **`src/references.py:443,464`** and **`src/render_output.py:148,171,172`**
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

### 3.7 The BibTeX author-name grammar exists twice

`src/bib_reader.py:79-84` (`_parse_authors`) and `src/references.py:129-134`
(`_format_name`) carry the same five lines, character for character:

```python
if "," in name:
    last, first = (p.strip() for p in name.split(",", 1))
else:
    parts = name.rsplit(" ", 1)
    first, last = (parts[0], parts[1]) if len(parts) == 2 else ("", parts[0])
```

**Why it looks correct and is not.**
[DEVELOPER-AGENTS.md's module boundary](../DEVELOPER-AGENTS.md#module-boundaries)
says `references.py` must never parse `bibliography.bib`, and it does not
-- it reads the ledger's `bib_fields` column, exactly as required. But
that boundary is about *the file*, and what is duplicated here is the
**grammar**: how a BibTeX author name divides into given and family. So
`references.py` obeys the letter of the rule while carrying a second,
independently-maintained copy of `bib_reader`'s most subtle piece of
parsing.

The failure mode is quiet and specific. Extend one side for a case the
grammar does not handle today -- a `von` particle, a `Jr.` suffix, a
second comma -- and the other keeps the old reading. The ledger would
then record one name and the rendered bibliography would print a
different one, for the same entry, with nothing failing. On a tool whose
purpose is citations you can trust, two disagreeing spellings of an
author is the wrong kind of quiet.

**Fragility**, in
[the review vocabulary](CODE-STANDARDS.md#code-smells-the-review-vocabulary).
The fix is not to relax the boundary: the five lines are plain stdlib
string handling with no bibtexparser in them, so they can live in one
module both import, and `references.py` keeps running under the bare
system interpreter. Found by `pylint`'s `duplicate-code` (see
[5.2](#52-pylint-a-measured-baseline)), not by reading -- which is the
argument for the linter in one finding.

### 3.8 `connect()` / `try` / `finally: close()` repeated at eight sites

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

### 3.9 Figure handling is per-genre, because the draft languages are

Tracked as [#230](https://github.com/prasadtalasila/chitragupta/issues/230),
which carries the resolution plan and its price.

A figure has two forms -- a TikZ picture and a plain-ASCII diagram
(`docs/WRITING-STANDARDS.md` §10). The rule the renderer applies is
uniform: **the draft keeps its native form inline, and the other form
becomes a file.** What is *not* uniform is what that produces on disk,
and the asymmetry is worth naming because a reviser meets it directly.

| Genre | Draft language | Inline | File | Marker |
|---|---|---|---|---|
| `tutorial-writer`, `textbook-chapter-writer`, `survey-writer` | Markdown | ASCII, in a fence | `figures/<name>.tex` | `<!-- figure: figures/<name> -->` |
| `thesis-chapter-writer` | LaTeX | TikZ, via `\input` | `figures/<name>.txt` | `%figure: figures/<name>` |

**The cause is one fact:** `thesis-chapter-writer` is the only genre
whose canonical deliverable is LaTeX. It emits a preamble-less `.tex`
fragment meant to be `\input` into the user's own thesis, so it never
passes through Markdown at all; its `.md` and `.pdf` are *previews*
generated from that fragment, through pandoc's LaTeX reader and, for
`pdf`, `pdflatex`. The other three are Markdown-native, and their
`--format md` render does not reach pandoc at all
(`src/render_output/__init__.py`, the early return for a Markdown input).

Everything else follows mechanically. A `verbatim` ASCII block left
inline in the fragment would print in the user's real thesis beside the
TikZ, so the fragment's ASCII must be a file. A Markdown draft's ASCII
is already the fence its `md` render emits, so a `.txt` there would be a
copy nothing reads and nothing keeps in step -- it was required for one
commit and reverted for exactly that reason. Neither half of that is
avoidable while the genres differ in source language.

**Why it is still debt.** It is the *opacity* smell
([the review vocabulary](CODE-STANDARDS.md#code-smells-the-review-vocabulary)):
two file layouts for one concept, so a reviser editing a figure has to
know which genre produced the draft before knowing which files exist.
`src/render_output/_figures.py` carries both directions
(`_substitute_tikz_for_ascii`, `_substitute_ascii_for_tikz`) and each has
its own marker regex.

**What has already been paid down.** The marker *vocabulary* was
unified: both spellings are `figure:` and both name a base name without a
suffix, with the renderer deriving `.tex`/`.txt`. Before that they were
`tikz-alt`/`ascii-alt` and each carried a full filename, so a draft named
one figure twice.

**The resolution, and its price.** Full uniformity is reachable: put
*both* forms in files in every genre and leave only a marker in the
draft, so every figure is one marker plus `<base>.tex` and `<base>.txt`
whatever the genre. It costs the three Markdown genres their inline
diagram -- someone opening `content/drafts/<topic>/tutorial.md` would see
a marker where the picture is now -- in the genres §10 calls the most
natural home for an ASCII figure. That trade was judged not worth making
and the reasoning is recorded rather than the conclusion alone, because
it is a judgement someone may reasonably re-decide.

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
  legitimately name the command removed in 5.2.0 -- the direct
  `src.sync` entry point, since replaced by `python -m src.corpus sync`.
  It is spelled indirectly here, because that scan reads this file too
  and is right to. The three are `src/sync.py` (the refusal),
  `tests/test_corpus_entrypoint.py` (which runs it), and the scan itself.

  `_ALLOWED` holds **exact relative paths**, so the same file at
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

## Tier 5: continuous integration and the linters

### 5.1 CI stopped running on `main` in July, and nothing noticed

**Fixed in the change that adds this section**, and recorded because the
shape of the failure is the lesson.

`.github/workflows/ci.yml` declared:

```yaml
on:
  push:
    tags-ignore: ['v*']
  pull_request:
    branches: [main]
```

The intent is clear and reasonable -- run on merges, but do not
double-run on the release tag `release.yml` already handles. GitHub's
rule is the opposite of what that spells: **when a `push` trigger carries
only tag filters and no `branches`, the workflow does not run on branch
pushes at all.** So from the commit that introduced it (`6388bad4`,
2026-07-31) the `push` trigger was dead. The evidence is exact: four
push-event runs in the repository's history, all dated 2026-07-31, the
last at `47d3b99e` -- an ancestor of the commit that added the filter --
and **81 commits have landed on `main` since without one.**

**Why it stayed invisible for six weeks.** `pull_request` kept firing, so
every PR was fully checked and every branch went green. The only thing
missing was the run nobody watches: the one on `main` after the merge.
A trigger that narrows silently produces no error, no annotation and no
red check -- it produces *fewer runs*, which looks exactly like nothing.

**What it cost.** Codecov has no report for any base commit, so every PR
comment carries "Please upload report for BASE" and shows `?` in the base
column, and the project dashboard has nothing to display. It reads as
"Codecov is broken" or "coverage is zero"; in fact the uploads work
perfectly -- the PR reports parse cleanly at 100.00% across 28 files,
with both matrix flags separated. There was never a baseline to
compare against, because the run that would have produced one never
happened.

The fix is `branches: [main]` in place of `tags-ignore`, which states the
original intent positively: run on merges to `main`, never on a tag, and
without starting a second redundant run beside each PR's.

**The general form, which has no detector:** a CI trigger, filter or
matrix entry that narrows what runs is invisible by construction. This
repository has tests that assert its scanners are non-vacuous
(`test_the_scan_reaches_the_source_tree`) for precisely this reason, and
the same argument applies to workflows -- nothing currently asserts that
a run happens where one is expected.

### 5.2 `pylint`: a measured baseline

**Adopted and enforced in 5.8.0.** `ci.yml`'s `lint` job runs
`pylint --rcfile=.pylintrc src scripts` at a binary zero-messages bar.
The residue below is fixed rather than suppressed, in this order: 3.1's
encoding sites first -- the whole item, not pylint's visible seven --
then the long lines, then the two context-manager names into `good-names`
and the four miscellaneous findings.

The categories listed as decisions now live in `.pylintrc`'s own
`disable=`, each with its reason beside it, so this table and that file
cannot drift into disagreeing.

Two consequences worth carrying forward. Wrapping the long lines **grew
ten registered files** -- `line-too-long` and the C2 length ratchet pull
against each other, and C0301 won; the counts in
`tests/test_code_standards_scan.py` moved with it. And the enrich group's
third-party imports are in `ignored-modules`, because they are lazy
imports that pylint still resolves statically, so a lint job that does not
download torch would otherwise report `import-error` against every one.

The measurement that produced all of that follows, unchanged.

[CODE-STANDARDS.md's build order](CODE-STANDARDS.md#build-order) puts a
linter first and declines to adopt one without "a measured baseline and a
`per-file-ignores` register of the same shape as this one". This is that
measurement, taken with the `.pylintrc` this project inherits from DTaaS
(the same source its own standards come from).

**Baseline: 9.50/10, 235 messages across `src/` and `scripts/`.**

Most of it is not debt. Disabling the categories this repository has
already decided against leaves **44 real findings**:

| Category | Count | Disposition |
|---|---|---|
| `line-too-long` (>100) | 31 | Real. "Keep lines short" is a review standard here with no detector; this is it, measured |
| `unspecified-encoding` | 7 | Real, and already [3.1](#31-text-io-on-the-locale-codec) -- pylint sees only the `open()` calls, 7 of that item's 32 sites |
| `invalid-name` | 2 | `pipeline_lock`, `interrupt_guard` -- deliberate lowercase context managers; belongs in `good-names` |
| Miscellaneous | 4 | `unused-import`, `trailing-newlines`, `use-maxsplit-arg`, `consider-using-with` |

The categories disabled, and why, since each is a decision rather than an
oversight:

- `import-outside-toplevel` (24) -- the documented lazy-import pattern
  that keeps tier-1 modules stdlib-only at import time.
- `missing-function-docstring`/`missing-class-docstring` (71) -- this
  project requires *why*-comments, and a docstring on every small private
  helper is the "obvious noise" the same checklist bans.
- `too-many-*` (35) -- C1/C2 already measure size, more strictly, and two
  detectors for one rule is the two-debt-lists problem build-order item 2
  names.
- `duplicate-code` (4) -- two are deliberate and documented, one is now
  [3.7](#37-the-bibtex-author-name-grammar-exists-twice).
- `broad-exception-caught` (10) -- each carries a stated cause.
- `protected-access`, `global-statement`, `unused-argument`,
  `attribute-defined-outside-init`, `redefined-outer-name` and
  `cyclic-import`.

**Why it was not wired into CI in the change that measured it.** Two of
the four residue rows are the two things that must not be papered over.
Fixing pylint's 7 `unspecified-encoding` sites while leaving 3.1's other
25 would close the detector on the register's top item without closing the
item. And DEVELOPER-AGENTS.md forbids shipping a check that has not been
made to pass. So the honest sequence was
[3.1](#31-text-io-on-the-locale-codec) first, then the 31 long lines, then
pylint enabled at a **binary** bar -- zero messages, never a `fail-under`
score, because [R3](AUTO-IMPROVEMENT.md#the-requirements) rules out
driving a number. That sequence is what 5.8.0 carried out, in that order.

Two side effects worth having, once it lands: the 11 inert `# noqa:
BLE001` markers ([Tier 2](#the-11-inert--noqa-ble001-markers)) become
live `# pylint: disable=broad-exception-caught` suppressions, and
`duplicate-code` becomes a standing detector for the class 3.7 belongs
to.

### 5.3 `markdownlint`: a measured baseline

**Adopted and enforced in 5.8.0**, at the same binary bar, over the same
globs. The judgement this section left open -- what to do about `MD060` --
was taken as **disable**: 839 of the 947 findings, table cell padding, and
the alternative was a diff touching every table in the documentation to
move spaces around, changing no rendered output. Everything else was
fixed, including four prose lines that began with an issue reference
(`#126 already fixes...`) which a naive `--fix` rewrote into H1 headings
before the corruption was caught and reverted.

One inherited config bug fell out of the adoption: the `overrides:` block
was **inert**. It is a markdownlint-**cli2** feature read from
`.markdownlint-cli2.yaml`, and a plain `.markdownlint.yaml` ignores the
key silently -- doubly inert here, since it named `.github/` paths the
lint globs never reach. Per-file exceptions are inline directives now, at
the single site that needs one.

The measurement follows, unchanged apart from the count: the baseline was
re-taken at **947** on the current tree, against the 927 recorded when
this section was written.

Same shape, with `.markdownlint.yaml` inherited from the same source, run
over this repository's own prose (root `*.md` plus `docs/`; `content/` is
the user's drafts and out of scope):

**927 findings**, of which:

| Rule | Count | Note |
|---|---|---|
| `MD060/table-column-style` | 827 | Table cell padding. Cosmetic, and 89% of the total |
| `MD013/line-length` | 37 | Genuinely low -- this repository already wraps prose short |
| `MD040/fenced-code-language` | 30 | Real: fenced blocks with no language tag |
| Everything else | 33 | Blank lines around headings and lists, trailing newlines, emphasis style |

The distribution is the finding. Strip `MD060` and the repository is at
**100 findings across roughly 30,000 words of prose**, which is close
enough to adopt. `MD060` alone would either produce a 827-line diff that
touches every table in the documentation or be disabled; that is a
judgement for whoever adopts it, not something to decide inside a debt
register. Adoption is otherwise cheap and should follow 5.2.

### 5.4 Checks that came back clean

Recorded so the next reviewer does not spend the afternoon re-running
them. Each is a
[CODE-STANDARDS.md review standard](CODE-STANDARDS.md#the-rest-of-the-checklist)
with no detector, checked by hand against the tree:

- **Over-configurability** ("a `config.toml` key with one caller and no
  user asking for it"). 41 public constants in `src/config.py`; the four
  with no external caller (`LOG_LEVELS`, `PARSER_START_METHODS`,
  `BIB_FILE`, `CONFIG_PATH`) are all internal validation tuples or
  intermediate values used within `config.py` itself. No speculative key.
- **Flag arguments** ("don't use flag arguments"). Nine functions take a
  boolean-defaulted parameter; every one is a CLI option plumbed to its
  implementation (`--force`, `--json`, `--write`, `--remove-stale`), not
  a switch between two behaviours bolted into one function.
- **Security patterns.** No `shell=True`, no `eval`/`exec`/`pickle`, no
  `yaml.load`, no bare `except:`, no mutable default argument, no
  `assert` used for runtime validation, no SQL built by concatenation.
  The one f-string in a SQL position is the `PRAGMA` documented under
  [What is not debt](#what-is-not-debt).
- **Resource lifecycle.** Every `sqlite3` connection in `src/` is closed
  in a `finally`; no leak. The repetition of that pattern is
  [3.8](#38-connect--try--finally-close-repeated-at-eight-sites), which
  is a tidiness item, not a correctness one.

## Reviewing with OpenCodeReview

`.opencodereview/rule.json` carries five per-tree rules, so the
OpenCodeReview plugin reviews this repository against its own standards
rather than against generic Python advice.
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md#reviewing-before-you-push-the-opencodereview-plugin)
says when and how to run it. Three limits belong on this list rather than
in that document, because they are costs rather than instructions:

- **It cannot review Markdown, so it cannot review the documents that
  govern this project.** OCR opens only extensions it recognises as code
  and drops the rest before rules are consulted
  (`exclude_reason: unsupported_ext`). Probed on the installed binary:
  `.py`, `.json`, `.yml`/`.yaml`, `.sh` and `.toml` in; `.md`, `.txt`,
  `.rst`, `.cfg` out. `AGENTS.md`, `DEVELOPER-AGENTS.md`,
  `docs/CODE-STANDARDS.md` and every skill under `.claude/` are therefore
  outside every review this tool can perform -- which matters more here
  than in most repositories, because those documents are read as standing
  instructions and a stale one is followed. Doc drift remains a human's
  job, and
  [CODE-STANDARDS.md's build order](CODE-STANDARDS.md#build-order) item 4
  is still the only proposal that would touch it.

  This cost was paid before it was noticed: the first revision of the
  rule file carried two Markdown rules, for the root prose documents and
  for `docs/`. Both resolved cleanly under `ocr rules check` and neither
  could ever fire. A rule that cannot fire is worse than no rule, because
  it implies coverage that does not exist -- so
  `tests/test_opencodereview_rules.py` now fails on one.
- **`ocr rules check` and the plugin disagree, and only one of them is
  about coverage.** `rules check` is a rule *lookup*: it answers for any
  path, including one OCR would never open. `ocr delegate preview
  --format json` is what reports whether a file is reachable. Verifying
  with the first while believing it means the second is exactly how the
  two dead rules above got shipped.
- **The schema is undocumented and was established by probing.** The
  published docs URL 404s, so the two fields OCR reads (`path` and
  `rule`) were found by feeding its unmarshaller wrong-typed values and
  reading the Go struct fields it named. Anything else in an entry is
  ignored without complaint. A future release could rename either and the
  only symptom would be rules quietly ceasing to match; the pinned field
  names in that test are what turns it into a failure.

The rules themselves are prose handed to a model, and nothing checks that
they are obeyed. They are an aid with the same standing as the review
layer, not a gate, and a run that reports clean is not evidence of
anything.

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
wrong for the one-commit case -- corrected in this change.

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
4. **[Tier 2] Annotate `src/review/verbatim_check.py`.** ~~47 functions,
   no behaviour change, and it removes the tree's only zero.~~ **Done**,
   in #133: 58/58 functions now annotated (the count grew from 47 to 53
   while that PR was adding tier 2's finders, then to 58 when three of
   them were split to bring cognitive complexity under SonarQube's
   threshold). See [Type
   annotations](#type-annotations-394-of-433).
5. ~~**[Tier 1] Split `src/dossier.py`** along the four ranges above, and
   delist whatever comes back under C1 in the same PR.~~ **Done**, in
   #219: `src/dossier/`, 12 modules each under the 250-code-line cap.
   `main()` stayed on the register -- still 49 statements, since the
   split moved every `_cmd_*` handler out but left its own argparse-tree
   statements where they were. See the `src/dossier.py` subsection
   below, kept as the historical record of what the split was measured
   against.
6. **[5.2] Enable `pylint` at a binary bar**, once 3.1 and the 31 long
   lines are done — the disable list and the 44-finding residue are
   already measured, so the remaining PR is small. `markdownlint`
   ([5.3](#53-markdownlint-a-measured-baseline)) follows it, after
   someone rules on `MD060`.
7. **[3.7] Move the BibTeX author-name grammar into one module.** Five
   duplicated lines, no boundary to relax, and the failure it prevents is
   two disagreeing spellings of the same author.
8. **[4.2] Count only entries with fields** in `bib_reader`'s
   dropped-entry warning, so it stops firing on every healthy Zotero
   export. Small, and it restores a guard that currently reads as noise.

Everything below that is real but can wait. Each of the five is one PR:
"several small, reviewable PRs over one large one" applies to this
project's own housekeeping as much as to its features, which is the
reason the register froze today's code rather than fixing it.
