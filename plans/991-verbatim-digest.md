# 📋 Verbatim digest: a sixth genre and an eleventh review aid (#991)

> **For agentic workers:** REQUIRED SUB-SKILL: use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to carry out this plan task by task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

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
| Step 9 figure | no (none drawn) | dropped, with the reason |
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

- [ ] **Step 1: Write the failing test**

Append to `tests/test_review_uncited.py`:

```python
class TestClaimBlocks:
    def test_yields_the_blocks_claim_sentences_is_built_from(self):
        """`claim_blocks` is the per-block half of `claim_sentences`:
        headings and the reference list are out, prose paragraphs are in,
        and the raw lines are the draft's own so a caller can map an
        offset back to a line."""
        text = (
            "# Title\n\nFirst para one. First para two.\n\n"
            "## Second\n\nSecond para [@smith_example_2024].\n\n"
            "## References\n\n[1] S. Smith, 2024.\n"
        )
        blocks = _claims.claim_blocks(text)
        assert [(line, prose) for line, _, prose in blocks] == [
            (3, "First para one. First para two."),
            (7, "Second para [@smith_example_2024]."),
        ]
        assert blocks[0][1] == ["First para one. First para two."]
        assert [s.text for s in _claims.claim_sentences(text)] == [
            "First para one.",
            "First para two.",
            "Second para [@smith_example_2024].",
        ]
```

Add `from chitragupta.review import _claims` to the imports if the file
does not already have it.

- [ ] **Step 2: Run it, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_uncited.py -k TestClaimBlocks -v
```

Expected: FAIL, `AttributeError: module ... has no attribute 'claim_blocks'`.

- [ ] **Step 3: Implement**

Replace `claim_sentences` in `chitragupta/review/_claims.py` with:

```python
def claim_blocks(text: str) -> list[tuple[int, list[str], str]]:
    """(first line, raw lines, prose text) for every block of `text`
    that carries a claim, in document order.

    The per-block half of `claim_sentences`, exposed on its own because
    the verbatim digest (`_digest_runs.py`) splits a block at its
    citation brackets rather than at sentence boundaries, and it must
    read exactly the blocks every other aid reads -- code blanked,
    headings and captions out, the reference list cut -- or two aids
    would disagree about what the draft's prose is.
    """
    lines = _body(text)
    found = []
    for start, end, block in _blocks.spans(lines):
        after = lines[end] if end < len(lines) else ""
        raw_block = lines[start - 1 : end]
        if block.strip() and not _excluded(raw_block, after):
            found.append((start, raw_block, block))
    return found


def claim_sentences(text: str) -> list[Sentence]:
    """Every sentence of `text` that carries a claim, in document order.

    The split is `chitragupta/sentences.py`'s, shared with tier 3 of the
    overlap scan and with `citation_provenance` -- C1's roadmap entry
    asks for a splitter "somewhere C2 can reuse it", and that module has
    been it since before C1 was planned. The blocks are `claim_blocks`,
    so a table row and a list item are each their own claim rather than
    fragments of one paragraph, and a block left empty by stripping its
    list marker is no claim at all.
    """
    found = []
    for start, raw_block, block in claim_blocks(text):
        block_cites = bool(citation_gate.extract_citekeys(block))
        for sent_start, sent_end in sentences.spans(block):
            found.append(
                Sentence(
                    _blocks.line_of_offset(start, raw_block, sent_start),
                    block[sent_start:sent_end],
                    bool(citation_gate.extract_citekeys(block[sent_start:sent_end])),
                    block_cites,
                )
            )
    return found
```

- [ ] **Step 4: Run the file and the uncited/provenance suites**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_uncited.py tests/test_citation_provenance.py -q
python scripts/code_standards.py chitragupta/review/_claims.py
```

Expected: all pass, and the standards scan reports nothing.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_claims.py tests/test_review_uncited.py
git commit -m "Expose the claim-bearing blocks of a draft as _claims.claim_blocks"
```

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

- [ ] **Step 1: Write the failing tests**

`tests/test_review_digest_runs.py`:

```python
"""chitragupta/review/_digest_runs.py: a verbatim digest read as runs.

The draft format has no markup: copied text is ordinary prose and a
citation ends each copied run (discussion #991). The attribution rule is
that a citation covers every sentence back to the previous citation, or
to the start of the block. These tests pin that rule, and the two
shapes it has to survive: a block that ends in a citation with nothing
after it, and a bracket that only looks like a citation.
"""

from chitragupta.review import _digest_runs as runs_mod

KEY = "shao_analysis_2023"
OTHER = "smith_example_2024"


def test_a_citation_covers_back_to_the_previous_citation():
    text = (
        "# Notes\n\n"
        f"One. Two. Three. [@{KEY}, p. 4-5]\n"
        "A connecting sentence of my own.\n"
        f"Four. [@{OTHER}, p. 12]\n"
    )
    found = runs_mod.runs(text)
    assert [(r.sentences, r.citekeys, r.pages) for r in found] == [
        (("One.", "Two.", "Three."), (KEY,), (4, 5)),
        (("A connecting sentence of my own.", "Four."), (OTHER,), (12, 12)),
    ]
    assert found[0].citation == f"[@{KEY}, p. 4-5]"
    assert found[0].text == "One. Two. Three."
    assert found[0].words == 3


def test_a_block_ending_in_a_citation_has_no_tail():
    text = f"Copied sentence. [@{KEY}]\n"
    assert [r.citekeys for r in runs_mod.runs(text)] == [(KEY,)]


def test_sentences_after_the_last_citation_are_an_uncited_tail():
    text = f"Copied. [@{KEY}] My own closing thought. And another.\n"
    found = runs_mod.runs(text)
    assert found[1].citekeys == ()
    assert found[1].citation is None
    assert found[1].pages is None
    assert found[1].sentences == ("My own closing thought.", "And another.")


def test_a_block_with_no_citation_is_one_uncited_run():
    found = runs_mod.runs("Only my words here. Two of them.\n")
    assert len(found) == 1 and found[0].citekeys == ()


def test_a_bracket_without_a_citekey_does_not_close_a_run():
    text = f"Shown [see 3] earlier. More [sic] text. [@{KEY}]\n"
    found = runs_mod.runs(text)
    assert len(found) == 1
    assert found[0].sentences == ("Shown [see 3] earlier.", "More [sic] text.")


def test_several_citekeys_in_one_bracket_close_one_run():
    found = runs_mod.runs(f"Copied. [@{KEY}; @{OTHER}]\n")
    assert found[0].citekeys == (KEY, OTHER)


def test_a_mid_sentence_citation_closes_the_run_there():
    found = runs_mod.runs(f"The first half [@{KEY}] and the rest.\n")
    assert [r.sentences for r in found] == [("The first half",), ("and the rest.",)]


def test_lines_are_the_drafts_own():
    text = f"# Title\n\nLine three. [@{KEY}]\n\nLine five. [@{OTHER}]\nLine six.\n"
    assert [r.line for r in runs_mod.runs(text)] == [3, 5, 6]


def test_headings_code_and_the_reference_list_are_not_runs():
    text = (
        "# Title\n\n```\nnot [@fake_key_2020] prose\n```\n\n"
        f"Real. [@{KEY}]\n\n## References\n\n[1] Entry.\n"
    )
    assert [r.sentences for r in runs_mod.runs(text)] == [("Real.",)]


class TestCitedPages:
    def test_a_range(self):
        assert runs_mod.cited_pages("[@k, pp. 4-5]") == (4, 5)

    def test_a_single_page(self):
        assert runs_mod.cited_pages("[@k, p. 12]") == (12, 12)

    def test_an_en_dash_and_reversed_order(self):
        assert runs_mod.cited_pages("[@k, p. 9–7]") == (7, 9)

    def test_no_locator(self):
        assert runs_mod.cited_pages("[@k]") is None
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest_runs.py -q
```

Expected: FAIL at import, no module `_digest_runs`.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_runs.py`:

```python
"""A verbatim digest read as citation-terminated runs (#991).

The digest format carries no markup: copied text is ordinary prose and a
citation ends each copied run. The attribution rule is the whole of this
module -- **a citation covers every sentence back to the previous
citation, or to the start of the block** -- so a block is split at its
citation brackets, not at its sentence boundaries, and each piece is
then sentence-split for the fallback `_digest_match.py` needs when a
run is not found whole.

The blocks are `_claims.claim_blocks`', so a heading, a caption, a code
fence and the reference list are read the way every other aid reads
them. A bracket counts as a citation only if the citekey extractor finds
a key in it: `[see 3]` and `[sic]` leave a run open.

What follows the last citation in a block is a run with no citekeys --
the drafter's own tail -- and a block with no citation at all is one such
run. A citation with nothing before it (two brackets in a row) covers
nothing and is dropped.

Stdlib only, interpreter tier 1 like the aid that reads it.
"""

import re
from dataclasses import dataclass

from chitragupta import citation_gate, sentences
from chitragupta.review import _blocks, _claims

# A bracket holding at least one `@`. Whether it is a citation is the
# extractor's call, not this pattern's.
_BRACKET = re.compile(r"\[[^\[\]]*@[^\[\]]*\]")

# `p. 4`, `pp. 4-5`, `page 4`, `pages 4–5`. The hint pandoc passes
# through as a locator; the aid treats it as a hint and reports the page
# the text was actually found on.
_PAGES = re.compile(r"\b(?:pp?\.|pages?)\s*(\d+)(?:\s*[-–—]+\s*(\d+))?")


@dataclass(frozen=True)
class Run:
    """One citation-terminated run, or the uncited tail of a block."""

    line: int
    sentences: tuple[str, ...]
    citekeys: tuple[str, ...]
    citation: str | None
    pages: tuple[int, int] | None

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    @property
    def words(self) -> int:
        return len(self.text.split())


def cited_pages(citation: str) -> tuple[int, int] | None:
    """`(first, last)` from the bracket's page locator, or None."""
    match = _PAGES.search(citation)
    if match is None:
        return None
    first = int(match.group(1))
    last = int(match.group(2)) if match.group(2) else first
    return (min(first, last), max(first, last))


def _segments(block: str) -> list[tuple[int, str, str | None]]:
    """`(offset, text, citation)` per piece of `block`: the text before
    each citation bracket with that bracket, then whatever trails the
    last one with None."""
    found, at = [], 0
    for match in _BRACKET.finditer(block):
        if not citation_gate.extract_citekeys_from_line(match.group(0)):
            continue
        found.append((at, block[at : match.start()], match.group(0)))
        at = match.end()
    found.append((at, block[at:], None))
    return found


def runs(text: str) -> list[Run]:
    """Every run of `text`, in document order."""
    found = []
    for start, raw_block, block in _claims.claim_blocks(text):
        for offset, segment, citation in _segments(block):
            spans = sentences.spans(segment)
            if not spans:
                continue
            keys = tuple(citation_gate.extract_citekeys_from_line(citation)) if citation else ()
            found.append(
                Run(
                    _blocks.line_of_offset(start, raw_block, offset + spans[0][0]),
                    tuple(segment[a:b] for a, b in spans),
                    keys,
                    citation,
                    cited_pages(citation) if citation else None,
                )
            )
    return found
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest_runs.py -q
python scripts/code_standards.py chitragupta/review/_digest_runs.py
```

Expected: all pass, no C1/C2 finding. If
`test_a_mid_sentence_citation_closes_the_run_there` fails on a trailing
space in the first sentence, the tightening in `sentences.spans` has
changed; the expected tuple is the stripped sentence.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_runs.py tests/test_review_digest_runs.py
git commit -m "Read a verbatim digest as citation-terminated runs"
```

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

- [ ] **Step 1: Write the failing tests**

`tests/test_review_digest_match.py`:

```python
"""chitragupta/review/_digest_match.py: is this run really in the source,
and what is each sentence that is not?

Four outcomes per run, in the order the module tries them: found whole
(one span), every sentence found separately (one span, "assembled"),
some sentences found (spans for those, findings for the rest), and a
source that cannot be checked at all. The three finding classes are the
discussion's: `copy-mismatch` for a sentence most of whose words are on
one page, `unquoted-text` for everything else the drafter wrote, and
`unsupported-text` on top of that where the cited source does not
lexically support it, or nothing cites it. The headline is the
unsupported fraction: words in sentences carrying any finding, a
sentence counted once, over all words.
"""

import pytest

from chitragupta import config
from chitragupta.passages import Passage, distinctive
from chitragupta.review import _digest_match as match
from chitragupta.review._digest_runs import Run

KEY = "shao_analysis_2023"

SOURCE_P4 = (
    "Layered twins separate the physical entity from its models. "
    "Each layer exposes one interface to the next."
)
SOURCE_P7 = "Operators can start developing against the interface alone."


def passage(page: int, text: str) -> Passage:
    return Passage(page, distinctive(text), text)


def a_lookup(*passages: Passage, reason: str | None = None):
    calls = []

    def lookup(citekey: str):
        calls.append(citekey)
        return list(passages), reason

    lookup.calls = calls
    return lookup


