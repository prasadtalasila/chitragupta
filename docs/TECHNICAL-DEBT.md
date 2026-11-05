# 🧾 Technical debt: what is owed, and what only looks like it

Status: **reference.**

[CODE-STANDARDS.md](CODE-STANDARDS.md) says what the code must look like.
This document says where it currently doesn't and, just as important,
where it looks like it doesn't but is right. Nothing here is enforced.
The one part of this project's debt that *is* enforced, the C1/C2
ratchet, lives in `code-standards-register.toml` and
`tests/test_code_standards_scan.py`, and is [pointed
at](#-tier-1-the-debt-the-ratchet-already-holds), never restated.

**Written for** someone deciding what to take next, and for the agent that
picks this repository up cold and needs to know which surprising thing is
a bug and which is a decision. It assumes `DEVELOPER-AGENTS.md` for the
process around a change.

**Not covered here:** anything about drafts ([AGENTS.md](../AGENTS.md)),
prose standards ([WRITING-STANDARDS.md](WRITING-STANDARDS.md)), or
features not yet built ([FEATURE-ROADMAP.md](FEATURE-ROADMAP.md)). A
thing that was never built is not a debt.

## 🧭 Table of contents

- [How something gets on this list](#-how-something-gets-on-this-list)
- [Tier 1: the debt the ratchet already holds](#-tier-1-the-debt-the-ratchet-already-holds)
- [Tier 2: refactoring opportunities](#-tier-2-refactoring-opportunities)
- [Tier 5: continuous integration and the linters](#-tier-5-continuous-integration-and-the-linters)
- [What is not debt](#-what-is-not-debt)
- [What to take first](#-what-to-take-first)

## 📋 How something gets on this list

An item must meet all three conditions:

1. **It is a cost already incurred**, not a feature not yet written. "A
   module is 1,600 code lines" qualifies. "There is no citation graph"
   does not; that belongs on a roadmap, and confusing the two turns a
   debt register into a wish list.
2. **It names a file, a count, or a call site.** "The code could be
   cleaner" is a score, and
   [R3](AUTO-IMPROVEMENT.md#-the-requirements) rules out driving a score
   to zero.
3. **Someone would be worse off if it were left.** A stylistic
   disagreement is not debt.

It comes **off** the list the way it went on: in its own pull request,
against this file. Coming off means the section is deleted, not marked
done and kept. The pull request that closed an item is the record of why
it was owed and what paying it cost.

**The debt on this list is not a gate.** `python -m chitragupta.draft gate`
is the only gate in the project ([SOUL.md](../SOUL.md)). Nothing here goes
red because an item is unpaid.

`tests/test_technical_debt_scan.py` checks something else: whether this
document *describes the C1/C2 register correctly*. A wrong sentence about
the register is a factual error in prose, and it is the one class of claim
here with a machine-readable source of truth. Leaving an entry open
forever is fine; saying it is on a register it left is not.

## 🧱 Tier 1: the debt the ratchet already holds

`code-standards-register.toml` freezes **3 functions** over C1 (25
statements) and **1 module** over C2 (250 code lines), each with its
current size recorded beside it, which
`test_every_registered_offender_records_its_current_count` keeps honest.
Its `c1js`/`c2js` tables hold the same ratchet for `assets/webapp/`.
`tests/test_code_standards_scan.py` reads that file and is what fails a
build.

**That register is the authority, and this section does not copy it.** A
debt stated in two places will eventually be stated two different ways,
and only one of the two is checked on every run. So this tier holds no
subsections.

## 🔧 Tier 2: refactoring opportunities

Measured on 2026-11-05 at 6.166.1 over `chitragupta/` and `scripts/` (not
`tests/` or `bench/`, for the reasons in [What is not debt](#-what-is-not-debt);
R15 is the one exception, since it duplicates config rather than test
setup).
Each item is copies or sizes counted by an AST walk, not a judgement of
style. Each one also costs something already: a fix that lands in one
copy and not the other, or an edit that must split code before it can
change it. None is on the C1/C2 register, and none is a gate. Paying one
deletes its entry, in the PR that pays it.

### Logic that exists in more than one place

- **R1.** **Six temp-file-then-`os.replace` writers.** `_atomic_write.write_atomically`
  is the shared one, and its own docstring says it is "not yet shared".
  The others are `_json_cache.py:102`, `overlap_index_doc.py:133` and
  `:143` (`_atomic_write_json`, `_atomic_write_bytes`), `enrich/doc_vectors.py:62`
  and `registry/_pages.py:191`. They differ in cleanup on failure, and
  `doc_vectors.py` uses a fixed `.json.tmp` name, so two concurrent
  writers share one temp file. *Refactor:* route the other five through
  `write_atomically`. (The `retrieval_cache`/`_docling_cache` pair is a
  decision, under What is not debt.)
- **R2.** **`overlap_index_doc.py` and `overlap_skipgram.py` share three function
  bodies, identical down to the AST:** `fingerprint_document`
  (`:241`/`:316`), `_save_doc_cache` (`:197`/`:279`) and
  `postings_for_gram` (`overlap_index_query.py:46`/`overlap_skipgram.py:408`).
  *Refactor:* one implementation, parameterised by the fingerprint type.
- **R3.** **`_area(box)` is defined four times:** `figure/_advisory.py:227`,
  `figure/_connectors.py:181`, `figure/_contrast.py:181` and
  `review/figure_layout/_geometry.py:146`, in two identical pairs.
  *Refactor:* one function in `_geometry`, where `contains` and
  `intersects` already live.
- **R4.** **The finding-id convention is implemented eight times:**
  `finding_id` in `citation_coverage.py`, `synthesis.py`,
  `uncited_prose.py`, `_citation_provenance_render.py`,
  `_claim_support_render.py` (the last two identical), `_citekey_union_render.py`,
  `_quotation_render.py` and `verbatim_check/_shared.py`. In all,
  `hexdigest()[:12]` appears in 11 modules. The agenda's dedup and
  `--accept` rely on every copy agreeing. *Refactor:* one `review._ids.finding_id(*parts)`.
- **R5.** **Each aid renders its report its own way.** `render_markdown` is
  defined in 10 modules, `format_report` in 7, `_finding_lines` in 5,
  `_summary` in 4 and `_how_to_read` in 3, all under `chitragupta/review/`.
  `review.header` is the only part they share. *Refactor:* a report
  skeleton (header, how-to-read, summary, findings) that each aid fills.
- **R6.** **Ten aids each rebuild their own `Command:` line, and they disagree.**
  `_command` is in `agenda/__init__.py`, `citation_coverage.py`,
  `citation_provenance.py`, `citekey_union.py`, `claim_support.py`,
  `figure_layout/__init__.py`, `quotation.py`, `synthesis.py`,
  `uncited_prose.py` and `verbatim_digest.py`. `provenance` and `agenda`
  leave out `--write`, five others record it, and the sample project's
  reports show both. *Refactor:* derive the line from the parsed
  `argparse` namespace in one place.
- **R7.** **`_grouped` is identical** in `registry/_pages.py:47` and
  `registry/_terms.py:63`. *Refactor:* keep one, in `registry/__init__.py`.
- **R8.** **The caption modules repeat one interface.** `render_output/_equation_captions.py`,
  `_figure_captions.py` and `_tables.py` each define `references` and
  `warnings`, and `_equation_captions.py:122` and `_tables.py:125` are
  identical. *Refactor:* one caption-kind table driving the three.
- **R9.** **The same `drifted` property is defined twice,** on
  `dossier/_drift.py:193` and `dossier/_status.py:68`. *Refactor:* a
  shared mixin, or a function both call.
- **R10.** **Two TikZ node-declaration scanners.** `review/figure_layout/_scan.py::declaration`
  (12 branches) and `figure/_focal.py::declaration` (12 branches) walk
  the same grammar: nested options, the first parenthesised group not
  introduced by `at`, and the label brace. They return different
  tuples. A spelling one learns, the other misses, which is the shape
  of #1162. *Refactor:* one scanner returning `(options, name, label, end)`.
- **R11.** **Three ways to read the version.** `chitragupta/__main__.py:111` and
  `install.py:141` ask the installed metadata, while `review/__init__.py:108`
  reads `pyproject.toml`. Under an editable install of another checkout,
  `--version` and the report headers name different versions.
  *Refactor:* one `chitragupta.version()`.
- **R12.** **Three subprocess wrappers in `scripts/`:** `check_version_bump.py:168`
  (`_git`), `merge_pr.py:197` (`_gh`) and `relock.py:56` (`_run`).
  Each re-derives "decode UTF-8, not the locale", and `merge_pr`
  documents this by pointing at `check_version_bump`. *Refactor:* one
  `scripts/_proc.py`.
- **R13.** **Three functions called `sidecar_path`.** Two are citekey-keyed
  paths, `_passage_sidecar.py:23` and `tldr.py:71`, the second
  re-implementing the first's naming "the same way". The third,
  `evidence_appendix.py:176`, is a different thing under the same name.
  *Refactor:* one citekey-sidecar helper, and rename the third.
- **R14.** **Four enrich stages hand-build the same result dict.** `run_stage`
  in `enrich/keyword_extract.py`, `topic_converge.py`, `topic_graph.py`
  and `topic_seeding.py` each spell out `{"status", "detail"}`.
  The placement was forced when the stages lived in `enrich/__main__.py`
  at the C2 ceiling. They have since moved to `enrich/stages.py` (72 code
  lines), so nothing still forces it. *Refactor:* a `StageResult`
  constructor, with every stage's shaping in `stages.py`.
- **R15.** **`tests/conftest.py`'s `isolated_config` restates config's paths
  by hand:** 24 entries, `CONTENT_DIR` and the 23 paths derived from it in
  `config.py` and `config_enrich.py`, "diffable by eye". A path added
  to config and missed there leaves a test writing to the real
  `content/`. *Refactor:* have config expose its derived-path table,
  and build both from it.

### Size held exactly at the limit

- **R16.** **Fourteen functions at exactly 25 statements**, so the next edit to
  any of them must split it first. They are `sync.py::run`,
  `sync_pool.py::_drain_pool`, `render_output/__init__.py::render`,
  `passages.py::source_passages`, `seed_topics.py::report`,
  `enrich/topic_converge.py::run_topic_converge`,
  `enrich/docling_parse.py::parse_corpus`, `discover/_render.py::render_topic`,
  `figure/__main__.py::_look_in_draft`, `pdf_text/_converter.py::_docling_converter`,
  `review/verbatim_check/__init__.py::build_parser`,
  `review/figure_layout/_report.py::_figure_lines`,
  `_markdown_inert.py::_Container._item` and
  `scripts/check_version_bump.py::main`. A further 82 sit at 20 to 24.
- **R17.** **Seven modules at exactly 250 code lines:**
  `scripts/populate_bib_groups.py`, `unit/__init__.py`, `sync_residue.py`,
  `review/verbatim_check/__init__.py`, `render_output/_pandoc.py`,
  `figure/__main__.py` and `dossier/_outline.py`. Another 77 are
  between 200 and 249. The cost is already visible: R14's
  scattered code, and `tests/conftest.py`'s table, which exists to dodge C1.
- **R18.** **`render_output/__init__.py` is the hub of the render path:** 247
  code lines, `render` at 25 statements and 10 parameters, and 50
  private names imported from its own siblings. *Refactor:* a
  `RenderRequest` value passed down, so `render` sequences steps and
  does not thread arguments.
- **R19.** **`dossier/_status.py` crowds three near-limit functions into 240
  code lines:** `status` (23), `_cmd_status` (23) and
  `_print_status_drift` (24). *Refactor:* split computing the status
  from printing it.
- **R20.** **`figure/__main__.py` is at 250 code lines with `_look_in_draft` (25)
  and `_look` (23).** *Refactor:* move the `look` command into
  `figure/_look.py`, beside its model.

### Signatures that thread state

- **R21.** **`render_output/_pandoc.py::_pandoc_command` takes 14 parameters.**
  *Refactor:* the same `RenderRequest` as R18.
- **R22.** **The exact tier's three functions take 11, 11 and 8 parameters:**
  `verbatim_check/_exact.py`'s `_exact_finding:142`,
  `_exact_findings_from_groups:93` and `_exact_tier_findings:20`.
  *Refactor:* a scan-context object built once per scan.
- **R23.** **The embedding tier's three take 9, 9 and 8:**
  `verbatim_check/_embed.py`'s `_embed_tier_findings:21`,
  `_findings_within:89` and `_embed_finding:267`. *Refactor:* the same
  context object as R22.
- **R24.** **`verbatim_check/_scan_cmd.py`'s `scan_payload` (8) and `cmd_scan`
  (7), and `_scan_render.render_scan_markdown` (7),** pass the same
  findings, limits and command trio from hand to hand. *Refactor:* one
  scan result value.
- **R25.** **`dossier/_retrieval.py::log_retrieval` takes 9 parameters,** one
  per column of the row it writes. *Refactor:* pass the row.
- **R26.** **`figure/_check.py::apply` takes 7, and so does
  `review/_emit.py::emit`,** on every aid's output path. *Refactor:*
  `emit` takes an aid-output value, so adding a format means changing
  one type, not 13 callers.

### Private names used as public API

- **R27.** **273 distinct `_`-prefixed names are imported across module
  boundaries.** The leaders are `render_output/__init__.py` (50),
  `overlap_index.py` (26), `review/verbatim_check/__init__.py` (19)
  and `dossier/_cli.py` (14). A leading underscore no longer tells a
  reader what is safe to change. *Refactor:* promote the cross-module
  ones, or re-export them through each package's `__init__`.
- **R28.** **`chitragupta.review._emit` is imported by 13 modules**: it is the
  review layer's output API under a private name. *Refactor:* make it
  `review.emit`.
- **R29.** **`render_output._figures` has two de-facto-public helpers.**
  `_resolve_sibling` and `_figure_refs` are imported by 7 and 6
  modules. *Refactor:* name them as the package's API.
- **R30.** **`verbatim_check._shared._line_at` and `_masking._DraftWord` are each
  imported by 4 sibling modules.** *Refactor:* the same promotion,
  inside the package.

### Complex single functions

- **R31.** **The functions with the most branches:**
  `scripts/generate_unicode_sty.py::_styled` (14),
  `hook_launchers.py::faults` (12), `review/agenda/_render.py::_aid_note`
  (11), `_passage_records.py::passage_records` (11) and
  `discover/_render.py::render_topic` (11, and at 25 statements).
  *Refactor:* table-driven dispatch where the branches are cases, as
  `_aid_note`'s are.
- **R32.** **`_markdown_inert.py` holds two of them:** `_Container._item` (25
  statements) and `_container` (10 branches), in a 247-line module.
  It is the code every gate run uses to tell prose from code and
  comments. *Refactor:* split the block scanner from the inline one.

## 🧱 Tier 5: continuous integration and the linters

Tiers 3 and 4 are empty. The numbers here are kept because `.pylintrc`,
`ci.yml` and `pyproject.toml` cite these subsections by number.

`ci.yml`'s `lint` job enforces four tools, each at a binary
zero-findings bar, never a `fail-under` score, because
[R3](AUTO-IMPROVEMENT.md#-the-requirements) rules out driving a number:

- `pylint --rcfile=.pylintrc chitragupta scripts .claude/hooks`
- `ruff check chitragupta scripts .claude/hooks`
- `ruff format --check chitragupta scripts tests bench .claude/hooks`
- `markdownlint-cli2` over the repository's own prose (root `*.md`,
  `docs/`, `.claude/`, `.agents/`, `.opencode/` and `plans/`)

The configuration files are the authority for what each tool checks:
`.pylintrc`'s `disable=` list carries the reason beside each disabled
category, and `pyproject.toml`'s `[tool.ruff]` carries the ruff
selection. `bench/` stays outside the linters by its own standing
decision; `bench/README.md` has the reasoning.

**One gap is open.** `pylint`'s `duplicate-code` is in `.pylintrc`'s
`disable=` list, and no other tool re-implements it for `chitragupta/`
or `scripts/`. A new duplicated block there is caught by nothing.
`tests/test_duplicate_helper_scan.py` covers module-level helpers in
`tests/` only.

### 📊 5.1 `pylint`: a measured baseline

Measured with the `.pylintrc` this project inherits from DTaaS, before
adoption: **9.50/10, 235 messages across `chitragupta/` and `scripts/`.**
Disabling the categories this repository decided against left **44 real
findings**:

| Category | Count | Disposition |
| --- | --- | --- |
| `line-too-long` (>100) | 31 | Real. Fixed by wrapping |
| `unspecified-encoding` | 7 | Fixed with the rest of the locale-codec sites; pylint saw only the `open()` calls |
| `invalid-name` | 2 | `pipeline_lock`, `interrupt_guard`: deliberate lowercase context managers; in `good-names` |
| Miscellaneous | 4 | `unused-import`, `trailing-newlines`, `use-maxsplit-arg`, `consider-using-with` |

The disabled categories are decisions, each reasoned in `.pylintrc`:
`import-outside-toplevel` (the lazy-import pattern that keeps tier-1
modules stdlib-only at import time), the docstring checks (this project
requires *why*-comments, not a docstring on every small helper),
`too-many-*` (C1/C2 already measure size, more strictly),
`broad-exception-caught` (each site carries a stated cause, checked by
ruff's `BLE001` instead) and `duplicate-code` (the open gap above).

The enrich group's third-party imports are in `ignored-modules`: they are
lazy imports that pylint still resolves statically, so a lint job that
does not install torch would otherwise report `import-error` at each.

### 📊 5.2 `markdownlint`: a measured baseline

The baseline over the repository's prose, before adoption:

| Rule | Count | Note |
| --- | --- | --- |
| `MD060/table-column-style` | 827 | Table cell padding, 89% of the total; `markdownlint-cli2 --fix` applies it |
| `MD013/line-length` | 37 | Low; prose here is wrapped short |
| `MD040/fenced-code-language` | 30 | Real: fenced blocks with no language tag |
| Everything else | 33 | Blank lines around headings and lists, trailing newlines, emphasis style |

`MD060`'s width arithmetic counts an escaped pipe (`\|`) as the two
characters it is in the source, not the one it renders as. Pad a table
cell that contains one to its source width.

Per-file exceptions are inline directives at the site that needs one.
An `overrides:` block in `.markdownlint.yaml` is inert: it is a
markdownlint-cli2 feature read only from `.markdownlint-cli2.yaml`.

### 📊 5.4 `ruff`: a measured baseline

`pyproject.toml`'s `[tool.ruff.lint]` selects `["E", "F", "BLE",
"RUF100"]`, deliberately narrower than ruff's own catalogue. `BLE` makes
a blind `except` a finding; `RUF100` makes a `# noqa: BLE001` a checked
claim instead of a comment nothing reads, so the suppression list and
the code cannot disagree. `E501` enforces line length.

Baseline for that selection, with no `per-file-ignores`: **60 findings
across `chitragupta/` and `scripts/`.**

| Rule | Count | Disposition |
| --- | --- | --- |
| `F401` unused-import | 41 | All in `__init__.py` re-exports; `per-file-ignores` |
| `E402` module-import-not-at-top | 11 | The same `__init__.py` files, importing late on purpose to dodge a circular import; `per-file-ignores` |
| `F821` undefined-name | 4 | A missing `array` import in `chitragupta/overlap_skipgram.py`; fixed |
| `BLE001` blind-except | 2 | Narrowed to the one exception actually raised; fixed |
| `E501` line-too-long | 1 | A table row inside an f-string template, which pylint's checker does not see; fixed |
| `RUF100` unused-noqa | 1 | A marker on an `except` that re-raises, which `BLE001` exempts; removed |

The `per-file-ignores` entry is `"__init__.py" = ["F401", "E402"]`,
because the pattern is identical at every site.

`ruff`'s pin is exact. `RUF100`'s verdict on an `except` block depends on
carve-outs such as the re-raise one above, which are narrower than
`BLE001` looks. An unpinned bump could move that verdict and turn
`ci.yml` red on a rule this project never touched.

`ruff format` uses a fixed hanging indent, never alignment to the opening
paren. `.git-blame-ignore-revs` lists the whole-tree reformat commit so
`git blame` skips it; `scripts/release.py` excludes that file from the
release archive, because it means something only against this
repository's history.

## 🚫 What is not debt

This is the other half of this document's job. Every item below looks like a
finding to a reviewer applying a checklist, and every one is a decision
with its reasoning attached. Changing any of them makes the codebase
worse.

| Looks like | Actually |
| --- | --- |
| Very long comments; `.github/workflows/ci.yml` roughly half prose | Required. [The comment rules](CODE-STANDARDS.md#-the-comment-rules-and-the-misreading-to-avoid): *why*-comments are mandatory here, and the size rules count statements precisely so that explaining yourself is free |
| Long developer documents (`DEVELOPER-AGENTS.md`, this directory) | Length is not the defect. Shorten by turning a late-firing rule into a command or a check, never by deleting rationale. A word budget is a continuous score, which [R3](AUTO-IMPROVEMENT.md#-the-requirements) rules out |
| `con.execute(f"PRAGMA user_version = {target}")` (`chitragupta/ledger.py:155`) | Not SQL injection. `PRAGMA` does not accept `?` binding, and `target` is `len(_MIGRATIONS)`, this module's own constant. The comment above it says exactly that |
| `_load_cache`/`_save_cache` duplicated in `retrieval_cache.py` and `enrich/_docling_cache.py` | Different requirements, and each docstring names them: retrieval needs a per-writer-unique temp name for concurrent subagents and a per-process memo on the index file's `(path, size, mtime_ns)`, because its payload is 14 MB and is read many times per run. Docling's is neither, and says why |
| 19 broad `except Exception` handlers in `chitragupta`/`scripts` (2 more in `bench/`) | Each has a stated cause and a `# noqa: BLE001` marker that `ruff` reads. See [5.4](#-54-ruff-a-measured-baseline) |
| `--target host\|docker` accepted but never branched on | Deliberate: the probes decide, the flag is informational. Removing it is a CLI break for no gain |
| C2 permits a registered module to grow | [Deliberate](CODE-STANDARDS.md#-what-a-ratchet-is-and-the-debt-register). Pinning each to today's size fails on every ordinary edit and gets the rule turned off |
| No timestamp in any review report | A product rule: two runs over unchanged input produce byte-identical output, so reports diff across revisions |
| Tests duplicate setup instead of DRYing it | [Adopted position](CODE-STANDARDS.md#-tests): a test that reads top to bottom is worth more than a DRY one |
| `tests/test_pdf_text.py` at over 2,000 code lines | C2 does not cover tests, for a stated reason: a test module's length tracks the surface of the module under test |
| Tests duplicating setup, several asserts in one test, 2,000-line test modules, five tests with no assert | All four are checked positions, not drift; see `.opencodereview/rule.json`'s `tests` entry. The assert-free five are documented "does not raise" tests |
| `class TestRealConfigToml` in `tests/test_config.py` asserting against the real `config.toml` | Deliberate and named in its own docstring: it is a sanity check on the constants as actually computed. Unlike the two cases `tests/test_unversioned_data_scan.py` guards against, it does not claim to be testing a *default*, which is why it is that scan's one registered exception rather than a fixed test |
| `bench/repro_check.py` has no test module | It self-checks instead. `self_check()` runs from `main()` on every invocation, with assertions proving the detector can see a difference before a zero from it is believed. It is a deliberate answer to `bench/` sitting outside coverage, stated in its own docstring |
| `bench/` outside C1/C2, coverage, the release archive and the linters | A decision, not arrears; `bench/README.md`'s self-check section has the reasoning for each of the four |

## 🎯 What to take first

Ordered by what breaks if it is left, not by size.

1. **Duplicate code in `chitragupta/` and `scripts/` goes undetected.**
   See [Tier 5](#-tier-5-continuous-integration-and-the-linters). The
   cost is a fix landing in one copy and not the other. Any detector
   added must be binary, like the others.
2. **The C1/C2 register.** Each entry is taken in its own pull request,
   largest first; the register says which.
3. **From Tier 2, the copies that already disagree or can collide:**
   R6 (the `Command:` lines), R1 (`doc_vectors.py`'s fixed temp
   name), R11 (the version readers) and R4 (the finding ids the
   agenda deduplicates on). Then R10, whose next TikZ spelling would
   otherwise be taught to one scanner only.
