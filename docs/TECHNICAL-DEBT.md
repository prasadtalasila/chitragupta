# Technical debt: what is owed, and what only looks like it

Status: **register, not a standard.** Written 2026-08-13, from a
full-tree review of `chitragupta/`, `scripts/`, `bench/`, `docker/` and
`.github/`. Nothing here is enforced. The one part of this project's debt
that *is* enforced -- the C1/C2 ratchet -- lives in
`tests/test_code_standards_scan.py` and is
[pointed at](#tier-1-the-debt-the-ratchet-already-holds), never restated.

**Reconciled 2026-08-18** against the tree as it now stands, since a
register that only shrinks the way it says it should is one this
document's own prose has to keep up with too: three items had been closed
without ever being marked done, and `bench/` and the test suite were both
re-measured, having grown substantially.

**Compacted in #294.** Thirteen closed items each kept a full section --
four fifths of this document was history, and this file is loaded to
answer "what is owed", not "what was". They are gone, and the record of
each is the pull request that closed it. Nothing was re-opened, and every
item left open below was re-checked against the current code first. The
surviving items were renumbered to close the gaps, so a number here means
what this document says it means today and nothing else.

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
   "`chitragupta/dossier.py` is 1605 code lines" qualifies. "There is no citation
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

**Coming off means the section is deleted**, not marked done and kept.
That changed in #294, after thirteen closed items had grown to four
fifths of this file. The pull request that closed an item is the record
of why it was owed and what paying it cost, and it is a better record
than a section here: it carries the diff. So cite a PR number for
history, and cite a section number here only for something still open --
and expect the numbers to be **closed up when an item goes**, since a
register whose numbering is mostly gaps is a register still carrying its
history in the one place it said it wouldn't.

**The debt on this list is not a gate.** `python -m chitragupta.draft gate`
remains the only gate in the project ([SOUL.md](../SOUL.md)), and a debt
list that could fail a build would be a threshold tuned to today's worst
code -- exactly what the ratchet exists to avoid. Nothing here goes red
because an item is unpaid, and #239 did not change that.

What #239 added -- `tests/test_technical_debt_scan.py` -- checks
something else entirely: whether this document *describes the C1/C2
register correctly*. A wrong sentence about the register is a factual
error in prose, not an outstanding cost, and it is the one class of claim
here with a machine-readable source of truth to check against. The
distinction is the whole reason the test could be added without making
the debt itself a gate: leaving an entry open forever is fine, and saying
it is on a register it left is not.

## Tier 1: the debt the ratchet already holds

`tests/test_code_standards_scan.py` freezes **3 functions** over C1 (25
statements) and **11 modules** over C2 (250 code lines), each with its
current size in a trailing comment that
`test_every_registered_offender_records_its_current_count` keeps honest.

Those two counts had drifted badly -- this section claimed 26 and 13
until #228 -- which is [build order](CODE-STANDARDS.md#build-order) item
4, the doc-drift detector, demonstrating the exact failure it was
proposed for. CODE-STANDARDS.md's copy of the same pair stayed correct
throughout, because a test pinned it and nothing pinned this one.

**Something pins this one now**, as of #239:
`tests/test_technical_debt_scan.py` fails if the two numbers above stop
matching `len(LEGACY_LONG_FUNCTIONS)`/`len(LEGACY_LONG_FILES)`, and also
if any Tier 1 subsection heading or `[Tier 1]` item in [What to take
first](#what-to-take-first) names an entry the register no longer holds.
That is the narrow, checkable half of build order item 4 -- claims *about
the register*, which has a machine-readable source of truth. Free prose
about anything else is still nobody's detector, deliberately.

**That register is the authority. This section does not copy it** -- a
debt stated in two places is a debt that will eventually be stated two
different ways, and only one of the two is checked on every run. So this
tier holds no subsections at all: both of its named entries are closed
(`chitragupta/sync.py::run` in #178, `chitragupta/dossier.py` in #219),
and what each was measured against is in the pull request that split it.

**Tracked in #361** (the C2 register: two of the eleven modules). #360,
the C1 register's four splittable functions, closed in #366 -- the count
above already reflects it.

## Tier 2: the debt CODE-STANDARDS.md already named

[Build order](CODE-STANDARDS.md#build-order) lists four things that would
extend the enforced half. All are built now -- item 1 as `pylint`, item 2
as `ruff` (`docs/TECHNICAL-DEBT.md`'s ruff subsection under
[Tier 5](#tier-5-continuous-integration-and-the-linters)), item 3 (type
annotations and a checker) in #355. **This tier holds no subsections at
all**, the same shape [Tier 1](#tier-1-the-debt-the-ratchet-already-holds)
is in once its own two named entries closed: nothing named by build order
currently costs anything to leave, so there is nothing left to measure
below.

## Tier 3: found by review, tracked nowhere

New in this review. Each names a call site.

### 3.1 `bench/` is outside every check in the repository

**Tracked in #356.**

6,183 lines of Python across 22 files (2026-08-13: 2,021 across 8 --
grown substantially since, mostly the plagiarism/paraphrase-tier
benchmark scripts `docs/PLAGIARISM-DESIGN.md` cites), and it is excluded
from all four things that hold the rest of the tree:

- C1 and C2 (`STATEMENT_ROOTS`/`CODE_LINE_ROOTS` in the scan test)
- coverage (`source = ["chitragupta", "scripts", ".claude/hooks"]` in
  `pyproject.toml`)
- the release archive (`scripts/release.py`)
- the linters -- `pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks`
  and `ruff check chitragupta scripts .claude/hooks`
  ([5.1](#51-pylint-a-measured-baseline)/ruff subsection), never `bench/`

Measured against the ratchet it does not face, with the ratchet's own
`long_functions`/`long_files` from `tests/test_code_standards_scan.py`
run directly against `("bench",)` rather than approximated: `bench/` now
holds **20 functions over C1** and **10 modules over C2**,
`bench_collection_scope.py` the largest module at 543 code lines and
`repro_check.py`'s own `main()` the largest function at 69 statements.

CODE-STANDARDS.md states the C1/C2 exclusion and its reason -- one-shot
analysis code whose `main()` reads top to bottom on purpose -- and
explicitly prefers saying so to "the alternative reading, which is that
its long functions ... were quietly not counted." That is the right call.

The **untested** half is the part no document addressed, and it is
narrower than it first looks. `bench/repro_check.py`, the one that
decides whether a parser change reproduces, has always handled it:
`self_check()` runs from `main()` on every invocation, and its docstring
names this exact gap -- "`bench/` sits outside CI's coverage targets, so
nothing in the test suite will ever catch a regression here. This runs on
every invocation instead." Nine assertions prove the detector can see a
difference before a zero from it is believed.

**Narrowed in #294** -- the "pattern of one" half, which is why this item
is still here rather than deleted with the ones that closed outright.
`bench/`'s two other number-publishing scripts, `bench_drift.py` and
`sweep_sync.py`, now each run their own `self_check()` from `main()`, and
`bench/README.md` states the convention a new script here is expected to
follow rather than leaving it a habit of one file. Writing it down was
worth what it usually is: the first run of
`bench_drift.py`'s new probe found that its subset override had reached
nothing since `chitragupta/dossier.py` became a package in #224, so its
three dossier counts had been three measurements of the same whole set.

**Re-measured 2026-08-22:** 14 of the 22 scripts now carry a
`self_check()`, well past the 3 #294 left it at
(`for f in bench/*.py; do grep -q "def self_check" $f || echo $f; done`).
What stays open is the wider half #294 declared out of scope: **8**
scripts still hold no assertion at all, and `bench/` is still outside all
four checks above. That is the same accepted call it always was -- the
convention is a floor for scripts that publish a number, not a plan to
bring `bench/` under the ratchet.

## Tier 4: the test suite

36,546 lines across 93 modules (2026-08-13: 21,780 across 40 -- both trees
have grown substantially since), against `chitragupta/`'s 25,171 -- the suite is
about 1.5x the code it tests, holds 100% line and branch coverage, and is in
better shape than the code. A full review found no dead helper, no
order-dependent test, no network access, no `xfail`, no bare
`pytest.raises(Exception)`, and no test writing outside `tmp_path`. Most
of what a checklist would flag here is deliberate and stated: duplicated
setup (a test that reads top to bottom beats a DRY one), long modules
(C2 does not cover tests, for a stated reason), several asserts per test
(one *behaviour* per test), and five assertion-free tests that are each a
documented "does not raise".

Three findings, of which two were fixed in the change that first
recorded them (#235 and #236) because both were making the suite fail on
a maintainer's machine while passing in CI, the worst direction for a
test to be wrong in. The third is below.

### 4.1 Tests that assert against un-versioned per-host data

**The general rule below is tracked in #358**; the two instances that
prompted it were already fixed when this was first recorded.

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
`chitragupta/bib_reader.py` already warns when bibtexparser silently drops an
entry it cannot parse, and that gap -- not the total -- is the thing
worth failing on, because a dropped entry is a paper the user believes
is citable and is not. The fix derives the expectation from the file
itself, so it holds at any library size.

**The general rule, now in `.opencodereview/rule.json`'s `tests` entry:**
flag any assertion whose truth depends on a file the repository does not
track. It is invisible to CI by construction, so it can only be caught by
review.

## Tier 5: continuous integration and the linters

### 5.1 `pylint`: a measured baseline

**Adopted and enforced in 5.8.0.** `ci.yml`'s `lint` job runs
`pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks` at a binary
zero-messages bar.
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

**Baseline: 9.50/10, 235 messages across `chitragupta/` and `scripts/`.**

Most of it is not debt. Disabling the categories this repository has
already decided against leaves **44 real findings**:

| Category | Count | Disposition |
|---|---|---|
| `line-too-long` (>100) | 31 | Real. "Keep lines short" is a review standard here with no detector; this is it, measured |
| `unspecified-encoding` | 7 | Fixed as part of the locale-codec item (closed 2026-08-13) -- pylint saw only the `open()` calls, 7 of that item's 32 original sites |
| `invalid-name` | 2 | `pipeline_lock`, `interrupt_guard` -- deliberate lowercase context managers; belongs in `good-names` |
| Miscellaneous | 4 | `unused-import`, `trailing-newlines`, `use-maxsplit-arg`, `consider-using-with` |

**The `line-too-long` row's residue is tracked in #362**, alongside
[build order](CODE-STANDARDS.md#build-order) item 1's missing formatter --
this baseline table itself stays as measured, the historical record
5.8.0's adoption sequence was carried out against.

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
  the duplicated BibTeX author-name grammar (closed in #234).
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
the locale-codec item first, then the 31 long lines, then
pylint enabled at a **binary** bar -- zero messages, never a `fail-under`
score, because [R3](AUTO-IMPROVEMENT.md#the-requirements) rules out
driving a number. That sequence is what 5.8.0 carried out, in that order.

**Neither of the two side effects this paragraph predicted actually
happened at the time, and `.pylintrc` said why:** both
`broad-exception-caught` and `duplicate-code` are in its `disable=` list,
category-wide, the same as every other row this section's own residue
table calls a "decision rather than an oversight." So the `# noqa:
BLE001` markers stayed exactly that -- `pylint` never asked for a
`# pylint: disable=broad-exception-caught` at any of them, because the
category itself never fired. **That half is closed now**, by
[5.4](#54-ruff-a-measured-baseline): `ruff`'s `BLE001` reads the markers
`pylint` couldn't. The other half is not --
`duplicate-code` found the four instances the baseline measurement used
to surface the duplicated author-name grammar, then
was turned off rather than kept running, so a fifth duplication
introduced today would still not be caught by anything. No tool this
project runs re-implements it; that remains open.

### 5.2 `markdownlint`: a measured baseline

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
over this repository's own prose -- root `*.md`, `docs/**/*.md`,
`.claude/**/*.md` and `plans/**/*.md`, per `ci.yml`'s `markdownlint` step
([DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md#the-linters-which-are-enforced));
`content/` is the user's drafts and out of scope:

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

**This judgement is tracked in #362**, alongside the `line-too-long`
residue above -- both are the remaining half of
[build order](CODE-STANDARDS.md#build-order) item 1.

### 5.3 Checks that came back clean

Recorded so the next reviewer does not spend the afternoon re-running
them. Each is a
[CODE-STANDARDS.md review standard](CODE-STANDARDS.md#the-rest-of-the-checklist)
with no detector, checked by hand against the tree:

- **Over-configurability** ("a `config.toml` key with one caller and no
  user asking for it"). 41 public constants in `chitragupta/config.py`; the four
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
- **Resource lifecycle.** Every `sqlite3` connection in `chitragupta/` is closed
  in a `finally`; no leak. The repetition of that pattern was
  the repeated `connect()`/`finally: close()` block, now
  resolved into one `ledger.connection()` context manager -- it was a
  tidiness item, not a correctness one.

### 5.4 `ruff`: a measured baseline

**Adopted and enforced.** `ci.yml`'s `lint` job runs
`ruff check chitragupta scripts .claude/hooks` at the same binary
zero-messages bar as pylint and markdownlint, closing
[build order item 2](CODE-STANDARDS.md#build-order) -- the `# noqa`-free
policy [5.1](#51-pylint-a-measured-baseline) named as still open, because
`pylint` disables `broad-exception-caught` category-wide rather than
requiring a per-site suppression.

Unlike `.pylintrc` and `.markdownlint.yaml`, there was no DTaaS config to
inherit: `pyproject.toml`'s `[tool.ruff.lint]` `select` was decided
fresh, and deliberately narrower than ruff's own (much broader) default
-- `["E", "F", "BLE", "RUF100"]`, not the ~400-rule catalogue a bare
`ruff check` enables with no config at all. `BLE` is the rule this
adoption exists for; `E`/`F` are pyflakes/pycodestyle's core correctness
checks plus the "keep lines short" review rule build order already named
for `ruff` (`E501`, closing the gap [5.1](#51-pylint-a-measured-baseline)
left: line length was a hand-fixed wrap, not an enforced check); `RUF100`
is what makes a `# noqa: BLE001` a checked claim instead of a comment
nothing reads -- the actual mechanism that turns the suppression list and
the register into one list, which is what build order item 2 asked for.

**Baseline, that selection, no `per-file-ignores`: 60 findings across
`chitragupta/` and `scripts/`.**

| Rule | Count | Disposition |
|---|---|---|
| `F401` unused-import | 41 | All in six `__init__.py` re-exports (`registry/`, `spec/`, `unit/`, `dossier/`, `render_output/`, `review/figure_layout/`) -- `per-file-ignores` |
| `E402` module-import-not-at-top | 11 | Same four of those six `__init__.py` files, importing late on purpose to dodge a circular import -- `per-file-ignores` |
| `F821` undefined-name | 4 | `chitragupta/overlap_skipgram.py`'s `CorpusSkipgramIndex` annotated three fields `"array[int]"` with no `array` import in the module -- real, fixed by adding it |
| `BLE001` blind-except | 2 | `style_check.language_of`/`style_acronym_drift.findings`, each catching a blind `Exception` where `dossier.dossier_dir` only ever raises `dossier.DossierError` -- real, fixed by narrowing rather than suppressing |
| `E501` line-too-long | 1 | `chitragupta/dossier/_create.py:33`, a 125-column Markdown table row inside an f-string template -- real, and pylint's own blind spot: `unspecified-encoding`'s checker does not see inside a multi-line string literal, so a 10.00/10 `pylint` run says nothing about it |
| `RUF100` unused-noqa | 1 | `chitragupta/pdf_text.py`'s `_extract_docling` -- fixed by removing the marker |

The `per-file-ignores` entry is `"__init__.py" = ["F401", "E402"]`,
wholesale rather than 52 per-line `noqa`s, because that pattern is
identical at all six sites and ruff's own per-file-ignores mechanism is
built for exactly this shape.

**The 12 `chitragupta`/`scripts` markers this adoption exists for
(`docs/TECHNICAL-DEBT.md`'s former "11 inert" count, plus
`scripts/check_version_bump.py`'s, added after that count was taken)
turned out to split 11/1.** Eleven are confirmed live: `ruff` would
report `BLE001` at each without its `# noqa`, checked directly rather
than assumed. The twelfth, `pdf_text.py`'s, was not -- `_extract_docling`
re-raises via `raise ... from exc`, which `BLE001`'s own definition of
"blind" exempts, so the marker suppressed nothing and was removed (the
*why*-comment beside it stayed; only the `noqa:` tag was dead weight).
That is `RUF100` doing the job build order item 2 asked for: proving the
suppressed set was the *right* set, rather than leaving it asserted.

**`bench/`'s two markers were checked the same way and are genuine.**
`bench/make_corpus.py` and `bench/bench_docling.py` would both report
`BLE001` without their `# noqa`, verified directly (neither except block
re-raises). They stay exactly as written. `bench/` itself is not in
`ci.yml`'s `ruff` invocation -- [Tier 3.1](#31-bench-is-outside-every-check-in-the-repository)
excludes it from every check in the repository, unchanged by this
adoption, so the tag is inert in practice (nothing runs `ruff` over
`bench/`) but correct on the evidence, which is the more honest state
than stripping a suppression a real check would still need.

**`ruff`'s pin is exact for a reason beyond Sonar S8544.** `RUF100`'s
verdict on a given `except` block depends on carve-outs like the
re-raise one above, which are undocumented and narrower than `BLE001`
looks on its own -- an unpinned bump could move that verdict and redden
`ci.yml` on a rule this project never touched. `.pylintrc` and
`.markdownlint.yaml` don't carry this risk the same way; `ruff`'s pin in
`ci.yml` is where the next reader bumping it will meet the reason.

## Reviewing with OpenCodeReview

`.opencodereview/rule.json` carries five per-tree rules, so the
OpenCodeReview plugin reviews this repository against its own standards
rather than against generic Python advice.
[DEVELOPER-AGENTS.md](../DEVELOPER-AGENTS.md#reviewing-before-you-push-the-opencodereview-plugin)
says when and how to run it. Three limits belong on this list rather than
in that document, because they are costs rather than instructions.
**Tracked in #359.**

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
forgotten. It is *unreachable* by reading: GitHub composes that body from
the repository's `squash_merge_commit_message` setting, and no amount of
reading a document changes what a server-side default produces. See
[Process debt](#process-debt-the-formats-that-are-not-adhered-to). A
shorter `DEVELOPER-AGENTS.md` would not have moved that number by one.

There is a sharper version of this, which #238 has since shown: the rule
is not reachable by *configuration* either, since no value of that
setting produces a commit body from a PR description. It is reachable
only by a step at merge time, which is what point 3 below actually asks
for.

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

**Conclusions 2 and 3 are tracked in #357** -- applying "prefer a
mechanism to a sentence" beyond the Merging section it already produced.

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

**Partly resolved in #238** (settings applied 2026-08-18). The table
above is the measurement as taken on 2026-08-13 and is kept as the
baseline; what follows is what each cause turned into. **Rows 1 and 2 --
the ones that stay open below -- are tracked in #357.**

**The dominant cause was a repository setting, not discipline.**
`squash_merge_commit_message` was `COMMIT_MESSAGES`, which builds the
squash body by concatenating the branch's commit messages with `*`
bullets. The documented shape therefore survived only if whoever merged
hand-edited the body in the web UI, every time. Restating the rule more
firmly could not fix a default; that is why this was debt and not a
lapse.

A second, quieter defect: `squash_merge_commit_title` was
`COMMIT_OR_PR_TITLE`, so GitHub used the PR title on a multi-commit
branch and the *commit's* title on a single-commit one.
`DEVELOPER-AGENTS.md` asserted the PR title unconditionally, which was
wrong for the one-commit case.

**All three settings are now applied:**

- `squash_merge_commit_title=PR_TITLE` -- **closed the title outright.**
  The PR title is the commit title unconditionally, GitHub appends the
  `(#N)` itself, and the "add it by hand when you pass `--subject`"
  exception is retired. Rows 3 and 4 of the table above cannot recur by
  this route.
- `allow_merge_commit=false`, `allow_rebase_merge=false` -- "Merge
  method: squash" is a property of the repository rather than a sentence.
- `squash_merge_commit_message=PR_BODY` -- **did not close the body, and
  the claim that it would was wrong.** This section previously said
  `.github/pull_request_template.md` "already shapes that body". It
  shapes it into a *review* document -- `## Test plan`, `## Checklist`,
  tick-boxes -- which is a different artefact from a commit message, so
  merging unedited now lands the template on `main` instead of
  `*`-concatenated commit titles. Both are wrong; the new one is at
  least conspicuous.

**So rows 1 and 2 stay open, and no setting closes them.**
`squash_merge_commit_message` takes exactly three values -- `PR_BODY`,
`COMMIT_MESSAGES`, `BLANK` -- and none transforms the text, because
there is no templating step between a PR description and a commit body
for a setting to hook into. The body is therefore supplied at merge time
via `gh pr merge --body-file`, which
[DEVELOPER-AGENTS.md's Merging section](../DEVELOPER-AGENTS.md#merging)
now documents as the standing mechanism rather than as a stopgap.

The estimate this section carried -- "roughly 15 of the ~20 violations
closed by configuration" -- was too optimistic for that reason. The
title-side rows are closed permanently; the body-side rows moved from
"the default fights you" to "one flag at merge time", which is an
improvement in kind but not the automatic fix that was predicted.

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
| `con.execute(f"PRAGMA user_version = {target}")` (`chitragupta/ledger.py:128`) | Not SQL injection. `PRAGMA` does not accept `?` binding, and `target` is `len(_MIGRATIONS)` -- this module's own constant. The comment above it says exactly that |
| `_load_cache`/`_save_cache` duplicated in `retrieval.py` and `enrich/docling_parse.py` | Different requirements, and each docstring names the difference: retrieval needs a per-writer-unique temp name for concurrent subagents, docling does not and says why |
| 11 broad `except Exception` handlers in `chitragupta`/`scripts` (2 more in `bench/`) | Each has a stated cause and a `# noqa: BLE001` marker `ruff` now reads. See [5.4](#54-ruff-a-measured-baseline) -- confirmed live, not assumed so |
| `--target host\|docker` accepted but never branched on | Deliberate: the probes decide, the flag is informational. Removing it is a CLI break for no gain |
| C2 permits a registered module to grow | [Deliberate](CODE-STANDARDS.md#what-a-ratchet-is-and-the-debt-register). Pinning each to today's size fails on every ordinary edit and gets the rule turned off |
| No timestamp in any review report | A product rule: two runs over unchanged input produce byte-identical output, so reports diff across revisions |
| Tests duplicate setup instead of DRYing it | [Adopted position](CODE-STANDARDS.md#tests): a test that reads top to bottom is worth more than a DRY one |
| `tests/test_pdf_text.py` at 1806 code lines | C2 does not cover tests, for a stated reason: a test module's length tracks the surface of the module under test |
| Tests duplicating setup, several asserts in one test, 2,000-line test modules, five tests with no assert | All four are checked positions, not drift -- see [Tier 4](#tier-4-the-test-suite). The assert-free five are documented "does not raise" tests |
| `class TestRealConfigToml` in `tests/test_config.py` asserting against the real `config.toml` | Deliberate and named in its own docstring -- it is a sanity check on the constants as actually computed. Unlike [4.1](#41-tests-that-assert-against-un-versioned-per-host-data), it does not claim to be testing a *default* |
| `bench/repro_check.py` has no test module | It self-checks instead. `self_check()` runs from `main()` on every invocation, with nine assertions proving the detector can see a difference before a zero from it is believed -- a deliberate answer to `bench/` sitting outside coverage, stated in its own docstring |
| `chitragupta/citation_gate.py` reading the draft with no `encoding=` (true when this row was written; fixed since, in the locale-codec pass) | Was never a way to break the gate regardless. Citekeys are ASCII, so extraction returns the same result from mojibake as from correct text. Verified, because the opposite conclusion is the natural one |

## What to take first

Ordered by what breaks if it is left, not by size.

Short, and deliberately so. Everything the 2026-08-18 reconciliation
found open is resolved as of #295's batch (PRs #290, #292, #293, #237
and #291), and §3.1's "pattern of one" closed in PR #294, which gave
`bench_drift.py` and `sweep_sync.py` a `self_check()` each and wrote the
convention down in `bench/README.md`.

1. **[3.1] The rest of `bench/`.** 8 of its 22 scripts still carry no
   self-check, and the directory remains outside C1/C2, coverage, the
   release archive and the linters. Open and accepted rather than
   scheduled: the convention is a floor for a script that publishes a
   number, not a plan to bring `bench/` under the ratchet. Tracked in
   #356.