def a_run(*sentences: str, citekeys=(KEY,), pages=None, line=3) -> Run:
    citation = f"[@{KEY}]" if citekeys else None
    return Run(line, tuple(sentences), tuple(citekeys), citation, pages)


def test_a_run_found_whole_is_one_span_and_no_finding():
    checked = match.Checked()
    run = a_run(
        "Layered twins separate the physical entity from its models.",
        "Each layer exposes one interface to the next.",
        pages=(4, 4),
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert checked.findings == []
    assert len(checked.spans) == 1
    span = checked.spans[0]
    assert (span.tier, span.pages, span.note) == ("exact", (4,), None)
    assert checked.words_total == run.words
    assert checked.words_copied == run.words
    assert checked.words_flagged == 0
    assert (checked.unsupported_fraction, checked.copied_fraction) == (0.0, 1.0)


def test_a_page_hint_the_text_is_not_on_becomes_a_note():
    checked = match.Checked()
    run = a_run("Operators can start developing against the interface alone.", pages=(4, 5))
    match.check_run(run, a_lookup(passage(7, SOURCE_P7)), checked)
    assert checked.spans[0].note == "cited p. 4-5, found on p. 7"


def test_sentences_found_in_different_places_are_one_assembled_span():
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Operators can start developing against the interface alone.",
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4), passage(7, SOURCE_P7)), checked)
    assert checked.findings == []
    assert len(checked.spans) == 1
    assert checked.spans[0].pages == (4, 7)
    assert checked.spans[0].note == "assembled from 2 places"


def test_a_nearly_matching_sentence_is_a_copy_mismatch_naming_the_missing_words():
    checked = match.Checked()
    run = a_run("Layered twins separate the physical entity from its blueprints.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["copy-mismatch"]
    finding = checked.findings[0]
    assert finding.detail["page"] == 4
    assert finding.detail["missing"] == ["blueprints"]
    assert finding.detail["share"] >= match.MISMATCH_SHARE
    assert checked.spans == []
    assert checked.words_flagged == run.words
    assert checked.unsupported_fraction == 1.0


def test_the_drafters_own_supported_sentence_is_unquoted_only():
    checked = match.Checked()
    # Mostly the source's words, but below MISMATCH_SHARE: a paraphrase.
    run = a_run("Twins that are layered keep the physical entity apart from models of it.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text"]


def test_an_unsupported_sentence_carries_both_classes_and_is_counted_once(monkeypatch):
    monkeypatch.setattr(config, "PROVENANCE_WEAK_SCORE", 0.5)
    checked = match.Checked()
    run = a_run("Pelicans migrate in autumn along the coast.")
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert checked.findings[1].detail["support_score"] < 0.5
    assert checked.words_flagged == run.words


def test_an_uncited_tail_is_unquoted_and_unsupported_without_a_lookup():
    checked = match.Checked()
    lookup = a_lookup(passage(4, SOURCE_P4))
    match.check_run(a_run("My own closing thought.", citekeys=()), lookup, checked)
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert lookup.calls == []
    assert checked.findings[0].citekeys == ()


def test_a_mixed_run_keeps_the_found_sentences_as_spans():
    checked = match.Checked()
    run = a_run(
        "Each layer exposes one interface to the next.",
        "Pelicans migrate in autumn along the coast.",
    )
    match.check_run(run, a_lookup(passage(4, SOURCE_P4)), checked)
    assert [s.text for s in checked.spans] == ["Each layer exposes one interface to the next."]
    assert [f.cls for f in checked.findings] == ["unquoted-text", "unsupported-text"]
    assert checked.words_copied == 8
    assert checked.words_flagged == 7
    assert checked.words_total == 15
    assert checked.unsupported_fraction == round(7 / 15, 3)


def test_a_source_without_reading_order_is_unverifiable():
    checked = match.Checked()
    page_only = Passage(4, distinctive(SOURCE_P4), None)
    run = a_run("Layered twins separate the physical entity from its models.")
    match.check_run(run, a_lookup(page_only), checked)
    assert checked.spans == [] and checked.findings == []
    assert checked.unverifiable == [
        {
            "line": 3,
            "citekeys": [KEY],
            "words": run.words,
            "reason": f"{KEY}: no reading-ordered passages -- only page-level text",
        }
    ]
    assert checked.words_total == run.words
    assert checked.words_unverifiable == run.words
    assert checked.unverifiable_fraction == 1.0
    assert checked.words_flagged == 0


def test_a_citekey_the_ledger_lacks_carries_the_lookups_reason():
    checked = match.Checked()
    lookup = a_lookup(reason="not in the ledger -- run `python -m chitragupta.corpus sync`")
    match.check_run(a_run("Anything."), lookup, checked)
    assert checked.unverifiable[0]["reason"].startswith(f"{KEY}: not in the ledger")


def test_two_citekeys_pool_their_passages():
    checked = match.Checked()
    seen = {}

    def lookup(citekey):
        seen[citekey] = True
        return ([passage(4, SOURCE_P4)] if citekey == KEY else [passage(2, SOURCE_P7)]), None

    run = Run(
        3,
        ("Operators can start developing against the interface alone.",),
        (KEY, "smith_example_2024"),
        f"[@{KEY}; @smith_example_2024]",
        None,
    )
    match.check_run(run, lookup, checked)
    assert set(seen) == {KEY, "smith_example_2024"}
    assert checked.spans[0].pages == (2,)
    assert checked.spans[0].citekeys == (KEY, "smith_example_2024")


def test_an_empty_digest_has_fractions_zero():
    checked = match.Checked()
    assert (checked.unsupported_fraction, checked.copied_fraction, checked.unverifiable_fraction) == (0.0, 0.0, 0.0)


class TestPageNote:
    @pytest.mark.parametrize(
        ("cited", "pages", "expected"),
        [
            (None, [4], None),
            ((4, 5), [], None),
            ((4, 5), [5], None),
            ((4, 4), [7], "cited p. 4, found on p. 7"),
            ((4, 5), [7, 8], "cited p. 4-5, found on p. 7, 8"),
        ],
    )
    def test_notes_only_a_disagreement(self, cited, pages, expected):
        assert match.page_note(cited, pages) == expected
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest_match.py -q
```

Expected: FAIL at import.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_match.py`:

```python
"""Is each run of a verbatim digest really in the source it cites, and
what is every sentence that is not? (#991)

**The run is the unit; the sentence is the diagnosis.** A run that
`_quotation_match.locate` finds whole is one copied span and raises
nothing. Only a run that is not found whole is split into sentences,
and only to show where it breaks: a sentence found on its own is still
copied; one whose distinctive words are mostly on one page is a
`copy-mismatch` naming the words that are not; anything else is the
drafter's own, `unquoted-text`, and additionally `unsupported-text`
when no citation covers it or the cited source does not support it
lexically -- the provenance aid's own `score_claim` under the same
`PROVENANCE_WEAK_SCORE` it bands on.

**The headline is the unsupported fraction**: the words of every
sentence carrying at least one finding, a sentence counted once however
many classes it carries, over all words. It is the number a repair pass
drives down. The copied fraction and the not-checkable share are kept
beside it so the three account for the whole digest.

`MISMATCH_SHARE` is the one number here and it is not tuned: it is the
share `near_miss` already reports, read as "most of the sentence is on
that page". docs/CODE-STANDARDS.md's R3 bars optimising it, and the
honest statement is that no corpus has been measured against it yet.

A source with no reading-ordered passages cannot be checked. Its run is
`unverifiable`, counted in the total and the not-checkable share and
nowhere else -- never `absent` after a failed comparison, the same
refusal `quotation.py` makes.

Stdlib only, interpreter tier 1.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from chitragupta import config
from chitragupta.passages import Passage, distinctive
from chitragupta.review import _quotation_match
from chitragupta.review._digest_runs import Run
from chitragupta.review.citation_provenance import score_claim

# Worst first: the order the report lists classes in, and the order a
# repair pass works them.
CLASSES = ("unsupported-text", "copy-mismatch", "unquoted-text")

# A sentence `locate` cannot find, at least this share of whose
# distinctive words sit on one page, is a copy that drifted rather than
# the drafter's own words.
MISMATCH_SHARE = 0.8

_NO_READING_ORDER = "no reading-ordered passages -- only page-level text"

Lookup = Callable[[str], tuple[list[Passage], str | None]]


@dataclass(frozen=True)
class Span:
    """Verified copied text: a whole run, or one sentence of a broken one."""

    line: int
    citekeys: tuple[str, ...]
    text: str
    tier: str
    pages: tuple[int, ...]
    cited: tuple[int, int] | None
    note: str | None


@dataclass(frozen=True)
class Finding:
    cls: str
    line: int
    text: str
    citekeys: tuple[str, ...]
    detail: dict = field(default_factory=dict)


def _fraction(part: int, whole: int) -> float:
    """0.0 for an empty digest: a number rather than a crash, and it
    reads as what it is."""
    return round(part / whole, 3) if whole else 0.0


@dataclass
class Checked:
    spans: list[Span] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    unverifiable: list[dict] = field(default_factory=list)
    words_total: int = 0

    @property
    def words_copied(self) -> int:
        return sum(len(span.text.split()) for span in self.spans)

    @property
    def words_flagged(self) -> int:
        """Words of every distinct flagged sentence. Keyed by line and
        text so the same sentence written twice is two sentences and one
        sentence with two classes is one."""
        flagged = {(finding.line, finding.text) for finding in self.findings}
        return sum(len(text.split()) for _, text in flagged)

    @property
    def words_unverifiable(self) -> int:
        return sum(run["words"] for run in self.unverifiable)

    @property
    def unsupported_fraction(self) -> float:
        return _fraction(self.words_flagged, self.words_total)

    @property
    def copied_fraction(self) -> float:
        return _fraction(self.words_copied, self.words_total)

    @property
    def unverifiable_fraction(self) -> float:
        return _fraction(self.words_unverifiable, self.words_total)


def page_note(cited: tuple[int, int] | None, pages: list[int] | tuple[int, ...]) -> str | None:
    """`cited p. A-B, found on p. X` when no found page is in the hint's
    range; None when there is no hint, no page, or agreement."""
    if cited is None or not pages:
        return None
    first, last = cited
    if any(first <= page <= last for page in pages):
        return None
    hint = f"p. {first}" if first == last else f"p. {first}-{last}"
    return f"cited {hint}, found on p. {', '.join(str(page) for page in pages)}"


def _span(run: Run, text: str, tier: str, pages: list[int]) -> Span:
    return Span(run.line, run.citekeys, text, tier, tuple(pages), run.pages, page_note(run.pages, pages))


def _own(run: Run, sentence: str, passages: list[Passage]) -> list[Finding]:
    """`unquoted-text`, plus `unsupported-text` when nothing cites the
    sentence or its cited sources do not lexically support it."""
    found = [Finding("unquoted-text", run.line, sentence, run.citekeys)]
    score, passage = score_claim(sentence, passages) if run.citekeys else (0.0, None)
    if score < config.PROVENANCE_WEAK_SCORE:
        detail = {"support_score": round(score, 3), "page": passage.page if passage else None}
        found.append(Finding("unsupported-text", run.line, sentence, run.citekeys, detail))
    return found


def _mismatch(run: Run, sentence: str, quotable: list[Passage]) -> Finding | None:
    """A `copy-mismatch` finding, or None when the sentence is not mostly
    on any one page."""
    share, page = _quotation_match.near_miss(sentence, quotable)
    if share < MISMATCH_SHARE:
        return None
    on_page: set[str] = set().union(*(p.words for p in quotable if p.page == page))
    detail = {"page": page, "share": round(share, 3), "missing": sorted(distinctive(sentence) - on_page)}
    return Finding("copy-mismatch", run.line, sentence, run.citekeys, detail)


def _sentence_level(run: Run, quotable: list[Passage], passages: list[Passage], checked: Checked) -> None:
    """The diagnosis for a run not found whole."""
    spans, findings = [], []
    for sentence in run.sentences:
        located = _quotation_match.locate(sentence, quotable)
        if located is not None:
            spans.append(_span(run, sentence, *located))
            continue
        mismatch = _mismatch(run, sentence, quotable)
        findings.extend([mismatch] if mismatch else _own(run, sentence, passages))
    if not findings and len(spans) > 1:
        # Every sentence is in the source, just not contiguously: one
        # copied span, with where it came from. Information, not a finding.
        pages = sorted({page for span in spans for page in span.pages})
        places = len({span.pages for span in spans})
        note = f"assembled from {places} places"
        spans = [Span(run.line, run.citekeys, run.text, "assembled", tuple(pages), run.pages, note)]
    checked.spans.extend(spans)
    checked.findings.extend(findings)


def _sources(run: Run, lookup: Lookup) -> tuple[list[Passage], list[Passage], list[str]]:
    """Every passage the run's citekeys reach, the quotable ones, and one
    reason per citekey that has none."""
    passages, quotable, reasons = [], [], []
    for citekey in run.citekeys:
        found, reason = lookup(citekey)
        readable = [p for p in found if p.quotable]
        passages.extend(found)
        quotable.extend(readable)
        if not readable:
            reasons.append(f"{citekey}: {reason or _NO_READING_ORDER}")
    return passages, quotable, reasons


def check_run(run: Run, lookup: Lookup, checked: Checked) -> None:
    """Verify one run and record the outcome on `checked`."""
    checked.words_total += run.words
    if not run.citekeys:
        for sentence in run.sentences:
            checked.findings.extend(_own(run, sentence, []))
        return
    passages, quotable, reasons = _sources(run, lookup)
    if not quotable:
        checked.unverifiable.append(
            {"line": run.line, "citekeys": list(run.citekeys), "words": run.words, "reason": "; ".join(reasons)}
        )
        return
    located = _quotation_match.locate(run.text, quotable)
    if located is not None:
        checked.spans.append(_span(run, run.text, *located))
        return
    _sentence_level(run, quotable, passages, checked)
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest_match.py -q
python scripts/code_standards.py chitragupta/review/_digest_match.py
```

Expected: all pass, no finding. If
`test_the_drafters_own_supported_sentence_is_unquoted_only` reports
`copy-mismatch`, the paraphrase shares too many distinctive words; swap
more content words, not the constant. If the module lands over 250
code lines, move `_fraction`'s and the three fraction properties'
reasons from docstrings to comments before splitting anything.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_match.py tests/test_review_digest_match.py
git commit -m "Verify each run of a verbatim digest against its source"
```

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

- [ ] **Step 1: Write the failing tests**

`tests/test_review_digest.py` (first part; Tasks 5 and 6 append):

```python
"""chitragupta/review/verbatim_digest.py and its render/recheck halves:
the eleventh review aid, over a verbatim digest.

A digest is private study text written mostly in the sources' own words
(discussion #991). The aid leads with the unsupported fraction, lists
every sentence that is not verified source text as a `[surfaced]` item
in the agenda's own line format, and under `--baseline` says whether a
repair pass made the fraction fall. Advisory like the other ten: exit 0
whatever it finds, no lock, no draft blocked.
"""

import json
from pathlib import Path

import pytest

from chitragupta import config, ledger, review
from chitragupta.review import __main__ as review_main
from chitragupta.review import _digest_match as match
from chitragupta.review import _digest_recheck as recheck
from chitragupta.review import _digest_render as render
from chitragupta.review import verbatim_digest
from chitragupta.review._digest_runs import Run
from tests.test_review_units import draft_at

KEY = "shao_analysis_2023"
SOURCE = (
    "Layered twins separate the physical entity from its models. "
    "Each layer exposes one interface to the next."
)


@pytest.fixture(autouse=True)
def _a_synced_ledger(isolated_config):
    """An empty, current ledger: the aid reads read-only (#843) and a
    missing one is refused, so every test has to say it synced."""
    ledger.connect().close()


def a_source(citekey: str, *records: tuple[int, str]) -> Path:
    """A rung-2 passage sidecar: reading-ordered text with a page each."""
    path = config.PARSED_DIR / f"{citekey}.passages.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([{"text": t, "page": p, "label": "text"} for p, t in records]),
        encoding="utf-8",
    )
    return path


