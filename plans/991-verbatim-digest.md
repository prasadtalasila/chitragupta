# 📋 Verbatim digest: a sixth genre and an eleventh review aid (#991)

Status: **built on branch `worktree-bridge-cse_01C6bspGKiyF8JQyyV8aAMCr`, PR pending.**
What changed on the way: on a `pdftotext` corpus every run is "not
checkable", and the author chose to restrict the aid to the enriched
corpus (a Docling sidecar per cited source) rather than match against
unordered page text, so the skill copies from the sidecar and the
report names the stage to run; the `review/__init__.py` split and the
registry entries moved into Task 4, since `review.header` needs the
`AIDS` key; the "assembled" fixture needed a passage between its two
sentences, since adjacent passages are legitimately an `exact-pair`
match; and the agenda's registry-copy heuristic moved from three names
to four, because the exclusion tuple now names three.

Written 2026-10-09 against `main` at
`8b588b5` (#1039), for
[discussion 991](https://github.com/prasadtalasila/chitragupta/discussions/991),
and revised the same day on the author's six changes: no `.digest` in a
file the skill writes, the unsupported fraction as the headline, the
skill named `review-digest`, the survey's draft-and-render workflow
reused, and the guide explaining page mismatch and NLI support. One PR,
one MINOR bump (`6.138.0` → `6.139.0`).

**Written for** whoever builds #991: a session that changes
`chitragupta/review/`, `chitragupta/dossier/__init__.py`,
`chitragupta/review/_units.py`, `tests/`, the three skill trees and
`docs/`, and so is governed by `DEVELOPER-AGENTS.md` and
`docs/CODE-STANDARDS.md`. Every path below is from the repository root.

**Assumed:** you have read the discussion itself (the goals, the
constraints, the component table, the classification rules, the
trade-off table and the four open questions), `docs/REVIEW.md`,
`docs/AGENDA.md`, `.claude/skills/survey-writer/SKILL.md`,
`chitragupta/review/quotation.py` with `_quotation_match.py` beside it,
and `chitragupta/review/agenda/` (`_identity.py`, `_recheck.py`,
`__init__.py`'s `run`).

**Not covered here:** wiring the NLI `support` model into the digest
aid (explained in the guide, declined as a flag; see the decisions),
and any change to `agenda`, `agenda-reviser`, the five genre skills,
the evidence sidecar or the gate: the discussion rules those out and
this plan keeps them byte-identical except where a count they state
becomes false.

**Goal:** a person can ask for a verbatim digest of a topic, get
`content/drafts/<topic>/<name>.md` written mostly in the cited papers'
own words and rendered the way a survey is, and run
`python -m chitragupta.review digest` on it to see the unsupported
fraction, every sentence that is not verified source text, and whether
a repair pass made that number fall.

**Architecture:** one new genre (`digest` in `dossier.GENRES`, with a
`review-digest` skill per harness that follows `survey-writer`'s
draft-and-render workflow), one new review aid
(`chitragupta/review/verbatim_digest.py` plus four `_digest_*.py`
helpers), registered in `review.AIDS` and `review/_registry.AIDS` and
deliberately excluded from what `agenda` reads. The aid splits the
digest into citation-terminated runs, matches each run against the
cited source with `_quotation_match.locate`, drops to sentence level
only where a run breaks, and classifies what is left as
`unsupported-text`, `copy-mismatch` or `unquoted-text`, all
`[surfaced]`. The headline is the unsupported fraction: words in
sentences carrying any finding, over all words. `--baseline` compares a
run against an earlier `.json`.

**Tech stack:** stdlib Python (interpreter tier 1, like every other
aid), pytest at 100% line and branch coverage, Markdown skill files in
three harness copies, `.opencode/opencode.json`.

**Spec:** discussion #991 plus the author's six revisions recorded in
the Status line. This plan argues from them; read both.

## 🧭 Table of contents

- [Decisions this plan makes](#-decisions-this-plan-makes)
- [Where the survey workflow is inverted](#-where-the-survey-workflow-is-inverted)
- [Global constraints](#-global-constraints)
- [File structure](#-file-structure)
- [Review focus](#-review-focus)
- [Task 1: `_claims.claim_blocks`, a seam the digest parser needs](#task-1-_claimsclaim_blocks-a-seam-the-digest-parser-needs)
- [Task 2: `_digest_runs.py`, the digest as citation-terminated runs](#task-2-_digest_runspy-the-digest-as-citation-terminated-runs)
- [Task 3: `_digest_match.py`, verification, the three classes, the fractions](#task-3-_digest_matchpy-verification-the-three-classes-the-fractions)
- [Task 4: `_digest_render.py`, items, Markdown and the JSON payload](#task-4-_digest_renderpy-items-markdown-and-the-json-payload)
- [Task 5: `_digest_recheck.py`, `--baseline`](#task-5-_digest_recheckpy---baseline)
- [Task 6: `verbatim_digest.py`, the CLI, and registration](#task-6-verbatim_digestpy-the-cli-and-registration)
- [Task 7: the `digest` genre](#task-7-the-digest-genre)
- [Task 8: the `review-digest` skill, three copies](#task-8-the-review-digest-skill-three-copies)
- [Task 9: documentation and the count sweep](#task-9-documentation-and-the-count-sweep)
- [Task 10: version, full checks, PR](#task-10-version-full-checks-pr)
- [Self-review against #991](#-self-review-against-991)

## ⚖ Decisions this plan makes

Each answers something the discussion left open or did not say, or
records one of the author's revisions. Where a decision contradicts the
discussion's wording it says so and why.

| Decision | Chosen | Why, and the alternative |
| --- | --- | --- |
| **Names** (open question 1, revised) | Skill `review-digest` (OpenCode copy `review-digest-opencode`); aid key `digest`; module `chitragupta/review/verbatim_digest.py`; report label "Verbatim digest" | The author's name for the skill. `review digest` reads as the other ten aids do |
| **No `.digest` in a file the skill writes** (revised) | The digest is `content/drafts/<topic>/<name>.md`, named like any draft; what makes it a digest is `- genre: digest` in its dossier's `scope.md`, exactly as a survey is a survey. Its report is `content/review/<topic>/<name>.digest.md` + `.json` under the ordinary `<stem>.<aid>` rule, and its renders are `content/rendered/<topic>/<name>.{tex,pdf,md}` | The author's call. The discussion's `<name>.digest.md` would have doubled the infix in the report name and needed a stem-stripping special case; this needs nothing. The `.digest` in the *report* name is the aid's suffix, like `.quotation` or `.agenda`, and is not a file the skill writes |
| **Ignore rule** | None added. The existing blanket `content/*` already ignores every digest, its dossier, its report and its renders outside the one tracked example topic, and `tests/test_gitignore_covers_content.py` already proves that | The discussion asked for a rule keyed on a name, like the sidecar's `.evidence` infix. With no infix there is nothing to key on, and the example topic's drafts are curated by hand; a digest will not land there by accident. Named in `docs/VERBATIM-DIGEST.md` so the reader knows the file is per-host data like every other draft |
| **Headline metric** (revised) | **Unsupported fraction** = words in sentences carrying at least one finding (`unsupported-text`, `copy-mismatch` or `unquoted-text`, a sentence counted once) ÷ total words. The copied fraction (verified copied words ÷ total) is kept as the second line, and the not-checkable share as the third, so the three account for the whole digest | The author's call: the number a repair pass drives down is the one to lead with. `--baseline` reports it before and after, and `fell` requires it not to rise |
| **Writes unconditionally** | `.md` and `.json` are filed on every run, as `agenda` does; `--json` only picks stdout; `--formats` as every aid | The `.json` is the next pass's `--baseline`, which is the reason `agenda` has no `--write` flag either (`agenda/__init__.py`'s `run` docstring) |
| **Page mismatch** (open question 2, revised to explain) | A note on the copied span (`cited p. 4-5, found on p. 7`), never a class and never a finding; the guide gets a section on what a page is here and why a note arises | The three classes are what a person watches fall. A page note is a locator to correct, not unsupported text. What "page" means (the parse's physical page, not the printed folio), why a run can report two pages, and how to repair it are in `docs/VERBATIM-DIGEST.md`, Task 9 |
| **Draft and render workflow** (open question 3, revised) | The skill follows `survey-writer`'s process step for step: dossier, retrieval, gate, references, `draft render` to `tex`/`pdf`/`md`, read-as-the-reader, steering, prose check, fingerprint stamp, present. Three survey steps are replaced by `review digest` with the reason stated in the skill: the critique against the evidence packet, the verbatim scan, and the evidence sidecar | The author's call. Reuses the chain every genre runs and the hook already enforces; a digest renders like any draft. The three replaced steps would each report the digest's defining property as a defect: the scan flags every run, the critique reads a `claim:`/`quote:` packet the digest never drafts from, and a sidecar would print the digest back. The survey minimises copying and the digest maximises it, so the reuse is of the *mechanical chain* only; every step and rule that carries the survey's anti-copying posture is listed and inverted in [Where the survey workflow is inverted](#-where-the-survey-workflow-is-inverted) |
| **Support tier** (open question 4, revised to explain) | `unsupported-text` stays lexical (`citation_provenance.score_claim` under `config.PROVENANCE_WEAK_SCORE`), and the guide explains what `review support`'s NLI entailment model adds, how to run it on a digest by hand, and why it is not wired in | Reuses a threshold that ships and is documented; needs no optional dependency; keeps the aid at interpreter tier 1. The explanation is in `docs/VERBATIM-DIGEST.md`, Task 9, and the skill's step 14 names the command |
| **`copy-mismatch` boundary** | `MISMATCH_SHARE = 0.8`: a sentence `locate` cannot find whose distinctive words are at least 80% present on one page of the source | "Nearly matches" needs a number. `near_miss` already computes this share; the constant is published with its reason and is not to be tuned (docs/CODE-STANDARDS.md R3). Below it the sentence is the drafter's own and is `unquoted-text` |
| **A sentence is its own whole** | A finding carries the whole sentence; a half-copied sentence is a `copy-mismatch` with the missing words listed | The discussion's stated con. Splitting a sentence into copied and original halves is a second matcher this plan does not build |
| **Several citekeys in one bracket** | `[@a; @b]` closes one run matched against the union of both sources' passages; items carry every key, the id uses the first | One run, one citation, as the attribution rule says |
| **A citation anywhere closes a run** | The run ends at the bracket wherever it sits, even mid-sentence; what follows starts the next run | One rule with no special case. The skill writes citations at the end of a sentence, so the mid-sentence case is a drafting error the report shows as a broken run |
| **`agenda` does not read it** | `digest` joins `agenda` and `union` in `agenda/_sources.AID_NAMES`'s exclusion, and `TestAidNames` is updated to say so | Required by the discussion, and `AID_NAMES` is derived from `review.AIDS`, so without the exclusion every existing agenda would gain a "digest: read" line and `--baseline` would run the digest aid live |
| **Genre tables** | `_units.UNITS["digest"] = "document"`, `_units.UNCITED_PROSE["digest"] = "ordinary"` | Both tables are pinned to `dossier.GENRES` by tests. A digest fuses nothing, so the whole document is its unit, as for a tutorial; its connecting sentences carry no citation by design and the digest aid is what judges them |
| **Which step scans bind the skill** | Named in `_HELPERS` of the verbatim-scan scan and in `_EXCLUDED_SKILLS` of the pre-gate critique scan, each with its reason. It **does** carry the prose-check step, so the style scan needs no exemption. The acronym scan lists its five skills by name and is left as is | Follows from the workflow decision above |
| **Item identity** | `agenda/_identity.item_id("digest", cls, section, first citekey, sentence)` and `section_anchor`, imported | The one place agenda items get an id; a copy here is what `tests/test_duplicate_helper_scan.py` exists to catch |
| **`review/__init__.py` at the C2 ceiling** | `require_reviewable` and `report_dir` move to `chitragupta/review/_paths.py` and are re-imported into `review/__init__.py` under their names | The module holds 250 code lines today and `AIDS` needs one more. The split is forced and lands at the boundary the module's own docstring draws; `report_path` stays because it needs `AIDS`. No caller changes |
| **No sample-project report** | `docs/examples/sample-project/content/review/` gains nothing | A digest is per-host data; REVIEW.md's sentence about the sample set gets the exception named |

## 🔄 Where the survey workflow is inverted

`survey-writer` is built to **minimise** copying: it drafts from
`claim:` lines written in the drafter's own words, fuses two or more
sources per paragraph so no paragraph can be a transcription, critiques
the draft against the evidence packet, and runs the verbatim scan. The
digest is built to **maximise** copying. Reusing the survey workflow
therefore means reusing its mechanical chain (dossier, retrieval, gate,
references, render, prose check, stamp) and inverting, step by step,
everything in it that exists to keep source wording out of the draft.
The skill (Task 8) says so at each step, and the global rules that state
the survey's posture get a carve-out naming the digest (Task 9), so a
reader of either file meets a decision rather than a contradiction.

| Survey step or rule | Carries the anti-copying posture? | In the digest |
| --- | --- | --- |
| Step 0 dossier, reader, scope, dialect | no | kept. Dialect governs only the connecting sentences; copied text keeps its source's spelling |
| Step 1 retrieval per sub-theme, `outline.md` queries verbatim | no | kept |
| Step 2 evidence packet: `claim:` in your own words, `quote:` "only when a quotation is genuinely warranted", "`claim:` is the only field you may draft prose from" | **yes**, the heart of it | **inverted, inside the contract rather than against it.** Every passage the digest will copy is recorded as a `quote:`, since in a digest every run *is* an intended quotation; the block's `claim:` still says in the drafter's words what the passage establishes, which is what a later `draft-reviser` reads. The connecting sentences are the only prose drafted from `claim:`. `docs/DOSSIER.md`'s "`quote:` is usable in a draft only inside quotation marks with an attribution" gains the digest as the one named exception: attributed per run, no quotation marks, never a drafting source |
| "Prose standards" section and `docs/WRITING-STANDARDS.md` §4 sentence craft | partly: it governs the drafter's voice | applies to the connecting sentences only. The skill says the copied text is exempt by definition and the prose check (step 16) will flag it; report and fix none |
| Step 6 draft, and `docs/WRITING-STANDARDS.md` §11 "a paragraph closes on more than one citekey; you cannot transcribe two sources simultaneously" | **yes** | **inverted.** One source per run, by rule; a run is a transcription by design. §11's table gets a `digest` row: unit "document", "every run is one source's words; the rule has no paragraph to bind at, and `review digest` is the check that applies". `_units.UNITS["digest"] = "document"` (Task 7) is the code half |
| Step 7 never write a citekey you did not retrieve | no | kept unchanged |
| Step 8 section map | no | kept |
| Step 9 figure | no (none drawn) | nothing drawn; a source's figure crop may be placed beside its run, the one exception AGENTS.md records |
| Step 10 critique against the evidence packet (shared `critique.md`, which itself runs the verbatim scan and edits toward less overlap) | **yes** | **replaced** by `review digest` (step 14); named in `_EXCLUDED_SKILLS` |
| Steps 11-12 gate, references, render | no | kept verbatim |
| Step 13 evidence sidecar | yes: it is where verbatim wording goes *instead of* the draft | **replaced**: the digest is the sidecar's content, cited per run |
| Step 14 read as the reader | no | kept, with digest-specific checks |
| Step 16 prose check | partly | kept, report-only, with the expectation stated that copied text is flagged |
| Step 17 verbatim scan (shared `verbatim-scan.md`) | **yes** | **replaced** by `review digest`; named in the scan's `_HELPERS` |
| Step 18 stamp and present | no | kept |
| `AGENTS.md` "Verbatim source wording has one legitimate home, and it is not the draft ... never copy a span out of one back into body prose" | **yes**, and it binds every skill | gets the carve-out: *one genre, the verbatim digest, is that wording with a citation closing every run, and it is never a source for any other draft* (Task 9 step 2) |
| `docs/GENRE.md` "What all N have in common": the verbatim scan is run, the critique is shared by the genre skills | **yes** | the section names the digest's two exemptions and why (Task 9 step 2) |
| `agenda-reviser`'s `verbatim-run` repair, which paraphrases short runs unattended | **yes**, and the discussion forbids changing it | the `agenda` never reads the digest aid, but `review agenda` run by hand on a digest would still queue every run from `review verbatim scan`'s report if someone had filed one, and `agenda-reviser` would then paraphrase the digest away. Guarded in prose only, since the two skills are frozen: the digest skill, `docs/VERBATIM-DIGEST.md` and one sentence in `docs/AGENDA.md` say never to run `agenda-reviser` on a digest. Recorded as the one residual hazard this PR cannot close in code |

## 🔒 Global constraints

- A citekey appears in a test, a doc or the skill only if it is one the
  repository already uses in fixtures (`shao_analysis_2023`,
  `smith_example_2024`) or is a plainly synthetic one in a fixture that
  writes its own source text. Never a plausible real key (CLAUDE.md).
- Every check reports and exits 0. `review digest` returns 1 only for a
  draft the layer will not read and 2 only for a malformed invocation,
  the codes `chitragupta/review/__main__.py` documents. Nothing here is a
  gate, and nothing may be promoted to one.
- `chitragupta/` modules: at most 250 code lines each, at most 25
  statements per function, stdlib only, no `__main__` block in an aid
  module (`tests/test_review_entrypoint.py`). Measure with
  `python scripts/code_standards.py <path>` before committing a module.
- 100% line and branch coverage, enforced by `fail_under = 100`.
- The three `SKILL.md` copies are identical after
  `tests/fixtures/skill_harness_phrases.toml`'s substitutions and the
  `-opencode` suffix; the new skill names no harness tool, so it needs
  no phrase entry.
- Version: `6.139.0` in `pyproject.toml` (MINOR: a new module and a new
  subcommand).
- `python -m chitragupta.draft gate` runs on every digest, unchanged.

## 🗂 File structure

| Path | Status | Responsibility |
| --- | --- | --- |
| `chitragupta/review/_claims.py` | modify | gains `claim_blocks(text)`, the per-block half of `claim_sentences`, so the digest parser reads the same blocks the other aids do |
| `chitragupta/review/_digest_runs.py` | create | `Run`; `runs(text)` splits each claim-bearing block at its citation brackets into citation-terminated runs and an uncited tail; `cited_pages` |
| `chitragupta/review/_digest_match.py` | create | `Span`, `Finding`, `Checked` with the three fractions; `check_run` verifies one run against its sources and classifies what fails; `MISMATCH_SHARE`, `CLASSES` |
| `chitragupta/review/_digest_render.py` | create | `items` (ids, anchors, order), `payload`, `render_markdown` |
| `chitragupta/review/_digest_recheck.py` | create | `load_baseline`, `compare`, `recheck_command`, `recheck_payload`, `format_recheck` |
| `chitragupta/review/verbatim_digest.py` | create | `build_parser`, `run`, `build_report` |
| `chitragupta/review/_paths.py` | create | `require_reviewable`, `report_dir`, moved out of `review/__init__.py` unchanged |
| `chitragupta/review/__init__.py` | modify | `AIDS["digest"]`; imports the two moved functions; docstring counts |
| `chitragupta/review/_registry.py` | modify | `AIDS["digest"]` |
| `chitragupta/review/__main__.py` | modify | docstring entry, `DESCRIPTION` count |
| `chitragupta/review/agenda/_sources.py` | modify | `AID_NAMES` excludes `digest`; comment |
| `chitragupta/dossier/__init__.py` | modify | `GENRES` gains `digest` |
| `chitragupta/review/_units.py` | modify | `UNITS` and `UNCITED_PROSE` gain `digest` |
| `tests/test_review_digest_runs.py` | create | Task 2 |
| `tests/test_review_digest_match.py` | create | Task 3 |
| `tests/test_review_digest.py` | create | Tasks 4, 5, 6 (render, recheck, CLI) |
| `tests/test_review_uncited.py` | modify | one test for `claim_blocks` |
| `tests/test_review_agenda.py`, `tests/test_review_units.py`, `tests/test_review_uncited.py`, `tests/test_dossier.py`, `tests/test_architecture_review_layer.py`, `tests/test_features_doc.py`, `tests/test_skill_frontmatter.py`, `tests/test_skill_verbatim_scan_step.py`, `tests/test_skill_style_check_step.py`, `tests/test_skill_pregate_feedback_step.py` | modify | counts and exclusion sets, each named in the task that moves it |
| `.claude/skills/review-digest/SKILL.md`, `.agents/skills/review-digest/SKILL.md`, `.opencode/skills/review-digest-opencode/SKILL.md` | create | the genre skill |
| `.opencode/opencode.json` | modify | deny `review-digest` |
| `docs/VERBATIM-DIGEST.md` | create | the guide, including the page-mismatch and NLI-support sections |
| `docs/REVIEW.md`, `docs/CLI.md`, `docs/GENRE.md`, `docs/FEATURES.md`, `docs/GLOSSARY.md`, `docs/DOSSIER.md`, `docs/WRITING-PROCESS.md`, `docs/ARCHITECTURE.md`, `docs/DIAGRAMS.md` + `docs/diagrams/00-main-workflow.mmd` + its SVG, `docs/CONFIG.md`, `docs/PERFORMANCE.md`, `docs/PLAGIARISM.md`, `AGENTS.md`, `README.md`, `DEVELOPER.md`, `mkdocs.yml`, `config.toml.example`, `docs/examples/*/config.toml`, `bench/bench_review_cost.py` | modify | Task 9 |
| `pyproject.toml` | modify | version |

## 🔍 Review focus

Inputs the discussion implies and a person will meet; each has its test
in the task named.

1. **A digest whose block ends with a citation and nothing after it**
   (the common case) must produce no uncited tail: an empty trailing
   segment is dropped, not reported as an empty `unquoted-text`.
   Task 2, `test_a_block_ending_in_a_citation_has_no_tail`.
2. **A citation bracket that is not a citation** (`[see 3]`, `[sic]`,
   a `[@label]` example reference) must not close a run.
   Task 2, `test_a_bracket_without_a_citekey_does_not_close_a_run`.
3. **A cited source with only page-level text** (a rung-3 parse) must
   land in `unverifiable` with a reason, and its words must count
   toward the total and the not-checkable share, never toward copied,
   flagged or a finding.
   Task 3, `test_a_source_without_reading_order_is_unverifiable`.
4. **A baseline that is another aid's `.json`** (the likeliest typo,
   `notes.agenda.json`) must be refused with exit 2 before any work.
   Task 5, `test_another_aids_payload_is_refused`; Task 6,
   `test_a_bad_baseline_exits_two_before_reading_the_ledger`.
5. **An empty digest or one with no runs at all** must report every
   fraction as 0.0 rather than divide by zero, and exit 0.
   Task 3, `test_an_empty_digest_has_fractions_zero`; Task 6,
   `test_a_digest_with_no_prose_exits_zero`.

---

### Task 1: `_claims.claim_blocks`, a seam the digest parser needs

`_claims.claim_sentences` already decides which blocks of a draft carry
a claim: code blanked, headings, captions, comments and table headers
excluded, the reference list cut off. The digest parser needs those same
blocks *before* they are split into sentences, because a citation
bracket is what splits a digest block, not a full stop. Expose the block
half as a public function and rebuild `claim_sentences` on it. No
behaviour changes.

**Files:**

- Modify: `chitragupta/review/_claims.py:186-225`
- Test: `tests/test_review_uncited.py` (the file that already covers
  `_claims`)

**Interfaces:**

- Produces: `claim_blocks(text: str) -> list[tuple[int, list[str], str]]`,
  one `(first line, raw lines, prose text)` per claim-bearing block in
  document order. `claim_sentences` keeps its signature and output.

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 2: `_digest_runs.py`, the digest as citation-terminated runs

**Files:**

- Create: `chitragupta/review/_digest_runs.py`
- Test: `tests/test_review_digest_runs.py`

**Interfaces:**

- Consumes: `_claims.claim_blocks`, `_blocks.line_of_offset`,
  `sentences.spans`, `citation_gate.extract_citekeys_from_line`.
- Produces:

```python
@dataclass(frozen=True)
class Run:
    line: int                      # first line of the run's first sentence
    sentences: tuple[str, ...]     # the run's sentences, bracket excluded
    citekeys: tuple[str, ...]      # () for an uncited tail
    citation: str | None           # the bracket as written, None for a tail
    pages: tuple[int, int] | None  # the locator hint, (first, last)
    text -> str                    # sentences joined with one space
    words -> int                   # len(text.split())

def runs(text: str) -> list[Run]
def cited_pages(citation: str) -> tuple[int, int] | None
```

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 3: `_digest_match.py`, verification, the three classes, the fractions

**Files:**

- Create: `chitragupta/review/_digest_match.py`
- Test: `tests/test_review_digest_match.py`

**Interfaces:**

- Consumes: `Run` from Task 2; `_quotation_match.locate(quote, passages)`
  → `(tier, pages) | None`; `_quotation_match.near_miss(quote, passages)`
  → `(share, page)`; `citation_provenance.score_claim(claim, passages)`
  → `(score, passage)`; `passages.distinctive(text)` → `set[str]`;
  `config.PROVENANCE_WEAK_SCORE`.
- Produces:

```python
MISMATCH_SHARE = 0.8
CLASSES = ("unsupported-text", "copy-mismatch", "unquoted-text")   # worst first

@dataclass(frozen=True)
class Span:      # verified copied text
    line: int; citekeys: tuple[str, ...]; text: str; tier: str
    pages: tuple[int, ...]; cited: tuple[int, int] | None; note: str | None

@dataclass(frozen=True)
class Finding:
    cls: str; line: int; text: str; citekeys: tuple[str, ...]; detail: dict

@dataclass
class Checked:
    spans: list[Span]; findings: list[Finding]; unverifiable: list[dict]; words_total: int
    words_copied -> int        # words in spans
    words_flagged -> int       # words in distinct sentences carrying any finding
    words_unverifiable -> int  # words in runs that could not be checked
    unsupported_fraction -> float   # the headline: words_flagged / words_total
    copied_fraction -> float
    unverifiable_fraction -> float

Lookup = Callable[[str], tuple[list[Passage], str | None]]
def check_run(run: Run, lookup: Lookup, checked: Checked) -> None
def page_note(cited, pages) -> str | None
```

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 4: `_digest_render.py`, items, Markdown and the JSON payload

**Files:**

- Create: `chitragupta/review/_digest_render.py`
- Test: `tests/test_review_digest.py` (new; this task starts it)

**Interfaces:**

- Consumes: `Checked`, `Span`, `Finding`, `CLASSES` from Task 3;
  `agenda._identity.item_id`, `section_anchor`; `dossier.sections`;
  `review.header`, `review.envelope`.
- Produces:

```python
def items(checked: Checked, draft_text: str) -> list[dict]
    # {"id", "class", "disposition": "surfaced", "section", "citekeys", "line", "summary", "detail"}
    # ordered by CLASSES, then line, then id
def payload(draft: Path, command: str, checked: Checked, rows: list[dict]) -> dict
    # envelope + unsupported_fraction, copied_fraction, unverifiable_fraction,
    # words_total, words_flagged, words_copied, words_unverifiable,
    # counts, items, spans, unverifiable
def render_markdown(draft: Path, command: str, checked: Checked, rows: list[dict]) -> str
```

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 5: `_digest_recheck.py`, `--baseline`

**Files:**

- Create: `chitragupta/review/_digest_recheck.py` (replacing the placeholder)
- Test: `tests/test_review_digest.py` (append)

**Interfaces:**

- Consumes: a `payload` dict from Task 4 (`items`, `counts`,
  `unsupported_fraction`, `copied_fraction`).
- Produces:

```python
def load_baseline(path) -> dict                # ValueError when unusable
def compare(payload: dict, baseline: dict) -> dict
    # {"resolved": [item], "persisting": [item], "new": [item],
    #  "counts_before": {cls: n}, "counts_after": {cls: n},
    #  "unsupported_before": float, "unsupported_after": float,
    #  "copied_before": float, "copied_after": float,
    #  "fell": bool}   # no class count rose, at least one fell, no new item,
    #                  # and the unsupported fraction did not rise
def recheck_command(draft, baseline) -> str
def recheck_payload(draft, baseline, comparison) -> dict
def format_recheck(baseline, comparison) -> str
```

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 6: `verbatim_digest.py`, the CLI, and registration

This task also makes the forced split of `review/__init__.py` and
decides `agenda`'s exclusion. It is one task because none of it is
testable through the entry point until all of it exists.

**Files:**

- Create: `chitragupta/review/verbatim_digest.py` (replacing the placeholder)
- Create: `chitragupta/review/_paths.py`
- Modify: `chitragupta/review/__init__.py` (`AIDS`, imports, docstring)
- Modify: `chitragupta/review/_registry.py:26-38`
- Modify: `chitragupta/review/__main__.py` (docstring list, `DESCRIPTION`)
- Modify: `chitragupta/review/agenda/_sources.py:26-61`
- Modify: `tests/test_review_agenda.py:111`
- Test: `tests/test_review_digest.py` (append), `tests/test_review.py`
  (unchanged, must stay green through the split)

**Interfaces:**

- Consumes: everything above; `review.require_reviewable`,
  `review.write`, `review.write_json`, `_emit.formats`, `_emit.announce`,
  `ledger.reading`, `passages.source_passages`.
- Produces:

```python
AID = "digest"
def build_report(draft: Path) -> tuple[Checked, list[dict]]
def build_parser(parser=None) -> argparse.ArgumentParser   # draft, --formats, --json, --baseline
def main(argv=None) -> int
def run(args) -> int
```

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 7: the `digest` genre

**Files:**

- Modify: `chitragupta/dossier/__init__.py:39`
- Modify: `chitragupta/review/_units.py:40-70`
- Test: `tests/test_review_units.py`, `tests/test_review_uncited.py`
  (both pin the tables to `dossier.GENRES` and will go red at Step 2),
  `tests/test_dossier.py` (one new test)

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 8: the `review-digest` skill, three copies

The skill follows `survey-writer`'s process step for step. Where a
survey step is replaced, the skill says so and why, in the step's own
place, so a reader comparing the two files sees a decision rather than
a gap.

**Files:**

- Create: `.claude/skills/review-digest/SKILL.md`
- Create: `.agents/skills/review-digest/SKILL.md` (same text, same `name:`)
- Create: `.opencode/skills/review-digest-opencode/SKILL.md`
  (same text; `name:` and the `#` heading carry `-opencode`, and so does
  every other skill it names: `draft-reviser-opencode`,
  `corpus-reviser-opencode`, `survey-writer-opencode`,
  `agenda-reviser-opencode`)
- Modify: `.opencode/opencode.json`: add `"review-digest": "deny"` in
  alphabetical position, after `figure-drawer`
- Modify: `tests/test_skill_frontmatter.py:38`
  (`== 33  # eleven skills, three harnesses`)
- Modify: `tests/test_skill_verbatim_scan_step.py:144`: `_HELPERS` gains
  `"review-digest"`, with its comment; and
  `test_genre_doc_still_speaks_for_every_skill_that_exists`: `count == 11`,
  the string `"What all eleven have in common"`, and the two message
  literals that say "all ten"
- Modify: `tests/test_skill_style_check_step.py:121`: the "What all ten
  have in common" literal only; the skill carries the prose-check step,
  so `_HELPERS` is unchanged
- Modify: `tests/test_skill_pregate_feedback_step.py:75-81`: add
  `"review-digest"` to `_EXCLUDED_SKILLS`; "The five skills that
  must never carry this step" → "The six"
- Modify: `tests/test_features_doc.py` and
  `tests/test_architecture_review_layer.py`: `_NUMBER_WORDS` gains
  `11: "Eleven"` in both; Task 9 makes the docs match

The reasons, as a comment beside each exclusion: *a digest is verbatim
by design (#991): the scan would flag every run as reuse, and the
critique loop reads a `claim:`/`quote:` packet the digest never drafts
from. Its own aid, `review digest`, is the step that replaces both. It
does run the prose check, reporting and fixing nothing, as every
drafting skill does.*

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 9: documentation and the count sweep

Step 4 of the shipping cycle, done as its own task because an eleventh
aid and a sixth genre move a count in many files outside the diff.
Three searches, in this order, and the exact edits each one found when
this plan was written against `8b588b5`. Re-run the greps: `main` may
have moved.

**Files:** every path in the table under File structure marked for
Task 9.

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

### Task 10: version, full checks, PR

Steps elided after the build: the tests and modules named above are
the record, and `git log` carries each task's commit.

---

## 🔎 Self-review against #991

| Item | Where it lands |
| --- | --- |
| Skill: refuses on an empty ledger, keeps a dossier, writes the digest, runs `draft gate` and `review digest` before presenting | Task 8, steps 0, 10, 14 |
| Revision 1: no `.digest` in a file the skill writes | Decisions table; Task 6 (`report_path` under the ordinary rule); Task 8 step 0 |
| Revision 2: unsupported fraction as the headline | Task 3 `Checked.unsupported_fraction`; Task 4 summary order; Task 5 `fell` |
| Revision 3: skill named `review-digest` | Task 8; `.opencode/opencode.json`; every doc row in Task 9 |
| Revision 4: page mismatch explained | Guide section "Pages, and what a page note means" (Task 9 step 1); CLI.md paragraph; skill step 14 and format rule |
| Revision 5: the survey's draft and render workflow | Task 8 process, steps 0-18 mirroring `survey-writer`, with the three replaced steps named in place |
| The survey minimises copying, the digest maximises it | [Where the survey workflow is inverted](#-where-the-survey-workflow-is-inverted): every survey step and global rule carrying the posture, and what the digest does with each; the skill's opening paragraph and steps 2 and 6 (Task 8); the AGENTS.md, DOSSIER.md, WRITING-STANDARDS §11 and AGENDA.md carve-outs (Task 9 step 2); the `agenda-reviser` hazard, guarded in prose |
| Revision 6: NLI support explained | Guide section "Lexical support, and what the NLI `support` aid adds" (Task 9 step 1); skill step 14 |
| Genre entry `digest` in the dossier's registry and `docs/GENRE.md` | Task 7; Task 9 step 2 |
| Review aid `digest` in `chitragupta/review/verbatim_digest.py` plus its renderer | Tasks 2-6 |
| Registration: one key each in `review.AIDS` and `review/_registry.AIDS`, drift check keeps them wired | Task 6 steps 3-4 (the existing `RuntimeError` in `_registry.py` is the drift check) |
| Ignore rule | Decisions table: the existing blanket, already tested |
| Docs: `docs/VERBATIM-DIGEST.md`, rows in REVIEW.md, GENRE.md, CLI.md, a router line in AGENTS.md | Task 9 steps 1-2 |
| Data flow ledger → dossier → `<name>.md` → gate + render + `review digest` → `content/review/<topic>/<name>.digest.{md,json}` | Task 6 `_file`; Task 8 steps 0-14 |
| Plain text plus closing citation; attribution rule | Task 2 `_segments`, `runs` |
| Whole-run match first, "assembled from N places" as information | Task 3 `check_run`, `_sentence_level` |
| Sentence-level fallback: `copy-mismatch` with differing words, `unquoted-text` | Task 3 `_mismatch`, `_own` |
| `unsupported-text` on top, via lexical provenance | Task 3 `_own` with `score_claim` |
| Page as a hint; actual page reported | Task 3 `page_note`; Task 2 `cited_pages` |
| Classes worst first; all `[surfaced]`; agenda-format item lines with 12-character ids | Task 4 |
| `--baseline` with per-class counts and the fractions | Task 5 |
| `agenda` and `agenda-reviser` untouched; no "digest: not run" line | Task 6 step 4 (`AID_NAMES`), Task 9 "do not touch" row |
| Repair loop, keep-conditions, only when asked | Task 8 step 17; `fell` in Task 5 |
| Every check exits 0; no gate | Task 6 `run`; global constraints |
| Cons: coarse attribution, parse quality, half-copied sentences, lexical support, surface area, SOUL.md tension | Decisions table; guide sections "What it does not do", "Lexical support", "The rule it lives under" |
| Pros: existing `verbatim scan` catches leakage | Skill's opening paragraph; AGENTS.md router line |

Type consistency checked: `Run.pages`/`Span.cited` are `(first, last)`
tuples; `Span.pages` is a tuple of found pages, serialised as a list;
`items` rows carry `class`, never `cls`; `compare` reads `counts`,
`unsupported_fraction` and `copied_fraction` from the payload
`payload()` writes; the aid writes under the draft's own path with no
stem rewriting anywhere.