def a_digest(body: str, name: str = "notes.md") -> Path:
    draft = draft_at(name)
    draft.write_text(body, encoding="utf-8")
    return draft


DIGEST = (
    "# Layered twins\n\n"
    "## Layers\n\n"
    f"Layered twins separate the physical entity from its models. [@{KEY}, p. 4]\n"
    "My own bridge sentence about pelicans.\n"
    f"Each layer exposes one interface to the next. [@{KEY}, p. 4]\n"
    "And a closing thought of mine.\n"
)


def a_checked() -> match.Checked:
    checked = match.Checked()
    run = Run(5, ("Layered twins separate the physical entity from its models.",), (KEY,), f"[@{KEY}, p. 4]", (4, 4))
    checked.spans.append(match.Span(5, (KEY,), run.text, "exact", (4,), (4, 4), None))
    checked.findings.append(match.Finding("unquoted-text", 6, "My own bridge sentence about pelicans.", (KEY,)))
    checked.findings.append(
        match.Finding("unsupported-text", 6, "My own bridge sentence about pelicans.", (KEY,), {"support_score": 0.0, "page": None})
    )
    checked.findings.append(match.Finding("unquoted-text", 8, "And a closing thought of mine.", ()))
    checked.findings.append(match.Finding("unsupported-text", 8, "And a closing thought of mine.", (), {"support_score": 0.0, "page": None}))
    checked.words_total = 25
    return checked


class TestItems:
    def test_one_item_per_finding_worst_class_first_then_by_line(self):
        rows = render.items(a_checked(), DIGEST)
        assert [(r["class"], r["line"]) for r in rows] == [
            ("unsupported-text", 6),
            ("unsupported-text", 8),
            ("unquoted-text", 6),
            ("unquoted-text", 8),
        ]
        assert all(r["disposition"] == "surfaced" for r in rows)
        assert rows[0]["section"] == "Layers"
        assert rows[0]["citekeys"] == [KEY]
        assert rows[1]["citekeys"] == []

    def test_ids_are_twelve_hex_characters_and_stable_across_runs(self):
        first = [r["id"] for r in render.items(a_checked(), DIGEST)]
        second = [r["id"] for r in render.items(a_checked(), DIGEST)]
        assert first == second
        assert all(len(i) == 12 and int(i, 16) >= 0 for i in first)
        assert len(set(first)) == 4

    def test_a_copy_mismatch_summary_names_the_missing_words(self):
        checked = match.Checked()
        checked.findings.append(
            match.Finding("copy-mismatch", 5, "Layered twins separate the physical entity from its blueprints.", (KEY,), {"page": 4, "share": 0.9, "missing": ["blueprints"]})
        )
        (row,) = render.items(checked, DIGEST)
        assert "missing: blueprints" in row["summary"]
        assert "p. 4" in row["summary"]

    def test_a_long_sentence_is_excerpted_on_the_line_and_whole_in_detail(self):
        checked = match.Checked()
        long = "Word " * 40
        checked.findings.append(match.Finding("unquoted-text", 5, long.strip(), ()))
        (row,) = render.items(checked, DIGEST)
        assert row["summary"].count("Word") < 40 and row["summary"].count("...") == 1
        assert row["detail"]["text"] == long.strip()


class TestPayload:
    def test_carries_the_envelope_the_fractions_and_the_counts(self):
        draft = a_digest(DIGEST)
        data = render.payload(draft, "cmd", a_checked(), render.items(a_checked(), DIGEST))
        assert data["aid"] == "digest" and data["draft"] == str(draft) and data["command"] == "cmd"
        assert data["notice"] == review.notice()
        assert data["words_total"] == 25 and data["words_copied"] == 9 and data["words_flagged"] == 12
        assert data["unsupported_fraction"] == 0.48
        assert data["copied_fraction"] == 0.36
        assert data["unverifiable_fraction"] == 0.0 and data["words_unverifiable"] == 0
        assert data["counts"] == {"unsupported-text": 2, "copy-mismatch": 0, "unquoted-text": 2}
        assert data["spans"] == [
            {"line": 5, "citekeys": [KEY], "text": "Layered twins separate the physical entity from its models.", "tier": "exact", "pages": [4], "cited": [4, 4], "note": None}
        ]
        assert data["unverifiable"] == []
        assert len(data["items"]) == 4

    def test_is_json_serialisable(self):
        draft = a_digest(DIGEST)
        json.dumps(render.payload(draft, "cmd", a_checked(), render.items(a_checked(), DIGEST)))


class TestMarkdown:
    def test_opens_with_the_header_and_leads_with_the_unsupported_fraction(self):
        draft = a_digest(DIGEST)
        checked = a_checked()
        text = render.render_markdown(draft, "cmd", checked, render.items(checked, DIGEST))
        assert text.startswith(f"# Verbatim digest: {draft}\n")
        assert review.BANNER in text
        summary = text.index("## Summary")
        assert text.index("- Unsupported fraction: 0.48 (12 of 25 words)") < text.index("- Copied fraction: 0.36 (9 of 25 words)")
        assert text.index("- Not checkable: 0.0 (0 of 25 words, 0 runs)") > summary
        assert "- unsupported-text: 2" in text

    def test_item_lines_use_the_agendas_format(self):
        checked = a_checked()
        rows = render.items(checked, DIGEST)
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, rows)
        assert f"- `{rows[0]['id']}` [surfaced] (Layers): {rows[0]['summary']}" in text

    def test_lists_copied_spans_and_unverifiable_runs(self):
        checked = a_checked()
        checked.unverifiable.append({"line": 9, "citekeys": [KEY], "words": 4, "reason": f"{KEY}: no reading-ordered passages -- only page-level text"})
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, render.items(checked, DIGEST))
        assert "## Copied spans" in text and f"line 5, `{KEY}`, p. 4, exact" in text
        assert "## Not checkable" in text and "line 9" in text

    def test_a_clean_digest_says_so(self):
        checked = match.Checked()
        text = render.render_markdown(a_digest(DIGEST), "cmd", checked, [])
        assert "No findings." in text
        assert "- Unsupported fraction: 0.0 (0 of 0 words)" in text
        assert "None." in text

    def test_carries_no_date(self):
        import datetime

        text = render.render_markdown(a_digest(DIGEST), "cmd", match.Checked(), [])
        assert str(datetime.date.today().year) not in text.replace(review.version(), "")
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q
```

Expected: FAIL at import (`_digest_recheck`, `_digest_render`,
`verbatim_digest` missing). Create empty placeholder modules only for
`_digest_recheck.py` and `verbatim_digest.py` for now (a module
docstring line each; Tasks 5 and 6 fill them) so the render tests can
run.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_render.py`:

```python
"""How the verbatim digest aid prints and serialises what it found (#991).

The report is the digest's own worklist. It leads with the unsupported
fraction, the number a repair pass drives down, with the copied fraction
and the not-checkable share beside it so the three account for the
whole digest. Item lines use `agenda`'s format -- a stable 12-character
id, `[surfaced]`, the section anchor, a one-line summary -- so a person
who has read an agenda reads this without learning a second shape, and
so the ids survive a revision the way agenda's do: `_identity.item_id`
hashes the sentence, never its line. Every item is `[surfaced]`:
whether a source backs a sentence and which passage should replace it
are judgement calls, and nothing a re-run can settle.

The payload is the findings as data, in `review.envelope`'s frame, and
it is what the next run's `--baseline` reads. No timestamp, for the
reason `review/__init__.py` gives.
"""

from pathlib import Path

from chitragupta import dossier, review
from chitragupta.review._digest_match import CLASSES, Checked, Finding
from chitragupta.review.agenda._identity import item_id, section_anchor

AID = "digest"

# How much of a sentence an item line shows. The payload carries the
# whole sentence in `detail.text`; the line is for scanning.
_EXCERPT = 90


def _excerpt(text: str) -> str:
    return text if len(text) <= _EXCERPT else text[: _EXCERPT - 3].rstrip() + "..."


def _summary(finding: Finding) -> str:
    quoted = f'"{_excerpt(finding.text)}"'
    if finding.cls == "copy-mismatch":
        missing = ", ".join(finding.detail["missing"]) or "(none)"
        return f"{quoted} -- nearly on p. {finding.detail['page']}; missing: {missing}"
    if finding.cls == "unsupported-text" and not finding.citekeys:
        return f"{quoted} -- no citation covers it"
    if finding.cls == "unsupported-text":
        return f"{quoted} -- lexical support {finding.detail['support_score']} in the cited source"
    return f"{quoted} -- not verified as copied"


def items(checked: Checked, draft_text: str) -> list[dict]:
    """One worklist row per finding, worst class first, then by line."""
    sections = dossier.sections(draft_text)
    rows = []
    for finding in checked.findings:
        section = section_anchor(sections, finding.line)
        citekey = finding.citekeys[0] if finding.citekeys else None
        rows.append(
            {
                "id": item_id(AID, finding.cls, section, citekey, finding.text),
                "class": finding.cls,
                "disposition": "surfaced",
                "section": section,
                "citekeys": list(finding.citekeys),
                "line": finding.line,
                "summary": _summary(finding),
                "detail": {"text": finding.text, **finding.detail},
            }
        )
    rows.sort(key=lambda row: (CLASSES.index(row["class"]), row["line"], row["id"]))
    return rows


def _counts(rows: list[dict]) -> dict[str, int]:
    return {cls: sum(1 for row in rows if row["class"] == cls) for cls in CLASSES}


def payload(draft: Path, command: str, checked: Checked, rows: list[dict]) -> dict:
    data = review.envelope(draft, AID, command)
    data.update(
        {
            "unsupported_fraction": checked.unsupported_fraction,
            "copied_fraction": checked.copied_fraction,
            "unverifiable_fraction": checked.unverifiable_fraction,
            "words_total": checked.words_total,
            "words_flagged": checked.words_flagged,
            "words_copied": checked.words_copied,
            "words_unverifiable": checked.words_unverifiable,
            "counts": _counts(rows),
            "items": rows,
            "spans": [
                {
                    "line": span.line,
                    "citekeys": list(span.citekeys),
                    "text": span.text,
                    "tier": span.tier,
                    "pages": list(span.pages),
                    "cited": list(span.cited) if span.cited else None,
                    "note": span.note,
                }
                for span in checked.spans
            ],
            "unverifiable": list(checked.unverifiable),
        }
    )
    return data


def _summary_lines(checked: Checked, rows: list[dict]) -> list[str]:
    total = checked.words_total
    lines = [
        "## Summary",
        "",
        f"- Unsupported fraction: {checked.unsupported_fraction} ({checked.words_flagged} of {total} words)",
        f"- Copied fraction: {checked.copied_fraction} ({checked.words_copied} of {total} words)",
        f"- Not checkable: {checked.unverifiable_fraction} "
        f"({checked.words_unverifiable} of {total} words, {len(checked.unverifiable)} runs)",
        f"- Copied spans: {len(checked.spans)}",
    ]
    lines += [f"- {cls}: {count}" for cls, count in _counts(rows).items()]
    return lines + [""]


def _findings_lines(rows: list[dict]) -> list[str]:
    lines = ["## Findings", ""]
    if not rows:
        return lines + ["No findings.", ""]
    for cls in CLASSES:
        rows_of = [row for row in rows if row["class"] == cls]
        if not rows_of:
            continue
        lines += [f"### {cls}", ""]
        for row in rows_of:
            where = f" ({row['section']})" if row["section"] else ""
            lines.append(f"- `{row['id']}` [surfaced]{where}: {row['summary']}")
        lines.append("")
    return lines


def _spans_lines(checked: Checked) -> list[str]:
    lines = ["## Copied spans", ""]
    for span in checked.spans:
        pages = ", ".join(str(page) for page in span.pages) or "?"
        keys = ", ".join(f"`{key}`" for key in span.citekeys)
        note = f" -- {span.note}" if span.note else ""
        lines.append(f'- line {span.line}, {keys}, p. {pages}, {span.tier}{note}: "{_excerpt(span.text)}"')
    if not checked.spans:
        lines.append("None.")
    lines.append("")
    if checked.unverifiable:
        lines += ["## Not checkable", ""]
        lines += [f"- line {run['line']}: {run['reason']} ({run['words']} words)" for run in checked.unverifiable]
        lines.append("")
    return lines


def render_markdown(draft: Path, command: str, checked: Checked, rows: list[dict]) -> str:
    lines = review.header(draft, AID, command)
    lines += [
        "Every item is **[surfaced]**: whether a source backs a sentence, and",
        "which passage should replace it, are judgement calls. The unsupported",
        "fraction and the per-class counts are what a repair pass drives down.",
        "",
    ]
    lines += _summary_lines(checked, rows)
    lines += _findings_lines(rows)
    lines += _spans_lines(checked)
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q -k "TestItems or TestPayload or TestMarkdown"
python scripts/code_standards.py chitragupta/review/_digest_render.py
```

Expected: all pass, no finding. `words_flagged == 12` is the two
flagged sentences (7 + 5 words), each counted once though each carries
two classes.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_render.py chitragupta/review/_digest_recheck.py chitragupta/review/verbatim_digest.py tests/test_review_digest.py
git commit -m "Render the verbatim digest report and its JSON payload"
```

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

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_review_digest.py`:

```python
def a_payload(draft: Path, *findings: match.Finding, total: int = 20) -> dict:
    checked = match.Checked()
    checked.findings.extend(findings)
    checked.words_total = total
    return render.payload(draft, "cmd", checked, render.items(checked, DIGEST))


class TestLoadBaseline:
    def test_reads_a_digest_payload_back(self, tmp_path):
        data = a_payload(a_digest(DIGEST))
        path = tmp_path / "notes.digest.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        assert recheck.load_baseline(path)["aid"] == "digest"

    def test_an_unreadable_path_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="Cannot read the baseline"):
            recheck.load_baseline(tmp_path / "missing.json")

    def test_non_json_is_refused(self, tmp_path):
        path = tmp_path / "x.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid JSON"):
            recheck.load_baseline(path)

    def test_another_aids_payload_is_refused(self, tmp_path):
        path = tmp_path / "notes.agenda.json"
        path.write_text(json.dumps({"aid": "agenda", "items": [], "command": "x"}), encoding="utf-8")
        with pytest.raises(ValueError, match="not a digest payload"):
            recheck.load_baseline(path)


class TestCompare:
    def test_resolved_persisting_new_by_id_and_the_counts(self):
        draft = a_digest(DIGEST)
        gone = match.Finding("unquoted-text", 6, "Gone sentence.", (KEY,))
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        fresh = match.Finding("copy-mismatch", 9, "Fresh sentence.", (KEY,), {"page": 4, "share": 0.9, "missing": []})
        before = a_payload(draft, gone, stays)
        after = a_payload(draft, stays, fresh)
        result = recheck.compare(after, before)
        assert [i["detail"]["text"] for i in result["resolved"]] == ["Gone sentence."]
        assert [i["detail"]["text"] for i in result["persisting"]] == ["Stays sentence."]
        assert [i["detail"]["text"] for i in result["new"]] == ["Fresh sentence."]
        assert result["counts_before"]["unquoted-text"] == 2
        assert result["counts_after"] == {"unsupported-text": 0, "copy-mismatch": 1, "unquoted-text": 1}
        assert result["fell"] is False

    def test_fell_means_no_class_rose_one_fell_nothing_new_and_the_fraction_did_not_rise(self):
        draft = a_digest(DIGEST)
        gone = match.Finding("unquoted-text", 6, "Gone sentence.", (KEY,))
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        assert recheck.compare(a_payload(draft, stays), a_payload(draft, gone, stays))["fell"] is True
        assert recheck.compare(a_payload(draft, stays), a_payload(draft, stays))["fell"] is False
        # One item gone but the digest shrank more: the fraction rose.
        shrunk = a_payload(draft, stays, total=2)
        assert recheck.compare(shrunk, a_payload(draft, gone, stays))["fell"] is False

    def test_both_fractions_travel(self):
        draft = a_digest(DIGEST)
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        result = recheck.compare(a_payload(draft, stays, total=10), a_payload(draft, stays, total=20))
        assert (result["unsupported_before"], result["unsupported_after"]) == (0.1, 0.2)
        assert (result["copied_before"], result["copied_after"]) == (0.0, 0.0)


class TestRecheckOutput:
    def test_command_names_the_baseline_and_json(self):
        assert recheck.recheck_command("content/drafts/t/notes.md", "b.json") == (
            "python -m chitragupta.review digest content/drafts/t/notes.md --baseline b.json --json"
        )

    def test_payload_and_text_say_the_same_thing(self):
        draft = a_digest(DIGEST)
        stays = match.Finding("unquoted-text", 8, "Stays sentence.", (KEY,))
        comparison = recheck.compare(a_payload(draft, stays), a_payload(draft, stays))
        data = recheck.recheck_payload(draft, "b.json", comparison)
        text = recheck.format_recheck("b.json", comparison)
        assert data["aid"] == "digest" and data["baseline"] == "b.json"
        assert data["fell"] is False and "fell: no" in text
        assert "baseline: b.json" in text
        assert "persisting: 1" in text and "resolved: 0" in text and "new: 0" in text
        assert "unquoted-text: 1 -> 1" in text
        assert "unsupported fraction: 0.1 -> 0.1" in text
        assert "copied fraction: 0.0 -> 0.0" in text
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q -k "Baseline or Compare or RecheckOutput"
```

Expected: FAIL, attributes missing.

- [ ] **Step 3: Implement**

`chitragupta/review/_digest_recheck.py`:

```python
"""`review digest --baseline`: this run against a recorded one (#991).

"Minimise unsupported text" is a number a person watches fall, never a
threshold. This is the arithmetic: items matched by their stable `id`
into `resolved`/`persisting`/`new`, the per-class counts before and
after, the unsupported and copied fractions before and after, and one
boolean, `fell`, true when no class rose, at least one fell, nothing
new appeared, and the unsupported fraction did not rise -- the
conditions the skill keeps a repair under. The fraction is checked as
well as the counts because deleting a flagged sentence and half the
copied text with it resolves an item and makes the digest worse.
Nothing is refreshed here: the aid recomputed everything before
comparing, so there is no stale report to guard against.

Mirrors `agenda/_recheck.py`'s payload keys where the two say the same
thing, because the skill reading this already reads that one.
"""

import json
import shlex
from pathlib import Path

from chitragupta import review
from chitragupta.review._digest_match import CLASSES


def load_baseline(path: str | Path) -> dict:
    """A previously filed `digest` payload, refused if it cannot serve.

    Two confident-wrong-answer failures are named: unreadable JSON, and
    another aid's payload (every aid's `.json` has a `command`, and the
    likeliest typo is the agenda's beside it).
    """
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Cannot read the baseline {path}: {exc}") from None
    except json.JSONDecodeError:
        raise ValueError(
            f"{path} is not a digest payload -- it is not valid JSON. "
            "Write one with `review digest <draft>`, which files it as the report's .json sibling."
        ) from None
    if not isinstance(payload, dict) or payload.get("aid") != "digest" or "items" not in payload:
        raise ValueError(
            f"{path} is not a digest payload. Write one with `review digest <draft>`, "
            "which files it as the report's .json sibling."
        )
    return payload


def compare(payload: dict, baseline: dict) -> dict:
    new_items, old_items = payload["items"], baseline["items"]
    new_ids = {item["id"] for item in new_items}
    old_ids = {item["id"] for item in old_items}
    before = {cls: baseline["counts"].get(cls, 0) for cls in CLASSES}
    after = {cls: payload["counts"].get(cls, 0) for cls in CLASSES}
    appeared = [item for item in new_items if item["id"] not in old_ids]
    rose = any(after[cls] > before[cls] for cls in CLASSES)
    fell = any(after[cls] < before[cls] for cls in CLASSES)
    unsupported_before = baseline.get("unsupported_fraction", 0.0)
    unsupported_after = payload["unsupported_fraction"]
    return {
        "resolved": [item for item in old_items if item["id"] not in new_ids],
        "persisting": [item for item in new_items if item["id"] in old_ids],
        "new": appeared,
        "counts_before": before,
        "counts_after": after,
        "unsupported_before": unsupported_before,
        "unsupported_after": unsupported_after,
        "copied_before": baseline.get("copied_fraction", 0.0),
        "copied_after": payload["copied_fraction"],
        "fell": fell and not rose and not appeared and unsupported_after <= unsupported_before,
    }


def recheck_command(draft: str | Path, baseline: str | Path) -> str:
    parts = ["python", "-m", "chitragupta.review", "digest", str(draft)]
    return shlex.join([*parts, "--baseline", str(baseline), "--json"])


def recheck_payload(draft: Path, baseline: str | Path, comparison: dict) -> dict:
    data = review.envelope(draft, "digest", recheck_command(draft, baseline))
    data["baseline"] = str(baseline)
    data.update(comparison)
    return data


def format_recheck(baseline: str | Path, comparison: dict) -> str:
    lines = [f"baseline: {baseline}", ""]
    for group in ("resolved", "persisting", "new"):
        lines.append(f"{group}: {len(comparison[group])}")
        lines += [f"  - `{item['id']}` [{item['class']}] {item['summary']}" for item in comparison[group]]
    lines.append("")
    for cls in CLASSES:
        lines.append(f"{cls}: {comparison['counts_before'][cls]} -> {comparison['counts_after'][cls]}")
    lines.append(f"unsupported fraction: {comparison['unsupported_before']} -> {comparison['unsupported_after']}")
    lines.append(f"copied fraction: {comparison['copied_before']} -> {comparison['copied_after']}")
    lines.append(f"fell: {'yes' if comparison['fell'] else 'no'}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q
python scripts/code_standards.py chitragupta/review/_digest_recheck.py
```

Expected: all pass, no finding.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/review/_digest_recheck.py tests/test_review_digest.py
git commit -m "Compare a verbatim digest report against a baseline"
```

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

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_review_digest.py`:

```python
class TestRegistration:
    def test_digest_is_an_aid_with_a_module_and_a_label(self):
        assert review.AIDS["digest"] == "Verbatim digest"
        from chitragupta.review import _registry

        assert _registry.AIDS["digest"][0] is verbatim_digest

    def test_the_report_lands_under_the_ordinary_rule(self, isolated_config):
        draft = config.DRAFTS_DIR / "t" / "notes.md"
        assert review.report_path(draft, "digest") == config.REVIEW_DIR / "t" / "notes.digest.md"

    def test_agenda_does_not_read_it(self):
        from chitragupta.review.agenda import _sources

        assert "digest" not in _sources.AID_NAMES

    def test_the_moved_path_helpers_keep_their_names(self):
        from chitragupta.review import _paths

        assert review.require_reviewable is _paths.require_reviewable
        assert review.report_dir is _paths.report_dir


class TestRun:
    def test_files_md_and_json_and_prints_the_summary(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        assert review_main.main(["digest", str(draft), "--formats", "md"]) == 0
        out = capsys.readouterr().out
        md = config.REVIEW_DIR / "dt" / "notes.digest.md"
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        assert md.is_file() and js.is_file()
        assert str(md) in out and str(js) in out
        data = json.loads(js.read_text(encoding="utf-8"))
        assert data["command"] == f"python -m chitragupta.review digest {draft} --formats md"
        assert data["counts"]["unquoted-text"] == 2
        assert data["counts"]["unsupported-text"] == 2
        assert data["words_copied"] == 17 and data["words_flagged"] == 12
        assert data["unsupported_fraction"] == round(12 / data["words_total"], 3)
        assert "Unsupported fraction" in md.read_text(encoding="utf-8")

    def test_json_goes_to_stdout_and_the_summary_to_stderr(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        assert review_main.main(["digest", str(draft), "--json", "--formats", "md"]) == 0
        captured = capsys.readouterr()
        assert json.loads(captured.out)["aid"] == "digest"
        assert "notes.digest.json" in captured.err

    def test_a_digest_with_no_prose_exits_zero(self, capsys):
        draft = a_digest("# Only a heading\n")
        assert review_main.main(["digest", str(draft), "--json", "--formats", "md"]) == 0
        assert json.loads(capsys.readouterr().out)["unsupported_fraction"] == 0.0

    def test_a_draft_outside_content_exits_one(self, tmp_path, capsys):
        outside = tmp_path / "notes.md"
        outside.write_text("x\n", encoding="utf-8")
        assert review_main.main(["digest", str(outside)]) == 1
        assert "content" in capsys.readouterr().err

    def test_a_missing_draft_exits_one(self, capsys):
        assert review_main.main(["digest", str(config.DRAFTS_DIR / "nope.md")]) == 1

    def test_a_bad_baseline_exits_two_before_reading_the_ledger(self, tmp_path, capsys, monkeypatch):
        draft = a_digest(DIGEST)
        bad = tmp_path / "notes.agenda.json"
        bad.write_text(json.dumps({"aid": "agenda", "items": []}), encoding="utf-8")
        monkeypatch.setattr(verbatim_digest, "build_report", lambda *_: pytest.fail("built a report"))
        assert review_main.main(["digest", str(draft), "--baseline", str(bad)]) == 2
        assert "not a digest payload" in capsys.readouterr().err

    def test_baseline_prints_the_comparison_and_refiles_the_report(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        # The repair: delete the closing thought.
        draft.write_text(DIGEST.replace("And a closing thought of mine.\n", ""), encoding="utf-8")
        assert review_main.main(["digest", str(draft), "--baseline", str(js), "--formats", "md"]) == 0
        out = capsys.readouterr().out
        assert "resolved: 2" in out and "new: 0" in out and "fell: yes" in out
        assert json.loads(js.read_text(encoding="utf-8"))["counts"]["unquoted-text"] == 1

    def test_baseline_with_json_prints_the_comparison_payload(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        capsys.readouterr()
        assert review_main.main(["digest", str(draft), "--baseline", str(js), "--json", "--formats", "md"]) == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["baseline"] == str(js) and data["fell"] is False
        assert data["command"].endswith("--json")
        assert "notes.digest.md" in captured.err

    def test_the_filed_command_is_the_bare_one_even_under_baseline(self, capsys):
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        review_main.main(["digest", str(draft), "--formats", "md"])
        js = config.REVIEW_DIR / "dt" / "notes.digest.json"
        review_main.main(["digest", str(draft), "--baseline", str(js), "--formats", "md"])
        assert "--baseline" not in json.loads(js.read_text(encoding="utf-8"))["command"]

    def test_passages_are_looked_up_once_per_citekey(self, monkeypatch):
        from chitragupta import passages as passages_mod

        calls = []
        real = passages_mod.source_passages

        def counting(con, citekey):
            calls.append(citekey)
            return real(con, citekey)

        monkeypatch.setattr(verbatim_digest.passages, "source_passages", counting)
        a_source(KEY, (4, SOURCE))
        draft = a_digest(DIGEST)
        verbatim_digest.build_report(draft)
        assert calls == [KEY]

    def test_the_standalone_parser_carries_the_same_defaults(self):
        """`tests/test_review_entrypoint.py` already pins that every aid
        declares its flags on the subparser and has no `__main__` block;
        this only covers `build_parser(None)`, the shape `main()` uses."""
        parser = verbatim_digest.build_parser()
        args = parser.parse_args(["x.md"])
        assert (args.formats, args.json, args.baseline) == ("md,tex,pdf", False, None)
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py -q -k "Registration or TestRun"
```

Expected: FAIL.

- [ ] **Step 3: Split `review/__init__.py`**

Create `chitragupta/review/_paths.py` holding `require_reviewable` and
`report_dir`, moved verbatim with their docstrings and comments
(`review/__init__.py:143-200` today), with this module docstring:

```python
"""Where a review report may be read from and goes to (#991).

`require_reviewable` and `report_dir` lived in `review/__init__.py` from
the day the layer had one output contract. They moved here when the
eleventh aid's `AIDS` entry needed one more line in a module already at
docs/CODE-STANDARDS.md's 250-code-line ceiling, and this is the boundary
that module's own docstring draws: this half is *where* a report goes,
the other half is what it looks like. `report_path` stays there because
it needs `AIDS`. Both names are re-exported from `review` unchanged, so
no caller moved.
"""

from pathlib import Path

from chitragupta import config
from chitragupta.review import _book_paths
```

In `chitragupta/review/__init__.py`: delete the two functions, add
this import after the `_book_paths` one:

```python
from chitragupta.review._paths import report_dir, require_reviewable  # noqa: F401
```

Keep the `_book_paths` import only if something else there still uses
it; otherwise drop it. Then add to `AIDS`:

```python
    "union": "Citekey union",
    "digest": "Verbatim digest",
}
```

Update the docstring: "Ten commands make up the review layer" → "Eleven
commands ...", add `chitragupta/review/verbatim_digest.py` to the list,
add `content/review/<topic>/survey.digest.md` to the path block, "all
ten are interpreter tier 1" → "all eleven", "makes the ten obey" →
"the eleven", and in the JSON paragraph add `digest` to the list of aids
that emit one from the day they landed.

Run:

```bash
python scripts/code_standards.py chitragupta/review/__init__.py chitragupta/review/_paths.py
```

Both under 250.

- [ ] **Step 4: Register**

`chitragupta/review/_registry.py`: add `verbatim_digest` to the import
list and

```python
    "union": (citekey_union, "does the assembly still carry every unit's citekeys?"),
    "digest": (verbatim_digest, "how much of a verbatim digest is not the sources' own words?"),
}
```

`chitragupta/review/__main__.py`:

```python
DESCRIPTION = "The review layer: eleven read-only aids over a finished draft. No gate."
```

Then "Ten aids, read over a finished draft" → "Eleven aids", and add to
the usage list:

```text
    python -m chitragupta.review digest <draft>
        for a verbatim digest: which runs are really in the source they
        cite, every sentence that is not, and the unsupported fraction.
        --baseline compares against an earlier run.
```

and `.digest.md` to the suffix list in the "subcommand names" paragraph.

`chitragupta/review/agenda/_sources.py`:

```python
AID_NAMES = tuple(aid for aid in review.AIDS if aid not in ("agenda", "union", "digest"))
```

with this added to the comment above it, after the `union` paragraph:

```python
# `digest` is excluded because its classes mean nothing outside a
# verbatim digest (#991): wired in, every existing agenda would carry a
# "digest: read" line for a report no survey or chapter ever has, and
# `--baseline`'s refresh would run the digest aid over prose that is
# not a digest. The digest's report is its own worklist, worked by the
# `review-digest` skill, never by `agenda-reviser`.
```

`tests/test_review_agenda.py:111`:

```python
        assert set(_sources.AID_NAMES) == set(review.AIDS) - {"agenda", "union", "digest"}
```

and extend that test's docstring with one sentence: "`digest` is
excluded for the same kind of reason: its classes describe a verbatim
digest and nothing else (#991)."

- [ ] **Step 5: Implement the CLI**

`chitragupta/review/verbatim_digest.py`:

```python
"""Verbatim digest report: how much of a digest is not the sources' own
words, and what every such sentence is (#991).

    python -m chitragupta.review digest <draft>
        split the digest into citation-terminated runs, find each in
        the source it cites, and list every sentence that is not
        verified source text. Leads with the unsupported fraction.

    python -m chitragupta.review digest <draft> --baseline <stem>.digest.json
        the same, then compare with an earlier run: resolved,
        persisting and new items, the counts and fractions before and
        after, and whether the unsupported text fell.

The eleventh aid in `review.AIDS`, and the first over a genre of its
own: a digest is private study text written mostly in the cited papers'
own words, with no quotation marks and a citation closing each copied
run (docs/VERBATIM-DIGEST.md). It is a draft like any other -- named
by the user, its genre recorded in its dossier's `scope.md` -- so its
report lands under the ordinary rule, `<stem>.digest.md` beside the
other aids' reports for the same draft. `_digest_runs.py` reads the
runs, `_digest_match.py` verifies them, `_digest_render.py` prints and
serialises, `_digest_recheck.py` compares. This file is the CLI.

**Not a gate, and advisory like the other ten.** Every finding is
`[surfaced]`: a person decides whether to cite, replace or delete.
Exits 0 whatever it finds. The digest is never a drafting source for any
other genre; `review verbatim scan` already catches its wording if it
reaches one.

**Files its report unconditionally**, like `agenda` and for the same
reason: the `.json` is the next pass's `--baseline`. `--json` only
decides what prints to stdout.

Stdlib only, interpreter tier 1. Reads the ledger read-only (#843).
"""

import argparse
import json
import shlex
import sys
from pathlib import Path

from chitragupta import config, ledger, passages, review
from chitragupta.review import _digest_match, _digest_recheck, _digest_render, _digest_runs, _emit

AID = "digest"


def build_report(draft: Path) -> tuple[_digest_match.Checked, list[dict]]:
    """Every run of `draft` checked, and the worklist rows for what failed.

    One ledger connection and one passage lookup per citekey for the
    whole run: a digest cites few papers many times.
    """
    text = draft.read_text(encoding="utf-8")
    checked = _digest_match.Checked()
    cache: dict[str, tuple[list, str | None]] = {}
    with ledger.reading() as con:

        def lookup(citekey: str):
            if citekey not in cache:
                cache[citekey] = passages.source_passages(con, citekey)
            return cache[citekey]

        for run in _digest_runs.runs(text):
            _digest_match.check_run(run, lookup, checked)
    return checked, _digest_render.items(checked, text)


def _command(draft: Path, args: argparse.Namespace) -> str:
    """The bare invocation, which is what the filed `.json` records even
    under `--baseline`: that file is the *next* run's baseline, so its
    envelope has to name a command that regenerates a report."""
    parts = ["python", "-m", "chitragupta.review", "digest", str(draft)]
    if args.formats != "md,tex,pdf":
        parts += ["--formats", args.formats]
    return shlex.join(parts)


def build_parser(parser=None) -> argparse.ArgumentParser:
    if parser is None:
        parser = argparse.ArgumentParser(
            description="How much of a verbatim digest is not the sources' own words.",
        )
    parser.add_argument("draft", help="The digest to check, under content/drafts/")
    parser.add_argument(
        "--formats",
        default="md,tex,pdf",
        help="Additional formats to render beside the Markdown report "
        "(default: md,tex,pdf). The .md and .json are always written.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the payload (or, with --baseline, the comparison) as JSON "
        "instead of the summary. The .json sibling is filed either way.",
    )
    parser.add_argument(
        "--baseline",
        help="Compare this run against a previously filed <stem>.digest.json: "
        "resolved, persisting and new items, counts and fractions before and "
        "after, and whether unsupported text fell.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


def _file(draft: Path, args: argparse.Namespace) -> tuple[dict, dict]:
    checked, rows = build_report(draft)
    command = _command(draft, args)
    body = _digest_render.render_markdown(draft, command, checked, rows)
    written = review.write(draft, AID, body, _emit.formats(args))
    payload = _digest_render.payload(draft, command, checked, rows)
    written["json"] = review.write_json(draft, AID, payload)
    return payload, written


def run(args: argparse.Namespace) -> int:
    """The baseline is loaded before anything is computed: a bad one is a
    usage error (exit 2) and should cost nothing. The draft is checked
    first because a draft the layer will not read is exit 1, the same
    order `agenda` keeps."""
    try:
        draft = review.require_reviewable(Path(args.draft))
    except (FileNotFoundError, config.OutsideContentDir) as exc:
        print(exc, file=sys.stderr)
        return 1
    baseline = None
    if args.baseline:
        try:
            baseline = _digest_recheck.load_baseline(args.baseline)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
    payload, written = _file(draft, args)
    if baseline is None:
        _emit.announce(payload, written, as_json=args.json)
        return 0
    comparison = _digest_recheck.compare(payload, baseline)
    if args.json:
        print(json.dumps(_digest_recheck.recheck_payload(draft, args.baseline, comparison), indent=2))
        review.print_written(written, stream=sys.stderr)
    else:
        print(_digest_recheck.format_recheck(args.baseline, comparison))
        review.print_written(written)
    return 0
```

- [ ] **Step 6: Run the review suites, expect pass; measure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_review_digest.py tests/test_review.py tests/test_review_entrypoint.py tests/test_review_agenda.py tests/test_review_quotation.py -q
python scripts/code_standards.py chitragupta/review/verbatim_digest.py chitragupta/review/__init__.py chitragupta/review/_paths.py chitragupta/review/_registry.py
```

Expected: all pass, no finding. `test_review_entrypoint.py`'s
"every aid declares its own flags" and "no `__main__` block" cases now
cover `digest` by iterating `_registry.AIDS`. If `words_copied == 17`
or `words_flagged == 12` fails, count the words in `DIGEST`'s sentences
and fix the expected number, not the matcher.

- [ ] **Step 7: Commit**

```bash
git add chitragupta/review/verbatim_digest.py chitragupta/review/_paths.py chitragupta/review/__init__.py chitragupta/review/_registry.py chitragupta/review/__main__.py chitragupta/review/agenda/_sources.py tests/test_review_digest.py tests/test_review_agenda.py
git commit -m "Add review digest, the verbatim digest aid, and keep it off the agenda"
```

---

### Task 7: the `digest` genre

**Files:**

- Modify: `chitragupta/dossier/__init__.py:39`
- Modify: `chitragupta/review/_units.py:40-70`
- Test: `tests/test_review_units.py`, `tests/test_review_uncited.py`
  (both pin the tables to `dossier.GENRES` and will go red at Step 2),
  `tests/test_dossier.py` (one new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_dossier.py`, in the class that covers `init`:

```python
    def test_digest_is_a_genre_init_records(self, isolated_config):
        """A digest is a draft named like any other; the genre line in
        scope.md is what makes it one (#991)."""
        draft = config.DRAFTS_DIR / "t" / "notes.md"
        draft.parent.mkdir(parents=True)
        draft.write_text("x\n", encoding="utf-8")
        assert "digest" in dossier.GENRES
        assert dossier.main(["init", str(draft), "--genre", "digest"]) == 0
        assert "- genre: digest" in (dossier.dossier_dir(draft) / "scope.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_dossier.py -k digest_is_a_genre -q
```

Expected: FAIL on `"digest" in dossier.GENRES`.

- [ ] **Step 3: Implement**

`chitragupta/dossier/__init__.py`:

```python
GENRES = ("survey", "thesis-chapter", "textbook-chapter", "tutorial", "deep-research", "digest")
```

and extend the comment above it: "`digest` (#991) is the sixth: a
verbatim digest, private study text in the sources' own words, with its
own review aid rather than a place on the agenda."

`chitragupta/review/_units.py`:

```python
UNITS = {
    "survey": "paragraph",
    "thesis-chapter": "paragraph",
    "deep-research": "paragraph",
    "textbook-chapter": "section",
    "tutorial": "document",
    # A digest fuses nothing: every run is one source's own words, so
    # the multi-source rule has no paragraph to bind at (#991).
    "digest": "document",
}
```

```python
UNCITED_PROSE = {
    ...
    "tutorial": "ordinary",
    # A digest's connecting sentences carry no citation by design; the
    # `digest` aid is what judges them, sentence by sentence (#991).
    "digest": "ordinary",
}
```

- [ ] **Step 4: Run, expect pass**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_dossier.py tests/test_review_units.py tests/test_review_uncited.py tests/test_review_synthesis.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add chitragupta/dossier/__init__.py chitragupta/review/_units.py tests/test_dossier.py
git commit -m "Register digest as the sixth dossier genre"
```

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

- [ ] **Step 1: Write the failing test**

Append to `tests/test_skill_frontmatter.py` after the count test:

```python
def test_the_digest_skill_exists_on_every_harness():
    assert {p.parent.name for p in SKILL_FILES} >= {"review-digest", "review-digest-opencode"}
```

and update the count to 33.

- [ ] **Step 2: Run, expect failure**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_skill_frontmatter.py -q
```

Expected: FAIL (30 files, skill missing).

- [ ] **Step 3: Write the skill**

`.claude/skills/review-digest/SKILL.md`:

````markdown
---
name: review-digest
description: Builds a verbatim digest -- a private study summary of a topic written mostly in the source papers' own words, copied exactly from parsed PDFs in the corpus, with a citation closing each copied run and no quotation marks -- through the same draft-and-render workflow survey-writer uses, then runs `python -m chitragupta.review digest` on it and works the report down on request. Every citekey comes from content/ledger.sqlite via chitragupta.retrieval, never invented. Triggers when the user asks for a digest, study notes, a reading summary or an extract "in the papers' own words" on a topic. The digest is never a deliverable and never a source for a survey, chapter or any other draft; to summarise in your own words use survey-writer, and to change a digest that exists use draft-reviser. Must run `python -m chitragupta.draft gate` and `review digest` before presenting, and refuses (telling the user to run `python -m chitragupta.corpus sync`) if the ledger is empty.
tags: [digest, study-notes, verbatim, citation]
---

# review-digest

A verbatim digest is private study text: most of it is copied exactly
from parsed PDFs in the corpus, each copied run ends with a citation,
there are no quotation marks, and a few short sentences of your own
connect the runs. It is read by one person to learn a topic. It is not a
deliverable, and **it is never a source for drafting anything else**:
its wording is the corpus's own, and `python -m chitragupta.review
verbatim scan` will flag it the moment it reaches a survey or a chapter.

Three goals, in this order (`docs/VERBATIM-DIGEST.md`):

1. **Maximise copied text.**
2. **Surface unsupported text.** Every sentence that is not verified
   source text is listed for the person to judge.
3. **Minimise unsupported text.** The report leads with the unsupported
   fraction; each repair pass leaves it lower than the one before, and
   `--baseline` makes that a number.

A digest is a draft like any other: named by the user, kept at
`content/drafts/<topic>/<name>.md`, with a dossier whose `scope.md`
records `- genre: digest`, rendered beside the other drafts in the
topic, and per-host data like every file under `content/`. Nothing in
its name marks it as a digest; the dossier does.

**This skill runs `survey-writer`'s workflow with its purpose turned
round.** A survey minimises copying: it drafts from `claim:` lines in
the drafter's own words, fuses sources so no paragraph can be a
transcription, and scans for verbatim reuse. A digest maximises copying.
The mechanical chain below is the survey's; every step of the survey's
that exists to keep source wording out of the draft is inverted here and
says so where it stands. `docs/WRITING-STANDARDS.md` §4 and §11 govern
the connecting sentences only. **Never run `agenda-reviser` on a
digest**: its `verbatim-run` repair paraphrases copied text unattended,
which would undo the digest.

Paths in this skill are from the project root, not from this skill's
own folder.

## Shared corpus layer (read, don't regenerate)

- `content/ledger.sqlite` -- per-citekey status, populated by `sync`
- `content/parsed/<citekey>.txt` -- the extracted PDF text **you copy
  from**. Copy from this file, or from `content/parsed/<citekey>.passages.json`
  when it exists, never from memory and never from a snippet you
  tidied: the aid matches what you wrote against this text, and a
  faithful copy of a bad parse is still a match
- `python -m chitragupta.draft retrieve search "<q>" --k 15 --log <draft>`
  finds candidates; `... evidence "<q>" --citekey <key> --log <draft>`
  reads more of one document

**Read-only means read-only: never run `python -m chitragupta.corpus sync`,
and never run `python -m chitragupta.enrich` or any `chitragupta/enrich/*`
build stage.** Both take the pipeline's write lock and are the user's to run.

**If the ledger is empty, stop.** Check before anything else:

```bash
python -m chitragupta.corpus ledger
```

If it reports no items, or none with status `parsed`, say so plainly and
stop. Tell the user to run `.venv-full/bin/python -m chitragupta.corpus sync`
and come back. Do not draft around it, do not sync, do not cite.

## Collection scoping (#195)

Before any retrieval:

```bash
python -m chitragupta.corpus ledger --collections
```

If it reports none, record `- collection: (whole corpus)` in `scope.md`'s
header and skip this section. Otherwise read
`.claude/skills-common/references/collection-scoping.md` now and follow
it for the whole run.

## When to invoke

- "Give me a digest of what the corpus says about X."
- "Study notes on X, in the papers' own words."
- "Pull the key passages on X together."

Not for a summary in your own words (`survey-writer`), not for changing
a digest that exists (`draft-reviser`, which reads the dossier), and not
for anything that will be submitted or published.

## The format

Plain prose plus a closing citation. No markup, no quotation marks:

```markdown
Sentence one. Sentence two. Sentence three. [@key, p. 4-5]
A connecting sentence of your own.
Another copied sentence. [@other, p. 12]
```

**A citation covers every sentence back to the previous citation, or to
the start of the paragraph.** So:

- Put the citation at the end of the last copied sentence, on the same
  line or the next, before any sentence of your own.
- Copy from one paper per run. Two papers under one citation leaves the
  second paper's text unmatched.
- Give the page as `p. N` or `pp. N-M`, counting the PDF's pages from 1
  as the parser does, not the printed page number. It is a hint: the
  report says which page it actually found the text on.
- Keep your own sentences short, few, and between runs, never inside
  one.
- Pandoc-style citations only (`[@citekey, p. 4]`, `[@a; @b]`).

## Process

The same steps as `survey-writer`, in the same order. Three of its
steps are replaced by `review digest` and say so below.

0. **Name the reader and the scope, and open the dossier.** Settle with
   the user what the digest covers and what it leaves out, and the path
   under `content/drafts/`: a topic that holds other genres wants
   `content/drafts/<topic>/<name>.md` so they sit together. Then:

   ```bash
   python -m chitragupta.draft dossier init content/drafts/<topic>/<name>.md --genre digest
   ```

   Fill in `scope.md`'s **Reader**, **Covers** and **Does not cover**
   now. The reader is the user, studying. Settle the **dialect** and
   write it to `scope.md`'s `language:` line; it governs only your own
   connecting sentences, since copied text keeps its source's spelling.
   `init` also stamps the corpus fingerprint.

1. **Retrieve per sub-theme, over-fetching.** Decide three to six
   sub-themes with the user (an `outline.md` in the dossier, if the user
   wrote one, settles them and its queries run verbatim). For each, run
   `python -m chitragupta.draft retrieve search "<query>" --k 15 --log <draft>`,
   then read the candidates' parsed text.

2. **Score every candidate before it counts, and record the passage
   you will copy as a `quote:`.** Record every candidate you read in
   `evidence.md` as the dossier contract asks (`docs/DOSSIER.md`): one
   block per citekey with `relevance:`, a `claim:` saying in your own
   words what the passage establishes, and a `quote:` holding the exact
   passage you intend to copy. This is the survey's contract read the
   other way round: a survey captures a `quote:` only when a quotation
   is genuinely warranted, and in a digest every run is one, so every
   passage you will copy is a `quote:` and `claim:` is drafted from only
   for the connecting sentences. The `quote:` is what a later
   `draft-reviser` or `review quotation` checks against the source.
   Every candidate you turn down goes in `rejected.md` with why.

3. **Re-search a thin sub-theme** with a reformulated query before
   settling for a weak passage.

4. **Pick passages worth copying.** For each sub-theme choose the
   passages -- a sentence to a paragraph each -- that say the thing
   best. Prefer a whole paragraph to three sentences from three places:
   a run found whole is one clean span; one assembled from several
   places is reported as such.

5. **Note disagreement.** Where two papers say opposite things, copy
   both, each under its own citation, and let a connecting sentence of
   yours name the disagreement.

6. **Draft, copying exactly.** This is where the survey's rule is
   inverted: a survey paragraph must rest on two or more sources so it
   cannot be a transcription of any one (`docs/WRITING-STANDARDS.md`
   §11); a digest run rests on exactly one source and is a transcription
   of it by design. Open `content/parsed/<citekey>.txt` and copy each
   passage character for character, including the parse's own noise. Do not fix hyphenation, ligatures, a dropped word or a
   reference marker; do not reorder; do not shorten. If the parse is too
   broken to read, pick another passage or another paper. Close each
   run with its citation and page. Where two runs need a bridge, write
   one short sentence of your own between them; every such sentence
   will be listed as `unquoted-text`, and one no source supports is
   also `unsupported-text`. Fewer is better.

7. **Never write a citekey you did not get from a retrieval result.**
   `python -m chitragupta.draft gate` is the only exit, and a hook runs it
   on every write under `content/drafts/`. A `FAIL` names the key; fix
   or remove it. Never guess a key, never rewrite one.

8. **Map sections to citekeys.**

   ```bash
   python -m chitragupta.draft dossier sections content/drafts/<topic>/<name>.md --citekeys --write
   ```

9. **No figure, and no critique against the evidence packet.** A
   digest draws nothing. `survey-writer`'s critique loop reads the
   `claim:`/`quote:` packet to check prose it wrote from it; a digest
   is not written from the packet but copied from the sources, and the
   check that applies to it is step 14's `review digest`.

10. **Gate.**

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    ```

    Re-run until it reports `OK`. Never show a digest that has not passed.

11. **Build the References section** from exactly the gated citekeys:

    ```bash
    python -m chitragupta.draft references content/drafts/<topic>/<name>.md
    ```

12. **Render tex and pdf.**

    ```bash
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format tex
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format pdf
    python -m chitragupta.draft render content/drafts/<topic>/<name>.md --format md
    ```

    All three land at `content/rendered/<topic>/<name>.{tex,pdf,md}`.
    This needs only bare `python` plus `pandoc`/`pdflatex` on PATH. If
    either command reports `[missing-binary]` or `[error]`, print a
    one-line warning in chat with that message and continue; a
    rendering failure never blocks presenting the `.md`.

    **No evidence sidecar.** A survey renders one because its body
    paraphrases and the sidecar shows the sources' words beside it. A
    digest *is* the sources' words, each run attributed where it
    stands, so a sidecar would print the digest back.

13. **Read it once as the reader.** Check that every connecting
    sentence of yours is needed, that no sentence of yours sits inside
    a copied run before its citation, and that each citation names one
    paper.

14. **Run the digest report.**

    ```bash
    python -m chitragupta.review digest content/drafts/<topic>/<name>.md --formats md
    ```

    It files `content/review/<topic>/<name>.digest.md` and `.json` and
    prints where. Read the report: the unsupported fraction first, then
    the copied fraction and the not-checkable share, the per-class
    counts, and every item. A page note on a copied span (`cited p. 4,
    found on p. 7`) is a locator to correct, not a finding;
    `docs/VERBATIM-DIGEST.md` explains how a page is counted. It is a
    review aid: it advises and never blocks.

    **No verbatim scan.** `survey-writer` runs `review verbatim scan`
    here because reuse in a survey is a defect. In a digest it is the
    design, and the scan would report every run; `review digest` is the
    check that applies.

    If the enrichment extra is installed, `python -m chitragupta.review
    support content/drafts/<topic>/<name>.md` scores each citing
    sentence with an NLI entailment model and is worth running on the
    `unsupported-text` items, which `review digest` judges lexically
    only. `docs/VERBATIM-DIGEST.md` says what each check can and cannot
    see.

15. **Record any steering** the user gave in chat in the dossier's
    `steering.md`, dated.

16. **Run the prose check.** After the gate passes and before
    presenting:

    ```bash
    python -m chitragupta.draft style content/drafts/<topic>/<name>.md
    ```

    Read `.claude/skills-common/references/prose-check.md` now and follow
    it: what the check can and cannot see, and how to report what it
    finds. Expect it to flag copied text, which keeps its source's
    style by design; say so when you report, and fix none of them. If
    the user wants a finding acted on in a connecting sentence of
    yours, that is `draft-reviser`'s copy-edit mode, never an edit made
    here.

17. **Work the report, only if the user asked for a pass.** Say what
    the report found and ask. If they want it repaired, take the items
    one at a time, worst class first, exactly as the report orders them:

    - `copy-mismatch`: open the source at the page the item names and
      restore the exact wording.
    - `unquoted-text`: replace the sentence with a copied passage that
      does the same job, or delete it.
    - `unsupported-text`: cite it correctly if a source says it, replace
      it with that source's words, or delete it.

    After each repair:

    ```bash
    python -m chitragupta.draft gate content/drafts/<topic>/<name>.md
    python -m chitragupta.review digest content/drafts/<topic>/<name>.md --baseline content/review/<topic>/<name>.digest.json --formats md
    ```

    Keep the repair only if all of these hold: the gate passes, the
    item is in `resolved`, no class count rose, `new` is empty, and the
    unsupported fraction did not rise. The comparison prints `fell: yes`
    exactly when the last four do. If any fails, revert the edit and
    move on. Log every attempt, kept or reverted, in the dossier's
    `revisions.md`: the date, the item id, the class, what you did, and
    the fraction before and after. Stop when the user says so, when no
    item is left, or after three passes whose fraction did not fall.
    Re-run step 12's renders once at the end of a pass that kept
    anything.

18. **Stamp the draft fingerprint, then present.**

    ```bash
    python -m chitragupta.draft dossier stamp content/drafts/<topic>/<name>.md
    ```

    Present the digest's path, the unsupported fraction with the copied
    fraction and the not-checkable share beside it, the per-class
    counts, the runs the aid could not check and why, the render
    outcome, and where the dossier and the report are. Say that the
    digest is private study text and never a source for another draft,
    that like every draft it is per-host data under `content/`, that a
    change to it goes through `draft-reviser`, and that another pass
    over the report is this skill's step 17, on request.

## Sources

The copying discipline here is the mirror of `docs/WRITING-STANDARDS.md`'s
§9 (verbatim wording has one home, and it is never the draft): a digest
is that home made explicit, with every run attributed. `SOUL.md`'s rule
against passing off a source's wording is kept by the citation that
closes every run and by the rule that a digest is never a drafting source.
````

Copy the file to `.agents/skills/review-digest/SKILL.md` unchanged, and
to `.opencode/skills/review-digest-opencode/SKILL.md` with the `name:`,
the `#` heading and the four skill names suffixed `-opencode`.

- [ ] **Step 4: Run every skill scan**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_skill_frontmatter.py tests/test_skill_harness_copies.py tests/test_skill_references.py tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py tests/test_skill_pregate_feedback_step.py tests/test_skill_acronym_step.py tests/test_skill_table_step.py tests/test_skill_figure_step.py tests/test_command_depth_scan.py tests/test_opencode_plugin.py -q
```

Expected: every file passes once the exclusion sets and counts above
are edited. The style scan requires the `§9 marks decidable` and
`fix none of them` riders within its lookahead of the command; the
shared reference the step names carries them, and the step's own
"fix none of them" is a second copy. `test_genre_doc_still_speaks_for_every_skill_that_exists`
and the "What all ten have in common" literals stay red until Task 9
edits `docs/GENRE.md`; do that edit now if you want this step green in
isolation.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/review-digest .agents/skills/review-digest .opencode/skills/review-digest-opencode .opencode/opencode.json tests/test_skill_frontmatter.py tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py tests/test_skill_pregate_feedback_step.py tests/test_features_doc.py tests/test_architecture_review_layer.py
git commit -m "Add the review-digest skill on every harness"
```

---

### Task 9: documentation and the count sweep

Step 4 of the shipping cycle, done as its own task because an eleventh
aid and a sixth genre move a count in many files outside the diff.
Three searches, in this order, and the exact edits each one found when
this plan was written against `8b588b5`. Re-run the greps: `main` may
have moved.

**Files:** every path in the table under File structure marked for
Task 9.

- [ ] **Step 1: Write `docs/VERBATIM-DIGEST.md`**

Sections, each a few paragraphs, in this repository's voice (emoji
headings, no em-dashes, tables for the fixed facts). The headings and
the facts each section must carry:

```markdown
# 📋 The verbatim digest

What it is (private study text in the sources' own words; never a
deliverable; never a drafting source), the three goals, the audience,
and that a digest is a draft like any other: named by the user, its
genre in its dossier, rendered beside the topic's other drafts, and
per-host data under content/ like every draft.

## 🧭 Table of contents

## ✍ Writing one: `review-digest`
The format block and the attribution rule, copied from the skill. The
survey workflow it follows and the three steps it replaces, with why.

## 🔍 Reading the report: `review digest`
Three fractions that account for the whole digest, in the order the
report prints them:

| Line | Counts | Direction |
| --- | --- | --- |
| Unsupported fraction | words of every sentence carrying any finding, a sentence counted once | down: the headline |
| Copied fraction | words of every verified copied span | up |
| Not checkable | words of every run whose source has no reading-ordered text | a fact about the parse, not the digest |

The three classes:

| Class | Means | Repair |
| --- | --- | --- |
| `unsupported-text` | your own sentence, and no citation covers it or the cited source does not lexically support it | cite it, replace it, or delete it |
| `copy-mismatch` | nearly on one page of the source; the item names the missing words | restore the source wording |
| `unquoted-text` | your own sentence, lexically supported | replace with a copied passage, or delete |

All three are `[surfaced]`, and why (judgement calls). The copied-span
list and the "assembled from N places" note.

## 📄 Pages, and what a page note means
What a page is here: the parser's physical page index, counted from 1
over the PDF as parsed (a Docling sidecar's `page`, or the form feeds
`pdftotext` emits), which is not the printed folio -- a paper whose
first page is numbered 1203 is still p. 1 here. The locator in a
citation is a hint; the aid matches text, not pages, and reports the
page or pages the text was found on. A run that crosses a page break
reports both pages. A note (`cited p. 4-5, found on p. 7`) appears only
when no found page is inside the cited range; it is not a finding, it
does not move any fraction, and the repair is to correct the locator.
Where a note can mislead: a source with reading-ordered passages from a
Docling sidecar and a rung-3 fallback can number pages differently
across re-parses, so a note after a sync is worth a look before an
edit. `docs/CITATION-PROVENANCE.md` has the passage ladder the pages
come from.

## 🔁 The repair loop and `--baseline`
The five keep-conditions, `fell`, the pass bound, and why the fraction
is checked as well as the counts (deleting a flagged sentence and half
the copied text with it resolves an item and makes the digest worse).

## 🧠 Lexical support, and what the NLI `support` aid adds
What `unsupported-text` measures: the share of a sentence's distinctive
words present in the cited source's best passage, under the provenance
aid's weak band (`[provenance].weak_score`, default 0.20). What that
catches (a sentence about something the source never mentions) and
what it cannot (a correct paraphrase in different words scores weak; a
sentence that negates the source scores strong). What `review support`
does instead: a real NLI entailment model over each citing sentence and
the passages that lexically match it, reporting entailed / neutral /
contradicted, so a negation is caught. Why it is not wired into
`review digest`: it needs the `enrich` extra (a torch model, hundreds of
megabytes, tens of seconds per draft), and every other digest check is
stdlib and instant; keeping the aid at interpreter tier 1 means it runs
on any host. How to use it on a digest: run `review support` on the
same file, read its report beside the digest's, and treat an
`unsupported-text` item the model marks entailed as "cite it correctly"
rather than "delete it". A later issue could add `--support` to run the
two together; the shape is the agenda's `claim-support` class.

## 🚧 What it does not do
Coarse attribution (a sentence of your own inside a run before its
citation), two papers under one citation, half-copied sentences, parse
noise, and that the `agenda` does not read it and `agenda-reviser`
never touches it, with why.

## ⚖ The rule it lives under
`SOUL.md`'s rule against passing off wording, and how a digest keeps it.
```

Write the full prose; the headings above are the outline, not the text.
Add to `mkdocs.yml` under `Writing:`, after the figure-drawer line:
`- "Study notes in the sources' words: review-digest": docs/VERBATIM-DIGEST.md`.

- [ ] **Step 2: The docs the diff already edits**

- `docs/REVIEW.md`: heading `## 🧩 The eleven aids`; line 4 "ten aids"
  → "eleven aids"; add a `**review digest**` paragraph after
  `review union`'s: *for a verbatim digest, which runs are really in the
  source they cite, the unsupported fraction, and every sentence that
  is not verified source text, as a worklist of its own; it never
  reaches the agenda. [VERBATIM-DIGEST.md](VERBATIM-DIGEST.md).* In the
  output contract block add
  `content/review/<topic>/survey.digest.md (+ .tex/.pdf, .json)`.
  "`review provenance` and `review agenda` write by default" →
  "`review provenance`, `review agenda` and `review digest` write by
  default". Qualify the sample-project sentence: "except `figure`'s ...
  and `digest`'s: the sample drafts include no digest". Line 282 "Nine
  of the ten aids are" → "Ten of the eleven aids are".
- `docs/CLI.md`: ToC entry `[chitragupta review digest]` in alphabetical
  position; a `### 📋` heading naming `chitragupta review digest`, in
  the shape of the `quotation` one: what it answers, the three-fraction
  table, the classes table, a short "Pages" paragraph pointing at the
  guide, the flag table (`<draft>`, `--formats`, `--json`,
  `--baseline`), the examples, and `**--json**` fields
  (`unsupported_fraction`, `copied_fraction`, `unverifiable_fraction`,
  `words_total`, `words_flagged`, `words_copied`, `words_unverifiable`,
  `counts`, `items` with `id`/`class`/`disposition`/`section`/
  `citekeys`/`line`/`summary`/`detail`, `spans`, `unverifiable`; under
  `--baseline`, `resolved`/`persisting`/`new`, `counts_before`/
  `counts_after`, `unsupported_before`/`unsupported_after`,
  `copied_before`/`copied_after`, `fell`). Tier table line 164 "all ten
  aids" → "all eleven aids". Line 2208 "All ten review aids now emit
  one" → "All eleven".
- `docs/GENRE.md`: picking table row *| someone studying privately, who
  wants the papers' own words | verbatim digest | `review-digest` |*;
  at-a-glance row for `review-digest` (output
  `content/drafts/<topic>/<name>.md`, citation density "every copied
  run", no subagents, cost "one run, plus `review digest`"); "The five
  drafting genres" → "The six drafting genres" (heading, ToC, line 107
  "All five drafting skills"), with a `### 📋 review-digest` subsection
  after `deep-research`'s: what it writes, who reads it, that it follows
  the survey workflow and replaces the critique loop, the verbatim scan
  and the sidecar with `review digest`, and that it is never a drafting
  source; "What all ten have in common" → "What all eleven have in
  common" (heading, ToC, line 429 "of the ten `SKILL.md` files"), and
  in that section one sentence naming the digest's two exemptions and
  that it does run the prose check; "Two of the ten are not drafting
  skills" → "Two of the eleven".
- `docs/FEATURES.md`: `### 🤖 Eleven skills` ("Five write a new draft"
  → "Six write a new draft"), a table row for `review-digest`;
  `## 🔍 Review layer: eleven advisory aids`, a table row for
  `review digest`; "Seven of the ten answer questions of judgement" →
  "Eight of the eleven"; line 327 "Four of the five genres emit" →
  "Four of the six".
- `AGENTS.md`: lines 44-47 list the six genre skills; line 227 "Four of
  the five genres emit one" → "Four of the six genres emit one;
  `tutorial-writer` and `review-digest` do not"; line 281 "ten aids" →
  "eleven aids"; in the skill paragraph near line 202 add a router
  sentence: *A **verbatim digest** (`review-digest`) is private study
  text in the sources' own words, checked by
  `python -m chitragupta.review digest`; it is never a source for any
  other draft, and `draft-reviser` is still the way to change one.*
  **The carve-out**, at lines 221-233 ("Verbatim source wording has one
  legitimate home, and it is not the draft ... never copy a span out of
  one back into body prose"): append *One genre is the exception by
  construction: a verbatim digest (`review-digest`) is that wording,
  with a citation closing every copied run, recorded as `quote:` in its
  dossier and never a source for any other draft; `docs/VERBATIM-DIGEST.md`
  carries its rule, and `agenda-reviser` is never run on one.*
- `docs/DOSSIER.md:134` ("Only `claim:` may be drafted prose from") and
  `:292` ("`quote:` is ... usable in a draft only inside quotation
  marks with an attribution"): after each, one sentence naming the
  digest as the exception: in a digest every copied run is a recorded
  `quote:` rendered in place with its citation and no quotation marks,
  and `claim:` is drafted from only for the connecting sentences.
- `docs/WRITING-STANDARDS.md` §11's unit table: a `digest` row, unit
  "document", meaning "every run is one source's own words, closed by
  its citation; the rule has no paragraph to bind at, and
  `python -m chitragupta.review digest` is the check that applies".
  §4: one sentence that in a digest the sentence-level rules bind the
  connecting sentences only.
- `docs/AGENDA.md`: one sentence, where the item classes are
  introduced: the agenda never reads `review digest`, and
  `agenda-reviser` must never be run on a digest, because its
  `verbatim-run` repair paraphrases copied text unattended.

- [ ] **Step 3: Everywhere else the counts moved**

Run, and fix every hit the way the examples show:

```bash
grep -rn -i 'ten aids\|ten commands\|ten read-only\|all ten\|the ten\|nine of the ten\|seven of the ten\|ten review\|five genre\|five drafting\|of the five\|ten skills\|ten `SKILL' --include=*.md --include=*.py --include=*.toml --include=*.example --include=*.mmd . | grep -v node_modules | grep -v '^./site' | grep -v '^./plans/'
```

Known sites at `8b588b5` and the edit:

| File | Edit |
| --- | --- |
| `README.md:272` | "all ten review-layer commands" → "all eleven" |
| `README.md:373` | "Which of the ten skills" → "eleven"; add a table row for `docs/VERBATIM-DIGEST.md` after `FIGURE-DRAWER.md`'s |
| `DEVELOPER.md:223,318,321,370` | ten → eleven; add `verbatim_digest.py` where the review files are listed |
| `docs/ARCHITECTURE.md` Layer 4 (`344`, `376`, `397`) | "Ten aids behind one command" → "Eleven aids"; "Seven of the ten aids" → "Eight of the eleven"; after the `union` paragraph: "`digest` is the eleventh, and the first over a genre of its own ... [REVIEW.md]". `tests/test_architecture_review_layer.py` fails on any surviving "ten aids" in that section |
| `docs/ARCHITECTURE.md:75`, `docs/DIAGRAMS.md:309`, `docs/diagrams/00-main-workflow.mmd:57` | "five genre skills" → "six genre skills", add `· review-digest` to the label. Then re-render: `python scripts/render_diagrams.py 00-main-workflow --puppeteer-config /tmp/pp.json` with `{"args": ["--no-sandbox"]}` in that file; the recipe for `mmdc` 11 in a container is in `docs/DIAGRAMS.md`. Commit the `.mmd`, the `.svg` and `docs/diagrams/svg/sources.json` together; `tests/test_diagrams_in_sync.py` fails otherwise |
| `docs/ARCHITECTURE.md:653`, `docs/CLI.md:164`, `docs/CONFIG.md:144` | "all ten aids" / "all ten of" → eleven |
| `config.toml.example:41`, `docs/examples/sample-project/config.toml:41`, `docs/examples/codex/config.toml:41`, `docs/examples/opencode/config.toml:41` | "all ten of chitragupta.review's" → "all eleven" (four copies, keep them identical) |
| `docs/GLOSSARY.md:35,74` | "one of the five drafting skills (...)" → six, naming the digest; "one of the ten read-only reports" → eleven |
| `docs/DOSSIER.md:331,345,350,379,497` | "Four of the five drafting skills" → "Four of the six"; the sidecar table gains a `review-digest` row answering **no**, because every run is already the source's own words with its citation and a sidecar would print the digest back; "five" → "six" at 379 and 497 |
| `docs/WRITING-PROCESS.md:58,68,84` | "four of the five genres" → "four of the six"; "Which of the five genres" → six |
| `docs/AUTO-IMPROVEMENT.md:11,562` | leave: both record what was true when the JSON contract landed. Add after line 562 one sentence: "`digest` (#991) emits one too, and is the one aid the agenda deliberately does not read." |
| `docs/PERFORMANCE.md:23,537` | "the ten review aids" → eleven; "nine of the ten aids" → "ten of the eleven aids; `digest` reads a digest, not a draft, and is not timed here" |
| `docs/PLAGIARISM.md` "See also" | a link to VERBATIM-DIGEST.md, one line: the one genre where verbatim reuse is the design, and what keeps it out of every other draft |
| `bench/bench_review_cost.py:1` | docstring: "over all ten aids" → "over the ten aids a draft review runs; `digest` (#991) reads a digest and is not timed here" |
| `chitragupta/review/_claims.py:164` | "all five genres as they stand" → "all six" |
| `chitragupta/review/synthesis.py:162` | "three of the five genres" → "four of the six": check the sentence's actual claim before editing it |
| `chitragupta/review/_book_paths.py:59` | "the other nine aids" → "the other ten" |
| `chitragupta/review/citekey_union.py:46` | "One of the ten commands" → eleven |
| `chitragupta/review/agenda/*.py` | **do not touch** the "eight aids" the agenda reads: that number did not move, and bumping it is the mistake DEVELOPER-AGENTS.md records |
| `docs/DIAGRAMS.md:11,739` | "five genre skills" → six where the sentence is about the set |

- [ ] **Step 4: What the docs already decided**

Grep for the claims the change touches, not the files:

```bash
grep -rn -i 'never a source\|passing off\|own words\|quotation marks' SOUL.md docs/WRITING-STANDARDS.md docs/PLAGIARISM.md AGENTS.md
```

Read each hit against the digest. Three contradict it and are the
carve-outs Step 2 already makes (AGENTS.md's "one legitimate home",
DOSSIER.md's "only `claim:` may be drafted from", WRITING-STANDARDS
§11's "cannot be a transcription"). Anything else the grep finds that
states the survey's posture as a rule for *every* draft gets the same
one-sentence exception; `SOUL.md` itself should need none, because the
digest keeps its rule (every run attributed, never passed off, never a
drafting source), and if a sentence there reads otherwise, say so in the
PR rather than editing SOUL.md in a feature PR.

- [ ] **Step 5: Run the doc pins**

Run:

```bash
.venv-full/bin/python -m pytest tests/test_architecture_review_layer.py tests/test_features_doc.py tests/test_docs_pins.py tests/test_diagrams_in_sync.py tests/test_skill_verbatim_scan_step.py tests/test_skill_style_check_step.py tests/test_packaging_command_table.py tests/test_cli_help_is_short.py -q
npx markdownlint-cli2 "docs/**/*.md" "*.md" ".claude/**/*.md" ".agents/**/*.md" ".opencode/**/*.md"
```

Expected: all pass, lint clean. (`bash scripts/check_local.sh` in
Task 10 runs the same lint CI does; this is the quick loop.)

- [ ] **Step 6: Commit**

```bash
git add -A docs AGENTS.md README.md DEVELOPER.md mkdocs.yml config.toml.example bench/bench_review_cost.py chitragupta/review/_claims.py chitragupta/review/synthesis.py chitragupta/review/_book_paths.py chitragupta/review/citekey_union.py
git commit -m "Document the verbatim digest and move every count it changed"
```

---

### Task 10: version, full checks, PR

- [ ] **Step 1: Bump the version**

`pyproject.toml`: `version = "6.139.0"`. MINOR: a new module and a new
subcommand, nothing existing changes shape.

- [ ] **Step 2: Full suite with coverage**

Run:

```bash
.venv-full/bin/python -m pytest --cov --cov-report=term-missing -q
```

Expected: 0 failed, 100% line and branch. Any `Missing` line under a
`_digest_*` or `verbatim_digest` module gets a test in the file that
owns it (Tasks 2-6), not a `pragma`. The likely gaps: `_mismatch` with
an empty `missing` list (a sentence whose distinctive words are all on
the page but whose flattened stream is not: pin with a reordered
sentence), `_spans_lines` with spans and no unverifiable runs (already
`TestPayload`), and `_command` with the default formats (add a run
without `--formats`, which will try to render `tex`/`pdf` and skip them
with a warning on a host without pandoc).

- [ ] **Step 3: CI's lint job**

Run:

```bash
bash scripts/check_local.sh
```

Expected: exit 0. It runs the version-bump check, pylint under 3.13,
both ruff checks, shellcheck, actionlint, markdownlint, the node tests
and Vale.

- [ ] **Step 4: Smoke test against a real corpus**

On a host with a synced ledger (the committed sample project under
`docs/examples/sample-project/` has five CC0 papers and their `.bib`):

```bash
cd docs/examples/sample-project
python -m chitragupta.corpus sync
# write a six-line digest by hand from content/parsed/<one of its citekeys>.txt
# as content/drafts/dt-overview/notes.md, and
python -m chitragupta.draft dossier init content/drafts/dt-overview/notes.md --genre digest
python -m chitragupta.draft gate content/drafts/dt-overview/notes.md
python -m chitragupta.draft render content/drafts/dt-overview/notes.md --format pdf
python -m chitragupta.review digest content/drafts/dt-overview/notes.md --formats md
# delete one sentence of your own, then:
python -m chitragupta.review digest content/drafts/dt-overview/notes.md --baseline content/review/dt-overview/notes.digest.json --formats md
git status --short   # nothing under content/ may appear
```

Record the unsupported fraction before and after and the `fell:` line
in the PR's test plan. Do not commit the digest, its dossier, its
render or its report.

- [ ] **Step 5: OpenCodeReview**

Run the OpenCodeReview plugin over the branch (`/open-code-review:review`)
and act on what it finds; if the host has no LLM endpoint, run the
`pr-review-toolkit:code-reviewer` agent instead and say which ran in
the test plan.

- [ ] **Step 6: Open the PR**

Title: `Add the verbatim digest: a sixth genre and the review digest aid`.
Body from `.github/pull_request_template.md`, `## Description` naming
discussion #991, `## Commit message` fence:

```text
- Add `python -m chitragupta.review digest`, the eleventh review aid:
  splits a verbatim digest into citation-terminated runs, verifies
  each against the cited source with the quotation matcher, and lists
  every sentence that is not verified source text as a `[surfaced]`
  item in three classes, leading with the unsupported fraction.
- Add `--baseline` to it, comparing a run against an earlier `.json`
  by item id, with the counts and fractions before and after.
- Add `digest` to `dossier.GENRES` and to the genre-to-unit tables.
- Add the `review-digest` skill on all three harnesses, following the
  survey's draft-and-render workflow, and deny its bare name in
  `.opencode/opencode.json`.
- Keep `review digest` off the agenda: `agenda/_sources.AID_NAMES`
  excludes it, so existing agendas are byte-identical.
- Move `require_reviewable` and `report_dir` to `review/_paths.py`,
  re-exported unchanged, to keep `review/__init__.py` under C2.
- Expose `_claims.claim_blocks`, the per-block half of
  `claim_sentences`, for the digest parser.
- Add docs/VERBATIM-DIGEST.md, with the page and NLI-support
  explanations, and move every aid, genre and skill count the change
  made false.
- Bump the version to 6.139.0.
```

Check it with `python scripts/merge_pr.py --check` before opening. Then
the rest of the cycle: green CI, one Copilot round, re-check `main`,
`python scripts/merge_pr.py <N>`, tag, release asset.

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
